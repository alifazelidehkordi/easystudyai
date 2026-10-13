#!/usr/bin/env python3
"""Locate professor lecture figures / page renderings with exact source anchors.

Read-only. This scans local imported Markdown and checks referenced image paths.
It does not recognize structures in pictures; the tutor must inspect each image.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HEADER = re.compile(r"^## (Page \d+|Slide \d+|Document|Source text)\s*$", re.MULTILINE)
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\n]+)\)")


def figure_kind(alt: str) -> str:
    if alt.startswith("Lecture PDF page"):
        return "page_render"
    if alt.startswith("Original figure"):
        return "embedded_slide_figure"
    if alt.startswith("DOCX figure"):
        return "detached_docx_figure"
    return "unclassified"


def index_figures(directory: Path, query: str = "") -> list[dict]:
    if not directory.is_dir():
        return []
    root = directory.resolve()
    words = [word.casefold() for word in query.split() if word.strip()]
    figures = []
    for file in sorted(directory.glob("*.md")):
        if not file.is_file() or file.is_symlink():
            continue
        markdown = file.read_text(encoding="utf-8")
        headers = list(HEADER.finditer(markdown))
        for idx, heading in enumerate(headers):
            block = markdown[heading.end():headers[idx + 1].start() if idx + 1 < len(headers) else len(markdown)]
            if words and not all(word in block.casefold() or word in heading.group(1).casefold() for word in words):
                continue
            for item in IMAGE.finditer(block):
                alt, linked = item.groups()
                # Imported assets are local relative paths. External URLs are ignored.
                if linked.startswith(("http://", "https://", "data:")):
                    continue
                target = (file.parent / linked).resolve()
                if not target.is_relative_to(root):
                    continue  # never follow image references outside the import library
                figures.append({
                    "lecture": file.name,
                    "anchor": heading.group(1),
                    "kind": figure_kind(alt),
                    "description_from_import": alt,
                    "path": str(target),
                    "exists": target.is_file(),
                    "medical_content_verified": False,
                })
    return figures


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory", type=Path, default=Path("course/processed"))
    p.add_argument("--query", default="", help="Words from same slide/page text (not image recognition)")
    p.add_argument("--json", action="store_true", help="Structured results for a harness")
    p.add_argument("--limit", type=int, default=30)
    args = p.parse_args()
    if args.limit < 1 or args.limit > 500:
        p.error("--limit must be 1–500")
    try:
        figures = index_figures(args.directory, args.query)
        if args.json:
            print(json.dumps({"total": len(figures), "figures": figures[:args.limit]}, ensure_ascii=False, indent=2))
        else:
            print(f"Indexed {len(figures)} local lecture visual(s). Figures are not medically verified.")
            for figure in figures[:args.limit]:
                status = "found" if figure["exists"] else "MISSING"
                print(f"\n{figure['lecture']} — {figure['anchor']} — {figure['kind']} [{status}]")
                print(f"  {figure['path']}")
                print(f"  {figure['description_from_import']}")
            if len(figures) > args.limit:
                print(f"\n{len(figures) - args.limit} more result(s); increase --limit")
    except (OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
