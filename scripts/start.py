#!/usr/bin/env python3
"""EasyStudyAI single entry point using your existing Pi/Codex subscription.

Examples:
  python scripts/start.py --lecture "course/lectures/Heart.pdf"
  python scripts/start.py --harness pi
  python scripts/start.py --lecture "course/lectures/Slides.pdf" --ocr
  python scripts/start.py --check-only

This launches the installed harness normally; it does not implement model API
calls, request keys, or bypass the subscription's limits/login.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", choices=("codex", "pi"), default="codex")
    parser.add_argument("--lecture", type=Path, help="Your original lecture PDF/PPTX/DOCX/TXT/MD")
    parser.add_argument("--ocr", action="store_true", help="Opt-in local Tesseract OCR for scan-only PDFs")
    parser.add_argument("--ocr-lang", default="eng", help="Installed local Tesseract language pack")
    parser.add_argument("--tessdata", help="Local Tesseract language-data directory")
    parser.add_argument("--check-only", action="store_true",
                        help="Print launch instructions without starting a model/harness")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    executable = shutil.which(args.harness)
    if args.lecture:
        if args.ocr and args.lecture.suffix.lower() != ".pdf":
            parser.error("--ocr only applies to PDF files")
        command = [sys.executable, str(root / "scripts" / "learn.py"), str(args.lecture.expanduser().resolve())]
        if args.ocr:
            command += ["--ocr", "--ocr-lang", args.ocr_lang]
            if args.tessdata:
                command += ["--tessdata", args.tessdata]
        if args.check_only:
            print("Preparation command:", " ".join(repr(x) for x in command))
        else:
            print("Preparing source in local, gitignored lecture folders:", flush=True)
            result = subprocess.run(command, cwd=root, check=False)
            if result.returncode:
                print("Preparation did not succeed; tutor not launched.", file=sys.stderr)
                return result.returncode
    if executable:
        print(f"Ready to start {args.harness} in {root}.")
        print("Use the normal ChatGPT/Codex subscription login in your harness.")
        print("Ask: Read AGENTS.md, check the newest lecture brief and readiness report, "
              "then Probe → Plan → Teach from my original notes.")
        if not args.check_only:
            try:
                return subprocess.run([executable], cwd=root, check=False).returncode
            except (OSError, KeyboardInterrupt) as exc:
                print("Launch interrupted:", exc, file=sys.stderr)
                return 1
    else:
        print(f"{args.harness!r} not found on PATH.")
        print("Install that CLI from its official docs and sign in with your ChatGPT/Codex subscription.")
        print(f"Then run it in: {root}")
        if not args.check_only:
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
