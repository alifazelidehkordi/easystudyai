#!/usr/bin/env python3
"""Local, source-linked spaced-review cards. No accounts, embeddings or APIs.

Examples:
  python scripts/study.py add --topic "Cardiac cycle" --question "What closes the aortic valve?" --answer "Reverse pressure gradient at the end of systole" --source heart-pdf.md --anchor "Page 5"
  python scripts/study.py due
  python scripts/study.py reveal CARD_ID
  python scripts/study.py grade CARD_ID --rating good
  python scripts/study.py stats

All data is saved to gitignored course/progress.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

INTERVALS = (0, 1, 3, 7, 14, 30, 60)


def current_day() -> date:
    return date.today()


def load_db(database: Path) -> dict:
    if not database.exists():
        return {"version": 1, "cards": []}
    obj = json.loads(database.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or obj.get("version") != 1 or not isinstance(obj.get("cards"), list):
        raise ValueError("Unsupported or damaged progress file: back it up before proceeding")
    return obj


def save_db(database: Path, obj: dict) -> None:
    database.parent.mkdir(parents=True, exist_ok=True)
    temp = database.with_name(database.name + ".tmp")
    try:
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(obj, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, database)
    finally:
        if temp.exists():
            temp.unlink()


def valid_reference(notes: Path, source: str, anchor: str) -> None:
    if not source or Path(source).name != source or source in {".", ".."} or not source.endswith(".md"):
        raise ValueError("--source must be a single imported Markdown filename, e.g. heart-pdf.md")
    if not anchor or "\n" in anchor or "\r" in anchor:
        raise ValueError("--anchor must be an exact non-empty page or slide heading, e.g. Page 3")
    file = notes / source
    if not file.is_file() or file.is_symlink():
        raise ValueError(f"Missing imported lecture: {file}")
    body = file.read_text(encoding="utf-8")
    if not re.search(r"^## " + re.escape(anchor) + r"\s*$", body, flags=re.MULTILINE):
        raise ValueError(f"No heading '## {anchor}' in {source}; check the imported notes")


def add_card(database: Path, notes: Path, topic: str, question: str, answer: str,
             source: str, anchor: str, today: date | None = None) -> dict:
    today = today or current_day()
    if not all(isinstance(x, str) and x.strip() for x in (topic, question, answer)):
        raise ValueError("Topic, question and answer cannot be empty")
    valid_reference(notes, source, anchor)
    obj = load_db(database)
    if any(c["question"].strip().casefold() == question.strip().casefold()
           and c["source"] == source and c["anchor"] == anchor for c in obj["cards"]):
        raise ValueError("That question is already linked to this lecture location")
    card = {
        "id": uuid.uuid4().hex[:12], "topic": topic.strip(),
        "question": question.strip(), "answer": answer.strip(),
        "source": source, "anchor": anchor,
        "created": today.isoformat(), "due": today.isoformat(),
        "box": 0, "reviews": []
    }
    obj["cards"].append(card)
    save_db(database, obj)
    return card


def find_card(obj: dict, card_id: str) -> dict:
    for card in obj["cards"]:
        if card.get("id") == card_id:
            return card
    raise ValueError(f"No card with ID {card_id}")


def due_cards(obj: dict, today: date | None = None) -> list[dict]:
    today = today or current_day()
    return sorted(
        (c for c in obj["cards"] if date.fromisoformat(c["due"]) <= today),
        key=lambda c: (c["due"], c["topic"].casefold(), c["id"])
    )


def grade_card(database: Path, card_id: str, rating: str, today: date | None = None) -> dict:
    today = today or current_day()
    if rating not in {"again", "hard", "good", "easy"}:
        raise ValueError("Use again, hard, good or easy")
    obj = load_db(database)
    card = find_card(obj, card_id)
    if date.fromisoformat(card["due"]) > today:
        raise ValueError("Card is not due yet; avoid grading it multiple times early")
    box = int(card["box"])
    if rating == "again":
        box = 0
    elif rating == "hard":
        box = max(1, box)
    elif rating == "good":
        box = min(6, box + 1)
    else:
        box = min(6, box + 2)
    card["box"] = box
    card["due"] = (today + timedelta(days=INTERVALS[box])).isoformat()
    card["reviews"].append({"date": today.isoformat(), "rating": rating})
    save_db(database, obj)
    return card


def stats(obj: dict, today: date | None = None) -> dict:
    cards = obj["cards"]
    return {
        "total": len(cards), "due": len(due_cards(obj, today)),
        "mastered": sum(int(c["box"]) >= 4 for c in cards),
        "reviews": sum(len(c["reviews"]) for c in cards),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", type=Path, default=Path("course/progress.json"))
    parser.add_argument("--notes-dir", type=Path, default=Path("course/processed"))
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Add a source-grounded question")
    for flag in ("topic", "question", "answer", "source", "anchor"):
        add.add_argument("--" + flag, required=True)
    due = sub.add_parser("due", help="Show questions due today; answers remain hidden")
    due.add_argument("--limit", type=int, default=15)
    reveal = sub.add_parser("reveal", help="Show the answer to a question")
    reveal.add_argument("id")
    grade = sub.add_parser("grade", help="Record your actual self-assessment and reschedule")
    grade.add_argument("id")
    grade.add_argument("--rating", choices=("again", "hard", "good", "easy"), required=True)
    sub.add_parser("stats", help="Review queue summary")

    args = parser.parse_args()
    try:
        if args.command == "add":
            card = add_card(args.database, args.notes_dir, args.topic, args.question,
                            args.answer, args.source, args.anchor)
            print(f"Added {card['id']} — {card['topic']} — {card['source']} / {card['anchor']}")
        elif args.command == "due":
            if not 1 <= args.limit <= 100:
                raise ValueError("--limit must be 1 to 100")
            cards = due_cards(load_db(args.database))
            print(f"Due: {len(cards)} question(s)")
            for card in cards[:args.limit]:
                print(f"\n{card['id']} | {card['topic']} | {card['source']} / {card['anchor']}")
                print(card["question"])
            if len(cards) > args.limit:
                print(f"\n{len(cards) - args.limit} more due; raise --limit to see more")
        elif args.command == "reveal":
            card = find_card(load_db(args.database), args.id)
            print(f"{card['question']}\n\nAnswer: {card['answer']}")
            print(f"Source: {card['source']} / {card['anchor']}")
        elif args.command == "grade":
            card = grade_card(args.database, args.id, args.rating)
            print(f"{card['id']}: next review {card['due']} (stage {card['box']})")
        else:
            report = stats(load_db(args.database))
            print(f"Cards: {report['total']} | Due: {report['due']} | "
                  f"Mastered (stage 4+): {report['mastered']} | Reviews: {report['reviews']}")
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
