#!/usr/bin/env python3
"""Static checker for Espressif ESP32 projects (ESP-IDF / Arduino / PlatformIO)."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

GENERATED_NAMES = {"sdkconfig.h", "bootloader.bin", "partition-table.bin", "app_update.bin"}
BUILD_DIRS = {"build", ".pioenvs", ".piolibdeps", ".pio"}
SKIP_DIRS = {".git", ".svn", ".hg", ".agents", ".claude", ".codex", "__pycache__", "managed_components"}
FRAMEWORK_DIR_NAMES = {
    "main", "components", "app", "apps", "application", "bsp", "board",
    "components", "core", "drivers", "hal", "middleware", "tasks", "src",
}

KNOWN_TARGETS = {
    "esp32": "ESP32 (Xtensa)",
    "esp32s2": "ESP32-S2 (Xtensa)",
    "esp32s3": "ESP32-S3 (Xtensa, USB-JTAG)",
    "esp32c3": "ESP32-C3 (RISC-V, USB-JTAG)",
    "esp32c6": "ESP32-C6 (RISC-V, WiFi6+BT5+Thread)",
    "esp32h2": "ESP32-H2 (RISC-V, Thread+Zigbee)",
}

FLASH_SIZES = {"1MB", "2MB", "4MB", "8MB", "16MB", "32MB", "64MB", "128MB"}


@dataclass
class Message:
    level: str  # info / warning / error
    text: str
    path: str | None = None


@dataclass
class ProjectInfo:
    project_type: str = "unknown"  # esp-idf / arduino / platformio / mixed
    target_chip: str | None = None
    target_arch: str | None = None  # xtensa / riscv
    flash_size: str | None = None
    flash_mode: str | None = None
    flash_freq: str | None = None
    partition_table: str | None = None
    wifi_enabled: bool = False
    bt_enabled: bool = False
    freertos_hz: int | None = None
    components: list[str] = field(default_factory=list)
    main_sources: list[str] = field(default_factory=list)
    build_outputs: list[str] = field(default_factory=list)
    sdkconfig_path: str | None = None
    cmakelists_path: str | None = None
    platformio_ini_path: str | None = None
    arduino_ino_path: str | None = None
    messages: list[Message] = field(default_factory=list)

    def add(self, level: str, text: str, path: str | None = None):
        self.messages.append(Message(level=level, text=text, path=path))


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def iter_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and d not in BUILD_DIRS]
        for fn in filenames:
            yield Path(dirpath) / fn


def is_build_path(path: Path, root: Path) -> bool:
    try:
        rel_path = path.relative_to(root)
        return any(part in BUILD_DIRS for part in rel_path.parts)
    except ValueError:
        return False


def detect_project_type(root: Path, info: ProjectInfo):
    """Detect ESP-IDF / Arduino / PlatformIO project type."""
    cmakelists = root / "CMakeLists.txt"
    platformio_ini = root / "platformio.ini"
    ino_files = list(root.rglob("*.ino"))

    is_idf = False
    if cmakelists.exists():
        content = read_text(cmakelists)
        if "IDF_PATH" in content or "project.cmake" in content or "idf_component_register" in content:
            is_idf = True
        info.cmakelists_path = rel(cmakelists, root)

    if platformio_ini.exists():
        info.platformio_ini_path = rel(platformio_ini, root)

    if ino_files:
        info.arduino_ino_path = rel(ino_files[0], root)

    if is_idf and platformio_ini.exists():
        info.project_type = "mixed (esp-idf + platformio)"
        info.add("warning", "Project contains both ESP-IDF CMakeLists and platformio.ini; clarify the active build system.")
    elif is_idf:
        info.project_type = "esp-idf"
    elif platformio_ini.exists() and ino_files:
        info.project_type = "platformio (arduino)"
    elif platformio_ini.exists():
        info.project_type = "platformio"
    elif ino_files:
        info.project_type = "arduino"
    else:
        info.project_type = "unknown"
        info.add("error", "No recognized ESP-IDF, Arduino, or PlatformIO project structure found.")


def parse_sdkconfig(root: Path, info: ProjectInfo):
    """Parse sdkconfig for key settings."""
    sdkconfig = root / "sdkconfig"
    if not sdkconfig.exists():
        # Try sdkconfig.defaults
        defaults = root / "sdkconfig.defaults"
        if defaults.exists():
            sdkconfig = defaults
            info.add("info", "No sdkconfig found; using sdkconfig.defaults for inspection. Run 'idf.py set-target <chip>' to generate sdkconfig.")
        else:
            info.add("warning", "No sdkconfig or sdkconfig.defaults found. Target chip and flash settings are unknown.")
            return

    info.sdkconfig_path = rel(sdkconfig, root)
    content = read_text(sdkconfig)

    # Target chip
    m = re.search(r'^CONFIG_IDF_TARGET="(\w+)"', content, re.MULTILINE)
    if m:
        info.target_chip = m.group(1)
        if info.target_chip in KNOWN_TARGETS:
            info.add("info", f"Target chip: {KNOWN_TARGETS[info.target_chip]} (CONFIG_IDF_TARGET={info.target_chip})")
            if info.target_chip in ("esp32c3", "esp32c6", "esp32h2"):
                info.target_arch = "riscv"
            else:
                info.target_arch = "xtensa"
        else:
            info.add("warning", f"Unrecognized target chip '{info.target_chip}'. Known: {', '.join(KNOWN_TARGETS.keys())}")
    else:
        info.add("warning", "CONFIG_IDF_TARGET not found in sdkconfig. Run 'idf.py set-target <chip>'.")

    # Flash size
    m = re.search(r'^CONFIG_ESPTOOLPY_FLASHSIZE_(\w+)=y', content, re.MULTILINE)
    if m:
        info.flash_size = m.group(1)
        info.add("info", f"Flash size: {info.flash_size}")
    else:
        m = re.search(r'^CONFIG_ESPTOOLPY_FLASHSIZE="(\w+)"', content, re.MULTILINE)
        if m:
            info.flash_size = m.group(1)

    # Flash mode
    m = re.search(r'^CONFIG_ESPTOOLPY_FLASHMODE_(\w+)=y', content, re.MULTILINE)
    if m:
        info.flash_mode = m.group(1)

    # Flash frequency
    m = re.search(r'^CONFIG_ESPTOOLPY_FLASHFREQ_(\w+)=y', content, re.MULTILINE)
    if m:
        info.flash_freq = m.group(1)

    # Partition table
    m = re.search(r'^CONFIG_PARTITION_TABLE_CUSTOM_FILENAME="([^"]+)"', content, re.MULTILINE)
    if m:
        info.partition_table = m.group(1)
        info.add("info", f"Custom partition table: {info.partition_table}")
    elif re.search(r'^CONFIG_PARTITION_TABLE_SINGLE_APP=y', content, re.MULTILINE):
        info.partition_table = "single_app (default)"
    elif re.search(r'^CONFIG_PARTITION_TABLE_TWO_OTA=y', content, re.MULTILINE):
        info.partition_table = "two_ota (default)"

    # WiFi
    if re.search(r'^CONFIG_ESP_WIFI_ENABLED=y', content, re.MULTILINE):
        info.wifi_enabled = True
        info.add("info", "WiFi is enabled.")

    # Bluetooth
    if re.search(r'^CONFIG_BT_ENABLED=y', content, re.MULTILINE):
        info.bt_enabled = True
        info.add("info", "Bluetooth is enabled.")
        if re.search(r'^CONFIG_BTDM_CTRL_MODE_BLE_ONLY=y', content, re.MULTILINE):
            info.add("info", "Bluetooth mode: BLE only.")
        elif re.search(r'^CONFIG_BTDM_CTRL_MODE_BR_EDR_ONLY=y', content, re.MULTILINE):
            info.add("info", "Bluetooth mode: Classic only.")
        elif re.search(r'^CONFIG_BTDM_CTRL_MODE_BTDM=y', content, re.MULTILINE):
            info.add("info", "Bluetooth mode: Dual mode (Classic + BLE).")

    # FreeRTOS tick rate
    m = re.search(r'^CONFIG_FREERTOS_HZ=(\d+)', content, re.MULTILINE)
    if m:
        info.freertos_hz = int(m.group(1))
        info.add("info", f"FreeRTOS tick rate: {info.freertos_hz} Hz")

    # Check for common issues
    if info.target_chip == "esp32s3" and not re.search(r'^CONFIG_ESP_CONSOLE_UART_DEFAULT=y', content, re.MULTILINE):
        if re.search(r'^CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y', content, re.MULTILINE):
            info.add("info", "Console output routed to USB-Serial-JTAG (built-in). Ensure the USB-JTAG port is used for monitoring.")

    # PSRAM
    if re.search(r'^CONFIG_SPIRAM=y', content, re.MULTILINE):
        info.add("info", "PSRAM (external RAM) is enabled.")
        if re.search(r'^CONFIG_SPIRAM_MODE_OCT=y', content, re.MULTILINE):
            info.add("info", "PSRAM mode: Octal (8-bit).")
        elif re.search(r'^CONFIG_SPIRAM_MODE_QUAD=y', content, re.MULTILINE):
            info.add("info", "PSRAM mode: Quad (4-bit).")


def check_partitions(root: Path, info: ProjectInfo):
    """Validate partitions.csv if custom partition table is used."""
    if not info.partition_table or info.partition_table.startswith("single_app") or info.partition_table.startswith("two_ota"):
        return

    part_path = root / info.partition_table
    if not part_path.exists():
        # Try common locations
        candidates = list(root.rglob(info.partition_table))
        if candidates:
            part_path = candidates[0]
        else:
            info.add("error", f"Custom partition table '{info.partition_table}' not found.", info.partition_table)
            return

    info.add("info", f"Parsing partition table: {rel(part_path, root)}")
    try:
        content = read_text(part_path)
        reader = csv.DictReader([line for line in content.splitlines() if not line.strip().startswith("#") and line.strip()])
        partitions = list(reader)
        total_size = 0
        for p in partitions:
            name = p.get("Name", p.get("name", "?"))
            ptype = p.get("Type", p.get("type", "?"))
            subtype = p.get("SubType", p.get("subtype", "?"))
            offset = p.get("Offset", p.get("offset", ""))
            size = p.get("Size", p.get("size", "?"))
            info.add("info", f"  Partition: {name} ({ptype}/{subtype}) offset={offset} size={size}")

        # Check for app partition
        app_parts = [p for p in partitions if p.get("Type", "").lower() in ("app", "0")]
        if not app_parts:
            info.add("warning", "No app partition found in partition table. The firmware will not boot.")
    except Exception as e:
        info.add("error", f"Failed to parse partition table: {e}", rel(part_path, root))


def check_cmakelists(root: Path, info: ProjectInfo):
    """Check project and component CMakeLists.txt."""
    top_cmake = root / "CMakeLists.txt"
    if not top_cmake.exists():
        return

    content = read_text(top_cmake)
    if "project(" not in content and "cmake_minimum_required" not in content:
        info.add("warning", "Top-level CMakeLists.txt does not look like a standard ESP-IDF project (missing project() or cmake_minimum_required).", "CMakeLists.txt")

    # Check main component
    main_cmake = root / "main" / "CMakeLists.txt"
    if main_cmake.exists():
        main_content = read_text(main_cmake)
        if "idf_component_register" not in main_content:
            info.add("warning", "main/CMakeLists.txt does not contain idf_component_register().", "main/CMakeLists.txt")
        # Find source files
        src_matches = re.findall(r'SRCS?\s+([^)]+)', main_content, re.DOTALL)
        for match in src_matches:
            files = re.findall(r'[\w./-]+\.(c|cpp|cc|cxx)', match)
            info.main_sources.extend(files)
    else:
        info.add("warning", "main/CMakeLists.txt not found. ESP-IDF projects require a main component.", "main/")

    # Check components directory
    components_dir = root / "components"
    if components_dir.exists() and components_dir.is_dir():
        for comp in sorted(components_dir.iterdir()):
            if comp.is_dir():
                info.components.append(comp.name)
                comp_cmake = comp / "CMakeLists.txt"
                if not comp_cmake.exists():
                    info.add("warning", f"Component '{comp.name}' has no CMakeLists.txt.", rel(comp, root))
        if info.components:
            info.add("info", f"Local components: {', '.join(info.components)}")

    # Check managed_components
    managed_dir = root / "managed_components"
    if managed_dir.exists():
        managed = [d.name for d in managed_dir.iterdir() if d.is_dir()]
        if managed:
            info.add("info", f"Managed components (idf-component-manager): {len(managed)} packages")


def check_arduino(root: Path, info: ProjectInfo):
    """Check Arduino-ESP32 project structure."""
    ino_files = list(root.rglob("*.ino"))
    if not ino_files:
        return

    info.add("info", f"Arduino sketch: {rel(ino_files[0], root)}")

    # Check for arduino-cli or platformio
    if not info.platformio_ini_path:
        info.add("info", "Pure Arduino project. Build with 'arduino-cli compile --fqbn esp32:esp32:<board>'.")

    # Check for common libraries
    src_content = read_text(ino_files[0])
    if "WiFi.h" in src_content:
        info.wifi_enabled = True
        info.add("info", "Arduino WiFi library detected.")
    if "BluetoothSerial.h" in src_content or "BLEDevice.h" in src_content:
        info.bt_enabled = True
        info.add("info", "Arduino Bluetooth library detected.")


def check_platformio(root: Path, info: ProjectInfo):
    """Check PlatformIO project configuration."""
    ini_path = root / "platformio.ini"
    if not ini_path.exists():
        return

    content = read_text(ini_path)
    info.add("info", "PlatformIO project detected.")

    # Parse platform
    m = re.search(r'^platform\s*=\s*espressif(\d+)\s*$', content, re.MULTILINE)
    if m:
        info.add("info", f"PlatformIO platform: espressif{m.group(1)}")

    # Parse board
    m = re.search(r'^board\s*=\s*(\S+)', content, re.MULTILINE)
    if m:
        info.add("info", f"PlatformIO board: {m.group(1)}")

    # Parse framework
    frameworks = re.findall(r'^framework\s*=\s*(.+)$', content, re.MULTILINE)
    if frameworks:
        info.add("info", f"PlatformIO framework(s): {frameworks[0].strip()}")

    # Parse upload port
    m = re.search(r'^upload_port\s*=\s*(\S+)', content, re.MULTILINE)
    if m:
        info.add("info", f"Upload port configured: {m.group(1)}")

    # Parse monitor speed
    m = re.search(r'^monitor_speed\s*=\s*(\d+)', content, re.MULTILINE)
    if m:
        info.add("info", f"Monitor baud: {m.group(1)}")


def check_build_outputs(root: Path, info: ProjectInfo):
    """Check for existing build outputs."""
    build_dir = root / "build"
    if build_dir.exists():
        # Look for app binary
        app_bins = list(build_dir.rglob("*.bin"))
        elf_files = list(build_dir.rglob("*.elf"))
        if app_bins:
            info.build_outputs.extend(rel(b, root) for b in app_bins[:5])
            info.add("info", f"Build output found: {len(app_bins)} .bin file(s) in build/")
        if elf_files:
            info.add("info", f"Build output found: {len(elf_files)} .elf file(s) in build/")

        # Check for project-specific binary
        project_name = root.name
        project_bin = build_dir / f"{project_name}.bin"
        if project_bin.exists():
            info.add("info", f"Project binary: {rel(project_bin, root)} ({project_bin.stat().st_size} bytes)")
    else:
        pio_build = root / ".pio"
        if pio_build.exists():
            info.add("info", "PlatformIO build directory found (.pio/).")
        else:
            info.add("info", "No build output found. Run 'idf.py build' or 'pio run' before flashing.")


def check_source_files(root: Path, info: ProjectInfo):
    """Check main source files for common patterns."""
    main_dir = root / "main"
    if not main_dir.exists():
        return

    c_files = list(main_dir.rglob("*.c")) + list(main_dir.rglob("*.cpp"))
    for f in c_files:
        content = read_text(f)
        rel_path = rel(f, root)

        # Check for app_main
        if "app_main" in content:
            info.add("info", f"Entry point app_main() found in {rel_path}")

        # Check for common mistakes
        if "vTaskDelay(" in content and "portTICK_PERIOD_MS" not in content and "pdMS_TO_TICKS" not in content:
            info.add("warning", f"vTaskDelay() called without pdMS_TO_TICKS()/portTICK_PERIOD_MS in {rel_path}. Raw tick values depend on CONFIG_FREERTOS_HZ.", rel_path)

        # Check for WiFi without nvs_flash_init
        if "esp_wifi_start" in content and "nvs_flash_init" not in content:
            info.add("warning", f"WiFi started without nvs_flash_init() in {rel_path}. WiFi requires NVS flash initialization first.", rel_path)

        # Check for GPIO on strapping pins
        for pin in ["GPIO_NUM_0", "GPIO_NUM_46", "GPIO0", "GPIO46"]:
            if pin in content:
                info.add("warning", f"Strapping pin {pin} referenced in {rel_path}. Verify this does not interfere with boot mode.", rel_path)


def run_checks(root: Path) -> ProjectInfo:
    info = ProjectInfo()
    root = root.resolve()

    if not root.exists():
        info.add("error", f"Project directory does not exist: {root}")
        return info

    detect_project_type(root, info)

    if info.project_type in ("esp-idf", "mixed (esp-idf + platformio)"):
        parse_sdkconfig(root, info)
        check_partitions(root, info)
        check_cmakelists(root, info)
        check_source_files(root, info)

    if info.project_type in ("arduino", "platformio (arduino)", "mixed (esp-idf + platformio)"):
        check_arduino(root, info)

    if info.project_type in ("platformio", "platformio (arduino)", "mixed (esp-idf + platformio)"):
        check_platformio(root, info)

    check_build_outputs(root, info)

    # Summary
    errors = [m for m in info.messages if m.level == "error"]
    warnings = [m for m in info.messages if m.level == "warning"]
    infos = [m for m in info.messages if m.level == "info"]

    info.add("info", f"Check complete: {len(errors)} error(s), {len(warnings)} warning(s), {len(infos)} info(s).")

    return info


def print_report(info: ProjectInfo, root: Path):
    """Print human-readable report."""
    print("=" * 70)
    print("ESP32 Project Check Report")
    print("=" * 70)
    print(f"Project type : {info.project_type}")
    print(f"Target chip  : {info.target_chip or 'unknown'} ({info.target_arch or 'unknown'})")
    print(f"Flash size   : {info.flash_size or 'unknown'}")
    print(f"Flash mode   : {info.flash_mode or 'default'}")
    print(f"Flash freq   : {info.flash_freq or 'default'}")
    print(f"Partitions   : {info.partition_table or 'default'}")
    print(f"WiFi         : {'enabled' if info.wifi_enabled else 'not detected'}")
    print(f"Bluetooth    : {'enabled' if info.bt_enabled else 'not detected'}")
    print(f"FreeRTOS Hz  : {info.freertos_hz or 'default'}")
    print(f"Components   : {', '.join(info.components) if info.components else 'none'}")
    print("-" * 70)

    for msg in info.messages:
        prefix = {"error": "ERROR", "warning": "WARN ", "info": "INFO "}[msg.level]
        location = f" [{msg.path}]" if msg.path else ""
        print(f"[{prefix}] {msg.text}{location}")

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Static checker for ESP32 projects (ESP-IDF / Arduino / PlatformIO)")
    parser.add_argument("project_dir", help="Path to the ESP32 project directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--probe", action="store_true", help="Also detect connected ESP32 devices")
    args = parser.parse_args()

    root = Path(args.project_dir)
    info = run_checks(root)

    if args.probe:
        try:
            from detect_esp_device import detect_devices
            devices = detect_devices()
            if devices:
                info.add("info", f"Connected devices: {len(devices)}")
                for d in devices:
                    info.add("info", f"  - {d}")
            else:
                info.add("warning", "No ESP32 devices detected. This is inconclusive — check USB connections and drivers.")
        except ImportError:
            info.add("warning", "detect_esp_device.py not found; skipping probe detection.")
        except Exception as e:
            info.add("warning", f"Probe detection failed: {e}")

    if args.json:
        print(json.dumps(asdict(info), indent=2, ensure_ascii=False))
    else:
        print_report(info, root)

    errors = [m for m in info.messages if m.level == "error"]
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
