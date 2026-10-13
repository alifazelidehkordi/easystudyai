"""Phase 3: source-anchored visual workflow and import-quality audits."""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WlLhZkAAAAASUVORK5CYII="
)


class Phase3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.notes = self.root / "processed"
        self.notes.mkdir()
        self.lecture = self.notes / "kidney-pdf.md"
        self.lecture.write_text(
            "# Imported lecture: Kidney.pdf\n"
            "- Original filename: Kidney.pdf\n\n"
            "## Page 1\n\n"
            "This kidney physiology page discusses glomerular filtration and plasma.\n\n"
            "## Page 2\n\n"
            "[No selectable text: check scanned page image.]\n\n"
            "![Lecture PDF page 2](assets/kidney-pdf/page-0002.png)\n",
            encoding="utf-8"
        )
        self.image = self.root / "sample.png"
        self.image.write_bytes(PNG_1PX)
        self.db = self.root / "visual_requests.json"
        self.images = self.root / "visuals"

    def run_script(self, name: str, *args: str, success: bool = True):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / name), *[str(a) for a in args]],
            cwd=str(ROOT), capture_output=True, text=True, timeout=20
        )
        if success and result.returncode != 0:
            self.fail(f"Command failed ({result.returncode}): {result.stderr}")
        return result

    def new_request(self):
        result = self.run_script(
            "visual_requests.py", "--database", self.db, "--notes-dir", self.notes,
            "request", "--source", self.lecture.name, "--anchor", "Page 1",
            "--topic", "Glomerular corpuscle", "--kind", "histology",
            "--reason", "Need visual explanation of glomerular capillaries"
        )
        self.assertIn("Special:MediaSearch?", result.stdout)
        return json.loads(self.db.read_text(encoding="utf-8"))["requests"][0]["id"]

    def test_requires_valid_page_and_prevents_duplicates(self):
        identifier = self.new_request()
        self.assertEqual(len(identifier), 12)
        duplicate = self.run_script(
            "visual_requests.py", "--database", self.db, "--notes-dir", self.notes,
            "request", "--source", self.lecture.name, "--anchor", "Page 1",
            "--topic", "glomerular corpuscle", "--kind", "histology",
            "--reason", "another reason", success=False
        )
        self.assertEqual(duplicate.returncode, 1)
        missing = self.run_script(
            "visual_requests.py", "--database", self.db, "--notes-dir", self.notes,
            "request", "--source", self.lecture.name, "--anchor", "Page 20",
            "--topic", "Glomerulus", "--kind", "histology",
            "--reason", "example", success=False
        )
        self.assertEqual(missing.returncode, 1)

    def test_review_gate_requires_two_confirmations(self):
        identifier = self.new_request()
        common = ["--database", str(self.db), "--notes-dir", str(self.notes),
                  "--image-dir", str(self.images)]
        early = self.run_script(
            "visual_requests.py", *common, "embed", identifier, success=False
        )
        self.assertEqual(early.returncode, 1)
        attached = self.run_script(
            "visual_requests.py", *common,
            "attach", identifier, "--file", str(self.image),
            "--title", "Renal corpuscle diagram",
            "--source-url", "https://commons.wikimedia.org/wiki/File:Example",
            "--creator", "Example author", "--license", "CC BY 4.0"
        )
        self.assertIn("Pending medical and rights review", attached.stdout)
        ledger = json.loads(self.db.read_text(encoding="utf-8"))
        file = ledger["requests"][0]["attachment"]["filename"]
        sidecar = self.images / (file + ".json")
        self.assertFalse(json.loads(sidecar.read_text())["medical_accuracy_reviewed"])
        without_rights = self.run_script(
            "visual_requests.py", *common,
            "approve", identifier, "--checked-medical", success=False
        )
        self.assertEqual(without_rights.returncode, 1)
        self.assertEqual(ledger["requests"][0]["status"], "attached")
        approved = self.run_script(
            "visual_requests.py", *common,
            "approve", identifier, "--checked-medical", "--checked-rights"
        )
        self.assertIn("human-reviewed", approved.stdout)
        self.assertTrue(json.loads(sidecar.read_text())["license_verified"])
        embed = self.run_script("visual_requests.py", *common, "embed", identifier)
        self.assertIn("course/visuals/", embed.stdout)
        self.assertIn("kidney-pdf.md, Page 1", embed.stdout)
        self.assertIn("not independently certified", embed.stdout)
        self.assertIn("Example author", (self.images / "ATTRIBUTIONS.md").read_text())
        second = self.run_script(
            "visual_requests.py", *common,
            "approve", identifier, "--checked-medical", "--checked-rights", success=False
        )
        self.assertEqual(second.returncode, 1)

    def test_search_returns_link_without_network(self):
        proc = self.run_script("visual_requests.py", "search", "--query", "heart anatomy")
        self.assertIn("search=heart+anatomy&type=image", proc.stdout)
        self.assertIn("commons.wikimedia.org", proc.stdout)

    def test_audit_flags_scan_and_missing_image(self):
        report = self.run_script("audit_lecture.py", str(self.lecture), "--json")
        output = json.loads(report.stdout)[0]
        self.assertEqual(output["sections"], 2)
        self.assertEqual(output["no_text_sections"], ["Page 2"])
        self.assertEqual(len(output["missing_or_unsafe_images"]), 1)
        self.assertTrue(output["needs_attention"])
        strict = self.run_script(
            "audit_lecture.py", str(self.lecture), "--strict", success=False
        )
        self.assertEqual(strict.returncode, 2)

    def test_audit_after_image_is_present(self):
        target = self.notes / "assets/kidney-pdf/page-0002.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(PNG_1PX)
        report = json.loads(self.run_script(
            "audit_lecture.py", str(self.lecture), "--json"
        ).stdout)[0]
        self.assertEqual(report["linked_visuals"], 1)
        self.assertEqual(report["missing_or_unsafe_images"], [])
        self.assertEqual(report["no_text_sections"], ["Page 2"])

    def test_clean_text_import_is_not_a_false_alarm(self):
        clean = self.notes / "example-txt.md"
        clean.write_text(
            "# Imported lecture: example.txt\n"
            "- Original filename: example.txt\n\n"
            "## Source text\n\n" + "Cardiac output is the product of heart rate and stroke volume. " * 5,
            encoding="utf-8"
        )
        result = self.run_script("audit_lecture.py", str(clean), "--strict")
        self.assertEqual(result.returncode, 0)
        self.assertIn("No blocking extraction warnings", result.stdout)


if __name__ == "__main__":
    unittest.main()
