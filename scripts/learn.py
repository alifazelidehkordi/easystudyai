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


def prepare(file: Path, notes: Path, briefs: Path, render_pages: bool = True,
            force: bool = False) -> tuple[Path, Path, dict, list[str]]:
    # Avoid accidentally sharing private course originals in a repository.
    if file.is_symlink():
        raise ValueError("Symlink lecture source not accepted")
    output, n, warnings = convert(
        file, notes, render_pages=render_pages and file.suffix.lower() == ".pdf",
        overwrite=force
    )
    brief, metrics = create_brief(output, briefs, overwrite=force)
    return output, brief, metrics, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lecture", type=Path, help="Original PDF, PPTX, DOCX, TXT or MD")
    parser.add_argument("--notes", type=Path, default=Path("course/processed"))
    parser.add_argument("--briefs", type=Path, default=Path("course/briefs"))
    parser.add_argument("--no-page-images", action="store_true",
                        help="Skip PDF screenshots to save disk space; limits image-based tutoring")
    parser.add_argument("--force", action="store_true",
                        help="Replace existing imported source and generated brief")
    args = parser.parse_args()
    try:
        notes, brief, metrics, warnings = prepare(
            args.lecture.expanduser(), args.notes, args.briefs,
            not args.no_page_images, args.force
        )
        print("Imported notes:", notes)
        print("Teaching brief:", brief)
        print("Sections:", metrics["sections"])
        if warnings or metrics["no_text_sections"] or metrics["missing_visuals"]:
            print("Extraction needs attention. Inspect original pages before teaching.")
            for warning in warnings[:7]:
                print("CHECK:", warning)
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
