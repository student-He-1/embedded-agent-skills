#!/usr/bin/env python3
"""Serial port monitor for ESP32 development.

Lists serial ports, opens a monitor with timestamps and ANSI color filtering,
and supports sending text/hex data. Requires pyserial: pip install pyserial
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Error: pyserial is not installed. Run: python -m pip install pyserial", file=sys.stderr)
    sys.exit(1)


# ANSI escape code pattern
ANSI_PATTERN = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def list_ports():
    """List all available serial ports with details."""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No serial ports found.")
        print("Check USB connections and drivers (CP210x, CH340, FTDI).")
        return

    print(f"Found {len(ports)} serial port(s):\n")
    print(f"{'Port':<12} {'Description':<45} {'VID:PID':<12} {'Manufacturer'}")
    print("-" * 90)
    for p in ports:
        vid_pid = f"{p.vid:04X}:{p.pid:04X}" if p.vid and p.pid else "N/A"
        manufacturer = p.manufacturer or "N/A"
        desc = p.description[:43]
        print(f"{p.device:<12} {desc:<45} {vid_pid:<12} {manufacturer}")

    # Highlight likely ESP32 devices
    esp_keywords = ["CP210", "CH340", "CH341", "FTDI", "Espressif", "USB-Serial", "USB JTAG"]
    esp_ports = [p for p in ports if any(kw.lower() in (p.description + p.manufacturer).lower() for kw in esp_keywords)]
    if esp_ports:
        print(f"\nLikely ESP32 devices: {', '.join(p.device for p in esp_ports)}")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return ANSI_PATTERN.sub('', text)


def open_monitor(port: str, baud: int, timestamp: bool = False, no_ansi: bool = False,
                 duration: int = 0, send_text: str = "", send_hex: str = "",
                 send_line: bool = False):
    """Open a serial monitor and print received data."""
    try:
        ser = serial.Serial(port, baud, timeout=1)
    except serial.SerialException as e:
        print(f"Error: Could not open {port}: {e}", file=sys.stderr)
        print("Check that the port exists and is not in use by another program.", file=sys.stderr)
        sys.exit(1)

    print(f"Connected to {port} at {baud} baud.")
    if timestamp:
        print("Timestamps enabled.")
    print("Press Ctrl+C to exit.\n")

    # Send data if requested
    if send_text:
        data = send_text.encode("utf-8")
        if send_line:
            data += b"\n"
        ser.write(data)
        print(f"[TX] {send_text}")
    elif send_hex:
        try:
            hex_bytes = bytes.fromhex(send_hex.replace(" ", ""))
            ser.write(hex_bytes)
            print(f"[TX HEX] {send_hex}")
        except ValueError:
            print(f"Error: Invalid hex data: {send_hex}", file=sys.stderr)
            ser.close()
            sys.exit(1)

    start_time = time.time()
    buffer = ""

    try:
        while True:
            if duration > 0 and (time.time() - start_time) > duration:
                print(f"\n[Duration {duration}s reached, exiting.]")
                break

            if ser.in_waiting > 0:
                raw = ser.read(ser.in_waiting)
                text = raw.decode("utf-8", errors="replace")
                buffer += text

                # Print complete lines
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.rstrip("\r")
                    if no_ansi:
                        line = strip_ansi(line)
                    if timestamp:
                        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        print(f"[{ts}] {line}")
                    else:
                        print(line)
            else:
                time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n[Interrupted by user]")
    finally:
        ser.close()
        print("Serial port closed.")


def main():
    parser = argparse.ArgumentParser(description="Serial port monitor for ESP32")
    parser.add_argument("--list", action="store_true", help="List available serial ports and exit")
    parser.add_argument("-p", "--port", help="Serial port (e.g. COM6, /dev/ttyUSB0)")
    parser.add_argument("-b", "--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--timestamp", action="store_true", help="Add timestamps to output")
    parser.add_argument("--no-ansi", action="store_true", help="Strip ANSI color codes")
    parser.add_argument("--duration", type=int, default=0, help="Exit after N seconds (0 = forever)")
    parser.add_argument("--send", help="Text string to send after connecting")
    parser.add_argument("--send-line", action="store_true", help="Append newline to --send data")
    parser.add_argument("--send-hex", help="Hex bytes to send (e.g. '00 00 80 3F')")
    args = parser.parse_args()

    if args.list:
        list_ports()
        return

    if not args.port:
        print("Error: --port is required (or use --list to see available ports).", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    open_monitor(
        port=args.port,
        baud=args.baud,
        timestamp=args.timestamp,
        no_ansi=args.no_ansi,
        duration=args.duration,
        send_text=args.send or "",
        send_hex=args.send_hex or "",
        send_line=args.send_line,
    )


if __name__ == "__main__":
    main()
