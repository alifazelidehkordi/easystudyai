"""Regression tests for local medical-study review and figure indexing."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(name: str):
    source = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), source)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.notes = self.root / "processed"
        self.notes.mkdir()
        (self.notes / "cardiac-pdf.md").write_text(
            "# Imported lecture: Cardiac.pdf\n\n"
            "## Page 1\n\nThe SA node depolarizes.\n\n"
            "## Page 2\n\nAortic valve closure begins diastole.\n", encoding="utf-8"
        )
        self.db = self.root / "private" / "progress.json"
        self.review = load("study.py")
        self.start = date(2026, 10, 13)

    def add(self):
        return self.review.add_card(
            self.db, self.notes, "Cardiac cycle", "What closes the aortic valve?",
            "Aortic pressure exceeding LV pressure", "cardiac-pdf.md", "Page 2",
            today=self.start
        )

    def test_add_and_review_schedule(self):
        card = self.add()
        self.assertEqual(self.review.stats(self.review.load_db(self.db), self.start)["due"], 1)
        self.assertEqual(card["due"], "2026-10-13")
        self.assertNotIn("personal", self.db.read_text())
        graded = self.review.grade_card(self.db, card["id"], "good", today=self.start)
        self.assertEqual(graded["due"], "2026-10-14")
        self.assertEqual(self.review.due_cards(self.review.load_db(self.db), self.start), [])
        with self.assertRaises(ValueError):
            self.review.grade_card(self.db, card["id"], "easy", today=self.start)
        graded2 = self.review.grade_card(self.db, card["id"], "easy", today=date(2026, 10, 14))
        self.assertEqual(graded2["due"], "2026-10-21")
        self.assertEqual(graded2["box"], 3)
        self.assertEqual(len(graded2["reviews"]), 2)
        self.assertEqual(self.review.stats(self.review.load_db(self.db), self.start)["reviews"], 2)

    def test_again_is_due_same_day(self):
        card = self.add()
        new = self.review.grade_card(self.db, card["id"], "again", self.start)
        self.assertEqual(new["due"], self.start.isoformat())
        self.assertEqual(new["box"], 0)
        self.assertEqual(len(self.review.due_cards(self.review.load_db(self.db), self.start)), 1)

    def test_reject_unsourced_or_duplicate_question(self):
        self.add()
        with self.assertRaises(ValueError):
            self.add()
        with self.assertRaises(ValueError):
            self.review.add_card(self.db, self.notes, "Cardiac", "X?", "Y", "../unrelated.md", "Page 1")
        with self.assertRaises(ValueError):
            self.review.add_card(self.db, self.notes, "Cardiac", "X?", "Y", "cardiac-pdf.md", "Page 88")
        with self.assertRaises(ValueError):
            self.review.add_card(self.db, self.notes, "", "X?", "Y", "cardiac-pdf.md", "Page 1")
        self.assertEqual(len(self.review.load_db(self.db)["cards"]), 1)

    def test_corrupt_database_fails_without_overwrite(self):
        self.db.parent.mkdir(parents=True)
        self.db.write_text('{"version": 100, "cards":[]}', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.review.load_db(self.db)
        self.assertEqual(json.loads(self.db.read_text())["version"], 100)


class FigureTests(unittest.TestCase):
    def test_figure_anchor_query_and_missing_file(self):
        figures = load("figures.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "assets" / "renal-pptx" / "slide-0002-figure-01.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"image fixture")
            source = root / "renal-pptx.md"
            source.write_text(
                "# Renal lecture\n\n"
                "## Slide 1\n\nCardiovascular topic.\n\n"
                "## Slide 2\n\nRenal cortex and tubules.\n\n"
                "![Original figure, slide 2](assets/renal-pptx/slide-0002-figure-01.png)\n\n"
                "## Slide 3\n\nRenal papilla.\n\n"
                "![Original figure, slide 3](assets/renal-pptx/slide-0003-figure-01.png)\n",
                encoding="utf-8"
            )
            found = figures.index_figures(root, "cortex")
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["anchor"], "Slide 2")
            self.assertEqual(found[0]["kind"], "embedded_slide_figure")
            self.assertTrue(found[0]["exists"])
            self.assertFalse(found[0]["medical_content_verified"])
            all_figures = figures.index_figures(root)
            self.assertEqual(len(all_figures), 2)
            self.assertFalse(all_figures[1]["exists"])

    def test_unsafe_paths_ignored(self):
        figures = load("figures.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "processed"
            root.mkdir()
            (root / "source.md").write_text(
                "## Page 1\n\n![escape](../../secrets.png)\n"
                "![web](https://external.example/image.png)\n", encoding="utf-8"
            )
            self.assertEqual(figures.index_figures(root), [])


if __name__ == "__main__":
    unittest.main()
