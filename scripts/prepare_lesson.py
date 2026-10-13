#!/usr/bin/env python3
"""Generate a source-linked teaching brief from an imported lecture.

Deterministic navigation aid, NOT an AI summary or medical validation.
No internet, model API or embeddings required.
"""
from __future__ import annotations
import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from audit_lecture import audit

SECTION = re.compile(r"^## (Page \d+|Slide \d+|Document|Source text)\s*$", re.MULTILINE)
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\n]+)\)")
WORD = re.compile(r"\b[\w'-]+\b", re.UNICODE)
OBJECTIVE = re.compile(r"^\s*(?:learning\s+)?(?:objectives?|outcomes?|goals?)\s*:?\s*$", re.I)
BULLET = re.compile(r"^\s*(?:[-*•]|\d{1,2}[.)])\s+(.+)$")
SOURCE = re.compile(r"^- Original filename:\s*(.+)$", re.MULTILINE)
TICK = chr(96)


def tidy(value: str) -> str:
    return " ".join(value.split())


def safe_inline(value: str, limit: int = 100) -> str:
    return tidy(value).replace("|", "\\|").replace(TICK, "'")[:limit]


def sections_of(markdown: str) -> list[tuple[str, str]]:
    headings = list(SECTION.finditer(markdown))
    return [
        (heading.group(1), markdown[heading.end():headings[i + 1].start() if i + 1 < len(headings) else len(markdown)])
        for i, heading in enumerate(headings)
    ]


def remove_media(content: str) -> str:
    content = IMAGE.sub(" ", content)
    return re.sub(r"\[No selectable text:[^\]\n]+\]|\[No readable text/inline figure[^\]\n]+\]", " ", content)


def explicit_objectives(content: str, anchor: str) -> list[tuple[str, str]]:
    """Only verbatim bullets beneath a literal 'learning objectives' heading."""
    lines = content.splitlines()
    result = []
    for i, line in enumerate(lines):
        if not OBJECTIVE.fullmatch(line.strip().strip("*# ")):
            continue
        started = False
        for candidate in lines[i + 1:i + 13]:
            text = candidate.strip()
            if not text and not started:
                continue
            match = BULLET.match(text)
            if not match:
                break
            objective = tidy(match.group(1))
            if 8 <= len(objective) <= 350:
                result.append((objective, anchor))
                started = True
        if result:
            break
    return result


def section_title(content: str) -> str:
    for line in remove_media(content).splitlines():
        clean = tidy(line).lstrip("#-:*• ")
        if clean and not clean.startswith(("Paragraph ", "Table ", "[")):
            return safe_inline(clean, 76)
    return "(No readable heading)"


def create_brief(imported: Path, destination: Path, overwrite: bool = False) -> tuple[Path, dict]:
    if not imported.is_file() or imported.is_symlink() or imported.suffix.lower() != ".md":
        raise ValueError("Expected a real imported Markdown file: " + str(imported))
    raw = imported.read_text(encoding="utf-8")
    report = audit(imported)
    sections = sections_of(raw)
    if not sections:
        raise ValueError("No source-anchored sections: inspect/reimport the lecture")
    found = SOURCE.search(raw)
    original = found.group(1) if found else imported.name
    target = destination / (imported.stem + "-brief.md")
    if target.exists() and not overwrite:
        raise ValueError("Brief exists; use --force to replace: " + str(target))
    objectives, table, previews, visuals = [], [], [], []
    for anchor, body in sections:
        plain = remove_media(body)
        pictures = IMAGE.findall(body)
        word_count = len(WORD.findall(plain))
        objectives.extend(explicit_objectives(plain, anchor))
        scan_gap = "No selectable text:" in body or "No readable text/inline figure" in body
        flag = "CHECK ORIGINAL: text gap" if scan_gap else ("Very short text" if word_count < 20 else "—")
        table.append(
            f"| {safe_inline(anchor)} | {section_title(body)} | {word_count} | {len(pictures)} | {flag} |"
        )
        if not scan_gap:
            excerpt = safe_inline(plain, 230)
            if excerpt:
                previews.append(f"- **{anchor}**: {excerpt}")
        if pictures:
            visuals.append(
                f"- **{anchor}**: {len(pictures)} image link(s). Open the original "
                "figure before teaching. The index does not verify image content."
            )
    unique = []
    seen = set()
    for obj, anchor in objectives:
        key = (obj.casefold(), anchor)
        if key not in seen:
            unique.append((obj, anchor))
            seen.add(key)
    lines = [
        "# Teaching brief — " + original,
        "",
        "- Imported source: " + TICK + imported.name + TICK,
        "- Original lecture: " + TICK + original + TICK,
        "- Created UTC: " + datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "- **This is an automatic index, not a verified medical summary.**",
        "- The tutor must inspect full imported sections and original lecture images.",
        "",
        "## Explicit learning objectives from lecture text",
        "",
    ]
    if unique:
        lines += [f"- {obj} — ({original}, {anchor})" for obj, anchor in unique]
    else:
        lines.append(
            "No explicit bullet-style objectives detected. Do not attribute generated "
            "learning objectives to your professor."
        )
    lines += [
        "",
        "## Source map",
        "",
        "| Actual anchor | First readable text (not inferred topic) | Words | Image links | Flag |",
        "|---|---|---:|---:|---|",
        *table,
        "",
        "## Short verbatim source previews (check full notes)",
        "",
        *(previews or ["No readable excerpt found; inspect the original document."]),
        "",
        "## Figure index",
        "",
        *(visuals or ["No linked figures in text extraction; original lecture may still contain visuals."]),
        "",
        "## Technical import audit",
        "",
        f"- Sections: {report['sections']}; linked visuals: {report['linked_visuals']}",
        f"- Missing image references: {len(report['missing_or_unsafe_images'])}",
        f"- Sections with no extracted text: {len(report['no_text_sections'])}",
        "",
    ]
    if report["issues"]:
        lines += ["**Check before teaching:**"] + ["- " + item for item in report["issues"]]
    else:
        lines.append("No structural problems detected. Medical facts are not verified.")
    lines += [
        "",
        "## Teaching instructions",
        "",
        "1. Read AGENTS.md and the teach/medical-sources/medical-visuals/review skills.",
        "2. Read the full original lecture or matching imported source sections, not just this brief.",
        "3. Probe prerequisite understanding with 2–4 questions.",
        "4. Propose a short ordered teaching plan and verify its source anchors.",
        "5. Teach one concept at a time and wait for the learner's answer to each check.",
        "6. Prefer original lecturer figures, then reviewed supplemental visuals as needed.",
        "7. Offer only fact-checked, source-anchored retention questions.",
        "",
        "Never present this generated index as your professor's analysis or a clinical answer key.",
        "",
    ]
    destination.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    info = {
        "sections": len(sections),
        "explicit_objectives": len(unique),
        "linked_visuals": report["linked_visuals"],
        "missing_visuals": len(report["missing_or_unsafe_images"]),
        "no_text_sections": len(report["no_text_sections"]),
    }
    return target, info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("imported", type=Path, help="Previously imported course/processed/*.md file")
    parser.add_argument("--output", type=Path, default=Path("course/briefs"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        target, info = create_brief(args.imported, args.output, args.force)
        print("Prepared:", target)
        print("Sections: {sections}; objective quotes: {explicit_objectives}; visuals: {linked_visuals}; missing: {missing_visuals}; no text: {no_text_sections}".format(**info))
        print("Give the brief to Codex or Pi, but teach from original lecture material.")
        return 0
    except (OSError, ValueError, UnicodeError) as error:
        print("ERROR:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
