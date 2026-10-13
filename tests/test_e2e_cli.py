"""End-to-end offline CLI demo: import, search, create review, reveal and rate."""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class FullLearningCycleTests(unittest.TestCase):
    def run_script(self, script: str, *args: object) -> str:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), *(str(a) for a in args)],
            check=True, capture_output=True, text=True, timeout=30
        )
        return proc.stdout

    def test_import_search_and_review_sample_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes = root / "processed"
            db = root / "progress.json"
            source = ROOT / "examples" / "demo-lecture.txt"
            output = self.run_script("import_notes.py", source, "--output", notes)
            self.assertIn("Imported 1 section(s)", output)
            self.assertTrue((notes / "demo-lecture-txt.md").is_file())
            search = self.run_script("search_notes.py", "stroke volume", "--directory", notes)
            self.assertIn("Source text", search)
            self.assertIn("demo-lecture-txt.md", search)
            created = self.run_script(
                "study.py", "--database", db, "--notes-dir", notes,
                "add", "--topic", "Cardiac output",
                "--question", "What determines cardiac output?",
                "--answer", "Heart rate multiplied by stroke volume",
                "--source", "demo-lecture-txt.md", "--anchor", "Source text"
            )
            card = re.search(r"Added ([0-9a-f]{12})", created)
            self.assertIsNotNone(card)
            card_id = card.group(1)
            due = self.run_script("study.py", "--database", db, "due")
            self.assertIn("What determines cardiac output?", due)
            self.assertNotIn("Heart rate multiplied by stroke volume", due)
            revealed = self.run_script("study.py", "--database", db, "reveal", card_id)
            self.assertIn("Heart rate multiplied by stroke volume", revealed)
            graded = self.run_script("study.py", "--database", db, "grade", card_id, "--rating", "good")
            self.assertIn("next review", graded)
            report = self.run_script("study.py", "--database", db, "stats")
            self.assertIn("Reviews: 1", report)


if __name__ == "__main__":
    unittest.main()
