#!/usr/bin/env python3
"""Interactive CLI active-recall review when no native Pi quiz widget is available.

No model API, internet or account needed. Cards are created by the tutor from
verified imported lecture anchors with scripts/study.py add.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from study import due_cards, grade_card, load_db, stats


def study_session(database: Path, limit: int = 12, input_fn=input, output_fn=print) -> dict:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    queue = due_cards(load_db(database))[:limit]
    if not queue:
        output_fn("No review questions due. Add source-linked questions during your next lesson.")
        return {"due": 0, "answered": 0, "stopped": False}
    output_fn(f"{len(queue)} question(s) due. Try to answer before revealing the key.")
    answered = 0
    for idx, card in enumerate(queue, 1):
        output_fn("")
        output_fn(f"[{idx}/{len(queue)}] {card['topic']} — {card['source']} / {card['anchor']}")
        output_fn(card["question"])
        reply = input_fn("Your answer (enter to reveal, /quit to stop): ")
        if reply.strip().casefold() in {"/quit", "/q"}:
            output_fn("Session stopped. Unreviewed cards remain due.")
            return {"due": len(queue), "answered": answered, "stopped": True}
        output_fn(f"Expected answer: {card['answer']}")
        if reply.strip():
            output_fn("Compare your answer against the source. Be cautious with partial or lucky answers.")
        while True:
            rating = input_fn("Self-rate [again / hard / good / easy] or /quit: ").strip().casefold()
            if rating in {"/quit", "/q"}:
                output_fn("Session stopped; this card was not graded.")
                return {"due": len(queue), "answered": answered, "stopped": True}
            if rating in {"again", "hard", "good", "easy"}:
                break
            output_fn("Choose exactly: again, hard, good or easy.")
        updated = grade_card(database, card["id"], rating)
        answered += 1
        output_fn(f"Saved. Next due: {updated['due']}.")
    result = stats(load_db(database))
    output_fn(f"Finished {answered}/{len(queue)}. Total: {result['total']}; due today: {result['due']}.")
    return {"due": len(queue), "answered": answered, "stopped": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("course/progress.json"))
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()
    try:
        study_session(args.database, args.limit)
        return 0
    except (OSError, ValueError, json.JSONDecodeError, EOFError, KeyboardInterrupt) as exc:
        print(f"Session ended without grading the current question: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
