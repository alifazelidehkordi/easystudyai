#!/usr/bin/env python3
"""Convert professor PDFs, PowerPoints, Word files or text to cited Markdown.

Everything runs locally. This script never connects to any LLM/API.
OCR is intentionally not attempted: scanned pages require visual review.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from datetime import datetime, timezone


def slug(text: str) -> str:
    return (re.sub(r"[^a-zA-Z0-9_-]+", "-", text).strip("-")[:70] or "lecture").lower()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def tidy(value: str) -> str:
    return (value or "").replace("\x00", "").replace("\r\n", "\n").strip()


def read_pdf(source: Path, assets: Path, render_pages: bool, ocr: bool = False,
             ocr_language: str = "eng", tessdata: str | None = None):
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("PDF support requires pip install -r requirements.txt") from exc
    result, warnings = [], []
    with pymupdf.open(source) as pdf:
        if pdf.is_encrypted:
            raise RuntimeError("Encrypted PDF: unlock a permitted copy first")
        for number, page in enumerate(pdf, 1):
            text = tidy(page.get_text("text", sort=True))
            ocr_used = False
            if not text and ocr:
                try:
                    ocr_page = page.get_textpage_ocr(
                        language=ocr_language, dpi=180, full=True, tessdata=tessdata
                    )
                    text = tidy(page.get_text("text", textpage=ocr_page))
                    ocr_used = True
                except Exception as exc:
                    raise RuntimeError(
                        "Local OCR failed. Install Tesseract language data for "
                        f"{ocr_language!r}, set TESSDATA_PREFIX or pass --tessdata. "
                        "No cloud OCR or API was called."
                    ) from exc
            chunk = [f"## Page {number}", ""]
            if ocr_used:
                chunk += ["[LOCAL OCR TRANSCRIPTION — UNVERIFIED: check original page]", ""]
                warnings.append(
                    f"Page {number}: local OCR transcription; verify every medical term, "
                    "number and diagram label against page image"
                )
            chunk += [text or "[No selectable text: check scanned page image.]"]
            if not text:
                warnings.append(
                    f"Page {number}: no extracted text"
                    + (" after local OCR" if ocr else "; OCR not performed")
                )
            if render_pages:
                assets.mkdir(parents=True, exist_ok=True)
                filename = f"page-{number:04}.png"
                page.get_pixmap(dpi=120, alpha=False).save(str(assets / filename))
                chunk += ["", f"![Lecture PDF page {number}](assets/{assets.name}/{filename})"]
            result.append("\n".join(chunk) + "\n")
    return result, warnings


def read_pptx(source: Path, assets: Path):
    try:
        from pptx import Presentation
        from pptx.enum.shapes import MSO_SHAPE_TYPE
    except ImportError as exc:
        raise RuntimeError("PowerPoint support requires pip install -r requirements.txt") from exc

    sections, warnings = [], []

    def visit_shapes(shapes, slide_number: int, lines: list[str], counter: list[int]):
        """Walk text, tables and pictures, including many grouped shapes."""
        for shape in shapes:
            if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                visit_shapes(shape.shapes, slide_number, lines, counter)
                continue
            if shape.has_text_frame and tidy(shape.text):
                lines.extend([tidy(shape.text), ""])
            if shape.has_table:
                rows = [
                    [tidy(cell.text).replace("\n", " ").replace("|", "\\|") for cell in row.cells]
                    for row in shape.table.rows
                ]
                if rows:
                    lines.append("| " + " | ".join(rows[0]) + " |")
                    lines.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
                    lines.extend("| " + " | ".join(row) + " |" for row in rows[1:])
                    lines.append("")
            if shape.has_chart:
                # Charts may rely on colors/legends and embedded worksheets:
                # presenting bare numbers as a faithful image would be unsafe.
                lines.extend(["[Chart object: inspect original slide for axes, legend and units.]", ""])
                warnings.append(f"Slide {slide_number}: chart is not rendered/extracted")
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                ext = shape.image.ext.lower()
                if ext not in {"png", "jpg", "jpeg", "webp", "gif"}:
                    warnings.append(f"Slide {slide_number}: skipped image type {ext}")
                    continue
                counter[0] += 1
                assets.mkdir(parents=True, exist_ok=True)
                filename = f"slide-{slide_number:04}-figure-{counter[0]:02}.{ext}"
                (assets / filename).write_bytes(shape.image.blob)
                lines.extend([f"![Original figure, slide {slide_number}](assets/{assets.name}/{filename})", ""])

    for n, slide in enumerate(Presentation(str(source)).slides, 1):
        lines = [f"## Slide {n}", ""]
        visit_shapes(slide.shapes, n, lines, [0])
        if slide.has_notes_slide:
            notes_frame = slide.notes_slide.notes_text_frame
            notes = tidy(notes_frame.text if notes_frame is not None else "")
            if notes:
                lines.extend([f"### Speaker notes (slide {n}; not visible on slide)", "", notes, ""])
        if len(lines) <= 2:
            lines.append("[No readable text/inline figure; inspect original slide.]")
        sections.append("\n".join(lines) + "\n")
    warnings.append(
        "PowerPoint SmartArt, charts, groups, positioning and notes may not faithfully "
        "survive extraction: always inspect the original slides."
    )
    return sections, warnings

def read_docx(source: Path, assets: Path):
    try:
        from docx import Document
        from docx.parts.image import ImagePart
    except ImportError as exc:
        raise RuntimeError("Word support requires pip install -r requirements.txt") from exc
    document = Document(source)
    chunks = ["## Document", ""]
    # Preserve the interleaving of Word paragraphs and tables. Printed page
    # numbers are not available from DOCX text alone.
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    para_index = 0
    table_index = 0
    for block in document.iter_inner_content():
        if isinstance(block, Paragraph):
            para_index += 1
            text = tidy(block.text)
            if text:
                chunks.extend([f"Paragraph {para_index}: {text}", ""])
        elif isinstance(block, Table):
            table_index += 1
            chunks.extend([f"### Table {table_index}", ""])
            for row in block.rows:
                chunks.append(" | ".join(
                    tidy(cell.text).replace("\n", " ").replace("|", "\\|")
                    for cell in row.cells
                ))
            chunks.append("")
    # Images may be attached outside the paragraph sequence.
    seen = set()
    for part in document.part.related_parts.values():
        if not isinstance(part, ImagePart):
            continue
        ext = part.filename.rsplit(".", 1)[-1].lower()
        if ext not in {"png", "jpg", "jpeg", "webp", "gif"}:
            continue
        fingerprint = hashlib.sha256(part.blob).hexdigest()[:10]
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        assets.mkdir(parents=True, exist_ok=True)
        filename = f"doc-figure-{fingerprint}.{ext}"
        (assets / filename).write_bytes(part.blob)
        chunks.extend([f"![DOCX figure; position not established](assets/{assets.name}/{filename})", ""])
    return ["\n".join(chunks)], [
        "DOCX paragraph numbers are not printed page numbers; figure/table ordering may differ from original."
    ]


def convert(source: Path, destination: Path, render_pages: bool, overwrite: bool,
            ocr: bool = False, ocr_language: str = "eng",
            tessdata: str | None = None):
    if not source.is_file():
        raise ValueError(f"File not found: {source}")
    ext = source.suffix.lower()
    if ocr and ext != ".pdf":
        raise ValueError("Local OCR is supported for PDF files only")
    if ext not in {".pdf", ".pptx", ".docx", ".txt", ".md"}:
        raise ValueError(f"Unsupported file type: {ext}")
    destination.mkdir(parents=True, exist_ok=True)
    stem = slug(source.stem) + "-" + ext.lstrip(".")
    output = destination / (stem + ".md")
    if output.exists() and not overwrite:
        raise ValueError(f"Already imported: {output} (use --force to replace)")
    assets = destination / "assets" / stem
    if ext == ".pdf":
        sections, warnings = read_pdf(
            source, assets, render_pages, ocr=ocr,
            ocr_language=ocr_language, tessdata=tessdata
        )
    elif ext == ".pptx":
        sections, warnings = read_pptx(source, assets)
    elif ext == ".docx":
        sections, warnings = read_docx(source, assets)
    else:
        sections, warnings = ["## Source text\n\n" + tidy(source.read_text(encoding="utf-8-sig"))], []
    # Keep absolute paths, patient/student names, and environment details out of generated citations.
    header = [
        f"# Imported lecture: {source.name}",
        "",
        f"- Original filename: {source.name}",
        f"- Source SHA256: {sha256(source)}",
        f"- Imported at (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "- Provenance: lecturer/student-provided, NOT externally verified",
        "- Cite the original filename and the exact page/slide/paragraph anchors below",
        "- Inspect layouts, figure labels, table alignment and all scan-only pages",
        "",
    ]
    if warnings:
        header.extend(["## Import warnings", "", *["- " + warning for warning in warnings], ""])
    output.write_text("\n".join(header + sections), encoding="utf-8")
    return output, len(sections), warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--output", type=Path, default=Path("course/processed"))
    parser.add_argument("--render-pages", action="store_true", help="Render every PDF page as PNG")
    parser.add_argument("--ocr", action="store_true",
                        help="Opt-in LOCAL Tesseract OCR for PDF pages with no text layer")
    parser.add_argument("--ocr-lang", default="eng",
                        help="Installed Tesseract language pack (default: eng)")
    parser.add_argument("--tessdata", default=None,
                        help="Local Tesseract tessdata directory, if auto-discovery fails")
    parser.add_argument("--force", action="store_true", help="Replace existing Markdown")
    args = parser.parse_args()
    try:
        output, n, warnings = convert(
            args.file.expanduser(), args.output, args.render_pages, args.force,
            ocr=args.ocr, ocr_language=args.ocr_lang, tessdata=args.tessdata
        )
        print(f"Imported {n} section(s) to {output}; warnings: {len(warnings)}")
        for warning in warnings:
            print("CHECK:", warning)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
