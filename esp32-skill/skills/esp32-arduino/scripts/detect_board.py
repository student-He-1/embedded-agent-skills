#!/usr/bin/env python3
"""Detect connected ESP32 boards without modifying the target.

Uses arduino-cli board list and esptool chip_id for read-only detection.
An empty result is explicitly inconclusive, not proof that no board is connected.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Board:
    port: str
    protocol: str = ""
    board_name: str = ""
    fqbn: str = ""
    chip_model: str = ""
    chip_revision: str = ""
    mac: str = ""
    flash_size: str = ""
    psram_size: str = ""
    usb_mode: str = ""
    crystal_freq: str = ""
    features: list[str] = field(default_factory=list)
    confidence: str = "unknown"
    evidence: list[str] = field(default_factory=list)


# Arduino IDE ships arduino-cli under this relative path. The IDE is often
# installed on a non-system drive, so every common drive letter is probed.
ARDUINO_CLI_REL = "resources/app/lib/backend/resources/arduino-cli.exe"


def arduino_cli_roots() -> list[str]:
    """Candidate Arduino IDE install roots (env overrides, then per-drive)."""
    roots = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Arduino IDE"),
        os.path.expandvars(r"%PROGRAMFILES%\Arduino IDE"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Arduino IDE"),
    ]
    for drive in ("C", "D", "E", "F", "G"):
        roots.append(f"{drive}:\\Program Files\\Arduino IDE")
        roots.append(f"{drive}:\\Arduino IDE")
    return roots


# Serial port names: Windows COMx, or POSIX /dev/tty* / /dev/cu.*
SERIAL_PORT_RE = re.compile(
    r"^(COM\d+|/dev/(tty(USB|ACM|S)\d+|cu\.[\w.]+))$", re.IGNORECASE
)


def is_serial_port(port: str) -> bool:
    """True for Windows COMx and POSIX /dev/tty* / /dev/cu.* device names."""
    return bool(SERIAL_PORT_RE.match(port or ""))


def arduino_data_dirs() -> list[Path]:
    """Arduino data directory candidates, most specific first.

    Honors ARDUINO_DIRECTORIES_DATA, which arduino-cli and Arduino IDE 2.x use to
    relocate the data directory away from the OS default (e.g. onto another drive).
    """
    dirs: list[Path] = []
    env = os.environ.get("ARDUINO_DIRECTORIES_DATA", "").strip()
    if env:
        dirs.append(Path(env))
    dirs.append(Path.home() / "AppData" / "Local" / "Arduino15")
    dirs.append(Path.home() / "AppData" / "Roaming" / "Arduino15")
    dirs.append(Path.home() / ".arduino15")
    seen: set[str] = set()
    out: list[Path] = []
    for d in dirs:
        key = str(d).lower()
        if key not in seen and d.exists():
            seen.add(key)
            out.append(d)
    return out


# esptool lives under <data-dir>/packages/esp32/tools/esptool_py/<version>/
ESPTOOL_GLOBS = (
    "packages/esp32/tools/esptool_py/*/esptool.exe",
    "packages/esp32/tools/esptool_py/*/esptool",
)


def find_arduino_cli() -> Optional[str]:
    """Locate arduino-cli: env override, then Arduino IDE installs, then PATH."""
    env = os.environ.get("ARDUINO_CLI_PATH", "").strip()
    if env and Path(env).exists():
        return env
    for root in arduino_cli_roots():
        candidate = Path(root) / ARDUINO_CLI_REL
        if candidate.exists():
            return str(candidate)
    return shutil.which("arduino-cli") or shutil.which("arduino-cli.exe")


def find_esptool() -> Optional[str]:
    """Locate esptool from the installed ESP32 core.

    Searches every candidate Arduino data directory (including the one named by
    ARDUINO_DIRECTORIES_DATA), then falls back to PATH.
    """
    for data_dir in arduino_data_dirs():
        for pattern in ESPTOOL_GLOBS:
            matches = [m for m in data_dir.glob(pattern) if m.is_file()]
            if matches:
                # Multiple core versions may be installed; take the last one.
                return str(sorted(matches)[-1])
    return shutil.which("esptool") or shutil.which("esptool.exe")



def run_command(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "command timed out"
    except FileNotFoundError as e:
        return -1, "", str(e)


def detect_with_arduino_cli(cli: str) -> list[Board]:
    boards: list[Board] = []
    # Try JSON output first (more reliable)
    rc, out, err = run_command([cli, "board", "list", "--format", "json"])
    if rc == 0 and out.strip():
        try:
            data = json.loads(out)
            for entry in data:
                port_info = entry.get("port", {}) if isinstance(entry, dict) else {}
                port = port_info.get("address", "") if isinstance(port_info, dict) else ""
                if not port or not is_serial_port(port):
                    continue
                b = Board(port=port)
                b.protocol = port_info.get("protocol", "")
                b.board_name = entry.get("board", "") if isinstance(entry, dict) else ""
                b.fqbn = entry.get("fqbn", "") if isinstance(entry, dict) else ""
                if "ESP32" in b.board_name or "esp32" in b.fqbn:
                    b.confidence = "likely"
                    b.evidence.append(f"arduino-cli: {b.board_name} ({b.fqbn})")
                boards.append(b)
            if boards:
                return boards
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    # Fallback: text parsing
    rc, out, err = run_command([cli, "board", "list"])
    if rc != 0:
        return boards
    for line in out.splitlines():
        if not line.strip() or line.startswith("Port"):
            continue
        m = re.match(r"((?:COM\d+)|(?:/dev/[\w/.]+))", line)
        if m:
            b = Board(port=m.group(1))
            # Try to extract FQBN
            fqbn_match = re.search(r"(esp32:\S+)", line)
            if fqbn_match:
                b.fqbn = fqbn_match.group(1)
            if "ESP32" in line or "esp32" in line:
                b.confidence = "likely"
                b.evidence.append(f"arduino-cli text: {line.strip()[:80]}")
            boards.append(b)
    return boards


def detect_with_esptool(esptool: str, port: str) -> Optional[Board]:
    """Read chip info via esptool for detailed chip info."""
    rc, out, err = run_command(
        [esptool, "--port", port, "chip-id"],
        timeout=25,
    )
    combined = out + err
    if rc != 0 or ("Chip type:" not in combined and "Detecting chip type" not in combined):
        return None

    b = Board(port=port)
    m = re.search(r"Chip type:\s+(.+)", combined)
    if m:
        b.chip_model = m.group(1).strip()
    else:
        m = re.search(r"Detecting chip type\.\.\.\s+(.+)", combined)
        if m:
            b.chip_model = m.group(1).strip()
    m = re.search(r"revision\s+(v\d+\.\d+)", combined, re.IGNORECASE)
    if m:
        b.chip_revision = m.group(1)
    m = re.search(r"MAC:\s+([0-9a-fA-F:]+)", combined)
    if m:
        b.mac = m.group(1)
    m = re.search(r"Crystal (?:is|frequency):\s+(\d+MHz)", combined)
    if m:
        b.crystal_freq = m.group(1)
    m = re.search(r"Features:\s+(.+)", combined)
    if m:
        b.features = [f.strip() for f in m.group(1).split(",") if f.strip()]
    m = re.search(r"Embedded PSRAM\s+(\d+MB)", combined)
    if m:
        b.psram_size = m.group(1)
    if "USB-Serial/JTAG" in combined:
        b.usb_mode = "USB-Serial/JTAG"
    b.confidence = "confirmed"
    b.evidence.append("esptool chip-id succeeded")
    return b


def detect_flash_size(esptool: str, port: str) -> str:
    rc, out, err = run_command(
        [esptool, "--port", port, "flash_id"],
        timeout=20,
    )
    combined = out + err
    m = re.search(r"Detected flash size:\s+(\S+)", combined)
    if m:
        return m.group(1)
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect connected ESP32 boards")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--port", help="Only probe a specific port")
    args = parser.parse_args()

    cli = find_arduino_cli()
    esptool = find_esptool()

    if not cli and not esptool:
        print("ERROR: neither arduino-cli nor esptool found", file=sys.stderr)
        print("Install Arduino IDE or ESP32 core, or add arduino-cli to PATH", file=sys.stderr)
        sys.exit(1)

    boards: list[Board] = []

    if cli:
        boards = detect_with_arduino_cli(cli)

    if args.port:
        boards = [b for b in boards if b.port == args.port]
        if not boards:
            boards = [Board(port=args.port)]

    if esptool:
        for b in boards:
            if not is_serial_port(b.port):
                continue
            detail = detect_with_esptool(esptool, b.port)
            if detail:
                detail.port = b.port
                detail.protocol = b.protocol or detail.protocol
                detail.board_name = b.board_name or detail.board_name
                detail.fqbn = b.fqbn or detail.fqbn
                detail.evidence = b.evidence + detail.evidence
                boards[boards.index(b)] = detail
                flash = detect_flash_size(esptool, b.port)
                if flash:
                    detail.flash_size = flash

    if args.json:
        print(json.dumps([asdict(b) for b in boards], indent=2, ensure_ascii=False))
        return

    if not boards:
        print("No boards detected.")
        print("This is inconclusive — check USB cable (data, not power-only),")
        print("drivers (CP210x / CH340), and that the board is powered.")
        return

    for i, b in enumerate(boards, 1):
        print(f"--- Board {i} ---")
        print(f"  Port:         {b.port}")
        print(f"  Chip:         {b.chip_model or b.board_name or 'unknown'}")
        if b.chip_revision:
            print(f"  Revision:     {b.chip_revision}")
        if b.mac:
            print(f"  MAC:          {b.mac}")
        if b.flash_size:
            print(f"  Flash:        {b.flash_size}")
        if b.psram_size:
            print(f"  PSRAM:        {b.psram_size}")
        if b.usb_mode:
            print(f"  USB mode:     {b.usb_mode}")
        if b.features:
            print(f"  Features:     {', '.join(b.features)}")
        print(f"  FQBN hint:    {b.fqbn or 'auto-detect needed'}")
        print(f"  Confidence:   {b.confidence}")
        if b.evidence:
            print(f"  Evidence:     {'; '.join(b.evidence)}")
        print()


if __name__ == "__main__":
    main()
