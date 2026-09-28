#!/usr/bin/env python3
"""Static checker for MicroPython ESP32 projects.

Checks local .py files for syntax errors, common MicroPython pitfalls,
project structure (boot.py, main.py, lib/), and pin usage.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


@dataclass
class Message:
    level: str  # info / warning / error
    text: str
    path: str | None = None


@dataclass
class ProjectInfo:
    has_boot_py: bool = False
    has_main_py: bool = False
    has_lib_dir: bool = False
    py_files: list[str] = field(default_factory=list)
    pins_used: dict[str, list[str]] = field(default_factory=dict)
    imports: list[str] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)

    def add(self, level: str, text: str, path: str | None = None):
        self.messages.append(Message(level=level, text=text, path=path))


# ESP32 strapping / restricted pins (classic ESP32)
RESTRICTED_PINS = {
    0: "Boot strapping pin (low = download mode)",
    1: "UART0 TX (connected to USB-UART, REPL)",
    3: "UART0 RX (connected to USB-UART, REPL)",
    6: "SPI flash (do not use)",
    7: "SPI flash (do not use)",
    8: "SPI flash (do not use)",
    9: "SPI flash (do not use)",
    10: "SPI flash (do not use)",
    11: "SPI flash (do not use)",
}

INPUT_ONLY_PINS = {34, 35, 36, 39}  # ESP32 classic input-only GPIOs


def check_syntax(filepath: Path, info: ProjectInfo):
    """Check Python syntax using ast.parse."""
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
        return tree, source
    except SyntaxError as e:
        info.add("error", f"Syntax error: {e.msg} (line {e.lineno})", str(filepath))
        return None, ""


def check_imports(tree: ast.AST, filepath: Path, info: ProjectInfo):
    """Extract and check imports."""
    if not tree:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                info.imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                info.imports.append(node.module)


def check_pins(source: str, filepath: Path, info: ProjectInfo):
    """Check for potentially problematic pin usage."""
    # Find Pin(n, ...) or Pin('n', ...) patterns
    pin_patterns = [
        r"Pin\(\s*(\d+)\s*,",
        r"Pin\(\s*['\"](\d+)['\"]\s*,",
        r"machine\.Pin\(\s*(\d+)\s*,",
    ]
    for pattern in pin_patterns:
        for m in re.finditer(pattern, source):
            pin_num = int(m.group(1))
            rel = str(filepath)
            if pin_num in RESTRICTED_PINS:
                info.add("warning", f"GPIO{pin_num} is restricted: {RESTRICTED_PINS[pin_num]}", rel)
            if pin_num in INPUT_ONLY_PINS and "OUT" in source[m.start():m.start() + 50]:
                info.add("error", f"GPIO{pin_num} is input-only, cannot be used as output", rel)
            info.pins_used.setdefault(f"GPIO{pin_num}", []).append(rel)


def check_common_mistakes(source: str, filepath: Path, info: ProjectInfo):
    """Check for common MicroPython mistakes."""
    rel = str(filepath)

    # time.sleep in interrupt context (heuristic)
    if "def " in source and "irq(" in source and "time.sleep" in source:
        info.add("warning", "time.sleep() may be called in interrupt context — avoid blocking in ISRs", rel)

    # Using print() in tight loops (heuristic)
    if "while True" in source and "print(" in source:
        info.add("info", "print() in while True loop — may slow down execution and fill serial buffer", rel)

    # Missing main.py
    if filepath.name == "boot.py" and "import webrepl" in source:
        info.add("info", "webrepl is imported in boot.py — ensure it is configured", rel)

    # Using CPython-only modules
    cpython_only = ["tkinter", "requests", "numpy", "pandas", "os.system", "subprocess"]
    for mod in cpython_only:
        if mod in source:
            info.add("warning", f"'{mod}' is not available in MicroPython", rel)

    # Pin.OUT without value (should be fine, but check)
    if "Pin.OUT" in source and "Pin(" in source:
        pass  # Valid usage

    # PWM duty range check (0-1023 for ESP32)
    pwm_duty = re.findall(r"duty\(\s*(\d+)\s*\)", source)
    for d in pwm_duty:
        val = int(d)
        if val > 1023:
            info.add("warning", f"PWM duty {val} exceeds max 1023 on ESP32", rel)


def check_project_structure(root: Path, info: ProjectInfo):
    """Check project layout."""
    boot = root / "boot.py"
    main = root / "main.py"
    lib = root / "lib"

    if boot.exists():
        info.has_boot_py = True
        info.add("info", "boot.py found")
    else:
        info.add("info", "No boot.py — board will use default boot sequence")

    if main.exists():
        info.has_main_py = True
        info.add("info", "main.py found (will run on boot)")
    else:
        info.add("warning", "No main.py — nothing will run automatically after boot")

    if lib.exists() and lib.is_dir():
        info.has_lib_dir = True
        lib_files = list(lib.rglob("*.py"))
        info.add("info", f"lib/ directory found with {len(lib_files)} module(s)")


def run_checks(root: Path) -> ProjectInfo:
    info = ProjectInfo()
    root = root.resolve()

    if not root.exists():
        info.add("error", f"Project directory does not exist: {root}")
        return info

    check_project_structure(root, info)

    # Find all .py files (skip lib if too deep? include all)
    py_files = sorted(root.rglob("*.py"))
    for f in py_files:
        # Skip hidden directories and __pycache__
        if any(part.startswith(".") or part == "__pycache__" for part in f.parts):
            continue
        rel_path = str(f.relative_to(root))
        info.py_files.append(rel_path)

        tree, source = check_syntax(f, info)
        if tree:
            check_imports(tree, f, info)
        if source:
            check_pins(source, f, info)
            check_common_mistakes(source, f, info)

    # Summary
    errors = [m for m in info.messages if m.level == "error"]
    warnings = [m for m in info.messages if m.level == "warning"]
    infos = [m for m in info.messages if m.level == "info"]
    info.add("info", f"Check complete: {len(errors)} error(s), {len(warnings)} warning(s), {len(infos)} info(s).")

    return info


def print_report(info: ProjectInfo):
    print("=" * 60)
    print("MicroPython Project Check Report")
    print("=" * 60)
    print(f"boot.py      : {'yes' if info.has_boot_py else 'no'}")
    print(f"main.py      : {'yes' if info.has_main_py else 'no'}")
    print(f"lib/         : {'yes' if info.has_lib_dir else 'no'}")
    print(f"Python files : {len(info.py_files)}")
    if info.imports:
        print(f"Imports      : {', '.join(sorted(set(info.imports))[:10])}")
    if info.pins_used:
        print(f"Pins used    : {', '.join(sorted(info.pins_used.keys()))}")
    print("-" * 60)

    for msg in info.messages:
        prefix = {"error": "ERROR", "warning": "WARN ", "info": "INFO "}[msg.level]
        location = f" [{msg.path}]" if msg.path else ""
        print(f"[{prefix}] {msg.text}{location}")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Static checker for MicroPython ESP32 projects")
    parser.add_argument("project_dir", nargs="?", default=".", help="Project directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    root = Path(args.project_dir)
    info = run_checks(root)

    if args.json:
        from dataclasses import asdict
        print(json.dumps(asdict(info), indent=2, ensure_ascii=False))
    else:
        print_report(info)

    errors = [m for m in info.messages if m.level == "error"]
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
