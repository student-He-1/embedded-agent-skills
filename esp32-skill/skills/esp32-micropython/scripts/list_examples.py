#!/usr/bin/env python3
"""List packaged ESP32 examples from examples/*/manifest.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = SCRIPT_DIR.parent / "examples"


def list_examples() -> list[dict]:
    """Read all manifest.json files under examples/."""
    examples = []
    if not EXAMPLES_DIR.exists():
        return examples

    for example_dir in sorted(EXAMPLES_DIR.iterdir()):
        if not example_dir.is_dir():
            continue
        manifest_path = example_dir / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                manifest["_path"] = str(example_dir)
                examples.append(manifest)
            except (json.JSONDecodeError, OSError) as e:
                print(f"Warning: failed to read {manifest_path}: {e}", file=sys.stderr)
    return examples


def print_table(examples: list[dict]):
    """Print examples as a formatted table."""
    if not examples:
        print("No examples found.")
        return

    print(f"Found {len(examples)} example(s):\n")
    print(f"{'Name':<25} {'Title':<40} {'Complexity':<12} {'Validated'}")
    print("-" * 90)
    for ex in examples:
        name = ex.get("name", "?")
        title = ex.get("title", "?")[:38]
        complexity = ex.get("complexity", "?")
        validated = "Yes" if ex.get("validated") else "No"
        print(f"{name:<25} {title:<40} {complexity:<12} {validated}")


def print_detail(examples: list[dict]):
    """Print detailed info for each example."""
    for ex in examples:
        print(f"\n{'='*70}")
        print(f"Name:        {ex.get('name', '?')}")
        print(f"Title:       {ex.get('title', '?')}")
        print(f"Description: {ex.get('description', '?')}")
        print(f"Path:        {ex.get('_path', '?')}")
        print(f"Target:      {ex.get('target_chip', 'any')}")
        print(f"Complexity:  {ex.get('complexity', '?')}")
        print(f"Validated:   {'Yes' if ex.get('validated') else 'No'} ({ex.get('validation_level', 'unknown')})")
        peripherals = ex.get("peripherals", [])
        if peripherals:
            print(f"Peripherals: {', '.join(peripherals)}")
        pins = ex.get("pins", [])
        if pins:
            print(f"Pins:        {', '.join(pins)}")
        sources = ex.get("source_files", [])
        if sources:
            print(f"Sources:     {', '.join(sources)}")
        tags = ex.get("tags", [])
        if tags:
            print(f"Tags:        {', '.join(tags)}")


def main():
    parser = argparse.ArgumentParser(description="List packaged ESP32 examples")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--detail", action="store_true", help="Show detailed info")
    parser.add_argument("--name", help="Filter by example name")
    args = parser.parse_args()

    examples = list_examples()

    if args.name:
        examples = [e for e in examples if args.name.lower() in e.get("name", "").lower()]

    if args.json:
        # Remove internal _path from JSON output
        for ex in examples:
            ex.pop("_path", None)
        print(json.dumps(examples, indent=2, ensure_ascii=False))
    elif args.detail:
        print_detail(examples)
    else:
        print_table(examples)

    sys.exit(0 if examples else 1)


if __name__ == "__main__":
    main()
