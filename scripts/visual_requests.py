#!/usr/bin/env python3
"""Manage visual needs and reviewed image attachments, locally and without an API.

The AI decides whether a picture genuinely helps; this program only records
source-anchored requests, generates a browser search link and tracks review.
It never searches the web, downloads pictures or validates medical accuracy.

Examples:
  python scripts/visual_requests.py request --source renal-pdf.md --anchor "Page 4" --topic "glomerular filtration" --kind histology --reason "Need a labeled corpuscle"
  python scripts/visual_requests.py list
  python scripts/visual_requests.py search --query "glomerulus PAS histology"
  python scripts/visual_requests.py attach REQUEST_ID --file /path/to/photo.png --title "..." --source-url "https://..." --creator "..." --license "..."
  python scripts/visual_requests.py approve REQUEST_ID --checked-medical --checked-rights
  python scripts/visual_requests.py embed REQUEST_ID
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from add_image import add_image
from study import valid_reference

KINDS = ("anatomy", "histology", "physiology", "pathology", "radiology", "other")
STATES = ("requested", "attached", "approved")


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check_text(value: str, label: str, max_length: int = 400) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > max_length or "\x00" in cleaned:
        raise ValueError(f"{label} must contain 1 to {max_length} characters")
    return cleaned


def search_link(query: str) -> str:
    query = check_text(query, "Query", 150)
    # Search happens only after the user/agent opens this ordinary web URL.
    return "https://commons.wikimedia.org/wiki/Special:MediaSearch?" + urlencode(
        {"search": query, "type": "image"}
    )


def read_ledger(file: Path) -> dict:
    if not file.exists():
        return {"version": 1, "requests": []}
    obj = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or obj.get("version") != 1 or not isinstance(obj.get("requests"), list):
        raise ValueError("Invalid visual-request ledger. Back it up rather than overwriting it.")
    return obj


def write_ledger(file: Path, obj: dict) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    temp = file.with_name(file.name + ".tmp")
    try:
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(obj, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, file)
    finally:
        if temp.exists():
            temp.unlink()


def find_request(obj: dict, request_id: str) -> dict:
    for req in obj["requests"]:
        if req.get("id") == request_id:
            return req
    raise ValueError("Unknown request ID: " + request_id)


def create_request(database: Path, notes_dir: Path, source: str, anchor: str, topic: str,
                   kind: str, reason: str) -> dict:
    valid_reference(notes_dir, source, anchor)
    if kind not in KINDS:
        raise ValueError("Unsupported medical visual kind")
    topic = check_text(topic, "Topic", 150)
    reason = check_text(reason, "Reason")
    obj = read_ledger(database)
    for item in obj["requests"]:
        if (item["source"], item["anchor"], item["topic"].casefold()) == (
            source, anchor, topic.casefold()
        ):
            raise ValueError("Already requested for this topic and lecture location: " + item["id"])
    entry = {
        "id": uuid.uuid4().hex[:12],
        "created_utc": timestamp(),
        "source": source, "anchor": anchor,
        "topic": topic, "kind": kind, "reason": reason,
        "status": "requested", "attachment": None
    }
    obj["requests"].append(entry)
    write_ledger(database, obj)
    return entry


def attach_request(database: Path, image_dir: Path, request_id: str, file: Path, title: str,
                   source_url: str, creator: str, license_name: str) -> dict:
    obj = read_ledger(database)
    req = find_request(obj, request_id)
    if req["status"] != "requested":
        raise ValueError("Cannot attach to an already attached/approved request")
    target, credit = add_image(file, image_dir, title, source_url, creator, license_name, reviewed=False)
    req["status"] = "attached"
    req["attachment"] = {
        "filename": target.name, "title": title, "credit": credit,
        "source_url": source_url, "creator": creator, "license": license_name
    }
    req["attached_utc"] = timestamp()
    write_ledger(database, obj)
    return req


def approve_request(database: Path, image_dir: Path, request_id: str,
                    checked_medical: bool, checked_rights: bool) -> dict:
    if not checked_medical or not checked_rights:
        raise ValueError("Both explicit review confirmations are required")
    obj = read_ledger(database)
    req = find_request(obj, request_id)
    if req["status"] != "attached" or not isinstance(req["attachment"], dict):
        raise ValueError("Only attached, not-yet-approved requests can be approved")
    name = req["attachment"]["filename"]
    if Path(name).name != name:
        raise ValueError("Invalid stored filename")
    file = image_dir / name
    metadata_file = image_dir / (name + ".json")
    if not file.is_file() or not metadata_file.is_file():
        raise ValueError("Image or attribution metadata is missing")
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    if metadata.get("filename") != name:
        raise ValueError("Attribution metadata mismatch")
    # This represents an explicit human review assertion, not a scientific check.
    metadata["medical_accuracy_reviewed"] = True
    metadata["license_verified"] = True
    metadata["review_method"] = "human_attestation"
    metadata["reviewed_utc"] = timestamp()
    temp = metadata_file.with_name(metadata_file.name + ".tmp")
    try:
        temp.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temp, metadata_file)
    finally:
        if temp.exists():
            temp.unlink()
    req["status"] = "approved"
    req["approved_utc"] = timestamp()
    write_ledger(database, obj)
    return req


def approved_embed(req: dict) -> str:
    if req["status"] != "approved" or not req.get("attachment"):
        raise ValueError("Image has not been reviewed and approved for study use")
    info = req["attachment"]
    safe_title = re.sub(r"[\[\]\(\)\n]", "", info["title"])
    return (
        f"![{safe_title}](course/visuals/{info['filename']})\n\n"
        f"*Visual linked to {req['source']}, {req['anchor']} (supplementary image; "
        f"not from the professor's original slide).* "
        f"{info['credit']}\n\n"
        "**Review:** user-confirmed medical and licensing checks; not independently certified."
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--database", type=Path, default=Path("course/visual_requests.json"))
    p.add_argument("--notes-dir", type=Path, default=Path("course/processed"))
    p.add_argument("--image-dir", type=Path, default=Path("course/visuals"))
    actions = p.add_subparsers(dest="command", required=True)
    new = actions.add_parser("request")
    new.add_argument("--source", required=True)
    new.add_argument("--anchor", required=True)
    new.add_argument("--topic", required=True)
    new.add_argument("--kind", choices=KINDS, required=True)
    new.add_argument("--reason", required=True)
    listing = actions.add_parser("list")
    listing.add_argument("--status", choices=STATES)
    listing.add_argument("--json", action="store_true")
    search = actions.add_parser("search")
    search.add_argument("--query", required=True, help="Return a regular browser search URL (no network call)")
    attach = actions.add_parser("attach")
    attach.add_argument("id")
    attach.add_argument("--file", type=Path, required=True)
    for arg in ("title", "source-url", "creator", "license"):
        attach.add_argument("--" + arg, required=True)
    approve = actions.add_parser("approve")
    approve.add_argument("id")
    approve.add_argument("--checked-medical", action="store_true")
    approve.add_argument("--checked-rights", action="store_true")
    embed = actions.add_parser("embed")
    embed.add_argument("id")
    try:
        args = p.parse_args()
        if args.command == "request":
            req = create_request(args.database, args.notes_dir, args.source, args.anchor,
                                 args.topic, args.kind, args.reason)
            print(f"Requested {req['id']}: {req['kind']} visual for {req['source']} / {req['anchor']}")
            print("Search page:", search_link(req["topic"]))
        elif args.command == "list":
            data = read_ledger(args.database)["requests"]
            data = [r for r in data if not args.status or r["status"] == args.status]
            if args.json:
                print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                print(f"{len(data)} visual request(s)")
                for req in data:
                    print(f"{req['id']} [{req['status']}] {req['topic']} — {req['source']} / {req['anchor']}")
        elif args.command == "search":
            print(search_link(args.query))
        elif args.command == "attach":
            req = attach_request(args.database, args.image_dir, args.id, args.file,
                                 args.title, args.source_url, args.creator, args.license)
            print(f"Attached to {req['id']}. Pending medical and rights review.")
        elif args.command == "approve":
            req = approve_request(args.database, args.image_dir, args.id,
                                  args.checked_medical, args.checked_rights)
            print(f"{req['id']} human-reviewed and approved for educational use.")
        elif args.command == "embed":
            print(approved_embed(find_request(read_ledger(args.database), args.id)))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
