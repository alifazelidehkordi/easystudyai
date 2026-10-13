#!/usr/bin/env python3
"""Audit one imported medical lecture against its original file.

Uses local file metadata and extraction evidence. This tool cannot certify
medical correctness, image anatomy, or whether a lesson is ready for an exam.
No model API, cloud backend or embeddings.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from audit_lecture import audit
from import_notes import sha256

HASH = re.compile(r"^- Source SHA256:\s*([a-f0-9]{64})\s*$", flags=re.MULTILINE)
TITLE = re.compile(r"^- Original filename:\s*(.+)\s*$", flags=re.MULTILINE)


def inspect_original(path: Path) -> tuple[int | None, str]:
    """Return source page/slide count and its reliability limit."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        try:
            import pymupdf
        except ImportError:
            return None, "Install PyMuPDF to compare page counts."
        with pymupdf.open(path) as doc:
            if doc.is_encrypted:
                return None, "Encrypted PDF could not be inspected."
            return len(doc), "PDF page count verified."
    if ext == ".pptx":
        try:
            from pptx import Presentation
        except ImportError:
            return None, "Install python-pptx to compare slide counts."
        return len(Presentation(str(path)).slides), "PowerPoint slide count verified."
    return None, "Word/text document sections cannot be compared to pages reliably."


def inspect(imported: Path, original: Path | None = None) -> dict:
    details = audit(imported)
    raw = imported.read_text(encoding="utf-8")
    match = HASH.search(raw)
    recorded_hash = match.group(1) if match else None
    filename_match = TITLE.search(raw)
    filename = filename_match.group(1).strip() if filename_match else details["original_filename"]
    blockers, warnings = [], []
    if details["no_text_sections"]:
        blockers.append(
            "Some slides/pages contain no extractable text: " +
            ", ".join(details["no_text_sections"][:12]) +
            "; inspect the original images before any teaching claims."
        )
    if details["missing_or_unsafe_images"]:
        blockers.append(
            f"{len(details['missing_or_unsafe_images'])} image link(s) missing or unsafe."
        )
    if details["sections"] == 0:
        blockers.append("No page/slide/text sections detected.")
    if details["scan_warnings"]:
        warnings.append("Some scanned pages require visual reading; OCR may be absent.")
    if details.get("ocr_sections"):
        warnings.append(
            "Local OCR was used on " + ", ".join(details["ocr_sections"]) +
            ". Verify medical terms, units, laterality, doses and numbers against page images."
        )
    if details["short_sections_to_check"]:
        warnings.append(
            "Low extracted text (may be normal title slides or image-heavy slides): " +
            ", ".join(details["short_sections_to_check"][:15])
        )
    warnings.extend(details["issues"])
    if filename.lower().endswith(".pdf") and not details["visual_types"].get("page snapshot"):
        warnings.append("No rendered PDF page snapshots found; diagrams may be invisible to the text-only tutor.")
    if filename.lower().endswith(".pptx"):
        warnings.append("Charts/SmartArt and complex slide layouts may be absent: inspect original slides.")
    if filename.lower().endswith(".docx"):
        warnings.append("DOCX paragraph numbers are not printed pages; inspect tables and detached figures.")
    source_check = "not provided"
    page_count = None
    if original is not None:
        if original.is_symlink() or not original.is_file():
            raise ValueError("Original must be an existing regular file, not a symlink")
        if original.name != filename:
            blockers.append(
                f"Wrong original file: expected '{filename}', given '{original.name}'."
            )
        current_hash = sha256(original)
        if not recorded_hash:
            blockers.append("Imported lecture has no recorded SHA256 for integrity check.")
        elif current_hash != recorded_hash:
            blockers.append("Original file content differs from imported lecture: reimport with --force.")
        else:
            source_check = "matching SHA256"
        page_count, explanation = inspect_original(original)
        if page_count is not None and original.suffix.lower() in {".pdf", ".pptx"}:
            if page_count != details["sections"]:
                blockers.append(
                    f"Source has {page_count} page/slide(s) but import has "
                    f"{details['sections']} sections."
                )
        warnings.append(explanation)
    else:
        warnings.append("Original file not provided: could not verify import freshness or page count.")
    return {
        "imported": imported.name,
        "original": filename,
        "original_validation": source_check,
        "original_page_or_slide_count": page_count,
        "source_sections": details["sections"],
        "linked_figures": details["linked_visuals"],
        "no_text_sections": details["no_text_sections"],
        "ocr_sections_needing_review": details.get("ocr_sections", []),
        "short_sections_to_check": details["short_sections_to_check"],
        "missing_images": details["missing_or_unsafe_images"],
        "blocking_issues": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
        "technical_status": ("needs_review" if blockers or details.get("ocr_sections")
                             else "no_blockers_detected"),
        "disclaimer": (
            "This is a local extraction/integrity audit, NOT a medical-content, "
            "clinical, figure-label, source-rights or privacy certification."
        ),
    }


def report_markdown(result: dict) -> str:
    content = [
        "# Lecture readiness report — " + result["original"],
        "",
        "Created UTC: " + datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "",
        "**Technical status:** " + result["technical_status"],
        "",
        "**Interpretation:** " + result["disclaimer"],
        "",
        f"- Imported lecture: {result['imported']}",
        f"- Original file integrity: {result['original_validation']}",
        f"- Imported sections: {result['source_sections']}",
        f"- Linked figures/page renders: {result['linked_figures']}",
        f"- OCR pages requiring visual confirmation: {len(result['ocr_sections_needing_review'])}",
        "",
        "## Must address before source-grounded teaching",
        "",
        *("- " + item for item in result["blocking_issues"]),
    ]
    if not result["blocking_issues"]:
        content += ["- No blocking extraction problems detected. The medical content has **not** been validated."]
    content += ["", "## Other warnings and manual inspection", ""]
    content += ["- " + item for item in result["warnings"]]
    if not result["warnings"]:
        content.append("- None from automatic checks. Manual visual review remains necessary.")
    content += [
        "",
        "## Manual verification checklist (not automatically completed)",
        "",
        "- [ ] I checked original tables and chart axes against extracted material.",
        "- [ ] I inspected anatomical views, laterality, stain, units, captions and arrows where relevant.",
        "- [ ] Any image-only pages/slides have been viewed or described directly from originals.",
        "- [ ] Explicit lecture objectives were copied correctly and inferred objectives are labeled.",
        "- [ ] No identifiable patient information is being copied into outputs or commits.",
        "- [ ] Course claims and supplementary external medical claims are distinguished.",
        "",
        "This report is a checklist and **not proof of factual correctness**.",
        "",
    ]
    return "\n".join(content)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("imported", type=Path, help="A course/processed/*.md lecture")
    parser.add_argument("--original", type=Path, help="Compare the real original and recorded checksum")
    parser.add_argument("--output", type=Path, default=Path("course/validation"))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Exit code 2 if blocking problems were found")
    args = parser.parse_args()
    try:
        result = inspect(args.imported, args.original)
        output = args.output / (args.imported.stem + "-validation.md")
        args.output.mkdir(parents=True, exist_ok=True)
        output.write_text(report_markdown(result), encoding="utf-8")
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Report: {output}")
            print(f"Technical status: {result['technical_status']}")
            for issue in result["blocking_issues"]:
                print("REVIEW:", issue)
            print("Verify medical figures and statements against original files.")
        return 2 if args.strict and result["blocking_issues"] else 0
    except (OSError, ValueError, RuntimeError, UnicodeError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
