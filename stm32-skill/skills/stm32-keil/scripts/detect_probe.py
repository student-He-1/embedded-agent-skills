#!/usr/bin/env python3
"""Detect connected debug probes and serial ports for STM32 targets.

Read-only: it never resets, programs, or modifies the target. It enumerates
USB devices via Windows PnP (PowerShell) and COM ports via pyserial, then
classifies debug probes (J-Link / ST-Link / DAPLink) and serial adapters.

An empty result is reported as INCONCLUSIVE, not as "nothing connected":
check the USB cable (data, not power-only), drivers, and that the board is
powered.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from typing import Optional

try:
    from serial.tools import list_ports
except Exception:  # pragma: no cover
    list_ports = None


# ---------------------------------------------------------------------------
# USB VID/PID tables
# ---------------------------------------------------------------------------

SEGGER_VID = "1366"
ST_VID = "0483"
MBED_VID = "0D28"

# PID -> human-readable model (probe families keyed by VID)
JLINK_PIDS = {
    "0101": "J-Link",
    "0105": "J-Link OB",
    "0107": "J-Link OB",
    "1015": "J-Link PRO",
    "1016": "J-Link",
    "5105": "J-Link OB",
}
STLINK_PIDS = {
    "3744": "ST-LINK/V2",
    "3748": "ST-LINK/V2-1",
    "374B": "ST-LINK/V3",
    "374F": "ST-LINK/V3",
    "3753": "ST-LINK/V3",
    "3757": "ST-LINK",
}
DAPLINK_PIDS = {
    "0204": "DAPLink",
    "0205": "DAPLink",
}

# USB-UART bridge chips (not debug probes; for direct USART wiring)
UART_BRIDGES = {
    "10C4": {  # Silicon Labs CP210x
        "family": "CP210x",
        "pids": {"EA60": "CP2102/CP2109", "EA63": "CP210x", "EA70": "CP210x", "EA71": "CP210x"},
    },
    "1A86": {  # QinHeng CH340/CH343
        "family": "CH340/CH343",
        "pids": {"7523": "CH340", "5523": "CH343", "7522": "CH341"},
    },
    "0403": {  # FTDI
        "family": "FTDI",
        "pids": {"6001": "FT232R", "6010": "FT2232", "6014": "FT232H", "6011": "FT4232"},
    },
    "067B": {  # Prolific
        "family": "Prolific",
        "pids": {"2303": "PL2303", "2304": "PL2303"},
    },
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Probe:
    type: str = "unknown"          # jlink | stlink | daplink | unknown
    model: str = ""
    vid: str = ""
    pid: str = ""
    serial: str = ""
    manufacturer: str = ""
    com_port: str = ""             # VCP/CDC exposed by the probe itself
    confidence: str = "unknown"    # confirmed | likely | unknown
    evidence: list[str] = field(default_factory=list)


@dataclass
class SerialPort:
    port: str
    description: str = ""
    vid: str = ""
    pid: str = ""
    serial: str = ""
    manufacturer: str = ""
    kind: str = "unknown"          # jlink-cdc | stlink-vcp | daplink-vcp | uart-bridge | unknown
    hwid: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(s: Optional[str]) -> str:
    return (s or "").strip()


def classify_probe(vid: str, pid: str, desc: str = "") -> tuple[str, str]:
    """Return (type, model) for a USB device; ('unknown','') if not a probe."""
    v = vid.upper()
    p = pid.upper()
    text = desc.lower()
    if v == SEGGER_VID:
        return "jlink", JLINK_PIDS.get(p, "J-Link")
    if v == ST_VID:
        if p in STLINK_PIDS:
            return "stlink", STLINK_PIDS[p]
        if "st-link" in text or "stlink" in text:
            return "stlink", "ST-LINK"
    if v == MBED_VID and p in DAPLINK_PIDS:
        return "daplink", DAPLINK_PIDS[p]
    if "daplink" in text:
        return "daplink", "DAPLink"
    if "j-link" in text or "jlink" in text:
        return "jlink", JLINK_PIDS.get(p, "J-Link")
    if "st-link" in text or "stlink" in text:
        return "stlink", STLINK_PIDS.get(p, "ST-LINK")
    return "unknown", ""


def get_pnp_usb_devices() -> list[dict]:
    """Enumerate present USB devices via PowerShell Get-PnpDevice.

    Returns dicts with friendly_name, vid, pid, serial, manufacturer, status.
    Works even when a probe exposes no COM port.
    """
    if not shutil.which("powershell") and not shutil.which("powershell.exe"):
        return []
    ps = (
        "Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB*' } | "
        "ForEach-Object { "
        "$m=[regex]::Match($_.InstanceId,'VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})'); "
        "$sn=[regex]::Match($_.InstanceId,'(?:&MI_\\d{2})?\\\\([0-9A-Za-z]+)$'); "
        "Write-Output ($_.FriendlyName + '|' + $m.Groups[1].Value + '|' + "
        "$m.Groups[2].Value + '|' + ($sn.Groups[1].Value) + '|' + $_.Status) }"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=40,
        )
    except Exception:
        return []
    out = []
    for line in r.stdout.splitlines():
        parts = line.split("|")
        if len(parts) < 5:
            continue
        name, vid, pid, serial, status = parts[:5]
        if not vid:
            continue
        out.append({
            "friendly_name": name,
            "vid": vid.upper(),
            "pid": pid.upper(),
            "serial": serial,
            "status": status,
        })
    return out


def get_com_ports() -> list[SerialPort]:
    """Enumerate COM ports via pyserial with USB metadata."""
    ports: list[SerialPort] = []
    if list_ports is None:
        return ports
    for p in list_ports.comports():
        vid = f"{p.vid:04X}" if p.vid else ""
        pid = f"{p.pid:04X}" if p.pid else ""
        sp = SerialPort(
            port=_norm(p.device),
            description=_norm(p.description),
            vid=vid,
            pid=pid,
            serial=_norm(p.serial_number),
            manufacturer=_norm(p.manufacturer),
            hwid=_norm(p.hwid),
        )
        sp.kind = classify_port_kind(sp)
        ports.append(sp)
    return ports


def classify_port_kind(sp: SerialPort) -> str:
    t, _ = classify_probe(sp.vid, sp.pid, sp.description)
    if t == "jlink":
        return "jlink-cdc"
    if t == "stlink":
        return "stlink-vcp"
    if t == "daplink":
        return "daplink-vcp"
    if sp.vid in UART_BRIDGES:
        return "uart-bridge"
    text = sp.description.lower()
    if "jlink" in text:
        return "jlink-cdc"
    if "st-link" in text or "stlink" in text:
        return "stlink-vcp"
    return "unknown"


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def detect() -> tuple[list[Probe], list[SerialPort]]:
    com_ports = get_com_ports()
    pnp = get_pnp_usb_devices()

    probes: list[Probe] = []
    seen_keys: set[str] = set()

    # Probes discovered through their own COM/CDC interface first.
    for sp in com_ports:
        ptype, model = classify_probe(sp.vid, sp.pid, sp.description)
        if ptype == "unknown":
            continue
        key = f"{sp.vid}:{sp.pid}:{sp.serial}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        probes.append(Probe(
            type=ptype,
            model=model,
            vid=sp.vid,
            pid=sp.pid,
            serial=sp.serial,
            manufacturer=sp.manufacturer,
            com_port=sp.port,
            confidence="confirmed",
            evidence=[f"CDC/VCP port {sp.port} ({sp.description})"],
        ))

    # Add probes that have no COM port (or composite parents) from PnP.
    for d in pnp:
        ptype, model = classify_probe(d["vid"], d["pid"], d["friendly_name"])
        if ptype == "unknown":
            continue
        # Composite device (no MI) is the canonical probe record; interface
        # children (MI_00 etc.) share its serial. Match by serial when present.
        key = f"{d['vid']}:{d['pid']}:{d['serial']}"
        existing = next(
            (p for p in probes
             if p.vid == d["vid"] and (p.serial == d["serial"] or not d["serial"])),
            None,
        )
        if existing:
            ev = f"PnP: {d['friendly_name']} ({d['status']})"
            if ev not in existing.evidence:
                existing.evidence.append(ev)
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        probes.append(Probe(
            type=ptype,
            model=model,
            vid=d["vid"],
            pid=d["pid"],
            serial=d["serial"],
            confidence="likely" if d["status"] == "OK" else "unknown",
            evidence=[f"PnP: {d['friendly_name']} ({d['status']})"],
        ))

    # Backfill probe com_port from a same-family CDC port not yet linked.
    for p in probes:
        if p.com_port:
            continue
        for sp in com_ports:
            if sp.vid == p.vid and (sp.serial == p.serial or not p.serial) \
                    and sp.kind in ("jlink-cdc", "stlink-vcp", "daplink-vcp"):
                p.com_port = sp.port
                p.evidence.append(f"associated VCP {sp.port}")
                break

    return probes, com_ports


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(probes: list[Probe], ports: list[SerialPort]) -> None:
    if probes:
        for i, p in enumerate(probes, 1):
            print(f"--- Probe {i} ---")
            print(f"  Type:         {p.type} {('(' + p.model + ')') if p.model else ''}")
            print(f"  VID:PID:      {p.vid}:{p.pid}")
            if p.serial:
                print(f"  Serial:       {p.serial}")
            if p.manufacturer:
                print(f"  Manufacturer: {p.manufacturer}")
            print(f"  VCP/CDC port: {p.com_port or 'none'}")
            print(f"  Confidence:   {p.confidence}")
            for e in p.evidence:
                print(f"  Evidence:     {e}")
            print()
    else:
        print("No debug probes detected.")
        print("This is INCONCLUSIVE, not proof that none is connected.")
        print("Check: USB data cable, probe drivers, board power, "
              "and that the probe is exposed (Device Manager).")
        print()

    print("=== Serial ports ===")
    if ports:
        for sp in ports:
            bridge = ""
            if sp.vid in UART_BRIDGES:
                bridge = UART_BRIDGES[sp.vid]["family"]
            print(f"  {sp.port:8} kind={sp.kind:12} "
                  f"{sp.description or ''} "
                  f"{(sp.vid + ':' + sp.pid) if sp.vid else ''} "
                  f"{bridge}")
    else:
        print("  (none)")
    print()

    if not probes:
        print("Note: STM32 boards with only an SWD header need an external")
        print("probe (J-Link / ST-Link / DAPLink). A USB port wired to USB OTG")
        print("(PA11/PA12) is not a debug channel.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Detect STM32 debug probes and serial ports")
    ap.add_argument("--json", action="store_true", help="Output JSON")
    args = ap.parse_args()

    probes, ports = detect()

    if args.json:
        print(json.dumps(
            {"probes": [asdict(p) for p in probes],
             "serial_ports": [asdict(s) for s in ports]},
            indent=2, ensure_ascii=False))
        return

    print_report(probes, ports)


if __name__ == "__main__":
    main()
