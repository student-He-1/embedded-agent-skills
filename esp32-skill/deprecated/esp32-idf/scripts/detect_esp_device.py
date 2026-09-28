#!/usr/bin/env python3
"""Detect connected ESP32 devices without opening or modifying the target.

Supports CP2102 (VID_10C4 PID_EA60), CH340 (VID_1A86 PID_7523), FTDI,
and Espressif built-in USB-Serial-JTAG (VID_303A).
Calls esptool.py chip_id to identify chip model, flash size, and MAC.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from typing import Optional

# Known USB VID:PID -> (kind, display_name)
KNOWN_USB_IDS = {
    "10C4:EA60": ("cp2102", "Silicon Labs CP2102 USB-UART"),
    "10C4:EA70": ("cp210x", "Silicon Labs CP210x USB-UART"),
    "1A86:7523": ("ch340", "WCH CH340 USB-UART"),
    "1A86:5523": ("ch341", "WCH CH341 USB-UART"),
    "0403:6001": ("ftdi", "FTDI FT232 USB-UART"),
    "0403:6010": ("ftdi", "FTDI FT2232 USB-UART/JTAG"),
    "303A:0009": ("esp-usb-jtag", "Espressif USB-Serial-JTAG (built-in)"),
    "303A:1001": ("esp-usb-jtag", "Espressif USB-JTAG (built-in)"),
    "303A:0002": ("esp-devkit", "Espressif DevKit USB-UART"),
    "0483:5740": ("stlink-vcp", "ST-Link VCP (not ESP32, but common)"),
}

KNOWN_USB_VENDORS = {
    "10C4": "Silicon Labs",
    "1A86": "WCH",
    "0403": "FTDI",
    "303A": "Espressif",
}

# Chip names from esptool chip_id output
CHIP_NAME_PATTERNS = [
    (r"ESP32-S3", "esp32s3", "Xtensa"),
    (r"ESP32-S2", "esp32s2", "Xtensa"),
    (r"ESP32-C3", "esp32c3", "RISC-V"),
    (r"ESP32-C6", "esp32c6", "RISC-V"),
    (r"ESP32-H2", "esp32h2", "RISC-V"),
    (r"ESP32[^-]", "esp32", "Xtensa"),
]


@dataclass
class Device:
    port: str
    kind: str
    display_name: str
    manufacturer: str = ""
    usb_id: str = ""
    serial_number: str = ""
    chip_model: Optional[str] = None
    chip_arch: Optional[str] = None
    mac_address: Optional[str] = None
    flash_size: Optional[str] = None
    confidence: str = "low"  # low / medium / high
    evidence: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def run_command(command: list[str], timeout: int = 15) -> str:
    """Run a command and return stdout. Raises RuntimeError on failure."""
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Command timed out after {exc.timeout}s: {' '.join(command)}") from exc
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(message or f"Command failed: {' '.join(command)}")
    return completed.stdout


def normalize_usb_id(instance_id: str, hardware_ids: list[str]) -> str:
    """Extract VID:PID from Windows instance ID or hardware IDs."""
    for value in [instance_id, *hardware_ids]:
        match = re.search(r"VID_([0-9A-F]{4}).*PID_([0-9A-F]{4})", value, flags=re.IGNORECASE)
        if match:
            return f"{match.group(1).upper()}:{match.group(2).upper()}"
    return ""


def detect_serial_ports_windows() -> list[dict]:
    """Detect serial ports on Windows using PowerShell Get-PnpDevice."""
    devices = []
    try:
        # Get all present PnP devices with COM ports
        ps_script = r'''
$ports = Get-PnpDevice -PresentOnly -Class Ports -ErrorAction SilentlyContinue
foreach ($port in $ports) {
    $friendly = $port.FriendlyName
    $instance = $port.InstanceId
    $hwids = ($port.HardwareId -join ';')
    $com = ''
    if ($friendly -match '\((COM\d+)\)') { $com = $matches[1] }
    Write-Output "DEVICE|$com|$friendly|$instance|$hwids"
}
# Also check USB devices for USB-JTAG that may not appear as Ports
$usb = Get-PnpDevice -PresentOnly -Class USB -ErrorAction SilentlyContinue
foreach ($dev in $usb) {
    $friendly = $dev.FriendlyName
    $instance = $dev.InstanceId
    $hwids = ($dev.HardwareId -join ';')
    if ($friendly -match 'JTAG|Serial|Espressif|CP210|CH340|FTDI') {
        Write-Output "USB|$friendly|$instance|$hwids"
    }
}
'''
        result = run_command(["powershell", "-NoProfile", "-Command", ps_script], timeout=20)
        for line in result.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("|")
            if parts[0] == "DEVICE" and len(parts) >= 5:
                com = parts[1].strip()
                friendly = parts[2].strip()
                instance = parts[3].strip()
                hwids = parts[4].strip().split(";") if parts[4].strip() else []
                if com:
                    usb_id = normalize_usb_id(instance, hwids)
                    devices.append({
                        "port": com,
                        "friendly_name": friendly,
                        "instance_id": instance,
                        "usb_id": usb_id,
                        "hardware_ids": hwids,
                    })
            elif parts[0] == "USB" and len(parts) >= 4:
                # USB device that may be a JTAG without COM port
                friendly = parts[1].strip()
                instance = parts[2].strip()
                hwids = parts[3].strip().split(";") if parts[3].strip() else []
                usb_id = normalize_usb_id(instance, hwids)
                if usb_id in KNOWN_USB_IDS:
                    devices.append({
                        "port": "",
                        "friendly_name": friendly,
                        "instance_id": instance,
                        "usb_id": usb_id,
                        "hardware_ids": hwids,
                        "is_jtag_only": True,
                    })
    except Exception as e:
        print(f"Warning: Windows PnP detection failed: {e}", file=sys.stderr)
    return devices


def detect_serial_ports_linux() -> list[dict]:
    """Detect serial ports on Linux using /sys and /dev."""
    devices = []
    try:
        import glob
        for tty in glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"):
            devices.append({"port": tty, "friendly_name": tty, "usb_id": "", "instance_id": "", "hardware_ids": []})
    except Exception:
        pass
    return devices


def detect_serial_ports_macos() -> list[dict]:
    """Detect serial ports on macOS."""
    devices = []
    try:
        import glob
        for tty in glob.glob("/dev/tty.usbserial*") + glob.glob("/dev/tty.SLAB_USBtoUART*") + glob.glob("/dev/tty.wchusbserial*") + glob.glob("/dev/cu.usbmodem*"):
            devices.append({"port": tty, "friendly_name": tty, "usb_id": "", "instance_id": "", "hardware_ids": []})
    except Exception:
        pass
    return devices


def detect_serial_ports() -> list[dict]:
    """Platform-agnostic serial port detection."""
    system = platform.system()
    if system == "Windows":
        return detect_serial_ports_windows()
    elif system == "Linux":
        return detect_serial_ports_linux()
    elif system == "Darwin":
        return detect_serial_ports_macos()
    return []


def find_esptool() -> Optional[str]:
    """Find esptool.py executable."""
    # Try esptool.py first (ESP-IDF virtualenv)
    for name in ["esptool.py", "esptool"]:
        path = shutil.which(name)
        if path:
            return path
    # Try python -m esptool
    try:
        run_command([sys.executable, "-m", "esptool", "version"], timeout=5)
        return f"{sys.executable} -m esptool"
    except Exception:
        pass
    return None


def identify_chip(port: str, esptool: str) -> Optional[dict]:
    """Call esptool chip_id to identify the chip. Returns None on failure."""
    if not port:
        return None

    cmd_parts = esptool.split() + ["--port", port, "--before", "default_reset", "chip_id"]
    try:
        output = run_command(cmd_parts, timeout=20)
    except Exception as e:
        return {"error": str(e)}

    result = {}
    # Chip model
    for pattern, chip, arch in CHIP_NAME_PATTERNS:
        if re.search(pattern, output, re.IGNORECASE):
            result["chip_model"] = chip
            result["chip_arch"] = arch
            break

    # MAC address
    m = re.search(r"MAC:\s*([0-9A-Fa-f:]+)", output)
    if m:
        result["mac_address"] = m.group(1).upper()

    # Flash size (from read_flash_id, not always in chip_id)
    m = re.search(r"flash size[^:]*:\s*(\d+\s*\w+)", output, re.IGNORECASE)
    if m:
        result["flash_size"] = m.group(1).strip()

    # Chip ID
    m = re.search(r"Chip is\s+(.+)", output)
    if m:
        result["chip_full_name"] = m.group(1).strip()

    return result if result else None


def detect_devices(identify: bool = True) -> list[Device]:
    """Detect connected ESP32 devices.

    Args:
        identify: If True, call esptool chip_id to identify each candidate.
                  Set False for faster read-only USB enumeration.
    """
    raw_devices = detect_serial_ports()
    esptool = find_esptool() if identify else None
    devices = []

    for raw in raw_devices:
        usb_id = raw.get("usb_id", "")
        port = raw.get("port", "")
        friendly = raw.get("friendly_name", "")

        # Determine device kind
        kind = "unknown"
        display_name = friendly or port
        manufacturer = ""
        confidence = "low"

        if usb_id in KNOWN_USB_IDS:
            kind, display_name = KNOWN_USB_IDS[usb_id]
            vid = usb_id.split(":")[0]
            manufacturer = KNOWN_USB_VENDORS.get(vid, "")
            confidence = "medium"
        elif any(kw in friendly.lower() for kw in ["cp210", "ch340", "ch341", "ftdi", "espressif", "usb-serial", "usb jtag", "silicon labs"]):
            kind = "usb-uart"
            confidence = "medium"
        elif port:
            # Generic COM port — could be anything
            kind = "generic-serial"
            confidence = "low"

        # Only consider devices that could be ESP32
        if kind == "unknown" and not port:
            continue

        device = Device(
            port=port,
            kind=kind,
            display_name=display_name,
            manufacturer=manufacturer,
            usb_id=usb_id,
            serial_number="",
            confidence=confidence,
            evidence=[f"USB ID: {usb_id}" if usb_id else f"Port: {port}", f"Friendly: {friendly}"],
        )

        # Try to identify chip via esptool
        if identify and esptool and port and kind in ("cp2102", "cp210x", "ch340", "ch341", "ftdi", "esp-usb-jtag", "esp-devkit", "usb-uart", "generic-serial"):
            chip_info = identify_chip(port, esptool)
            if chip_info and "error" not in chip_info:
                device.chip_model = chip_info.get("chip_model")
                device.chip_arch = chip_info.get("chip_arch")
                device.mac_address = chip_info.get("mac_address")
                device.flash_size = chip_info.get("flash_size")
                if device.chip_model:
                    device.confidence = "high"
                    device.evidence.append(f"esptool chip_id: {device.chip_model} ({device.chip_arch})")
                    if device.mac_address:
                        device.evidence.append(f"MAC: {device.mac_address}")
            elif chip_info and "error" in chip_info:
                device.evidence.append(f"esptool chip_id failed: {chip_info['error'][:100]}")

        devices.append(device)

    return devices


def print_devices(devices: list[Device]):
    """Print human-readable device list."""
    if not devices:
        print("No serial/USB devices detected.")
        print("Note: An empty result is inconclusive. Check USB connections, drivers, and try:")
        print("  Windows: Get-PnpDevice -PresentOnly | Where-Object { $_.Class -eq 'Ports' }")
        print("  Linux:   ls /dev/ttyUSB* /dev/ttyACM*")
        print("  macOS:   ls /dev/tty.usbserial* /dev/cu.usbmodem*")
        return

    print(f"Found {len(devices)} candidate device(s):")
    print("-" * 70)
    for i, d in enumerate(devices, 1):
        print(f"[{i}] {d.display_name}")
        print(f"    Port: {d.port or 'N/A (JTAG-only)'}")
        print(f"    Kind: {d.kind}")
        if d.usb_id:
            print(f"    USB ID: {d.usb_id} ({d.manufacturer})")
        if d.chip_model:
            print(f"    Chip: {d.chip_model} ({d.chip_arch})")
        if d.mac_address:
            print(f"    MAC: {d.mac_address}")
        if d.flash_size:
            print(f"    Flash: {d.flash_size}")
        print(f"    Confidence: {d.confidence}")
        for ev in d.evidence:
            print(f"    - {ev}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Detect connected ESP32 devices (read-only)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--no-identify", action="store_true", help="Skip esptool chip_id (faster, USB-only)")
    parser.add_argument("--port", help="Check a specific serial port only (e.g. COM6)")
    args = parser.parse_args()

    if args.port:
        # Check a specific port
        esptool = find_esptool()
        if not esptool:
            print("Error: esptool.py not found. Install ESP-IDF or run: pip install esptool", file=sys.stderr)
            sys.exit(1)
        chip_info = identify_chip(args.port, esptool)
        if chip_info:
            print(json.dumps(chip_info, indent=2, ensure_ascii=False))
        else:
            print(f"No ESP32 chip responded on {args.port}. Check wiring, boot mode, and drivers.", file=sys.stderr)
            sys.exit(1)
        return

    devices = detect_devices(identify=not args.no_identify)

    if args.json:
        print(json.dumps([d.to_dict() for d in devices], indent=2, ensure_ascii=False))
    else:
        print_devices(devices)

    # Exit code: 0 if any high-confidence device found, 1 otherwise
    high_conf = [d for d in devices if d.confidence == "high"]
    sys.exit(0 if high_conf else 1)


if __name__ == "__main__":
    main()
