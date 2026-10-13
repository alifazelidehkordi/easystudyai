"""Phase 4: source-grounded briefing and single-command import pipeline."""
from __future__ import annotations
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class LessonBriefTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lectures = self.root / "lectures"
        self.lectures.mkdir()
        self.notes = self.root / "notes"
        self.briefs = self.root / "briefs"

    def run_cli(self, script: str, *args: object, check: bool = True):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), *(str(x) for x in args)],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=30
        )
        if check and result.returncode != 0:
            self.fail(f"{script}: {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}")
        return result

    def test_one_command_extracts_only_explicit_objectives(self):
        file = self.lectures / "Renal physiology.txt"
        file.write_text(
            "Learning Objectives:\n"
            "- Explain how hydrostatic pressure supports glomerular filtration.\n"
            "- Distinguish the glomerulus from surrounding cortical tubules.\n\n"
            "The renal corpuscle contains a glomerular capillary tuft enclosed by Bowman's capsule.\n",
            encoding="utf-8"
        )
        result = self.run_cli(
            "learn.py", file, "--notes", self.notes, "--briefs", self.briefs
        )
        self.assertIn("Teaching brief:", result.stdout)
        imported = self.notes / "renal-physiology-txt.md"
        brief = self.briefs / "renal-physiology-txt-brief.md"
        self.assertTrue(imported.exists())
        self.assertTrue(brief.exists())
        content = brief.read_text(encoding="utf-8")
        self.assertIn("Explain how hydrostatic pressure", content)
        self.assertIn("renal-physiology-txt.md", content)
        self.assertIn("Renal physiology.txt, Source text", content)
        self.assertIn("an automatic index", content)
        self.assertNotIn(str(self.root), content)
        result2 = self.run_cli(
            "learn.py", file, "--notes", self.notes, "--briefs", self.briefs,
            check=False
        )
        self.assertNotEqual(result2.returncode, 0)
        self.assertIn("Already imported", result2.stderr)
        result3 = self.run_cli(
            "learn.py", file, "--notes", self.notes, "--briefs", self.briefs,
            "--force"
        )
        self.assertIn("Teaching brief:", result3.stdout)

    def test_no_inferred_objective_or_wrong_page(self):
        file = self.lectures / "Heart.txt"
        file.write_text(
            "Cardiac output equals stroke volume multiplied by heart rate. "
            "The sinoatrial node sets the intrinsic rhythm.",
            encoding="utf-8"
        )
        self.run_cli("learn.py", file, "--notes", self.notes, "--briefs", self.briefs)
        brief = (self.briefs / "heart-txt-brief.md").read_text(encoding="utf-8")
        self.assertIn("No explicit bullet-style objectives detected", brief)
        self.assertNotIn("Page 8", brief)
        self.assertIn("Source text", brief)
        self.assertIn("not a verified medical summary", brief)

    def test_skip_unanchored_import_and_missing_file(self):
        missing = self.run_cli(
            "learn.py", self.root / "missing.pdf", "--notes", self.notes,
            "--briefs", self.briefs, check=False
        )
        self.assertEqual(missing.returncode, 1)
        raw = self.root / "unanchored.md"
        raw.write_text("# Missing anchors\n\nSome text without a section heading.")
        invalid = self.run_cli(
            "prepare_lesson.py", raw, "--output", self.briefs, check=False
        )
        self.assertEqual(invalid.returncode, 1)
        self.assertIn("No source-anchored sections", invalid.stderr)

    def test_pdf_with_visual_page_if_installed(self):
        try:
            import pymupdf
        except ImportError:
            self.skipTest("optional PyMuPDF not installed")
        file = self.lectures / "Physiology.pdf"
        pdf = pymupdf.open()
        page = pdf.new_page()
        page.insert_text((72, 72), "Capillary hydrostatic pressure supports filtration.")
        pdf.save(file)
        pdf.close()
        self.run_cli("learn.py", file, "--notes", self.notes, "--briefs", self.briefs)
        self.assertTrue((self.notes / "assets/physiology-pdf/page-0001.png").is_file())
        brief = (self.briefs / "physiology-pdf-brief.md").read_text(encoding="utf-8")
        self.assertIn("Page 1", brief)
        self.assertIn("image link(s)", brief)

    def test_imported_text_source_is_preserved(self):
        file = self.lectures / "Lecture.txt"
        original = b"My lecturer's source notes.\n"
        file.write_bytes(original)
        self.run_cli("learn.py", file, "--notes", self.notes, "--briefs", self.briefs)
        self.assertEqual(file.read_bytes(), original)
        # The preparation tool does not move or modify original lecture files.
        self.assertTrue((self.briefs / "lecture-txt-brief.md").exists())


if __name__ == "__main__":
    unittest.main()
