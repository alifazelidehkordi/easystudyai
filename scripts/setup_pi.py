#!/usr/bin/env python3
"""Optionally copy the original project's Pi quiz/log extensions for personal use.

No original source is shipped with EasyStudyAI. Shared teach skills already
live in .agents/skills/ and work in both Pi and Codex CLI.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

UPSTREAM = "https://github.com/amosblomqvist/learn.git"
EXTENSIONS = ("quiz.ts", "ask-user-question.ts", "md-log.ts")


def install(root: Path, upstream: Path, replace: bool):
    source = upstream / "extensions"
    if not all((source / name).is_file() for name in EXTENSIONS):
        raise RuntimeError("Upstream source does not contain the three expected extensions")
    dest = root / ".pi" / "extensions"
    dest.mkdir(parents=True, exist_ok=True)
    for name in EXTENSIONS:
        path = dest / name
        if path.exists():
            if not replace:
                print("Already present (skipping):", path)
                continue
            backup = path.with_name(path.stem + ".backup-" + datetime.now().strftime("%Y%m%d-%H%M%S") + path.suffix)
            shutil.copy2(path, backup)
            print("Backed up:", backup)
        shutil.copy2(source / name, path)
        print("Installed:", path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Path to a locally cloned amosblomqvist/learn repository")
    parser.add_argument("--fetch", action="store_true", help="Clone upstream from GitHub now (requires git/network)")
    parser.add_argument("--replace", action="store_true", help="Back up and replace existing extension files")
    args = parser.parse_args()
    if bool(args.source) == bool(args.fetch):
        parser.error("Choose exactly one of --source PATH or --fetch")
    root = Path(__file__).resolve().parent.parent
    try:
        if args.source:
            install(root, args.source.expanduser().resolve(), args.replace)
        else:
            with tempfile.TemporaryDirectory(prefix="easystudy-upstream-") as folder:
                destination = Path(folder) / "original"
                subprocess.run(["git", "clone", "--depth", "1", UPSTREAM, str(destination)],
                               check=True, timeout=90)
                install(root, destination, args.replace)
    except (OSError, RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    print("\nPi will find these extensions in .pi/extensions and the shared medical skills in .agents/skills.")
    print("In Pi, use /login > OpenAI Codex. No API keys or extra model providers are installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
