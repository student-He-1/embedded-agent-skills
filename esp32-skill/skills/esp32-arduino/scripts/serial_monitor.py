#!/usr/bin/env python3
"""Serial monitor for ESP32 boards — read output for a fixed duration."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime


def list_ports() -> list[str]:
    """List available serial ports."""
    try:
        import serial.tools.list_ports
        return [p.device for p in serial.tools.list_ports.comports()]
    except ImportError:
        print("ERROR: pyserial not installed. Run: python -m pip install pyserial", file=sys.stderr)
        return []


def diagnose_open_error(port: str, err: Exception) -> tuple[str, str]:
    """Classify a serial open failure into (kind, actionable advice)."""
    msg = str(err)
    low = msg.lower()
    busy_markers = (
        "permissionerror(13", "access is denied", "拒绝访问",
        "resource busy", "device or resource busy",
    )
    missing_markers = (
        "filenotfounderror", "no such file", "could not open port",
        "系统找不到", "找不到指定的文件",
    )
    if any(m in low or m in msg for m in busy_markers):
        return ("busy",
                f"{port} is busy / access denied. Close the program holding it "
                "(Arduino IDE monitor, another monitor, Thonny, PuTTY), then retry.")
    if any(m in low or m in msg for m in missing_markers):
        return ("missing",
                f"{port} not found. Check the name with --list, the USB data "
                "cable, and board power.")
    return ("unknown", f"Cannot open {port}: {msg}")


def monitor(port: str, baud: int, duration: float, show_timestamp: bool = False, do_reset: bool = False) -> None:
    """Read serial output for a fixed duration."""
    try:
        import serial
    except ImportError:
        print("ERROR: pyserial not installed. Run: python -m pip install pyserial", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to {port} @ {baud} baud...")
    try:
        ser = serial.Serial(port, baud, timeout=1)
    except Exception as e:
        kind, advice = diagnose_open_error(port, e)
        print(f"ERROR: Could not open {port}: {e}", file=sys.stderr)
        print(advice, file=sys.stderr)
        sys.exit(1)

    if do_reset:
        # Reset the board via DTR/RTS toggle (classic ESP32 with USB-UART bridge)
        # Note: may not work on ESP32-S3 native USB-Serial/JTAG
        ser.setDTR(False)
        time.sleep(0.1)
        ser.setRTS(True)
        time.sleep(0.1)
        ser.setRTS(False)
        time.sleep(0.5)
    else:
        # Flush existing buffer without resetting
        time.sleep(0.3)
        ser.reset_input_buffer()

    print(f"Monitoring for {duration} seconds (Ctrl+C to stop)...")
    print("-" * 60)

    start = time.time()
    line_count = 0
    try:
        while time.time() - start < duration:
            if ser.in_waiting:
                line = ser.readline().decode("utf-8", errors="replace").rstrip()
                if line:
                    if show_timestamp:
                        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        print(f"[{ts}] {line}")
                    else:
                        print(line)
                    line_count += 1
            else:
                time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        ser.close()

    print("-" * 60)
    print(f"Read {line_count} line(s) in {duration:.0f}s.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serial monitor for ESP32")
    parser.add_argument("--port", help="Serial port (e.g. COM6); not needed with --list")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default 115200)")
    parser.add_argument("--duration", type=float, default=10, help="Duration in seconds (default 10)")
    parser.add_argument("--timestamp", action="store_true", help="Show timestamps")
    parser.add_argument("--reset", action="store_true", help="Reset board via DTR/RTS before monitoring (classic ESP32 only)")
    parser.add_argument("--list", action="store_true", help="List available ports and exit")
    args = parser.parse_args()

    if args.list:
        ports = list_ports()
        if ports:
            print("Available ports:")
            for p in ports:
                print(f"  {p}")
        else:
            print("No serial ports found.")
        return

    if not args.port:
        parser.error("--port is required unless --list is used")

    monitor(args.port, args.baud, args.duration, args.timestamp, args.reset)


if __name__ == "__main__":
    main()
