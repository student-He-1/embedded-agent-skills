#!/usr/bin/env python3
"""List the examples packaged with this STM32 skill.

Scans examples/*/README.md and prints each example's name, title, and a short
summary. Read-only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def skill_root() -> Path:
    # scripts/list_examples.py -> skill root is one level up.
    return Path(__file__).resolve().parent.parent


def parse_readme(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    title = ""
    for line in lines:
        m = re.match(r"^#\s+(.+?)\s*$", line)
        if m:
            title = m.group(1)
            break

    # Summary: first non-heading, non-empty paragraph after the title.
    summary = ""
    buf: list[str] = []
    started = False
    for line in lines:
        if re.match(r"^#", line):
            if started and buf:
                break
            started = True
            continue
        if not started:
            continue
        if line.strip():
            buf.append(line.strip())
        elif buf:
            break
    summary = " ".join(buf)
    summary = re.sub(r"\s+", " ", summary)
    if len(summary) > 160:
        summary = summary[:157] + "..."

    return {
        "name": path.parent.name,
        "title": title or path.parent.name,
        "summary": summary,
        "path": str(path.parent),
    }


def list_examples() -> list[dict]:
    examples_dir = skill_root() / "examples"
    if not examples_dir.is_dir():
        return []
    out = []
    for readme in sorted(examples_dir.glob("*/README.md")):
        out.append(parse_readme(readme))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="List packaged STM32 examples")
    ap.add_argument("--json", action="store_true", help="Output JSON")
    args = ap.parse_args()

    examples = list_examples()

    if args.json:
        print(json.dumps(examples, indent=2, ensure_ascii=False))
        return

    if not examples:
        print("No examples found under examples/.")
        sys.exit(0)

    print(f"Available examples ({len(examples)}):\n")
    for i, ex in enumerate(examples, 1):
        print(f"{i}. {ex['name']} — {ex['title']}")
        if ex["summary"]:
            print(f"   {ex['summary']}")
        print()


if __name__ == "__main__":
    main()
