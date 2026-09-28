#!/usr/bin/env python3
"""Monitor an STM32 serial port for a fixed duration (read-only on files).

Used to verify firmware behavior after build/flash: capture UART output,
optionally send a command (echo tests), and report what was received.

Examples:
  python serial_monitor.py --port COM16 --baud 115200 --duration 8
  python serial_monitor.py --port COM16 --send "hello" --send-newline
  python serial_monitor.py --port COM16 --hex-in "52 0D" --hex-out
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run: python -m pip install pyserial",
          file=sys.stderr)
    sys.exit(1)


@dataclass
class MonitorResult:
    port: str
    baud: int
    duration: float
    bytes_received: int = 0
    lines: list[str] = field(default_factory=list)
    raw_hex: str = ""
    text: str = ""
    sent: str = ""
    success: bool = False
    error: str = ""


def decode_bytes(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


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
                "(Keil debug session, another serial_monitor, PuTTY, VOFA+, "
                "Thonny, a serial assistant), then retry.")
    if any(m in low or m in msg for m in missing_markers):
        return ("missing",
                f"{port} not found. Check the name in Device Manager; on this "
                "board the J-Link CDC is COM16.")
    return ("unknown", f"Cannot open {port}: {msg}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Monitor STM32 serial output")
    ap.add_argument("--port", required=True, help="COM port, e.g. COM16")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--duration", type=float, default=10.0)
    ap.add_argument("--send", default="", help="String to send after opening")
    ap.add_argument("--send-newline", action="store_true",
                    help="Append CRLF to the sent string")
    ap.add_argument("--hex-in", action="store_true",
                    help="Interpret --send as hex bytes, e.g. '52 0D'")
    ap.add_argument("--hex-out", action="store_true", help="Show received bytes as hex")
    ap.add_argument("--timestamp", action="store_true", help="Prefix lines with t=...")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    res = MonitorResult(port=args.port, baud=args.baud, duration=args.duration)

    # Prepare payload to send
    send_bytes = b""
    if args.send:
        if args.hex_in:
            try:
                send_bytes = bytes.fromhex(args.send.replace(",", " "))
            except ValueError:
                res.error = "invalid hex in --send"
                print("ERROR:", res.error, file=sys.stderr)
                sys.exit(2)
        else:
            send_bytes = args.send.encode("utf-8")
            if args.send_newline:
                send_bytes += b"\r\n"
        res.sent = send_bytes.hex(" ")

    try:
        ser = serial.Serial(
            port=args.port,
            baudrate=args.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
        )
    except (serial.SerialException, OSError) as e:
        kind, advice = diagnose_open_error(args.port, e)
        res.error = f"{kind}: {e}"
        if args.json:
            print(json.dumps(asdict(res), indent=2))
        else:
            print(f"ERROR opening {args.port}: {e}", file=sys.stderr)
            print(advice, file=sys.stderr)
        sys.exit(1)

    received = bytearray()
    start = time.monotonic()
    pending_line = ""

    try:
        # Send first (after a brief settle)
        time.sleep(0.1)
        if send_bytes:
            ser.write(send_bytes)
            ser.flush()

        while time.monotonic() - start < args.duration:
            chunk = ser.read(256)
            if not chunk:
                continue
            received.extend(chunk)

            if not args.json:
                if args.hex_out:
                    stamp = f"[t={time.monotonic()-start:6.2f}] " if args.timestamp else ""
                    print(f"{stamp}{chunk.hex(' ')}")
                else:
                    text = decode_bytes(chunk)
                    pending_line += text
                    while "\n" in pending_line:
                        line, pending_line = pending_line.split("\n", 1)
                        stamp = f"[t={time.monotonic()-start:6.2f}] " if args.timestamp else ""
                        print(f"{stamp}{line.rstrip(chr(13))}")

        res.success = True
    except KeyboardInterrupt:
        res.success = True
    except serial.SerialException as e:
        res.error = str(e)
    finally:
        # Flush any partial line
        if not args.json and not args.hex_out and pending_line.strip():
            print(pending_line.rstrip("\r"))
        ser.close()

    res.bytes_received = len(received)
    res.raw_hex = received.hex(" ")
    res.text = decode_bytes(bytes(received))
    res.lines = [ln for ln in res.text.replace("\r", "").split("\n") if ln != ""]

    if args.json:
        print(json.dumps(asdict(res), indent=2, ensure_ascii=False))
        sys.exit(0 if res.success else 1)

    print()
    print("=== Serial summary ===")
    print(f"  Port:     {res.port} @ {res.baud}")
    print(f"  Duration: {res.duration}s")
    if res.sent:
        print(f"  Sent:     {res.sent}")
    print(f"  Received: {res.bytes_received} byte(s)")
    if res.error:
        print(f"  Error:    {res.error}")
    if res.bytes_received == 0 and not res.error:
        print("  (no data: trigger a reset, check baud/pins, or send a command)")
    sys.exit(0 if res.success else 1)


if __name__ == "__main__":
    main()
