#!/usr/bin/env python3
"""Offline diagnostics for EasyStudyAI. Never signs in or calls any API.

Run: python scripts/doctor.py [--json] [--require-harness]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path


def check(root: Path) -> dict:
    checks: list[dict] = []
    def record(name: str, level: str, message: str):
        checks.append({"name": name, "level": level, "message": message})

    if sys.version_info >= (3, 10):
        record("python", "ok", f"Python {sys.version_info.major}.{sys.version_info.minor}")
    else:
        record("python", "error", "Python >=3.10 required for local scripts")

    libs = [
        ("pymupdf", "PDF import / local OCR"),
        ("pptx", "PowerPoint import"),
        ("docx", "Word import"),
    ]
    for module, purpose in libs:
        installed = importlib.util.find_spec(module) is not None
        record(module, "ok" if installed else "warning",
               f"{purpose}: {'installed' if installed else 'not installed; pip install -r requirements.txt'}")

    harnesses = [h for h in ("codex", "pi") if shutil.which(h)]
    record("harness", "ok" if harnesses else "warning",
           ("Available: " + ", ".join(harnesses) if harnesses else
            "Neither Codex CLI nor Pi is on PATH. Install one and use ChatGPT/Codex sign-in."))

    tesseract = shutil.which("tesseract")
    record("local_ocr", "ok" if tesseract else "info",
           "Tesseract on PATH; --ocr is optional" if tesseract else
           "Tesseract not found on PATH; optional --ocr requires a local installation and language files.")

    if os.environ.get("OPENAI_API_KEY"):
        record("api_key", "info",
               "OPENAI_API_KEY is set in this shell but EasyStudyAI does not require or read it.")
    else:
        record("api_key", "ok", "No separate model API key required.")

    required = [
        "AGENTS.md", ".agents/skills/teach/SKILL.md",
        ".agents/skills/medical-sources/SKILL.md",
        ".agents/skills/medical-visuals/SKILL.md",
        ".agents/skills/prepare-lecture/SKILL.md",
        ".agents/skills/review/SKILL.md",
        "scripts/learn.py", "scripts/study.py",
    ]
    for name in required:
        if not (root / name).is_file():
            record("files", "error", f"Missing repository component: {name}")

    ignore = root / ".gitignore"
    ignored = set(ignore.read_text(encoding="utf-8").splitlines()) if ignore.is_file() else set()
    private_locations = [
        "course/lectures/", "course/processed/", "course/visuals/",
        "course/briefs/", "course/validation/", "course/sessions/",
        "course/progress.json", "course/visual_requests.json*",
        "course/LOCAL_COURSE.md",
    ]
    missing = [part for part in private_locations if part not in ignored]
    record("privacy", "error" if missing else "ok",
           ("Git ignore patterns missing: " + ", ".join(missing)) if missing else
           "Common lecture files, learning history and local course settings are gitignored.")
    record("privacy_scope", "info",
           "Gitignore is not encryption. Do not commit/upload real patient information. "
           "AI-read materials may be transmitted to the subscription provider.")

    lectures = sorted((root / "course" / "processed").glob("*.md"))
    briefs = sorted((root / "course" / "briefs").glob("*-brief.md"))
    record("lectures", "ok" if lectures else "info",
           f"{len(lectures)} imported lecture(s), {len(briefs)} brief(s).")
    if lectures:
        record("next", "info", "Run python scripts/study.py due or launch Codex/Pi in this folder.")
    else:
        record("next", "info", 'Start with: python scripts/learn.py "course/lectures/My lecture.pdf"')

    return {
        "overall": "needs_fixes" if any(c["level"] == "error" for c in checks) else "ready_for_local_use",
        "subscription_login_checked": False,
        "subscription_login_message": "Authentication cannot be checked by this offline script. Sign in via Codex CLI or Pi.",
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    parser.add_argument("--require-harness", action="store_true",
                        help="Exit 2 if neither Codex nor Pi is installed")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    result = check(root)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("EasyStudyAI local setup")
        for item in result["checks"]:
            print(f"[{item['level'].upper()}] {item['name']}: {item['message']}")
        print("Status:", result["overall"])
        print(result["subscription_login_message"])
    problems = result["overall"] == "needs_fixes"
    no_harness = not any(shutil.which(h) for h in ("codex", "pi"))
    return 2 if problems or (args.require_harness and no_harness) else 0


if __name__ == "__main__":
    raise SystemExit(main())
