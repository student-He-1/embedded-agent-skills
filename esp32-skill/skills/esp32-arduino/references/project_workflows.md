# Arduino ESP32 Project Workflows

Use this when setting up arduino-cli, compiling, flashing, managing libraries, or working with project structure.

## arduino-cli Setup

### Locating arduino-cli

Arduino IDE 2.x bundles arduino-cli internally:

```text
E:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe
C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe
```

The skill scripts auto-detect these paths. If you installed arduino-cli separately, ensure it is on PATH.

### Configuration

arduino-cli uses a default data directory at `%LOCALAPPDATA%\Arduino15`. This is where board cores, libraries, and tools are installed.

To relocate the data directory (e.g. onto another drive), either set the
`ARDUINO_DIRECTORIES_DATA` environment variable — which this skill's scripts
honor — or create `%APPDATA%\arduino-ide\.arduinoIDE\arduino-cli.yaml`:

```yaml
directories:
  data: <your-data-dir>            # e.g. D:\ArduinoData
  downloads: <your-data-dir>\staging
```

`ARDUINO_DIRECTORIES_DATA` is preferred for CLI/agent use: it needs no IDE restart
and is read directly by `detect_board.py` when locating `esptool`.

**Note:** Arduino IDE 2.x may install cores to the default `%LOCALAPPDATA%\Arduino15` regardless of this config. If `arduino-cli core list` shows no cores but the IDE works, use the default config (no `--config-file` flag) so both share the same directory.

### Installing the ESP32 Core

Add the board manager URL in Arduino IDE:
- File → Preferences → Additional boards manager URLs
- `https://espressif.github.io/arduino-esp32/package_esp32_index.json`

Then install via Board Manager (Tools → Board → Boards Manager), search "esp32".

Or via CLI:

```powershell
arduino-cli core update-index
arduino-cli core install esp32:esp32
```

China mirror (faster downloads): use `https://espressif.github.io/arduino-esp32/package_esp32_index.json` with the `-cn` core variant, or configure a mirror in `arduino-cli.yaml`.

## FQBN Mapping

Fully Qualified Board Name format: `vendor:architecture:board[:menu_option=value]`

Common ESP32 FQBNs:

| Board | FQBN |
|-------|------|
| ESP32 Dev Module (classic) | `esp32:esp32:esp32` |
| ESP32-S3 Dev Module | `esp32:esp32:esp32s3` |
| ESP32-S2 | `esp32:esp32:esp32s2` |
| ESP32-C3 Dev Module | `esp32:esp32:esp32c3` |
| ESP32-C6 | `esp32:esp32:esp32c6` |
| Node32s | `esp32:esp32:node32s` |
| ESP32 Wrover Module | `esp32:esp32:esp32wrover` |

The skill's `arduino_build.py` accepts short names (`esp32`, `esp32s3`, etc.) and resolves them automatically.

### S3 PSRAM / Flash / USB Options

For ESP32-S3-N16R8 (16MB Flash + 8MB PSRAM), add build properties:

```powershell
arduino-cli compile --fqbn esp32:esp32:esp32s3 `
  --build-property "build.flash_size=16MB" `
  --build-property "build.psram_type=opi" `
  --build-property "build.psram_size=8MB" `
  --build-property "build.usb_mode=hwcdc" `
  <project-dir>
```

Or via FQBN menu options:

```
esp32:esp32:esp32s3:FlashSize=16MB,PSRAM=opi,USBMode=hwcdc
```

**USB Mode is critical for S3:**
- `hwcdc` (Hardware CDC and JTAG): `Serial` outputs to the native USB port (most common for S3 dev boards)
- `default` / UART0: `Serial` outputs to GPIO1/GPIO3 UART (requires external USB-UART adapter)
- If you see no serial output from the native USB port, verify USB Mode is set to Hardware CDC

Select these in the IDE Tools menu:
- Flash Size: 16MB
- PSRAM: OPI PSRAM
- USB Mode: Hardware CDC and JTAG
- Partition Scheme: choose based on needs (default is fine for most)

## Compile

```powershell
arduino-cli compile --fqbn esp32:esp32:esp32s3 <project-dir>
```

Output shows:
- Sketch size (Flash usage)
- Global variables (RAM usage)
- Warnings (separate from errors)

First compile takes 1–3 minutes (compiles the entire core). Subsequent compiles are incremental and fast (~5–10 seconds).

### Build Cache

Compiled core and libraries are cached at `%LOCALAPPDATA%\arduino\sketches\<hash>\`. This can grow large (hundreds of MB). It is safe to delete — the next compile will rebuild.

## Flash

```powershell
arduino-cli upload -p <PORT> --fqbn esp32:esp32:esp32s3 <project-dir>
```

The upload process:
1. esptool connects to the chip
2. Reads chip info (model, MAC, features)
3. Erases relevant flash sectors
4. Writes bootloader, partition table, app binary
5. Verifies written data
6. Hard resets the board

### Upload Troubleshooting

**Port busy / Permission denied (13):**
- Close Arduino IDE Serial Monitor
- Close Thonny, PuTTY, VOFA+, or any program holding the port
- Retry

**Wrong boot mode / invalid head of packet:**
- Hold BOOT button
- Press RST/EN
- Release BOOT
- Retry upload

**Could not open port:**
- Check USB cable (must be data cable, not power-only)
- Check drivers (CP210x for classic ESP32, native USB for S3)
- Reconnect the board

**S3 port changes after upload:**
- ESP32-S3 with USB-Serial/JTAG re-enumerates after reset
- The port number may stay the same but the device resets
- Wait 2 seconds before opening serial monitor

## Library Management

### Install

```powershell
arduino-cli lib install "Adafruit NeoPixel"
arduino-cli lib install "Adafruit SSD1306"
```

Libraries install to `%LOCALAPPDATA%\Arduino15\libraries\` or `%USERPROFILE%\Documents\Arduino\libraries\`.

### List installed

```powershell
arduino-cli lib list
```

### Search

```powershell
arduino-cli lib search neopixel
```

### Common ESP32 Libraries

| Library | Purpose |
|---------|---------|
| Adafruit NeoPixel | WS2812 / WS2811 RGB LEDs |
| Adafruit SSD1306 | OLED displays (I2C/SPI) |
| Adafruit GFX Library | Graphics primitives (dependency for many display libs) |
| DHT sensor library | DHT11/DHT22 temperature/humidity |
| PubSubClient | MQTT client |
| ArduinoJson | JSON parsing/serialization |
| FastLED | Advanced LED strip control |
| U8g2 | Monochrome display library |
| OneWire | 1-Wire protocol (DS18B20 etc.) |

## Project Structure

### Minimal project

```text
my_project/
└── my_project.ino    # must match directory name
```

### Multi-file project

```text
my_project/
├─ my_project.ino     # main sketch (setup + loop)
├─ config.h           # configuration constants
├─ wifi_handler.cpp   # WiFi logic
├─ wifi_handler.h
└─ sensors/
   ├─ bme280.cpp
   └─ bme280.h
```

All `.ino`, `.cpp`, `.c` files in the project directory are compiled. Header files are included as needed.

### Library in project

You can bundle a library with your project:

```text
my_project/
├─ my_project.ino
└─ src/
   └─ MyLibrary/
      ├─ MyLibrary.h
      └─ MyLibrary.cpp
```

Include with `#include "src/MyLibrary/MyLibrary.h"`.

## Partition Tables

Default partition scheme for ESP32 Arduino is "Default 4MB with spiffs" (or similar). To use a custom partition table:

1. Create a `partitions.csv` in your project directory
2. Select "Custom" in Tools → Partition Scheme
3. Or add build property: `--build-property build.partitions=partitions.csv`

Common partition schemes:
- Default: 1MB app, ~1.5MB SPIFFS/LittleFS
- Huge APP: 3MB app, no SPIFFS
- Minimal SPIFFS: ~1.9MB app, small SPIFFS
- No OTA: single app partition, more space

For OTA updates, use a partition scheme with `app0` and `app1` partitions.

## Validation Chain

Run the static checker first:

```powershell
python scripts\check_arduino_project.py <project-dir>
```

Before flashing, detect connected boards:

```powershell
python scripts\detect_board.py
```

Compile:

```powershell
python scripts\arduino_build.py <project-dir> --board esp32s3
```

Flash:

```powershell
python scripts\arduino_upload.py <project-dir> --port <PORT> --board esp32s3
```

Verify with serial:

```powershell
python scripts\serial_monitor.py --port <PORT> --baud 115200 --duration 10
```

Report validation levels separately: source inspection → compile → flash → serial output → physical behavior.
