# ESP-IDF And Project Workflows

Use this when editing `sdkconfig`, `CMakeLists.txt`, building, or flashing ESP-IDF, Arduino-ESP32, or PlatformIO projects.

## sdkconfig Editing

Treat `sdkconfig` as the editable source for chip target, flash configuration, partition table, component enables, WiFi/BT stack, FreeRTOS, and security settings.

Preserve formatting:

```text
# Automatically generated file. DO NOT EDIT.
# Espressif IoT Development Framework (ESP-IDF) ...
CONFIG_IDF_TARGET="esp32s3"
CONFIG_ESPTOOLPY_FLASHSIZE_4MB=y
# CONFIG_ESPTOOLPY_FLASHSIZE_2MB is not set
```

- `KEY=VALUE` lines set a config option.
- `# CONFIG_XXX is not set` lines explicitly disable an option.
- Do not rewrite the whole file; change only the needed keys.
- After editing `sdkconfig`, run `idf.py reconfigure` or `idf.py build` to regenerate `build/config/sdkconfig.h`.
- For persistent defaults that survive `idf.py fullclean`, put them in `sdkconfig.defaults`.

Editing strategy:

1. Find the key in the existing `sdkconfig` or in `sdkconfig.defaults`.
2. If the key is absent, check the component's `Kconfig` file for the correct symbol name and type.
3. Change only that key. Do not remove unrelated `# CONFIG_... is not set` lines.
4. Run `idf.py reconfigure` to validate.
5. Inspect `build/config/sdkconfig.h` for the generated `#define` values.

Common keys:

```text
CONFIG_IDF_TARGET="esp32s3"           # Target chip
CONFIG_ESPTOOLPY_FLASHSIZE_4MB=y      # Flash size
CONFIG_ESPTOOLPY_FLASHMODE_DIO=y      # Flash mode (dio/qio/dout/qout)
CONFIG_ESPTOOLPY_FLASHFREQ_80M=y      # Flash frequency
CONFIG_PARTITION_TABLE_CUSTOM=y       # Custom partition table
CONFIG_PARTITION_TABLE_CUSTOM_FILENAME="partitions.csv"
CONFIG_ESP_WIFI_ENABLED=y             # WiFi stack
CONFIG_BT_ENABLED=y                   # Bluetooth stack
CONFIG_FREERTOS_HZ=1000               # RTOS tick rate
CONFIG_ESP_CONSOLE_UART_DEFAULT=y     # Console on UART0
CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y  # Console on built-in USB-JTAG (S3/C3)
```

## CMakeLists.txt Rules

### Project-level (top-level)

```cmake
cmake_minimum_required(VERSION 3.16)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(my_project)
```

- Do not remove `include($ENV{IDF_PATH}/tools/cmake/project.cmake)`.
- The `project()` name determines the output binary name (`my_project.bin`).

### Component-level (main/ or components/<name>/)

```cmake
idf_component_register(
    SRCS "main.c" "app.c"
    INCLUDE_DIRS "."
    REQUIRES driver nvs_flash esp_wifi
)
```

- `SRCS`: source files for this component.
- `INCLUDE_DIRS`: header directories for this component and dependents.
- `REQUIRES`: components this one depends on (public, propagated).
- `PRIV_REQUIRES`: private dependencies (not propagated).

Do not hand-edit `build/`, `CMakeCache.txt`, or generated makefiles.

## ESP-IDF Build Commands

```powershell
# Set target chip (generates sdkconfig)
idf.py set-target esp32s3

# Configure (menuconfig GUI)
idf.py menuconfig

# Build
idf.py build

# Clean
idf.py clean
idf.py fullclean   # removes build/ and sdkconfig

# Flash
idf.py -p COM6 flash

# Monitor (serial output)
idf.py -p COM6 monitor

# Build, flash, and monitor in one step
idf.py -p COM6 flash monitor

# Erase flash
idf.py -p COM6 erase-flash

# Size analysis
idf.py size
idf.py size-components
```

Exit monitor with `Ctrl+]` (Windows) or `Ctrl+]` (Linux/macOS).

## Partition Tables

Default partition tables are built into ESP-IDF. Use a custom `partitions.csv` when you need OTA, specific NVS size, or storage partitions.

```csv
# Name,   Type, SubType, Offset,  Size, Flags
nvs,      data, nvs,     0x9000,  0x6000,
phy_init, data, phy,     0xf000,  0x1000,
factory,  app,  factory, 0x10000, 1M,
```

- The bootloader is always at `0x0`.
- Partition table is at `0x8000`.
- NVS is typically at `0x9000`.
- App (factory) is typically at `0x10000`.
- Sizes can use `1M`, `512K`, `0x100000` notation.
- Enable custom partition in sdkconfig: `CONFIG_PARTITION_TABLE_CUSTOM=y` and `CONFIG_PARTITION_TABLE_CUSTOM_FILENAME="partitions.csv"`.

## Arduino-ESP32 Workflow

### Build with arduino-cli

```powershell
# Install core (one-time)
arduino-cli core install esp32:esp32

# Compile
arduino-cli compile --fqbn esp32:esp32:esp32s3 .\my_sketch\

# Upload
arduino-cli upload -p COM6 --fqbn esp32:esp32:esp32s3 .\my_sketch\

# Serial monitor
arduino-cli monitor -p COM6 -c baudrate=115200
```

Common FQBNs:
- `esp32:esp32:esp32` — classic ESP32
- `esp32:esp32:esp32s3` — ESP32-S3
- `esp32:esp32:esp32c3` — ESP32-C3

### Arduino as ESP-IDF Component

Arduino-ESP32 can be used as a component inside an ESP-IDF project:

```text
components/
  arduino/    # clone from https://github.com/espressif/arduino-esp32
main/
  CMakeLists.txt
  main.cpp    # use setup() and loop() or app_main()
```

Set `CONFIG_ARDUINO_SELECTIVE_COMPILATION=y` in sdkconfig to reduce build time.

## PlatformIO Workflow

```ini
; platformio.ini
[env:esp32-s3-devkitc-1]
platform = espressif32
board = esp32-s3-devkitc-1
framework = espidf   ; or arduino
monitor_speed = 115200
upload_port = COM6
```

```powershell
pio run                    # build
pio run --target upload    # flash
pio device monitor         # serial monitor
pio run --target clean     # clean
```

## Validation Chain

Run the static checker first:

```powershell
python scripts\check_idf_project.py <project-dir>
```

Before flashing, detect the connected device:

```powershell
python scripts\detect_esp_device.py
```

Then flash:

```powershell
python scripts\esp_flash.py <project-dir> --port COM6
```

Report validation levels separately:

- source/static inspection
- sdkconfig reconfigure
- compile/link (`idf.py build`)
- flash tool success
- physical board behavior (boot log, LED, serial output)
- serial/logic analyzer observation

Do not report hardware behavior as verified unless it was observed on connected hardware.

## esptool.py Direct Usage

When the helper scripts are unavailable, esptool can be called directly:

```powershell
# Identify chip
esptool.py --port COM6 chip_id

# Read MAC
esptool.py --port COM6 read_mac

# Flash (ESP-IDF layout)
esptool.py --chip esp32s3 --port COM6 --baud 460800 write_flash --flash_mode dio --flash_freq 80m --flash_size detect --verify 0x0 build\bootloader\bootloader.bin 0x8000 build\partition_table\partition-table.bin 0x10000 build\my_project.bin

# Erase flash
esptool.py --port COM6 erase_flash

# Read flash
esptool.py --port COM6 read_flash 0x0 0x400000 flash_dump.bin
```

## SDK / Example Lookup

Use evidence before authoring unfamiliar sdkconfig keys or component APIs:

1. The user's existing `sdkconfig` and `CMakeLists.txt`.
2. Packaged examples under `examples/`.
3. Local ESP-IDF examples: `$IDF_PATH/examples/`.
4. Component Kconfig: `$IDF_PATH/components/<component>/Kconfig`.
5. ESP-IDF Programming Guide: https://docs.espressif.com/projects/esp-idf/en/latest/

Search local IDF examples with:

```powershell
Get-ChildItem -Recurse -Path "$env:IDF_PATH\examples" -Filter "*.c" | Select-String -Pattern "uart_driver_install" | Select-Object -First 10
```
