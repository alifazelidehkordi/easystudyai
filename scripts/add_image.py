#!/usr/bin/env python3
"""Add a reviewed educational image to the local study library without any API.

The user/harness researches an image and downloads it separately; this tool
validates file type, copies it safely and preserves citation/credit metadata.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


TYPES = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".webp": (b"RIFF",),
}
MAX_BYTES = 15 * 1024 * 1024


def safe_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:55] or "visual"


def valid_image(path: Path):
    if not path.is_file():
        raise ValueError("Image does not exist")
    if path.is_symlink():
        raise ValueError("Symlink source files are not accepted")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Image exceeds 15 MiB")
    ext = path.suffix.lower()
    if ext not in TYPES:
        raise ValueError("Allowed images: PNG, JPEG, GIF and WebP. SVG is excluded.")
    with path.open("rb") as src:
        signature = src.read(16)
    if not any(signature.startswith(prefix) for prefix in TYPES[ext]):
        raise ValueError("File header does not match extension")
    if ext == ".webp" and signature[8:12] != b"WEBP":
        raise ValueError("Invalid WebP signature")


def add_image(image: Path, output: Path, title: str, source_url: str,
              creator: str, license_name: str, reviewed: bool = False):
    valid_image(image)
    parsed = urlparse(source_url)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise ValueError("Use the original image's HTTP(S) source page URL")
    if not all([title.strip(), creator.strip(), license_name.strip()]):
        raise ValueError("Title, creator and license text must be provided")
    content_hash = hashlib.sha256(image.read_bytes()).hexdigest()
    name = f"{safe_name(title)}-{content_hash[:10]}{image.suffix.lower()}"
    output.mkdir(parents=True, exist_ok=True)
    target = output / name
    if not target.exists():
        shutil.copyfile(image, target)
    metadata = {
        "filename": name, "title": title, "source_page": source_url,
        "creator": creator, "license": license_name,
        "sha256": content_hash, "added_utc": datetime.now(timezone.utc).isoformat(),
        "medical_accuracy_reviewed": reviewed,
        "license_verified": reviewed,
        "warning": "Review license terms, accuracy, view/laterality and patient privacy before use."
    }
    (output / (name + ".json")).write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    credit = f"{title} — {creator}, {license_name}; source: {source_url}"
    credits_path = output / "ATTRIBUTIONS.md"
    existing = credits_path.read_text(encoding="utf-8") if credits_path.exists() else "# Image attributions\n"
    if name not in existing:
        credits_path.write_text(existing + f"\n- {name}: {credit}\n", encoding="utf-8")
    return target, credit


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--file", type=Path, required=True, help="Already downloaded local image")
    p.add_argument("--title", required=True)
    p.add_argument("--source-url", required=True, help="Original image's reference page (not a made-up link)")
    p.add_argument("--creator", required=True)
    p.add_argument("--license", dest="license_name", required=True)
    p.add_argument("--reviewed", action="store_true", help="Only if you reviewed source, license and medical accuracy")
    p.add_argument("--output", type=Path, default=Path("course/visuals"))
    a = p.parse_args()
    try:
        dest, credit = add_image(a.file, a.output, a.title, a.source_url, a.creator, a.license_name, a.reviewed)
        print("Saved:", dest)
        print("Markdown: ![", a.title, "](", dest.as_posix(), ")", sep="")
        print("Credit:", credit)
        if not a.reviewed:
            print("NOT VERIFIED: review scientific details and license before showing to students")
        return 0
    except (OSError, ValueError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
