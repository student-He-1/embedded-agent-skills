#!/usr/bin/env python3
"""Static checks for a Keil MDK-uVision STM32 project.

Parses the .uvprojx XML (and the matching .uvoptx) and validates:
  - target device / vendor / Pack, toolchain (AC5 vs AC6)
  - source groups and that every referenced file exists on disk
  - include paths (existence), preprocessor defines
  - memory layout (Cpu string + on-chip memories / scatter file)
  - optimization, warning level, C99, MicroLIB, HEX output
  - configured debug probe and transport (SWD/JTAG)

Read-only: it never modifies the project. Findings are split into
errors / warnings / info.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

# AC5 Optimization dropdown order: Default, L0, L1, L2, L3
OPTIM_AC5 = {
    "0": "Default (compiler default)",
    "1": "Level 0 (-O0)",
    "2": "Level 1 (-O1)",
    "3": "Level 2 (-O2)",
    "4": "Level 3 (-O3)",
}
# AC6 (ARMCLANG) — order varies slightly by version; raw always shown
OPTIM_AC6 = {
    "0": "Default",
    "1": "-O0",
    "2": "-O1",
    "3": "-O2",
    "4": "-Os",
    "5": "-O3",
    "6": "-Oz",
    "7": "-Oz / smallest",
}

WLEVEL = {
    "0": "No Warnings (-W)",
    "1": "AC5-like Warnings",
    "2": "All Warnings",
}

FILE_TYPES = {
    "1": "C",
    "2": "ASM",
    "3": "Object",
    "4": "Library",
    "5": "Header",
    "7": "C++",
    "8": "Image",
}

PROBE_DLL = [
    (re.compile(r"JL2CM3|JLink|Segger", re.I), "jlink"),
    (re.compile(r"ST-?LINK|STLink", re.I), "stlink"),
    (re.compile(r"DAPLink|CMSIS_DAP|DAP_", re.I), "daplink"),
    (re.compile(r"UL2CM3|ULINK", re.I), "ulink"),
]

TRANSPORT = {"0": "JTAG", "1": "JTAG", "2": "SWD"}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    severity: str        # error | warning | info
    code: str
    message: str


@dataclass
class SourceFile:
    name: str
    type: str
    rel_path: str
    exists: bool
    group: str


@dataclass
class MemoryRegion:
    name: str
    start: str
    size: str
    kind: str            # rom | ram


@dataclass
class ProjectInfo:
    project_file: str
    target_name: str = ""
    device: str = ""
    vendor: str = ""
    pack_id: str = ""
    toolchain: str = ""          # AC5 | AC6
    compiler: str = ""
    cpu_raw: str = ""
    fpu: str = ""
    cpu_type: str = ""
    clock_hint: str = ""
    output_dir: str = ""
    output_name: str = ""
    create_hex: bool = False
    microlib: bool = False
    c99: bool = False
    optimization_raw: str = ""
    optimization: str = ""
    warning_raw: str = ""
    warning: str = ""
    defines: list[str] = field(default_factory=list)
    include_paths: list[str] = field(default_factory=list)
    missing_includes: list[str] = field(default_factory=list)
    scatter_file: str = ""
    scatter_exists: bool = False
    source_files: list[SourceFile] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    memory_regions: list[MemoryRegion] = field(default_factory=list)
    flash_driver_dll: str = ""
    debug_driver: str = ""
    probe_type: str = "unknown"
    transport: str = "unknown"
    debug_clock: str = ""
    uvoptx_exists: bool = False
    findings: list[Finding] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def text(el: Optional[ET.Element], default: str = "") -> str:
    if el is None or el.text is None:
        return default
    return el.text.strip()


def find_first(root: ET.Element, path: str) -> Optional[ET.Element]:
    return root.find(path)


def add(info: ProjectInfo, sev: str, code: str, msg: str) -> None:
    info.findings.append(Finding(sev, code, msg))


def locate_project(target: str) -> Optional[Path]:
    p = Path(target)
    if p.is_file() and p.suffix.lower() == ".uvprojx":
        return p
    if p.is_dir():
        # direct, then MDK-ARM subdir
        candidates = list(p.glob("*.uvprojx"))
        mdk = p / "MDK-ARM"
        if mdk.is_dir():
            candidates += list(mdk.glob("*.uvprojx"))
        # also one level down for <root>/<name>/MDK-ARM
        if not candidates:
            for sub in p.iterdir():
                if sub.is_dir() and (sub / "MDK-ARM").is_dir():
                    candidates += list((sub / "MDK-ARM").glob("*.uvprojx"))
        if candidates:
            return sorted(candidates, key=lambda c: len(str(c)))[0]
    return None


def parse_cpu_string(cpu: str) -> dict:
    out = {"iram": "", "iram2": "", "irom": "", "clock": "", "fpu": "", "cpu_type": ""}
    m = re.search(r"IRAM\((0x[0-9A-Fa-f]+)-(0x[0-9A-Fa-f]+)\)", cpu)
    if m:
        out["iram"] = f"{m.group(1)}-{m.group(2)}"
    m = re.search(r"IRAM2\((0x[0-9A-Fa-f]+)-(0x[0-9A-Fa-f]+)\)", cpu)
    if m:
        out["iram2"] = f"{m.group(1)}-{m.group(2)}"
    m = re.search(r"IROM\((0x[0-9A-Fa-f]+)-(0x[0-9A-Fa-f]+)\)", cpu)
    if m:
        out["irom"] = f"{m.group(1)}-{m.group(2)}"
    m = re.search(r"CLOCK\((\d+)\)", cpu)
    if m:
        out["clock"] = m.group(1)
    m = re.search(r"(FPU\d?)", cpu)
    if m:
        out["fpu"] = m.group(1)
    m = re.search(r'CPUTYPE\("([^"]+)"\)', cpu)
    if m:
        out["cpu_type"] = m.group(1)
    return out


def region_from_element(el: Optional[ET.Element], name: str, kind: str) -> Optional[MemoryRegion]:
    if el is None:
        return None
    start = text(el.find("StartAddress"))
    size = text(el.find("Size"))
    if not start or not size or start == "0x0" or size == "0x0":
        return None
    try:
        s = int(start, 16)
        z = int(size, 16)
    except ValueError:
        return None
    end = s + z - 1
    return MemoryRegion(name=name, start=f"0x{s:08X}-0x{end:08X}", size=f"0x{z:X} ({z} B)", kind=kind)


def classify_probe_dll(name: str) -> str:
    for rx, ptype in PROBE_DLL:
        if rx.search(name):
            return ptype
    return "unknown"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_project(uvprojx: Path) -> ProjectInfo:
    info = ProjectInfo(project_file=str(uvprojx))
    base = uvprojx.parent

    try:
        tree = ET.parse(uvprojx)
    except ET.ParseError as e:
        add(info, "error", "XML_PARSE", f"Cannot parse .uvprojx: {e}")
        return info
    root = tree.getroot()

    target = find_first(root, "Targets/Target")
    if target is None:
        add(info, "error", "NO_TARGET", "No <Target> in project")
        return info

    info.target_name = text(target.find("TargetName"))
    info.compiler = text(target.find("pCCUsed"))
    is_ac6 = text(target.find("uAC6"), "0") == "1"
    info.toolchain = "AC6 (ARMCLANG)" if is_ac6 else "AC5 (ARMCC)"

    opt = target.find("TargetOption")
    if opt is None:
        add(info, "error", "NO_OPTIONS", "No TargetOption")
        return info

    common = opt.find("TargetCommonOption")
    if common is not None:
        info.device = text(common.find("Device"))
        info.vendor = text(common.find("Vendor"))
        info.pack_id = text(common.find("PackID"))
        info.cpu_raw = text(common.find("Cpu"))
        info.output_dir = text(common.find("OutputDirectory"))
        info.output_name = text(common.find("OutputName"))
        info.create_hex = text(common.find("CreateHexFile"), "0") == "1"

        if info.cpu_raw:
            c = parse_cpu_string(info.cpu_raw)
            info.fpu = c["fpu"]
            info.cpu_type = c["cpu_type"]
            info.clock_hint = c["clock"]

    # Compiler settings
    cads = find_first(opt, "TargetArmAds/Cads")
    if cads is not None:
        info.optimization_raw = text(cads.find("Optim"))
        info.warning_raw = text(cads.find("wLevel"))
        info.c99 = text(cads.find("uC99"), "0") == "1"
        vc = cads.find("VariousControls")
        if vc is not None:
            defines = text(vc.find("Define"))
            info.defines = [d.strip() for d in defines.split(",") if d.strip()]
            includes = text(vc.find("IncludePath"))
            for inc in [x.strip() for x in includes.split(";") if x.strip()]:
                info.include_paths.append(inc)
                resolved = (base / inc).resolve()
                if not resolved.exists():
                    info.missing_includes.append(inc)

    opt_table = OPTIM_AC6 if is_ac6 else OPTIM_AC5
    info.optimization = opt_table.get(info.optimization_raw,
                                      f"unknown (raw={info.optimization_raw})")
    info.warning = WLEVEL.get(info.warning_raw, f"unknown (raw={info.warning_raw})")

    # Misc / linker
    misc = find_first(opt, "TargetArmAds/ArmAdsMisc")
    if misc is not None:
        info.microlib = text(misc.find("useUlib"), "0") == "1"
        ocm = misc.find("OnChipMemories")
        if ocm is not None:
            r = region_from_element(ocm.find("IROM"), "IROM (Flash)", "rom")
            if r:
                info.memory_regions.append(r)
            r = region_from_element(ocm.find("IRAM"), "IRAM (SRAM)", "ram")
            if r:
                info.memory_regions.append(r)
            # OCR entries describe linker RAM views; OCR_RVCT10 is the CCM on
            # F407. Skip ranges that duplicate an already-parsed region.
            existing_ranges = {(m.start, m.size) for m in info.memory_regions}
            for i in (9, 10):
                r = region_from_element(ocm.find(f"OCR_RVCT{i}"),
                                        f"IRAM2/CCM (OCR_RVCT{i})", "ram")
                if r and (r.start, r.size) not in existing_ranges:
                    info.memory_regions.append(r)
                    existing_ranges.add((r.start, r.size))

    ldads = find_first(opt, "TargetArmAds/LDads")
    if ldads is not None:
        scatter = text(ldads.find("ScatterFile"))
        if scatter:
            info.scatter_file = scatter
            info.scatter_exists = (base / scatter).resolve().exists()

    # Flash / utility driver recorded in uvprojx
    util = opt.find("Utilities")
    if util is not None:
        info.flash_driver_dll = text(util.find("Flash2"))

    # Groups / files
    groups = target.find("Groups")
    if groups is not None:
        for grp in groups.findall("Group"):
            gname = text(grp.find("GroupName"))
            for f in grp.findall("Files/File"):
                fname = text(f.find("FileName"))
                ftype_raw = text(f.find("FileType"))
                fpath = text(f.find("FilePath"))
                ftype = FILE_TYPES.get(ftype_raw, f"type{ftype_raw}")
                if not fpath:
                    continue
                exists = (base / fpath).resolve().exists()
                info.source_files.append(SourceFile(
                    name=fname, type=ftype, rel_path=fpath, exists=exists, group=gname))
                if not exists:
                    info.missing_files.append(f"{gname}/{fname}: {fpath}")

    # uvoptx: actual debug driver + transport
    uvoptx = uvprojx.with_suffix(".uvoptx")
    info.uvoptx_exists = uvoptx.exists()
    if uvoptx.exists():
        try:
            oroot = ET.parse(uvoptx).getroot()
            oopt = find_first(oroot, "Target/TargetOption")
            if oopt is not None:
                pmon = text(find_first(oopt, "DebugOpt/pMon"))
                info.debug_driver = pmon
                if pmon:
                    info.probe_type = classify_probe_dll(pmon)
                dd = oopt.find("DebugDescription")
                if dd is not None:
                    proto = text(dd.find("Protocol"))
                    info.transport = TRANSPORT.get(proto, f"unknown (raw={proto})")
                    info.debug_clock = text(dd.find("DbgClock"))
        except ET.ParseError:
            add(info, "warning", "UVSOPT_PARSE", "Could not parse .uvoptx")

    evaluate(info)
    return info


def evaluate(info: ProjectInfo) -> None:
    if not info.device:
        add(info, "error", "NO_DEVICE", "No target device specified")
    elif not re.match(r"STM32F407", info.device, re.I):
        add(info, "warning", "DEVICE_MISMATCH",
            f"Device '{info.device}' is not STM32F407*; this skill targets F407VET6")

    if not info.source_files:
        add(info, "warning", "NO_SOURCES", "No source files in any group")

    for mf in info.missing_files:
        add(info, "error", "MISSING_FILE", f"Source not found: {mf}")

    for mi in info.missing_includes:
        add(info, "warning", "MISSING_INCLUDE", f"Include path not found: {mi}")

    if info.scatter_file and not info.scatter_exists:
        add(info, "error", "MISSING_SCATTER",
            f"Scatter file not found: {info.scatter_file}")

    if info.probe_type == "unknown":
        if info.uvoptx_exists:
            add(info, "warning", "NO_PROBE_CFG",
                "Debug probe not recognized in .uvoptx; run detect_probe.py")
        else:
            add(info, "info", "NO_UVOPTX",
                "No .uvoptx yet (project never opened in Keil); open it once to "
                "generate IDE state and select the J-Link probe")
    elif info.transport not in ("SWD",):
        add(info, "warning", "NOT_SWD",
            f"Transport is {info.transport}; this board requires SWD (JTAG pins used by W25Qxx)")

    if not info.create_hex:
        add(info, "info", "NO_HEX",
            "HEX output disabled; flash via .axf or enable Create HEX File")

    if info.microlib:
        add(info, "info", "MICROLIB",
            "MicroLIB enabled (printf retarget uses fputc; smaller runtime)")
    else:
        add(info, "info", "STD_LIB",
            "Standard library (not MicroLIB); retarget fputc and ensure stack/heap sizes")

    required = {"USE_HAL_DRIVER", "STM32F407xx"}
    have = set(info.defines)
    if "USE_HAL_DRIVER" in have or info.device:
        for r in required:
            if r not in have:
                add(info, "warning", "MISSING_DEFINE",
                    f"Expected macro '{r}' for an F407 HAL project")


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(info: ProjectInfo) -> None:
    print("=== Project ===")
    print(f"  File:        {info.project_file}")
    print(f"  Target:      {info.target_name}")
    print(f"  Device:      {info.device} ({info.vendor})")
    print(f"  Pack:        {info.pack_id}")
    print(f"  Toolchain:   {info.toolchain}")
    if info.compiler:
        print(f"  Compiler:    {info.compiler}")
    if info.cpu_type:
        print(f"  CPU type:    {info.cpu_type}")
    if info.fpu:
        print(f"  FPU:         {info.fpu}")
    if info.clock_hint:
        print(f"  Clock hint:  {info.clock_hint} Hz (display only)")
    print()

    print("=== Build settings ===")
    print(f"  Output:      {info.output_dir}  name={info.output_name}  hex={info.create_hex}")
    print(f"  Optimize:    {info.optimization}")
    print(f"  Warnings:    {info.warning}")
    print(f"  C99:         {info.c99}   MicroLIB: {info.microlib}")
    print(f"  Defines:     {', '.join(info.defines)}")
    if info.scatter_file:
        print(f"  Scatter:     {info.scatter_file} (exists={info.scatter_exists})")
    print()

    print("=== Include paths ===")
    for inc in info.include_paths:
        flag = "" if inc not in info.missing_includes else "   [MISSING]"
        print(f"  {inc}{flag}")
    print()

    print("=== Memory regions ===")
    if info.memory_regions:
        for r in info.memory_regions:
            print(f"  {r.name:24} {r.kind.upper():3} {r.start}  size={r.size}")
    else:
        print("  (none parsed)")
    print()

    print("=== Debug / flash ===")
    print(f"  Probe:       {info.probe_type}")
    print(f"  Transport:   {info.transport}")
    if info.debug_clock:
        print(f"  Debug clock: {info.debug_clock} Hz")
    if info.debug_driver:
        print(f"  Debug DLL:   {info.debug_driver}")
    if info.flash_driver_dll:
        print(f"  Flash DLL:   {info.flash_driver_dll}")
    print()

    print(f"=== Source files ({len(info.source_files)}) ===")
    for sf in info.source_files:
        mark = "" if sf.exists else "   [MISSING]"
        print(f"  [{sf.group}] {sf.name} ({sf.type}) {sf.rel_path}{mark}")
    print()

    errors = [f for f in info.findings if f.severity == "error"]
    warns = [f for f in info.findings if f.severity == "warning"]
    infos = [f for f in info.findings if f.severity == "info"]

    print("=== Findings ===")
    for f in info.findings:
        tag = {"error": "ERROR", "warning": "WARN ", "info": "INFO "}[f.severity]
        print(f"  {tag} {f.code}: {f.message}")
    print()
    print(f"Summary: {len(errors)} errors, {len(warns)} warnings, {len(infos)} info")


def main() -> None:
    ap = argparse.ArgumentParser(description="Static check of a Keil STM32 project")
    ap.add_argument("target", help="Project directory or .uvprojx file")
    ap.add_argument("--json", action="store_true", help="Output JSON")
    args = ap.parse_args()

    uvprojx = locate_project(args.target)
    if uvprojx is None:
        print(f"ERROR: no .uvprojx found under '{args.target}'", file=sys.stderr)
        sys.exit(2)

    info = parse_project(uvprojx)

    if args.json:
        print(json.dumps(asdict(info), indent=2, ensure_ascii=False))
        sys.exit(1 if any(f.severity == "error" for f in info.findings) else 0)

    print_report(info)
    sys.exit(1 if any(f.severity == "error" for f in info.findings) else 0)


if __name__ == "__main__":
    main()
