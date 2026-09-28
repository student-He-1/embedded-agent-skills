#!/usr/bin/env python3
"""Compile wrapper for ESP32 Arduino projects using arduino-cli."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


DEFAULT_ARDUINO_CLI_PATHS = [
    r"E:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe",
    r"C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe",
    "arduino-cli",
]


def find_arduino_cli() -> str | None:
    import shutil
    for p in DEFAULT_ARDUINO_CLI_PATHS:
        if "\\" in p or "/" in p:
            if Path(p).exists():
                return p
        else:
            found = shutil.which(p)
            if found:
                return found
    return None


FQBN_MAP = {
    "esp32": "esp32:esp32:esp32",
    "esp32s3": "esp32:esp32:esp32s3",
    "esp32s2": "esp32:esp32:esp32s2",
    "esp32c3": "esp32:esp32:esp32c3",
    "esp32c6": "esp32:esp32:esp32c6",
    "esp32h2": "esp32:esp32:esp32h2",
}


def resolve_fqbn(board: str) -> str:
    """Resolve a short board name to full FQBN."""
    board_lower = board.lower().replace("-", "").replace("_", "")
    # Sort keys by length descending so "esp32s3" matches before "esp32"
    for key in sorted(FQBN_MAP.keys(), key=len, reverse=True):
        if key in board_lower:
            return FQBN_MAP[key]
    # If already a full FQBN, return as-is
    if ":" in board:
        return board
    return f"esp32:esp32:{board_lower}"


def compile_project(
    cli: str,
    project_dir: Path,
    fqbn: str,
    extra_args: list[str] | None = None,
) -> tuple[int, str]:
    cmd = [cli, "compile", "--fqbn", fqbn, str(project_dir)]
    if extra_args:
        cmd.extend(extra_args)

    print(f"Running: {' '.join(cmd)}")
    print("-" * 60)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    output = result.stdout + result.stderr

    # Parse sketch size info
    flash_match = re.search(r"Sketch uses\s+(\d+)\s+bytes\s+\((\d+)%\)", output)
    ram_match = re.search(r"Global variables use\s+(\d+)\s+bytes\s+\((\d+)%\)", output)

    if flash_match:
        print(f"\nFlash: {flash_match.group(1)} bytes ({flash_match.group(2)}%)")
    if ram_match:
        print(f"RAM:   {ram_match.group(1)} bytes ({ram_match.group(2)}%)")

    # Count warnings
    warnings = re.findall(r"warning:", output, re.IGNORECASE)
    if warnings:
        print(f"Warnings: {len(warnings)}")

    if result.returncode != 0:
        print("\n=== COMPILE FAILED ===")
        # Print relevant error lines
        for line in output.splitlines():
            if any(kw in line.lower() for kw in ["error", "fatal", "undefined", "not declared"]):
                print(f"  {line.strip()}")
    else:
        print("\n=== COMPILE SUCCESS ===")

    return result.returncode, output


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile ESP32 Arduino project")
    parser.add_argument("project_dir", help="Path to the Arduino project directory")
    parser.add_argument("--fqbn", default="esp32:esp32:esp32s3",
                        help="Full FQBN or short name (esp32, esp32s3, etc.)")
    parser.add_argument("--board", help="Short board name (alternative to --fqbn)")
    parser.add_argument("--build-property", action="append", default=[],
                        help="Extra build properties (can repeat)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    cli = find_arduino_cli()
    if not cli:
        print("ERROR: arduino-cli not found", file=sys.stderr)
        sys.exit(1)

    fqbn = resolve_fqbn(args.board) if args.board else args.fqbn
    project_dir = Path(args.project_dir).resolve()

    if not project_dir.exists():
        print(f"ERROR: project directory not found: {project_dir}", file=sys.stderr)
        sys.exit(1)

    extra = []
    for prop in args.build_property:
        extra.extend(["--build-property", prop])
    if args.verbose:
        extra.append("--verbose")

    rc, _ = compile_project(cli, project_dir, fqbn, extra)
    sys.exit(rc)


if __name__ == "__main__":
    main()
