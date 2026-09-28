#!/usr/bin/env python3
"""Build a Keil MDK-uVision STM32 project from the command line.

Wraps UV4.exe:
    UV4.exe -b|-r <project>.uvprojx -j0 -o <build.log>

It maps UV4 return codes, parses the build log for errors/warnings and the
final Program Size, and reports them separately. Building writes normal
outputs (Objects/Listings) into the project — do not point this at a project
the user has marked read-only.
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


# Keil MDK is often installed outside the system drive, and sometimes under the
# user profile (AppData\Local) rather than a Program Files tree. Common roots are
# therefore probed across drive letters instead of being hardcoded.
UV4_REL = r"UV4\UV4.exe"


def uv4_candidates() -> list[str]:
    """Candidate UV4.exe paths: env-expanded roots, then per-drive locations."""
    roots = [
        os.path.expandvars(r"%LOCALAPPDATA%\Keil_v5"),
        os.path.expandvars(r"%PROGRAMFILES%\Keil_v5"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Keil_v5"),
    ]
    for drive in ("C", "D", "E", "F", "G"):
        roots.append(f"{drive}:\\Keil_v5")
        roots.append(f"{drive}:\\AppData\\Local\\Keil_v5")
        roots.append(f"{drive}:\\Program Files\\Keil_v5")
    return [str(Path(r) / UV4_REL) for r in roots]

# UV4 command-line return codes
UV4_CODES = {
    0: ("clean", "no errors, no warnings"),
    1: ("warnings", "completed with warnings"),
    2: ("errors", "errors occurred"),
    3: ("cannot_write", "cannot write target file"),
    11: ("no_project", "project file not found"),
    12: ("device_unsupported", "device not supported"),
    15: ("file_read", "error reading file"),
    20: ("device_error", "device error"),
}

DIAG_RE = re.compile(
    r"^\s*(?P<file>.+?)\((?P<line>\d+)\):\s*"
    r"(?P<sev>error|warning|note)\s*:\s*(?P<msg>.*)$",
    re.IGNORECASE,
)
SIZE_RE = re.compile(r"Program Size:\s*(.+)$")
TOTAL_RE = re.compile(r"(\d+)\s*Error\(s\)\s*,\s*(\d+)\s*Warning\(s\)", re.IGNORECASE)
AXF_RE = re.compile(r"([^\s]+\.axf)\b", re.IGNORECASE)


@dataclass
class Diagnostic:
    severity: str
    file: str
    line: str
    message: str


@dataclass
class BuildResult:
    project: str
    uv4: str
    command: str
    return_code: int
    status: str
    status_detail: str
    log_file: str
    diagnostics: list[Diagnostic] = field(default_factory=list)
    program_size: str = ""
    axf: str = ""
    total_errors: int = 0
    total_warnings: int = 0


def locate_project(target: str) -> Optional[Path]:
    p = Path(target)
    if p.is_file() and p.suffix.lower() == ".uvprojx":
        return p
    if p.is_dir():
        candidates = list(p.glob("*.uvprojx"))
        mdk = p / "MDK-ARM"
        if mdk.is_dir():
            candidates += list(mdk.glob("*.uvprojx"))
        if not candidates:
            for sub in p.iterdir():
                if sub.is_dir() and (sub / "MDK-ARM").is_dir():
                    candidates += list((sub / "MDK-ARM").glob("*.uvprojx") )
        if candidates:
            return sorted(candidates, key=lambda c: len(str(c)))[0]
    return None


def find_uv4(explicit: str = "") -> Optional[str]:
    """Locate UV4.exe: --uv4, then UV4_PATH, then common locations, then PATH."""
    if explicit:
        return explicit if Path(explicit).exists() else None
    env = os.environ.get("UV4_PATH", "").strip()
    if env and Path(env).exists():
        return env
    for p in uv4_candidates():
        if Path(p).exists():
            return p
    return shutil.which("UV4.exe") or shutil.which("UV4")


def parse_log(log_path: Path) -> tuple[list[Diagnostic], str, str, int, int]:
    diags: list[Diagnostic] = []
    program_size = ""
    axf = ""
    total_errors = 0
    total_warnings = 0
    if not log_path.exists():
        return diags, program_size, axf, total_errors, total_warnings

    for raw in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.rstrip()
        m = DIAG_RE.match(line)
        if m:
            diags.append(Diagnostic(
                severity=m.group("sev").lower(),
                file=m.group("file").strip(),
                line=m.group("line"),
                message=m.group("msg").strip(),
            ))
            continue
        m = SIZE_RE.search(line)
        if m:
            program_size = m.group(1).strip()
        m = AXF_RE.search(line)
        if m and not axf:
            axf = m.group(1)
        m = TOTAL_RE.search(line)
        if m:
            total_errors = int(m.group(1))
            total_warnings = int(m.group(2))

    if not total_errors:
        total_errors = sum(1 for d in diags if d.severity == "error")
    if not total_warnings:
        total_warnings = sum(1 for d in diags if d.severity == "warning")
    return diags, program_size, axf, total_errors, total_warnings


def build(uv4: str, uvprojx: Path, rebuild: bool, log_dir: str) -> BuildResult:
    base = uvprojx.parent
    if log_dir:
        out_log = Path(log_dir) / f"{uvprojx.stem}_build.log"
        out_log.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_log = base / f"{uvprojx.stem}_build.log"

    flag = "-r" if rebuild else "-b"
    cmd = [uv4, flag, str(uvprojx), "-j0", "-o", str(out_log)]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    rc = proc.returncode
    status, detail = UV4_CODES.get(rc, ("unknown", f"unmapped return code {rc}"))

    diags, size, axf, nerr, nwarn = parse_log(out_log)

    # UV4 sometimes returns 0/1 but the log totals are authoritative.
    if nerr and status not in ("errors",):
        status = "errors"

    return BuildResult(
        project=str(uvprojx),
        uv4=uv4,
        command=" ".join(f'"{c}"' if " " in c else c for c in cmd),
        return_code=rc,
        status=status,
        status_detail=detail,
        log_file=str(out_log),
        diagnostics=diags,
        program_size=size,
        axf=axf,
        total_errors=nerr,
        total_warnings=nwarn,
    )


def print_result(r: BuildResult) -> None:
    print("=== Build ===")
    print(f"  Project:   {r.project}")
    print(f"  UV4:       {r.uv4}")
    print(f"  Command:   {r.command}")
    print(f"  Exit code: {r.return_code} ({r.status}: {r.status_detail})")
    print()

    if r.diagnostics:
        print("=== Diagnostics ===")
        for d in r.diagnostics:
            tag = {"error": "ERROR", "warning": "WARN ", "note": "NOTE "}.get(d.severity, d.severity)
            print(f"  {tag} {d.file}:{d.line}: {d.message}")
        print()

    if r.program_size:
        print(f"  Program Size: {r.program_size}")
    if r.axf:
        print(f"  Output AXF:   {r.axf}")
    print(f"  Totals: {r.total_errors} Error(s), {r.total_warnings} Warning(s)")
    print(f"  Log: {r.log_file}")

    if r.status in ("errors", "cannot_write", "no_project",
                    "device_unsupported", "file_read", "device_error"):
        print("\nBUILD FAILED.")
    elif r.status == "warnings":
        print("\nBUILD OK with warnings.")
    else:
        print("\nBUILD OK.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a Keil STM32 project")
    ap.add_argument("target", help="Project directory or .uvprojx")
    ap.add_argument("--uv4", default="", help="Path to UV4.exe")
    ap.add_argument("--rebuild", action="store_true", help="Rebuild all (-r)")
    ap.add_argument("--log-dir", default="", help="Directory for build log")
    ap.add_argument("--json", action="store_true", help="Output JSON")
    args = ap.parse_args()

    uvprojx = locate_project(args.target)
    if uvprojx is None:
        print(f"ERROR: no .uvprojx under '{args.target}'", file=sys.stderr)
        sys.exit(2)

    uv4 = find_uv4(args.uv4)
    if uv4 is None:
        print("ERROR: UV4.exe not found. Use --uv4 or set UV4_PATH", file=sys.stderr)
        sys.exit(2)

    result = build(uv4, uvprojx, args.rebuild, args.log_dir)

    if args.json:
        print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    else:
        print_result(result)

    sys.exit(1 if result.status in (
        "errors", "cannot_write", "no_project",
        "device_unsupported", "file_read", "device_error", "unknown") else 0)


if __name__ == "__main__":
    main()
