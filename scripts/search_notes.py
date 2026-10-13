#!/usr/bin/env python3
"""Search imported professor lectures locally; show grounded page/slide snippets.

No AI model, internet connection, API key, or embeddings are involved.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


def terms(query: str) -> list[str]:
    return re.findall(r"[\w-]+", query.casefold(), flags=re.UNICODE)


def split_sections(markdown: str):
    # Each section begins at a native page/slide/paragraph or generic source heading.
    blocks = re.split(r"(?=^## (?:Page \d+|Slide \d+|Document|Source text))", markdown, flags=re.MULTILINE)
    for block in blocks:
        anchor = re.search(r"^## ([^\n]+)", block, flags=re.MULTILINE)
        if anchor:
            yield anchor.group(1), block


def search(directory: Path, query: str, limit: int = 8):
    keys = terms(query)
    if not keys:
        raise ValueError("Please enter search terms")
    results = []
    for path in sorted(directory.glob("*.md")):
        if path.is_symlink() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for anchor, block in split_sections(text):
            folded = block.casefold()
            if not all(term in folded for term in keys):
                continue
            score = sum(folded.count(term) for term in keys)
            first = min(folded.find(term) for term in keys)
            snippet = " ".join(block[max(0, first - 90): first + 250].split())
            results.append((score, path, anchor, snippet))
    return sorted(results, key=lambda item: (-item[0], str(item[1]), item[2]))[:limit]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("query", help="Keywords to find in course imports")
    p.add_argument("--directory", type=Path, default=Path("course/processed"))
    p.add_argument("--top", type=int, default=8)
    args = p.parse_args()
    if not 1 <= args.top <= 50:
        p.error("--top must be 1 to 50")
    try:
        results = search(args.directory, args.query, args.top)
    except (OSError, ValueError) as exc:
        p.error(str(exc))
    if not results:
        print("No matching imported lecture sections. Try synonyms or import the lecture first.")
    for score, source, anchor, snippet in results:
        print(f"{source} — {anchor} (matches: {score})")
        print(f"  {snippet}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
