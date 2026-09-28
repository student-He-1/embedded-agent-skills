#!/usr/bin/env python3
"""Flash wrapper for ESP32 Arduino projects using arduino-cli."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

# Reuse board detection from detect_board
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from detect_board import find_arduino_cli, detect_with_arduino_cli  # noqa: E402
from arduino_build import resolve_fqbn  # noqa: E402


def verify_port(port: str, cli: str) -> bool:
    """Check if the port exists in arduino-cli board list."""
    boards = detect_with_arduino_cli(cli)
    return any(b.port == port for b in boards)


MAX_ATTEMPTS = 3


def classify_upload_failure(output: str) -> str:
    low = output.lower()
    busy_markers = ("busy", "permission", "access is denied", "拒绝访问")
    boot_markers = (
        "wrong boot mode", "invalid head of packet", "failed to connect",
        "timed out waiting for packet", "no serial data", "chip does not exist",
        "couldn't enter download mode",
    )
    missing_markers = ("could not open", "no such port", "系统找不到")
    if any(m in low or m in output for m in busy_markers):
        return "busy"
    if any(m in low for m in boot_markers):
        return "boot"
    if any(m in low or m in output for m in missing_markers):
        return "missing"
    return "fatal"


HINTS = {
    "busy": "Port busy: close serial monitor / Thonny / PuTTY, then retry.",
    "boot": "Boot mode: hold BOOT, press RST, release BOOT, then retry.",
    "missing": "Port not found: check the USB data cable and board power.",
    "fatal": "See the upload output above.",
}


def upload_project(
    cli: str,
    project_dir: Path,
    port: str,
    fqbn: str,
    max_attempts: int = MAX_ATTEMPTS,
) -> int:
    cmd = [cli, "upload", "-p", port, "--fqbn", fqbn, str(project_dir)]
    print(f"Running: {' '.join(cmd)}")
    print("-" * 60)

    last_rc = 1
    for attempt in range(1, max_attempts + 1):
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        output = result.stdout + result.stderr
        last_rc = result.returncode

        if result.returncode == 0:
            print(output)
            # Post-flash check: wait for re-enumeration (S3 USB-Serial/JTAG can
            # change the port), then re-detect the board.
            time.sleep(2)
            boards = detect_with_arduino_cli(cli)
            ports = sorted({b.port for b in boards if b.port})
            if ports:
                print(f"POST-FLASH: board re-enumerated on port(s): {', '.join(ports)}")
                print("=== UPLOAD SUCCESS (board re-detected) ===")
                return 0
            print("=== UPLOAD COMMAND OK, but board not re-detected ===")
            print("Check the USB cable or press RESET.")
            return 0

        kind = classify_upload_failure(output)
        if attempt < max_attempts and kind in ("busy", "boot"):
            print(f"Upload failed (attempt {attempt}/{max_attempts}: {kind}); "
                  f"retrying in 2 s...")
            if kind == "boot":
                print("  (if it keeps failing: " + HINTS["boot"] + ")")
            time.sleep(2)
            continue

        print(output)
        print("\n=== UPLOAD FAILED ===")
        print("HINT:", HINTS.get(kind, HINTS["fatal"]))
        return last_rc if last_rc else 1

    return last_rc


def main() -> None:
    parser = argparse.ArgumentParser(description="Flash ESP32 Arduino project")
    parser.add_argument("project_dir", help="Path to the Arduino project directory")
    parser.add_argument("--port", required=True, help="Serial port (e.g. COM6)")
    parser.add_argument("--fqbn", default="esp32:esp32:esp32s3",
                        help="Full FQBN or short name")
    parser.add_argument("--board", help="Short board name")
    parser.add_argument("--skip-verify", action="store_true",
                        help="Skip port existence check")
    args = parser.parse_args()

    cli = find_arduino_cli()
    if not cli:
        print("ERROR: arduino-cli not found", file=sys.stderr)
        sys.exit(1)

    fqbn = resolve_fqbn(args.board) if args.board else args.fqbn
    project_dir = Path(args.project_dir).resolve()

    if not args.skip_verify:
        if not verify_port(args.port, cli):
            print(f"WARNING: Port {args.port} not detected in board list.")
            print("The board may be disconnected or the port may have changed.")
            print("Use --skip-verify to force upload anyway.")
            # Don't exit — user may want to force it
            time.sleep(2)

    rc = upload_project(cli, project_dir, args.port, fqbn)
    sys.exit(rc)


if __name__ == "__main__":
    main()
