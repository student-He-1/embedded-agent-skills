#!/usr/bin/env python3
"""Flash an STM32 Keil project over SWD without editing project files.

Primary backend: SEGGER J-Link Commander (verified on this board).
Reserved backend: STM32CubeProgrammer CLI for ST-Link (not exercised here).

The script locates the build artifact (prefer .hex, fall back to .axf) from the
project's output settings, writes a temporary Commander script, runs it, and
parses the result.

WARNING: flashing REPLACES the firmware currently running on the board. The
on-disk project files are never touched, but the chip's flash is rewritten.

Usage:
  python stm32_flash.py <project-dir>
  python stm32_flash.py <project-dir> --probe jlink --device STM32F407VE
  python stm32_flash.py <project-dir> --file path/to/image.hex --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# Known tool locations
# ---------------------------------------------------------------------------
JLINK_PATHS = [
    r"C:\Program Files (x86)\SEGGER\JLink\JLink.exe",
    r"C:\Program Files\SEGGER\JLink\JLink.exe",
    r"C:\Program Files (x86)\SEGGER\JLink_V646c\JLink.exe",
]
STLINK_PROG_PATHS = [
    r"C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe",
    r"C:\Program Files (x86)\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe",
]

DEFAULT_DEVICE = "STM32F407VE"


@dataclass
class FlashResult:
    project: str
    probe: str
    device: str
    interface: str
    speed_khz: int
    image: str
    ran_after_flash: bool
    command: str
    return_code: int = -1
    success: bool = False
    verified: bool = False
    messages: list[str] = field(default_factory=list)
    output: str = ""


# ---------------------------------------------------------------------------
# Project / artifact discovery
# ---------------------------------------------------------------------------
def find_uvprojx(project_dir: Path) -> Optional[Path]:
    direct = sorted(project_dir.rglob("*.uvprojx"))
    direct = [p for p in direct if "Objects" not in p.parts]
    return direct[0] if direct else None


def jlink_device_name(keil_device: str) -> str:
    """Map a Keil device (STM32F407VETx) to a J-Link device (STM32F407VE)."""
    d = keil_device.strip()
    # Drop the package/temperature suffix (e.g. "Tx" in STM32F407VETx),
    # keeping series + pin-count + density: STM32F407VE.
    for suffix in ("Tx", "Hx", "Zx", "Cx", "Rx", "Vx", "Ix"):
        if d.endswith(suffix):
            return d[: -len(suffix)]
    return d


def find_artifact(uvprojx: Path, explicit: Optional[str]) -> Optional[Path]:
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None

    base = uvprojx.parent
    try:
        root = ET.parse(uvprojx).getroot()
        target = root.find("Targets/Target/TargetOption")
        common = target.find("TargetCommonOption")
        out_dir = (common.findtext("OutputDirectory") or "").strip()
        out_name = (common.findtext("OutputName") or "").strip()
    except Exception:
        out_dir, out_name = "", ""

    candidates = []
    if out_name:
        out_base = base / out_dir / out_name
        candidates = [
            out_base.with_suffix(".hex"),
            out_base.with_suffix(".axf"),
            out_base.with_suffix(".bin"),
        ]
    # Fallbacks: scan the MDK-ARM directory
    candidates += sorted(base.rglob("*.hex"))
    candidates += sorted(base.rglob("*.axf"))

    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def find_tool(paths: list[str], name: str) -> Optional[str]:
    for p in paths:
        if Path(p).exists():
            return p
    return shutil.which(name)


# ---------------------------------------------------------------------------
# J-Link backend
# ---------------------------------------------------------------------------
# Speed ladder (kHz) for automatic slowdown retries on this board.
SPEED_LADDER = [500, 200, 100, 50]

# Output signatures that indicate a high-speed SWD / RAMCode problem worth a
# slower retry.
RETRY_SPEED_SIGNATURES = (
    "verification of ramcode failed",
    "failed to download ramcode",
    "kept in reset forever",
    "could not power up debug port",
    "sw-dp scan error",
    "swd scan error",
)
RETRY_CONNECT_SIGNATURES = (
    "could not connect",
    "cannot connect",
    "could not find target",
    "no cortex-m",
)


def classify_failure(output: str) -> str:
    low = output.lower()
    for sig in RETRY_SPEED_SIGNATURES:
        if sig in low:
            return "speed"
    for sig in RETRY_CONNECT_SIGNATURES:
        if sig in low:
            return "connect"
    return "fatal"


VECTOR_RE = re.compile(
    r"(?:0x)?08000000\s*=\s*([0-9A-Fa-f]{8})[\s,]+\s*([0-9A-Fa-f]{8})"
)


def parse_vector_table(output: str) -> tuple[Optional[int], Optional[int]]:
    # J-Link prints both words on one line: "08000000 = <SP> <Reset_Handler>".
    m = VECTOR_RE.search(output)
    if m:
        return int(m.group(1), 16), int(m.group(2), 16)
    return None, None


def vector_table_ok(sp: Optional[int], reset: Optional[int]) -> bool:
    if sp is None or reset is None:
        return False
    # Initial SP must point into SRAM (0x20000000..0x2002FFFF).
    sp_ok = 0x20000000 <= sp <= 0x2002FFFF
    # Reset_Handler in Flash (0x08000000..0x0807FFFF) with Thumb bit set (odd).
    reset_ok = 0x08000000 <= reset <= 0x0807FFFF and (reset & 1) == 1
    return sp_ok and reset_ok


def build_jlink_script(res: FlashResult, image: Path, speed: int) -> str:
    lines = [
        f"device {res.device}",
        f"si {res.interface}",
        f"speed {speed}",
        "connect",
        "halt",
        f'loadfile "{image}"',
        "mem32 0x08000000 2",   # read back initial SP + Reset_Handler
    ]
    if res.ran_after_flash:
        lines += ["r", "g"]
    else:
        lines.append("r")
    lines.append("exit")
    return "\n".join(lines) + "\n"


def flash_jlink(res: FlashResult, image: Path, dry_run: bool) -> FlashResult:
    jlink = find_tool(JLINK_PATHS, "JLink.exe")
    if not jlink:
        res.messages.append("JLink.exe not found; install SEGGER J-Link or add to PATH")
        return res

    res.command = f'"{jlink}" -CommanderScript <temp>'

    if dry_run:
        res.messages.append("Dry run; Commander script that would be used:")
        res.output = build_jlink_script(res, image, res.speed_khz)
        res.success = True
        return res

    # Copy the image to an ASCII-only temp path so the Commander script stays
    # pure ASCII (the project path may contain non-ASCII characters).
    tmp_image = Path(tempfile.gettempdir()) / (
        f"_stm32_img_{os.getpid()}{image.suffix}"
    )
    shutil.copy2(image, tmp_image)

    # Speed ladder: requested speed first, then progressively slower.
    speeds = [res.speed_khz]
    for s in SPEED_LADDER:
        if s < res.speed_khz and s not in speeds:
            speeds.append(s)

    combined = ""
    try:
        for idx, speed in enumerate(speeds):
            script_text = build_jlink_script(res, tmp_image, speed)
            with tempfile.NamedTemporaryFile(
                "w", suffix=".jlink", delete=False, encoding="ascii"
            ) as fh:
                fh.write(script_text)
                script_path = fh.name

            cmd = [jlink, "-CommanderScript", script_path, "-ExitOnError", "1"]
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=60,
                    encoding="utf-8", errors="replace",
                )
                combined = proc.stdout + proc.stderr
                res.return_code = proc.returncode
            except subprocess.TimeoutExpired:
                combined = "J-Link command timed out"
                res.return_code = -1
            finally:
                try:
                    Path(script_path).unlink()
                except OSError:
                    pass

            if "O.K." in combined or "Programming done" in combined:
                sp, reset = parse_vector_table(combined)
                if vector_table_ok(sp, reset):
                    res.success = True
                    res.verified = True
                    res.speed_khz = speed
                    res.messages.append(
                        f"Readback verified: SP=0x{sp:08X}, "
                        f"Reset_Handler=0x{reset:08X} @ {speed} kHz"
                    )
                    res.output = combined
                    break
                # Load reported OK but the vector readback is bad at this speed
                # (unreliable high-speed read). Retry slower when possible.
                if idx + 1 < len(speeds):
                    res.messages.append(
                        f"Programming OK at {speed} kHz but readback bad; "
                        f"auto-retrying at {speeds[idx + 1]} kHz"
                    )
                    continue
                res.success = True
                res.speed_khz = speed
                res.messages.append(
                    "Programming reported OK but vector-table readback looks "
                    "wrong even at the slowest rate"
                )
                res.output = combined
                break

            kind = classify_failure(combined)
            if idx + 1 < len(speeds) and kind in ("speed", "connect"):
                nxt = speeds[idx + 1]
                reason = "RAMCode/reset" if kind == "speed" else "target connect"
                res.messages.append(
                    f"Flash failed at {speed} kHz ({reason}); "
                    f"auto-retrying at {nxt} kHz"
                )
                continue

            if kind == "connect":
                res.messages.append(
                    "Could not connect: check USB, SWD wiring, board power, BOOT0"
                )
            elif kind == "speed":
                res.messages.append(
                    "Flash failed even at the slowest rate; check wiring/power"
                )
            else:
                res.messages.append("Flash did not report success; see output")
            res.output = combined
            break
    finally:
        try:
            tmp_image.unlink()
        except OSError:
            pass

    return res


# ---------------------------------------------------------------------------
# ST-Link backend (reserved; requires STM32CubeProgrammer)
# ---------------------------------------------------------------------------
def flash_stlink(res: FlashResult, image: Path, dry_run: bool) -> FlashResult:
    prog = find_tool(STLINK_PROG_PATHS, "STM32_Programmer_CLI.exe")
    if not prog:
        res.messages.append(
            "STM32_Programmer_CLI.exe not found; install STM32CubeProgrammer for "
            "ST-Link backend (J-Link is the verified path)"
        )
        return res

    cmd = [
        prog,
        # STM32_Programmer_CLI expects freq in kHz; do not integer-divide by
        # 1000, which turns the 500 kHz default into an invalid 0.
        "-c", f"port={res.interface}", "freq=" + str(res.speed_khz),
        "-w", str(image),
        "-v",
        "-rst" if res.ran_after_flash else "-hardRst",
    ]
    res.command = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    if dry_run:
        res.success = True
        res.output = res.command
        return res

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace",
        )
        res.return_code = proc.returncode
        res.output = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        res.messages.append("STM32CubeProgrammer timed out")
        return res

    if "Download verified successfully" in res.output:
        res.success = True
        res.verified = True
    else:
        res.messages.append("ST-Link flash did not report verification")
    return res


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Flash an STM32 Keil project over SWD")
    ap.add_argument("project", help="Project directory containing the .uvprojx")
    ap.add_argument("--file", help="Explicit image (.hex/.axf/.bin)")
    ap.add_argument("--probe", choices=["jlink", "stlink", "auto"], default="auto")
    ap.add_argument("--device", default="", help="J-Link device, e.g. STM32F407VE")
    ap.add_argument("--interface", default="SWD", choices=["SWD", "JTAG"])
    ap.add_argument("--speed", type=int, default=500,
                    help="SWD speed in kHz (500 is the verified-stable rate on "
                         "this J-Link OB board; >=1000 can fail RAMCode verify)")
    ap.add_argument("--no-run", action="store_true", help="Do not start firmware after flash")
    ap.add_argument("--dry-run", action="store_true", help="Print actions without flashing")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    project_dir = Path(args.project).resolve()
    uvprojx = find_uvprojx(project_dir)
    if not uvprojx:
        print(f"ERROR: no .uvprojx under {project_dir}", file=sys.stderr)
        sys.exit(2)

    device = args.device
    if not device:
        try:
            root = ET.parse(uvprojx).getroot()
            keil_dev = root.findtext(
                "Targets/Target/TargetOption/TargetArmAds/Device"
            ) or root.findtext(
                "Targets/Target/TargetOption/TargetCommonOption/Device"
            ) or DEFAULT_DEVICE
            device = jlink_device_name(keil_dev)
        except Exception:
            device = DEFAULT_DEVICE

    image = find_artifact(uvprojx, args.file)
    if not image:
        print("ERROR: no flash artifact found; build the project first", file=sys.stderr)
        sys.exit(2)
    image = image.resolve()

    # Pick backend
    probe = args.probe
    if probe == "auto":
        probe = "jlink" if find_tool(JLINK_PATHS, "JLink.exe") else "stlink"

    res = FlashResult(
        project=str(project_dir),
        probe=probe,
        device=device,
        interface=args.interface,
        speed_khz=args.speed,
        image=str(image),
        ran_after_flash=not args.no_run,
        command="",
    )

    if probe == "jlink":
        res = flash_jlink(res, image, args.dry_run)
    else:
        res = flash_stlink(res, image, args.dry_run)

    if args.json:
        print(json.dumps(asdict(res), indent=2, ensure_ascii=False))
        sys.exit(0 if res.success else 1)

    print("=== Flash ===")
    print(f"  Project:   {res.project}")
    print(f"  Probe:     {res.probe}   interface={res.interface} @ {res.speed_khz} kHz")
    print(f"  Device:    {res.device}")
    print(f"  Image:     {res.image}")
    print(f"  Run after: {'yes' if res.ran_after_flash else 'no'}")
    print(f"  Command:   {res.command}")
    if res.messages:
        print("  Messages:")
        for m in res.messages:
            print(f"    - {m}")
    if args.dry_run and res.output:
        print("--- Commander script ---")
        print(res.output)
    print()
    if res.success and res.verified:
        print("FLASH OK (download verified).")
    elif res.success:
        print("FLASH COMMAND COMPLETED (verification not explicitly confirmed).")
    else:
        print("FLASH FAILED.")
        if res.output:
            print("--- tool output (tail) ---")
            print("\n".join(res.output.splitlines()[-25:]))
    sys.exit(0 if res.success else 1)


if __name__ == "__main__":
    main()
