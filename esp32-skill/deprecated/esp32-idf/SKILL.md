---
name: esp32-idf-deprecated
description: "[DEPRECATED - DO NOT USE] 本 skill 未验证成功（ESP-IDF 安装受阻），仅作留档，请勿安装或调用。Original draft description: Tool-neutral CLI agent rules for Espressif ESP32 development with ESP-IDF, Arduino-ESP32, PlatformIO, esptool, OpenOCD/GDB, and FreeRTOS. Use when an agent needs to inspect or modify ESP32 projects, edit sdkconfig/CMakeLists, avoid generated build outputs, use ESP-IDF and Arduino APIs, validate partitions and flash layout, flash and debug real hardware, or work on WiFi/Bluetooth/embedded firmware for ESP32, ESP32-S2/S3, ESP32-C3/C6, ESP32-H2."
---

> ## :warning: 已弃用 — 请勿使用
>
> 本 skill 的 ESP-IDF 路线**从未在本机验证成功**（安装阶段遇到 objdump DLL 错误 exit 1114）。
> 现仅作留档保留，脚本与文档均未经验证，`idf.py` 相关命令在本环境不可用。
>
> **请改用 `skills/esp32-arduino/`（Arduino 路线，已实机验证）。**

# ESP32 Agent Skill (Deprecated Draft)

Use this skill for Espressif ESP32 firmware projects based on ESP-IDF v5.x, Arduino-ESP32, or PlatformIO. It is intended for Claude Code, OpenCode, OpenClaw, Continue, Cursor, Codex, and similar CLI/editor agents.

## Default Workflow

1. Locate the project entrypoint: `CMakeLists.txt` + `main/` for ESP-IDF, `*.ino` for Arduino-ESP32, or `platformio.ini` for PlatformIO. Identify `sdkconfig`, `partitions.csv`, `components/`, and the active target chip (`IDF_TARGET`).
2. Run `python scripts/check_idf_project.py <project-dir>` when this skill is available.
3. Read `sdkconfig` for chip target, flash size, frequency, partition table, WiFi/BT stack, FreeRTOS settings, and component enables.
4. Inspect `partitions.csv` for partition layout, offsets, and sizes when flash layout or OTA/NVS is involved.
5. Before adding unfamiliar sdkconfig keys, inspect the user's existing `sdkconfig`, `examples/*/manifest.json`, local ESP-IDF examples, or `Kconfig` files under ESP-IDF components.
6. Modify the smallest relevant `sdkconfig`, `CMakeLists.txt`, component, or application-code surface.
7. Build through the active toolchain: `idf.py build` for ESP-IDF, `arduino-cli compile` for Arduino, or `pio run` for PlatformIO.
8. If flashing or debugging, run `python scripts/detect_esp_device.py` before selecting a port/backend. Confirm the detected chip and flash size match the project target.

## Core Rules

- Treat `sdkconfig` as the source of truth for chip target, flash configuration, partition table, component enables, WiFi/BT stack, FreeRTOS, and sleep/security settings.
- Treat `CMakeLists.txt` (project and component level) as the source of truth for source files, include paths, dependencies, and requirements.
- Do not hand-edit generated outputs such as `build/`, `sdkconfig.old`, `partition_table/partition-table.bin`, `bootloader/bootloader.bin`, `*.elf`, `*.bin`, `*.map`, or `config/sdkconfig.h`.
- Preserve `sdkconfig` formatting: `KEY=VALUE` lines, `# CONFIG_... is not set` comments, and the auto-generated header comment. Do not rewrite the whole file; change only the needed keys.
- Do not guess component names or Kconfig symbols. Validate against local `Kconfig` files, `idf.py menuconfig` output, or the ESP-IDF documentation.
- Preserve unrelated user code, comments, copyright headers, project layout, and existing `sdkconfig` settings. If a requested feature requires a larger rewrite, explain why before making it when possible.
- Do not change the target chip (`IDF_TARGET`), flash size, partition table, or debug backend without user confirmation.
- If the user asks only to "flash" or "debug", do not silently assume a serial port or JTAG adapter. Detect the connected device first. If detection is unknown, multiple devices are connected, or the project target conflicts with the physical chip, stop and ask the user which port/backend to use.
- Treat an empty device-detector result as inconclusive, not proof that no board is connected. CP2102/CH340/CP210x USB-UART bridges may appear only as Windows `Ports` (COM) devices. Inspect OS serial ports (`python scripts/serial_monitor.py --list` on Windows) and USB PnP devices, then try the intended backend's read-only chip-id command or ask the user before concluding the device is absent.
- If the build emits warnings, report them separately from build/flash success. Do not call a warning-producing build "clean".
- If hardware behavior is not verified on a connected board, say that validation stopped at source, build, or flash level.

## Chip Architecture Caution

ESP32 family uses two CPU architectures, and the toolchain differs:

- **Xtensa**: ESP32, ESP32-S2, ESP32-S3 → `xtensa-esp-elf-gdb`, `xtensa-esp32s3-elf` (IDF v5.3+ unified)
- **RISC-V**: ESP32-C3, ESP32-C6, ESP32-H2 → `riscv32-esp-elf-gdb`

When debugging or selecting GDB, detect the chip first with `python scripts/detect_esp_device.py` and choose the matching GDB. Do not use an Xtensa GDB against a RISC-V chip or vice versa.

## Board-Specific Pin Caution

When the user explicitly says the board is a generic ESP32-S3-DevKitC or similar with CP2102 USB-UART:

- GPIO0 is the boot strapping pin (low = download mode). Do not use it for ordinary output unless the user accepts that it affects boot mode.
- GPIO46 (ESP32-S3) is also a boot strapping pin. Treat it similarly.
- GPIO19/GPIO20 (ESP32-S3) are the built-in USB-JTAG D-/D+ pins. Do not use them for GPIO if the user relies on built-in USB-JTAG debugging.
- GPIO1/GPIO3 are UART0 TX/RX on classic ESP32, connected to the CP2102 USB-UART. Repurposing them breaks serial console and auto-download.
- For ESP32-C3, GPIO18/GPIO19 are USB-JTAG and also UART0; GPIO20/GPIO21 are the alternative UART0 pins.

If the user asks to drive or reuse one of these special pins for a non-default purpose, remind them of the board caveat first.

## Project Shape Checks

- **ESP-IDF projects** have a top-level `CMakeLists.txt` with `include($ENV{IDF_PATH}/tools/cmake/project.cmake)`, a `main/` component, and `sdkconfig`. Components live in `components/` or `managed_components/`.
- **Arduino-ESP32 projects** have a `*.ino` file and may use `arduino-cli` or the Arduino IDE. They can also be wrapped as an ESP-IDF component (`arduino-espressif32`).
- **PlatformIO projects** have `platformio.ini` with `platform = espressif32`. Build with `pio run`, flash with `pio run --target upload`.
- Framework projects may have `main/`, `components/`, `app/`, `bsp/`, `drivers/`, or `tasks/`. First identify ownership boundaries before adding peripherals or changing control logic.
- For control code, confirm whether timing comes from a FreeRTOS task delay, hardware timer ISR, LEDC PWM, or a main-loop poll before changing periods or priorities.

## Arduino-ESP32 Compatibility

When the project is Arduino-ESP32 (detected by `*.ino` or `platformio.ini` with Arduino framework):

- Use Arduino APIs (`pinMode`, `digitalWrite`, `Serial`, `ledcWrite`, `WiFi`, etc.) rather than ESP-IDF DriverLib calls, unless the user explicitly asks for ESP-IDF mixing.
- Build with `arduino-cli compile --fqbn esp32:esp32:<board> <sketch>` or `pio run`.
- Flash with `arduino-cli upload -p <port> --fqbn esp32:esp32:<board> <sketch>` or `pio run --target upload`.
- `sdkconfig` is not directly editable in pure Arduino projects; settings come from the board definition. Do not invent an `sdkconfig` for an Arduino project.
- When mixing Arduino as an ESP-IDF component, follow the ESP-IDF workflow and treat the Arduino component as a dependency.

## FreeRTOS Rules

ESP-IDF uses FreeRTOS by default (ESP-IDF v5.x uses upstream FreeRTOS with ESP extensions).

- Respect existing task, queue, semaphore, event group, and ISR boundaries.
- Do not add blocking calls (e.g., `vTaskDelay`, `uart_write_bytes` with large timeout) inside ISRs. Use `xSemaphoreGiveFromISR` or task notifications.
- For WiFi and Bluetooth, use the ESP event loop (`esp_event_handler_register`) rather than polling.
- Confirm whether a requested control period belongs in a FreeRTOS task, hardware timer ISR, or peripheral event callback before changing it.
- Do not disable the WiFi/BT controller or change `CONFIG_FREERTOS_HZ` without understanding the impact on protocol stacks.

## Ambiguous Requests

If the user omits important hardware parameters, do not silently choose risky values.

- For low-risk defaults, use this skill's `examples/` or local ESP-IDF examples, then tell the user which defaults were applied.
- For important parameters, ask before editing and offer a concrete recommendation.
- Important missing parameters include: target chip (ESP32/S3/C3/etc.), GPIO pin, UART baud/data/parity/stop bits, LEDC frequency/duty/resolution, ADC channel/attenuation, I2C address/SDA/SCL pins, SPI mode/CS pin, WiFi SSID/password, MQTT broker/topic, and external-module power/logic levels.

Example: if the user asks "add a UART", ask which UART instance, TX/RX pins, and baud rate they want, and recommend UART0 at 115200 on the default pins if they are unsure.

## External Modules And Hardware Debugging

When asked to drive an external module, sensor, motor driver, servo, display, radio, or custom board:

- Ask for the module datasheet, schematic, pin map, supply voltage, logic level, communication protocol, and key parameters when they are not available.
- Verify wiring assumptions before blaming code: power, ground, pull-ups, level shifting (ESP32 is 3.3V, not 5V tolerant), reset/enable pins, boot strapping pins, UART TX/RX crossover, I2C address, SPI mode, CS pin, and shared pins.
- ESP32 GPIO is **3.3V only and not 5V tolerant**. Connecting 5V signals directly can damage the chip.
- If repeated attempts fail and sdkconfig, build, flash, and code logic look correct, explicitly raise the possibility of wiring, power, module mode, datasheet mismatch, damaged hardware, wrong boot mode, or wrong test procedure.
- Separate "firmware looks correct" from "hardware proved correct".

## Reference Selection

Read references only when needed:

- `references/project_workflows.md`: `sdkconfig` editing, ESP-IDF / Arduino / PlatformIO project layout, Kconfig lookup, idf.py builds, partitions, esptool flashing, and OpenOCD.
- `references/freertos_idf_rules.md`: FreeRTOS usage, ISR rules, WiFi/BT event loops, NVS, and common runtime mistakes.
- `references/hardware_validation_notes.md`: verified ESP32-S3 lessons, CP2102 serial, boot mode, flash voltage, built-in USB-JTAG, and real-board caveats.
- `references/debug_backends.md`: esptool flash, OpenOCD/GDB probe, built-in USB-JTAG, panic handler, and backtrace analysis.

Use `examples/` as one source for reusable tested patterns. Prefer `scripts/list_examples.py` to inspect available examples before opening individual example files, but do not assume packaged examples outrank the user's existing project structure or official Espressif examples.

## Examples

Each reusable example should contain:

```text
examples/<name>/
├─ CMakeLists.txt        (project-level, for ESP-IDF)
├─ sdkconfig.defaults    (non-default sdkconfig overrides)
├─ partitions.csv        (if custom partition table)
├─ README.md
├─ manifest.json
└─ main/
   ├─ CMakeLists.txt
   └─ source files
```

Do not require users to drop full ESP-IDF projects into `examples/`. Use compact reference packages.

When applying an example to a user project:

- Treat skill examples as proven references, not mandatory project templates.
- Copy only the needed `sdkconfig` keys, `CMakeLists` entries, code pattern, or debugging lesson.
- Preserve the user's existing file layout and naming.
- Prefer the user's local style when it conflicts with an example's directory names or layering.
- Consider official ESP-IDF examples at `$IDF_PATH/examples/` at the same or higher priority when they better match the user's chip, peripheral, or framework.

## Tools

Run bundled scripts with Python 3.10 or newer. `serial_monitor.py` additionally requires `pyserial`; if import fails, tell the user to run `python -m pip install pyserial`. `detect_esp_device.py` and `esp_flash.py` require `esptool.py` (installed with ESP-IDF or via `pip install esptool`). ESP-IDF, Arduino-CLI, PlatformIO, OpenOCD, and GDB remain external workflow dependencies and are not installed by this skill.

- `python scripts/check_idf_project.py <project-dir>`: static project check for `sdkconfig`, `CMakeLists.txt`, partitions, components, target chip, build output, Arduino/PlatformIO clues, and validation hints.
- `python scripts/detect_esp_device.py`: read-only connected-device detection for CP2102/CH340 USB-UART serial ports and built-in USB-JTAG; calls `esptool chip_id` to identify chip model, flash size, and MAC. An empty result is explicitly inconclusive.
- `python scripts/esp_flash.py <project-dir>`: flash a built ESP-IDF/Arduino/PlatformIO project through esptool, auto-detecting serial port, chip, and `.bin` files with partition offsets. Supports erase, verify, and monitor.
- `python scripts/serial_monitor.py --list`: list serial ports.
- `python scripts/serial_monitor.py -p COM6 -b 115200`: open a serial monitor with timestamp and ANSI filtering.
- `python scripts/openocd_debug.py <project-dir> probe`: connect through OpenOCD, halt briefly, report target state, and resume (requires MSPM0? no — ESP32-capable OpenOCD).
- `python scripts/list_examples.py`: list packaged examples from `examples/*/manifest.json`.
- `python scripts/sdkconfig_helper.py <project-dir> --get CONFIG_XXX`: read or safely set a single sdkconfig key with backup.

## Flash Backends

Before flashing for a vague request such as "flash this project", run:

```text
python scripts/detect_esp_device.py
python scripts/check_idf_project.py <project-dir>
```

Device detection is read-only. Do not flash when multiple devices are connected, detection is unknown, or the physical chip conflicts with the project target until the user confirms the intended port and chip. On Windows, if no device is identified, inspect `Get-PnpDevice -PresentOnly` and `python scripts/serial_monitor.py --list`; a CP2102 or CH340 USB-UART bridge may expose only a virtual COM port.

The standard ESP-IDF flash path is `idf.py -p <port> flash` (which invokes esptool). For manual control:

```text
python scripts/esp_flash.py <project-dir> --port COM6
```

For Arduino projects:

```text
arduino-cli upload -p <port> --fqbn esp32:esp32:esp32s3 <sketch-dir>
```

For PlatformIO:

```text
pio run --target upload --upload-port <port>
```

After flashing, prefer `idf.py -p <port> monitor` or `python scripts/serial_monitor.py -p <port> -b 115200` to verify boot output.

## Debug Backends

Keep esptool-flash and OpenOCD/GDB as separate backends. Read `references/debug_backends.md` before debugging or diagnosing repeated probe failures.

For built-in USB-JTAG (ESP32-S3/C3) or an external JTAG adapter with an ESP32-capable OpenOCD:

```text
python scripts/openocd_debug.py <project-dir> probe
python scripts/openocd_debug.py <project-dir> run-to-symbol --symbol app_main
```

The OpenOCD target config depends on the chip: `target/esp32s3.cfg`, `target/esp32c3.cfg`, etc. Do not use an ESP32 (classic) config against an S3 or C3. If the target appears locked or flash-encrypted, stop and ask the user to perform their manual unlock/recovery procedure. Debug actions can halt the CPU, so report that risk before using breakpoints or register inspection on real-time control hardware.
