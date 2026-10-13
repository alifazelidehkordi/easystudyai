"""Run with: python -m unittest discover -s tests -v

The default tests require only Python's standard library.
Optional PDF/PPTX/DOCX tests run if the parser packages are installed.
"""
from __future__ import annotations

import base64
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(script: str):
    path = ROOT / "scripts" / script
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ImportTests(unittest.TestCase):
    def test_text_anchor_and_immutability(self):
        imp = load("import_notes.py")
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            file = directory / "Prof notes.txt"
            file.write_text("Heart rate times stroke volume = cardiac output.", encoding="utf-8")
            output, count, warnings = imp.convert(file, directory / "processed", False, False)
            self.assertEqual(count, 1)
            self.assertFalse(warnings)
            result = output.read_text(encoding="utf-8")
            self.assertIn("Prof notes.txt", result)
            self.assertIn("## Source text", result)
            self.assertIn("stroke volume", result)
            self.assertNotIn(str(directory.resolve()), result)
            with self.assertRaises(ValueError):
                imp.convert(file, directory / "processed", False, False)
            self.assertEqual(file.read_text(), "Heart rate times stroke volume = cardiac output.")

    def test_pdf_pages_if_installed(self):
        try:
            import pymupdf
        except ImportError:
            self.skipTest("optional PyMuPDF not installed")
        imp = load("import_notes.py")
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            pdf = pymupdf.open()
            pdf.new_page().insert_text((72, 72), "Cardiac cycle")
            file = d / "lecture.pdf"
            pdf.save(str(file))
            pdf.close()
            output, n, warnings = imp.convert(file, d / "converted", True, False)
            self.assertEqual(n, 1)
            self.assertIn("## Page 1", output.read_text())
            self.assertTrue((d / "converted/assets/lecture-pdf/page-0001.png").exists())

    def test_pptx_slide_if_installed(self):
        try:
            from pptx import Presentation
        except ImportError:
            self.skipTest("optional python-pptx not installed")
        imp = load("import_notes.py")
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            ppt = Presentation()
            slide = ppt.slides.add_slide(ppt.slide_layouts[0])
            slide.shapes.title.text = "Kidney"
            file = d / "lecture.pptx"
            ppt.save(str(file))
            output, _, _ = imp.convert(file, d / "out", False, False)
            self.assertIn("Kidney", output.read_text())
            self.assertIn("## Slide 1", output.read_text())


class SearchTests(unittest.TestCase):
    def test_section_search_returns_source_anchor(self):
        notes = load("search_notes.py")
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "anatomy-pdf.md"
            source.write_text("# Imported lecture\n\n## Page 1\n\nThe cortex.\n\n## Page 2\n\nThe renal corpuscle filters plasma.")
            results = notes.search(Path(tmp), "renal corpuscle")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0][2], "Page 2")


class VisualTests(unittest.TestCase):
    def test_local_image_copy_and_credit(self):
        add = load("add_image.py")
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            source = d / "sample.png"
            # Small binary data with the correct image signature; the importer
            # checks magic bytes, not visual content or scientific accuracy.
            source.write_bytes(base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WlLhZkAAAAASUVORK5CYII="
            ))
            output, credit = add.add_image(source, d / "images",
                                           "Renal cortex", "https://example.org/figure",
                                           "Teaching team", "CC BY 4.0")
            self.assertTrue(output.is_file())
            self.assertIn("Renal cortex", credit)
            metadata = (d / "images" / (output.name + ".json")).read_text()
            self.assertIn('"medical_accuracy_reviewed": false', metadata)
            self.assertIn("CC BY", (d / "images/ATTRIBUTIONS.md").read_text())
            with self.assertRaises(ValueError):
                add.add_image(source, d / "images", "Test", "file:///etc/passwd", "A", "CC BY")

    def test_disallow_svg(self):
        add = load("add_image.py")
        with tempfile.TemporaryDirectory() as tmp:
            svg = Path(tmp) / "x.svg"
            svg.write_text("<svg/>")
            with self.assertRaises(ValueError):
                add.valid_image(svg)


class PiSetupTests(unittest.TestCase):
    def test_copy_optional_upstream_extensions(self):
        setup = load("setup_pi.py")
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            source = d / "original/extensions"
            source.mkdir(parents=True)
            for name in setup.EXTENSIONS:
                (source / name).write_text("test upstream " + name)
            project = d / "project"
            setup.install(project, d / "original", replace=False)
            self.assertTrue((project / ".pi/extensions/quiz.ts").is_file())
            # A second install must not overwrite edits unless requested.
            example = project / ".pi/extensions/quiz.ts"
            example.write_text("my customization")
            setup.install(project, d / "original", replace=False)
            self.assertEqual(example.read_text(), "my customization")


if __name__ == "__main__":
    unittest.main()
