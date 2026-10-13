#!/usr/bin/env python3
"""Audit imported lecture Markdown for extraction gaps before AI teaching.

This is a conservative *technical* check, not a medical-content validator.
It never connects to the internet, calls a model, or reads patient records.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ANCHOR = re.compile(r"^## (Page \d+|Slide \d+|Document|Source text)\s*$", re.MULTILINE)
IMAGES = re.compile(r"!\[([^\]]*)\]\(([^)\n]+)\)")
TITLE = re.compile(r"^- Original filename: (.+)$", re.MULTILINE)
SMALL_TEXT_THRESHOLD = 35


def audit(path: Path) -> dict:
    if not path.is_file() or path.is_symlink() or path.suffix.lower() != ".md":
        raise ValueError(f"Not an imported Markdown file: {path}")
    body = path.read_text(encoding="utf-8")
    sections = list(ANCHOR.finditer(body))
    source_name = TITLE.search(body)
    original = source_name.group(1) if source_name else "unknown"
    count = 0
    missing_images = []
    pages_without_text = []
    low_text = []
    scan_warnings = []
    ocr_sections = []
    count_by_kind = {}
    for n, anchor in enumerate(sections):
        name = anchor.group(1)
        end = sections[n + 1].start() if n + 1 < len(sections) else len(body)
        block = body[anchor.end():end]
        if "LOCAL OCR TRANSCRIPTION — UNVERIFIED" in block:
            ocr_sections.append(name)
        figure_links = list(IMAGES.finditer(block))
        count += len(figure_links)
        for match in figure_links:
            link = unquote(match.group(2).strip())
            if link.startswith(("http://", "https://", "data:")):
                continue
            target = (path.parent / link).resolve()
            # Avoid reading unrelated files referenced by malformed imports.
            if not target.is_relative_to(path.parent.resolve()) or not target.is_file():
                missing_images.append(f"{name}: {link}")
            label = match.group(1)
            typ = "page snapshot" if label.startswith("Lecture PDF page") else (
                "lecture figure" if label.startswith("Original figure") else "other"
            )
            count_by_kind[typ] = count_by_kind.get(typ, 0) + 1
        text = IMAGES.sub("", block)
        text = re.sub(r"\[[^\]]+\]", "", text)  # remove importer placeholders
        text = re.sub(r"!\[[^\]]*\]\([^\n]+\)", "", text)
        if "No selectable text:" in block or "No readable text/inline figure" in block:
            pages_without_text.append(name)
        elif len(re.findall(r"\w+", text)) < SMALL_TEXT_THRESHOLD:
            low_text.append(name)
    for line in body.splitlines():
        if line.startswith("- Page ") and "no text layer" in line:
            scan_warnings.append(line.removeprefix("- "))
    issues = []
    if not sections:
        issues.append("No recognizable page/slide/text headings found; reimport or inspect source.")
    if pages_without_text:
        issues.append(f"{len(pages_without_text)} section(s) have no extractable text.")
    if ocr_sections:
        issues.append(f"{len(ocr_sections)} local OCR page(s) require human verification of medical terms and numbers.")
    if missing_images:
        issues.append(f"{len(missing_images)} referenced image(s) are missing or unsafe.")
    if original.lower().endswith(".pdf") and not any(
        info.get("page snapshot", 0) for info in [count_by_kind]
    ):
        issues.append("PDF page screenshots absent: rerun import with --render-pages if figures matter.")
    if original.lower().endswith(".pptx"):
        issues.append("PowerPoint charts, groups, and positioned objects may require original-slide inspection.")
    if original.lower().endswith(".docx"):
        issues.append("DOCX figures may not appear in original paragraph order or carry printed-page numbers.")
    return {
        "lecture": path.name, "original_filename": original,
        "sections": len(sections), "linked_visuals": count,
        "visual_types": count_by_kind,
        "no_text_sections": pages_without_text,
        "short_sections_to_check": low_text,
        "missing_or_unsafe_images": missing_images,
        "scan_warnings": scan_warnings,
        "ocr_sections": ocr_sections,
        "issues": issues,
        "needs_attention": bool(pages_without_text or missing_images or not sections or scan_warnings or ocr_sections),
        "disclaimer": "Technical extraction check only; not a scientific, image-content, or privacy review."
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path, nargs="?", default=Path("course/processed"),
                   help="Imported Markdown file or course/processed directory")
    p.add_argument("--json", action="store_true", help="Machine-readable report")
    p.add_argument("--strict", action="store_true", help="Return exit code 2 for missing text/figures")
    args = p.parse_args()
    try:
        if args.input.is_dir():
            sources = sorted(file for file in args.input.glob("*.md") if not file.is_symlink())
        else:
            sources = [args.input]
        if not sources:
            raise ValueError("No imported lecture files found")
        reports = [audit(path) for path in sources]
        if args.json:
            print(json.dumps(reports, indent=2, ensure_ascii=False))
        else:
            for report in reports:
                print(f"\n{report['lecture']}: {report['sections']} section(s), "
                      f"{report['linked_visuals']} image links")
                for issue in report["issues"]:
                    print("  CHECK:", issue)
                for issue in report["missing_or_unsafe_images"]:
                    print("    MISSING:", issue)
                if report["short_sections_to_check"]:
                    preview = ", ".join(report["short_sections_to_check"][:5])
                    print(f"  REVIEW SHORT TEXT: {preview}")
                if not report["needs_attention"]:
                    print("  No blocking extraction warnings; compare against the original.")
        if args.strict and any(report["needs_attention"] for report in reports):
            return 2
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
