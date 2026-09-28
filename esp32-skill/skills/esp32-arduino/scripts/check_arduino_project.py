#!/usr/bin/env python3
"""Static checker for ESP32 Arduino projects."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Message:
    level: str  # error, warning, info
    text: str
    path: str | None = None
    line: int | None = None


# ESP32 classic input-only pins
ESP32_INPUT_ONLY = {34, 35, 36, 39}
# ESP32 classic flash pins (never use)
ESP32_FLASH_PINS = {6, 7, 8, 9, 10, 11}
# ESP32-S3 flash pins
ESP32S3_FLASH_PINS = {6, 7, 8, 9, 10, 11}
# ESP32-S3 non-existent pins on QFN56
ESP32S3_MISSING_PINS = set(range(22, 33))
# Strapping pins (all variants)
STRAPPING_PINS = {0, 2, 5, 12, 15, 45, 46}

KNOWN_ESP32_LIBS = {
    "WiFi.h", "WiFiClient.h", "WiFiServer.h", "WiFiUdp.h",
    "BluetoothSerial.h", "BLEDevice.h", "BLEUtils.h", "BLEServer.h",
    "Wire.h", "SPI.h", "HardwareSerial.h", "EEPROM.h",
    "Preferences.h", "FS.h", "SPIFFS.h", "LittleFS.h", "SD.h",
    "ESP32PWM.h", "ESP32Servo.h", "Ticker.h", "driver/ledc.h",
    "Adafruit_NeoPixel.h", "Adafruit_GFX.h", "Adafruit_SSD1306.h",
    "DHT.h", "OneWire.h", "DallasTemperature.h",
    "PubSubClient.h", "ArduinoJson.h", "HTTPClient.h",
    "WebServer.h", "ESPAsyncWebServer.h", "AsyncTCP.h",
    "FastLED.h", "U8g2lib.h", "LiquidCrystal_I2C.h",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def find_ino_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.ino"))


def find_source_files(root: Path) -> list[Path]:
    exts = {".ino", ".cpp", ".c", ".h", ".hpp"}
    return sorted(
        p for p in root.rglob("*")
        if p.suffix.lower() in exts
        and "build" not in p.parts
        and ".git" not in p.parts
    )


def extract_includes(source: str) -> list[str]:
    return re.findall(r'#include\s+[<"]([^>"]+)[>"]', source)


def extract_pin_modes(source: str) -> list[tuple[int, str, int]]:
    """Return (pin_number, mode, line_number) for pinMode calls."""
    results = []
    for i, line in enumerate(source.splitlines(), 1):
        m = re.search(r'pinMode\s*\(\s*(\d+)\s*,\s*(OUTPUT|INPUT|INPUT_PULLUP)\s*\)', line)
        if m:
            results.append((int(m.group(1)), m.group(2), i))
    return results


def extract_digital_writes(source: str) -> list[tuple[int, int]]:
    """Return (pin_number, line_number) for digitalWrite calls."""
    results = []
    for i, line in enumerate(source.splitlines(), 1):
        m = re.search(r'digitalWrite\s*\(\s*(\d+)\s*,', line)
        if m:
            results.append((int(m.group(1)), i))
    return results


def check_project(project_dir: Path) -> list[Message]:
    messages: list[Message] = []

    if not project_dir.exists():
        messages.append(Message("error", f"Project directory does not exist: {project_dir}"))
        return messages

    ino_files = find_ino_files(project_dir)
    if not ino_files:
        messages.append(Message("error", "No .ino file found. Arduino projects require at least one .ino entrypoint."))
        return messages

    main_ino = ino_files[0]
    messages.append(Message("info", f"Entrypoint: {main_ino.name}", str(main_ino)))

    # Combine all source for analysis
    all_source = ""
    source_files = find_source_files(project_dir)
    for sf in source_files:
        all_source += read_text(sf) + "\n"

    # Check setup() and loop()
    if "void setup(" not in all_source and "void setup (" not in all_source:
        messages.append(Message("error", "setup() function not found. Arduino sketches require setup()."))
    if "void loop(" not in all_source and "void loop (" not in all_source:
        messages.append(Message("error", "loop() function not found. Arduino sketches require loop()."))

    # Check includes
    includes = extract_includes(all_source)
    external_includes = [inc for inc in includes if not inc.startswith("Arduino.h")]
    if external_includes:
        messages.append(Message("info", f"Library dependencies: {', '.join(sorted(set(external_includes)))}"))

    # Check pin usage
    all_pins = set()
    for pin, mode, line in extract_pin_modes(all_source):
        all_pins.add(pin)
        if pin in ESP32_FLASH_PINS:
            messages.append(Message("error", f"GPIO{pin} is connected to SPI flash. Never use as GPIO.", str(main_ino), line))
        if pin in ESP32_INPUT_ONLY and mode == "OUTPUT":
            messages.append(Message("error", f"GPIO{pin} is input-only on ESP32. Cannot use OUTPUT.", str(main_ino), line))
        if pin in STRAPPING_PINS and mode == "OUTPUT":
            messages.append(Message("warning", f"GPIO{pin} is a strapping pin. Output state at boot may affect boot mode.", str(main_ino), line))

    for pin, line in extract_digital_writes(all_source):
        all_pins.add(pin)
        if pin in ESP32_FLASH_PINS:
            messages.append(Message("error", f"GPIO{pin} is connected to SPI flash. Never use digitalWrite.", str(main_ino), line))
        if pin in ESP32_INPUT_ONLY:
            messages.append(Message("warning", f"GPIO{pin} is input-only. digitalWrite will have no effect.", str(main_ino), line))

    # Check for common mistakes
    if "Serial.begin(" in all_source and "while (!Serial)" in all_source:
        messages.append(Message("info", "Uses while(!Serial) — note this blocks forever on native USB if no monitor opens."))

    if "delay(" in all_source:
        delay_count = len(re.findall(r'delay\s*\(', all_source))
        if delay_count > 5:
            messages.append(Message("warning", f"Found {delay_count} delay() calls. Consider non-blocking timing with millis() for responsive sketches."))

    # Check for ESP32-specific APIs
    if "WiFi.begin(" in all_source:
        messages.append(Message("info", "WiFi usage detected. Ensure WiFi credentials are not hardcoded in shared code."))
    if "analogWrite(" in all_source:
        messages.append(Message("warning", "analogWrite() is deprecated on ESP32 Arduino core 3.x. Use ledcWrite() / LEDC API instead."))

    # Check for large stack allocations
    for i, line in enumerate(all_source.splitlines(), 1):
        m = re.search(r'(char|byte|uint8_t|int|float)\s+\w+\s*\[\s*(\d+)\s*\]', line)
        if m and int(m.group(2)) > 2048:
            messages.append(Message("warning", f"Large local array ({m.group(2)} elements) may cause stack overflow. Consider static or dynamic allocation.", None, i))

    if not any(m.level == "error" for m in messages):
        messages.append(Message("info", "Static check passed with no errors."))

    return messages


def main() -> None:
    parser = argparse.ArgumentParser(description="Static check for ESP32 Arduino projects")
    parser.add_argument("project_dir", help="Path to the Arduino project directory")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    messages = check_project(project_dir)

    if args.json:
        print(json.dumps([asdict(m) for m in messages], indent=2, ensure_ascii=False))
        return

    for m in messages:
        prefix = {"error": "ERROR", "warning": "WARN ", "info": "INFO "}[m.level]
        loc = ""
        if m.path:
            loc = f" [{Path(m.path).name}"
            if m.line:
                loc += f":{m.line}"
            loc += "]"
        print(f"  {prefix} {m.text}{loc}")

    errors = sum(1 for m in messages if m.level == "error")
    warnings = sum(1 for m in messages if m.level == "warning")
    print(f"\n{errors} error(s), {warnings} warning(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
