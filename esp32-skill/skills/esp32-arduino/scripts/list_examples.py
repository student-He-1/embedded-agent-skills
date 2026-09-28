#!/usr/bin/env python3
"""List packaged examples for the ESP32 Arduino skill."""

from __future__ import annotations

import json
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = SKILL_DIR / "examples"


def list_examples() -> list[dict]:
    examples = []
    if not EXAMPLES_DIR.exists():
        return examples

    for example_dir in sorted(EXAMPLES_DIR.iterdir()):
        if not example_dir.is_dir():
            continue

        info = {
            "name": example_dir.name,
            "path": str(example_dir),
            "ino_files": [],
            "description": "",
        }

        # Find .ino files
        for ino in sorted(example_dir.glob("*.ino")):
            info["ino_files"].append(ino.name)

        # Read README for description
        readme = example_dir / "README.md"
        if readme.exists():
            content = readme.read_text(encoding="utf-8", errors="replace")
            # First non-empty line after title
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    info["description"] = line[:120]
                    break

        examples.append(info)

    return examples


def main() -> None:
    examples = list_examples()

    if not examples:
        print("No examples found.")
        return

    print(f"Available examples ({len(examples)}):")
    print("-" * 60)
    for ex in examples:
        print(f"\n  {ex['name']}/")
        if ex["ino_files"]:
            print(f"    Sketch: {', '.join(ex['ino_files'])}")
        if ex["description"]:
            print(f"    {ex['description']}")

    print("\n" + "-" * 60)
    print(f"Examples directory: {EXAMPLES_DIR}")


if __name__ == "__main__":
    main()
