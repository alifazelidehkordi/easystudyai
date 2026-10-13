#!/usr/bin/env python3
"""One-command entry point: professor file -> private import -> teaching brief.

This runs entirely locally; your installed Codex CLI / Pi supplies the AI
conversation using your subscription, not a separate model API.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

from import_notes import convert
from prepare_lesson import create_brief
from validate_lecture import inspect, report_markdown


def prepare(file: Path, notes: Path, briefs: Path, render_pages: bool = True,
            force: bool = False, ocr: bool = False, ocr_language: str = "eng",
            tessdata: str | None = None) -> tuple[Path, Path, dict, list[str]]:
    # Avoid accidentally sharing private course originals in a repository.
    if file.is_symlink():
        raise ValueError("Symlink lecture source not accepted")
    output, n, warnings = convert(
        file, notes, render_pages=render_pages and file.suffix.lower() == ".pdf",
        overwrite=force, ocr=ocr, ocr_language=ocr_language, tessdata=tessdata
    )
    brief, metrics = create_brief(output, briefs, overwrite=force)
    return output, brief, metrics, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lecture", type=Path, help="Original PDF, PPTX, DOCX, TXT or MD")
    parser.add_argument("--notes", type=Path, default=Path("course/processed"))
    parser.add_argument("--briefs", type=Path, default=Path("course/briefs"))
    parser.add_argument("--validation", type=Path, help="Report folder (default: alongside briefs)")
    parser.add_argument("--ocr", action="store_true",
                        help="Use local Tesseract OCR for scan-only PDF pages; opt-in")
    parser.add_argument("--ocr-lang", default="eng",
                        help="Tesseract language pack; e.g. eng or ita")
    parser.add_argument("--tessdata", default=None,
                        help="Path to local Tesseract tessdata language directory")
    parser.add_argument("--no-page-images", action="store_true",
                        help="Skip PDF screenshots to save disk space; limits image-based tutoring")
    parser.add_argument("--force", action="store_true",
                        help="Replace existing imported source and generated brief")
    args = parser.parse_args()
    try:
        if args.ocr and args.lecture.suffix.lower() != ".pdf":
            raise ValueError("--ocr is supported for PDF files only")
        notes, brief, metrics, warnings = prepare(
            args.lecture.expanduser(), args.notes, args.briefs,
            not args.no_page_images, args.force,
            ocr=args.ocr, ocr_language=args.ocr_lang, tessdata=args.tessdata
        )
        validation = inspect(notes, args.lecture.expanduser())
        validation_dir = args.validation or (args.briefs.parent / "validation")
        validation_dir.mkdir(parents=True, exist_ok=True)
        validation_path = validation_dir / (notes.stem + "-validation.md")
        validation_path.write_text(report_markdown(validation), encoding="utf-8")
        print("Imported notes:", notes)
        print("Teaching brief:", brief)
        print("Verification checklist:", validation_path)
        print("Sections:", metrics["sections"])
        if validation["blocking_issues"] or warnings:
            print("Extraction needs attention. Inspect original pages before teaching.")
            for item in validation["blocking_issues"][:7] + warnings[:7]:
                print("CHECK:", item)
        print()
        print("Next: start codex or pi in this repository using your subscription.")
        print(
            "Ask: Read AGENTS.md and " + brief.as_posix() +
            ". Check the original source and teach my lecture through Probe, Plan, Teach. "
            "Use cited figures and quizzes; do not infer facts from the index alone."
        )
        return 0
    except (OSError, ValueError, RuntimeError, UnicodeError) as error:
        print("ERROR:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
