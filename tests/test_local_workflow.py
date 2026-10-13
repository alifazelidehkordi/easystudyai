"""Phase 6: local-only OCR, setup checks, launcher and CLI recall session."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


def run_script(name: str, *args: object, answer: str | None = None, expected: int = 0):
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name), *(str(x) for x in args)],
        cwd=ROOT, input=answer, capture_output=True, text=True, timeout=35
    )
    if r.returncode != expected:
        raise AssertionError(f"{name} exited {r.returncode} != {expected}\n{r.stdout}\n{r.stderr}")
    return r


def load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    obj = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(obj)
    return obj


class OfflineWorkflowTests(unittest.TestCase):
    def test_doctor_checks_source_and_privacy_without_api(self):
        r = run_script("doctor.py", "--json")
        result = json.loads(r.stdout)
        self.assertEqual(result["overall"], "ready_for_local_use")
        self.assertFalse(result["subscription_login_checked"])
        self.assertEqual(
            next(c for c in result["checks"] if c["name"] == "privacy")["level"],
            "ok",
        )
        self.assertIn("No separate model API key", str(result["checks"]))

    def test_start_check_only_does_not_open_harness(self):
        r = run_script(
            "start.py", "--check-only", "--lecture",
            ROOT / "examples" / "demo-lecture.txt"
        )
        self.assertIn("Preparation command:", r.stdout)
        self.assertIn("Ready to start", r.stdout) if "Ready to start" in r.stdout else self.assertIn(
            "not found on PATH", r.stdout
        )

    def test_ocr_rejected_for_non_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "original.txt"
            file.write_text("Text lecture without images", encoding="utf-8")
            result = run_script(
                "learn.py", file, "--ocr",
                "--notes", Path(tmp) / "processed",
                "--briefs", Path(tmp) / "briefs", expected=1
            )
            self.assertIn("--ocr is supported for PDF", result.stderr)
            invalid = run_script(
                "import_notes.py", file, "--ocr",
                "--output", Path(tmp) / "processed", expected=1
            )
            self.assertIn("PDF files only", invalid.stderr)

    def test_fake_local_ocr_marks_result_unverified(self):
        importer = load_script("import_notes.py")

        class Page:
            def get_text(self, kind, **kwargs):
                return "Glomerular filtration pressure" if kwargs.get("textpage") is not None else ""
            def get_textpage_ocr(self, **kwargs):
                self.params = kwargs
                return object()

        class FakeDoc:
            is_encrypted = False
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return None
            def __iter__(self):
                return iter([Page()])

        fake_module = types.SimpleNamespace(open=lambda path: FakeDoc())
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {"pymupdf": fake_module}):
            sections, warnings = importer.read_pdf(
                Path(tmp) / "dummy.pdf", Path(tmp) / "assets",
                render_pages=False, ocr=True, ocr_language="eng"
            )
        self.assertIn("LOCAL OCR TRANSCRIPTION — UNVERIFIED", sections[0])
        self.assertIn("Glomerular filtration pressure", sections[0])
        self.assertTrue(any("verify every medical term" in note for note in warnings))

    def test_ocr_metadata_is_flagged_for_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "scan-pdf.md"
            source.write_text(
                "# Imported lecture: scan.pdf\n- Original filename: scan.pdf\n\n"
                "## Page 1\n\n[LOCAL OCR TRANSCRIPTION — UNVERIFIED: check original page]\n\n"
                "The renal cortex contains glomeruli.\n\n"
                "![Lecture PDF page 1](assets/scan-pdf/page-0001.png)\n",
                encoding="utf-8"
            )
            image = root / "assets/scan-pdf/page-0001.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"image content")
            result = run_script(
                "validate_lecture.py", source, "--output", root / "validated", "--json"
            )
            info = json.loads(result.stdout)
            self.assertIn("Page 1", info["ocr_sections_needing_review"])
            self.assertEqual(info["technical_status"], "needs_review")
            self.assertIn("Local OCR was used", " ".join(info["warnings"]))
            report = (root / "validated/scan-pdf-validation.md").read_text()
            self.assertIn("OCR pages requiring visual confirmation: 1", report)

    def test_offline_active_recall_without_native_quiz_ui(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes = root / "processed"
            notes.mkdir()
            (notes / "cardiac-txt.md").write_text(
                "## Source text\n\nCardiac output = HR × SV.", encoding="utf-8"
            )
            db = root / "progress.json"
            add = run_script(
                "study.py", "--database", db, "--notes-dir", notes, "add",
                "--topic", "Cardiac output", "--question", "What determines cardiac output?",
                "--answer", "Heart rate times stroke volume",
                "--source", "cardiac-txt.md", "--anchor", "Source text"
            )
            self.assertIn("Added", add.stdout)
            review = run_script("study_session.py", "--database", db, answer="HR x SV\ngood\n")
            self.assertIn("Expected answer: Heart rate times stroke volume", review.stdout)
            self.assertIn("Finished 1/1", review.stdout)
            self.assertIn("due today: 0", review.stdout)
            data = json.loads(db.read_text())
            self.assertEqual(data["cards"][0]["reviews"][0]["rating"], "good")

    def test_quit_keeps_ungraded_card_due(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes = root / "notes"
            notes.mkdir()
            (notes / "renal.md").write_text("## Page 1\n\nRenal physiology.\n")
            db = root / "progress.json"
            run_script(
                "study.py", "--database", db, "--notes-dir", notes, "add",
                "--topic", "Renal", "--question", "Define GFR",
                "--answer", "Volume filtered per unit time",
                "--source", "renal.md", "--anchor", "Page 1"
            )
            quit_session = run_script("study_session.py", "--database", db, answer="/quit\n")
            self.assertIn("Unreviewed cards remain due", quit_session.stdout)
            self.assertEqual(json.loads(db.read_text())["cards"][0]["reviews"], [])


if __name__ == "__main__":
    unittest.main()
