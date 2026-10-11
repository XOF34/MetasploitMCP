#!/usr/bin/env python3
"""Build a copy/paste-ready summarization prompt from terminal input."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def build_prompt(acronym: str, source_text: str) -> str:
    """Return one prompt that asks an AI to explain and summarize the input."""
    acronym = acronym.strip()
    source_text = source_text.strip()
    if not acronym:
        raise ValueError("Acronym cannot be empty.")
    if not source_text:
        raise ValueError("Source text cannot be empty.")

    return f"""You are a precise technical editor.

Analyze the material below using the acronym "{acronym}" as its label or topic.
Return:
1. A one-sentence summary.
2. The 3-7 most important key points.
3. The main objectives, written as action statements.
4. Decisions, risks, dependencies, and open questions.
5. A short recommended next-step list.

Do not invent facts. If the acronym is ambiguous, state the likely meaning and
what information is missing. Keep the answer concise and use clear headings.

ACRONYM/TOPIC: {acronym}

SOURCE MATERIAL:
--- BEGIN SOURCE ---
{source_text}
--- END SOURCE ---
"""


def read_source(path: str | None) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()

    print("Paste the source material. Press Enter on an empty line when finished.",
          file=sys.stderr)
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line:
            break
        lines.append(line)
    return "\n".join(lines)


def copy_to_clipboard(text: str) -> str:
    commands = (
        ("pbcopy",),
        ("wl-copy",),
        ("xclip", "-selection", "clipboard"),
        ("xsel", "--clipboard", "--input"),
    )
    for command in commands:
        if shutil.which(command[0]):
            subprocess.run(command, input=text, text=True, check=True)
            return command[0]
    raise RuntimeError("No clipboard command found (tried pbcopy, wl-copy, xclip, xsel).")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create one copy/paste-ready AI summarization prompt."
    )
    parser.add_argument("-a", "--acronym", help="Acronym or short topic label.")
    parser.add_argument("-f", "--file", help="Read source material from a UTF-8 file.")
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy the generated code block to the system clipboard.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.acronym:
            acronym = args.acronym
        elif sys.stdin.isatty():
            acronym = input("Acronym/topic: ")
        else:
            raise ValueError("--acronym is required when source material is piped.")
        prompt = build_prompt(acronym, read_source(args.file))
        output = f"```text\n{prompt}```"
        print(output)
        if args.copy:
            print(f"Copied with {copy_to_clipboard(output)}.", file=sys.stderr)
    except (EOFError, OSError, RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
