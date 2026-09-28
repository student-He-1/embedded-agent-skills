#!/usr/bin/env python3
"""Detect connected ESP32 boards running MicroPython.

Uses mpremote to connect, read firmware version, and list the flash filesystem.
Also detects USB-UART bridges (CP2102, CH340, FTDI) via Windows PnP.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Known USB VID:PID for common ESP32 USB-UART bridges
KNOWN_USB_IDS = {
    "10C4:EA60": ("cp2102", "Silicon Labs CP2102 USB-UART"),
    "10C4:EA70": ("cp210x", "Silicon Labs CP210x USB-UART"),
    "1A86:7523": ("ch340", "WCH CH340 USB-UART"),
    "1A86:5523": ("ch341", "WCH CH341 USB-UART"),
    "0403:6001": ("ftdi", "FTDI FT232 USB-UART"),
    "303A:0009": ("esp-usb-jtag", "Espressif USB-Serial-JTAG"),
    "303A:1001": ("esp-usb-jtag", "Espressif USB-JTAG"),
}


@dataclass
class Board:
    port: str
    kind: str = "unknown"
    display_name: str = ""
    usb_id: str = ""
    micropython_version: str = ""
    python_version: str = ""
    platform: str = ""
    cpu_freq: int = 0
    flash_free: int = 0
    flash_total: int = 0
    files: list[dict] = field(default_factory=list)
    connected: bool = False
    error: str = ""

    def to_dict(self):
        return asdict(self)


def run_mpremote(port: str, *args: str, timeout: int = 15) -> tuple[int, str, str]:
    """Run mpremote with given arguments."""
    cmd = [sys.executable, "-m", "mpremote", "connect", port, *args]
    try:
        completed = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout
        )
        return completed.returncode, completed.stdout, completed.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "mpremote timed out"
    except FileNotFoundError:
        return -1, "", "mpremote not found"


def detect_serial_ports_windows() -> list[dict]:
    """Detect serial ports on Windows via PowerShell."""
    devices = []
    try:
        ps = r'''
$ports = Get-PnpDevice -PresentOnly -Class Ports -ErrorAction SilentlyContinue
foreach ($port in $ports) {
    $friendly = $port.FriendlyName
    $instance = $port.InstanceId
    $hwids = ($port.HardwareId -join ';')
    $com = ''
    if ($friendly -match '\((COM\d+)\)') { $com = $matches[1] }
    if ($com) { Write-Output "$com|$friendly|$instance|$hwids" }
}
'''
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=20
        )
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) >= 3:
                com = parts[0].strip()
                friendly = parts[1].strip()
                instance = parts[2].strip()
                hwids = parts[3].strip().split(";") if len(parts) > 3 else []
                usb_id = ""
                for v in [instance, *hwids]:
                    m = re.search(r"VID_([0-9A-F]{4}).*PID_([0-9A-F]{4})", v, re.IGNORECASE)
                    if m:
                        usb_id = f"{m.group(1).upper()}:{m.group(2).upper()}"
                        break
                devices.append({"port": com, "friendly": friendly, "usb_id": usb_id})
    except Exception:
        pass
    return devices


def detect_serial_ports_linux() -> list[dict]:
    import glob
    devices = []
    for tty in glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"):
        devices.append({"port": tty, "friendly": tty, "usb_id": ""})
    return devices


def detect_serial_ports() -> list[dict]:
    if platform.system() == "Windows":
        return detect_serial_ports_windows()
    elif platform.system() == "Linux":
        return detect_serial_ports_linux()
    return []


def identify_board(port: str) -> Board:
    """Connect to a port and identify MicroPython firmware."""
    board = Board(port=port)

    # Get firmware info
    code = (
        "import sys, machine, uos\n"
        "print('MP_VERSION:', sys.implementation)\n"
        "print('PY_VERSION:', sys.version)\n"
        "print('PLATFORM:', sys.platform)\n"
        "print('CPU_FREQ:', machine.freq())\n"
        "fs = uos.statvfs('/')\n"
        "print('FLASH_FREE:', fs[0] * fs[3])\n"
        "print('FLASH_TOTAL:', fs[0] * fs[2])\n"
    )
    rc, out, err = run_mpremote(port, "exec", code, timeout=10)
    if rc != 0:
        board.error = err.strip() or "Failed to connect"
        return board

    board.connected = True
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("MP_VERSION:"):
            board.micropython_version = line.split(":", 1)[1].strip()
        elif line.startswith("PY_VERSION:"):
            board.python_version = line.split(":", 1)[1].strip()
        elif line.startswith("PLATFORM:"):
            board.platform = line.split(":", 1)[1].strip()
        elif line.startswith("CPU_FREQ:"):
            try:
                board.cpu_freq = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.startswith("FLASH_FREE:"):
            try:
                board.flash_free = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.startswith("FLASH_TOTAL:"):
            try:
                board.flash_total = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass

    # List files
    rc, out, err = run_mpremote(port, "fs", "ls", timeout=10)
    if rc == 0:
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("ls"):
                continue
            # Format: "    139 boot.py"
            m = re.match(r"\s*(\d+)\s+(.+)", line)
            if m:
                board.files.append({"name": m.group(2), "size": int(m.group(1))})

    return board


def detect_boards(identify: bool = True) -> list[Board]:
    """Detect all connected ESP32 boards."""
    raw = detect_serial_ports()
    boards = []

    for d in raw:
        port = d["port"]
        usb_id = d.get("usb_id", "")
        friendly = d.get("friendly", "")

        kind = "unknown"
        display_name = friendly or port
        if usb_id in KNOWN_USB_IDS:
            kind, display_name = KNOWN_USB_IDS[usb_id]
        elif any(kw in friendly.lower() for kw in ["cp210", "ch340", "ch341", "ftdi", "espressif", "usb-serial"]):
            kind = "usb-uart"

        board = Board(port=port, kind=kind, display_name=display_name, usb_id=usb_id)

        if identify and kind in ("cp2102", "cp210x", "ch340", "ch341", "ftdi", "esp-usb-jtag", "usb-uart", "unknown"):
            identified = identify_board(port)
            if identified.connected:
                board = identified
                board.kind = kind
                board.display_name = display_name
                board.usb_id = usb_id
            else:
                board.error = identified.error

        boards.append(board)

    return boards


def print_boards(boards: list[Board]):
    if not boards:
        print("No serial devices detected.")
        print("Note: An empty result is inconclusive. Check USB cable (data, not charge-only), drivers, and connections.")
        return

    print(f"Found {len(boards)} candidate board(s):\n")
    for i, b in enumerate(boards, 1):
        print(f"[{i}] {b.display_name}")
        print(f"    Port: {b.port}")
        if b.usb_id:
            print(f"    USB ID: {b.usb_id}")
        if b.connected:
            print(f"    MicroPython: {b.micropython_version}")
            print(f"    Python: {b.python_version}")
            print(f"    Platform: {b.platform}")
            print(f"    CPU: {b.cpu_freq // 1000000} MHz")
            print(f"    Flash: {b.flash_free // 1024} KB free / {b.flash_total // 1024} KB total")
            if b.files:
                print(f"    Files ({len(b.files)}):")
                for f in b.files:
                    print(f"      {f['size']:>8}  {f['name']}")
        else:
            print(f"    Status: Not connected (MicroPython may not be running)")
            if b.error:
                print(f"    Error: {b.error[:100]}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Detect connected ESP32 MicroPython boards")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--no-identify", action="store_true", help="Skip mpremote connection (faster, USB-only)")
    parser.add_argument("--port", help="Check a specific port only")
    args = parser.parse_args()

    if args.port:
        board = identify_board(args.port)
        if args.json:
            print(json.dumps(board.to_dict(), indent=2, ensure_ascii=False))
        else:
            print_boards([board])
        sys.exit(0 if board.connected else 1)

    boards = detect_boards(identify=not args.no_identify)

    if args.json:
        print(json.dumps([b.to_dict() for b in boards], indent=2, ensure_ascii=False))
    else:
        print_boards(boards)

    connected = [b for b in boards if b.connected]
    sys.exit(0 if connected else 1)


if __name__ == "__main__":
    main()
