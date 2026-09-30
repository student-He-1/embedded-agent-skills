---
name: esp32-arduino
description: Agent rules for ESP32 / ESP32-S3 firmware development with Arduino IDE and arduino-cli. Use when an agent needs to create, inspect, modify, build, flash, or debug ESP32 Arduino projects (.ino), manage board/package/library configuration, validate hardware behavior through serial, or work with WiFi, Bluetooth, GPIO, PWM, I2C, SPI, UART, ADC on ESP32 family chips.
---

# ESP32 Arduino Agent Skill

Use this skill for ESP32 / ESP32-S3 firmware projects that use the Arduino framework through Arduino IDE or arduino-cli. It is intended for CLI/editor agents that need to participate in the full development loop: detect board → inspect project → compile → flash → serial verify.

## Default Workflow

1. Detect connected boards: `python scripts/detect_board.py`. Identify chip model (ESP32 / ESP32-S3 / ESP32-C3 / etc.), serial port, MAC, Flash/PSRAM size, and USB mode.
2. Locate the project `.ino` entrypoint, `platform.local.txt` overrides, and library dependencies. Run `python scripts/check_arduino_project.py <project-dir>` for static validation (add `--chip` when the target chip is not obvious from the sources).
3. Read the project's existing board configuration (FQBN, port, upload speed). If missing, derive from detected hardware and confirm with the user.
4. Modify only the requested source surface. Preserve unrelated code, comments, copyright headers, and project layout.
5. Compile: `python scripts/arduino_build.py <project-dir> --fqbn <fqbn>`. Report warnings separately from errors.
6. Flash: `python scripts/arduino_upload.py <project-dir> --port <port> --fqbn <fqbn>`. Confirm the port matches the connected board before flashing.
7. Verify: `python scripts/serial_monitor.py --port <port> --baud 115200 --duration 5`. Distinguish "compiled/flashed successfully" from "hardware behavior verified".

## Core Rules

- Treat the `.ino` sketch and user source files as the editable surface. Treat `build/`, `AppData/.../sketches/`, compiled `.bin`, bootloader, partition table, and core library sources as inspection-only.
- Do not hand-edit files under `packages/esp32/hardware/esp32/<version>/` (core, variants, tools). If a core modification is needed, explain why and ask the user first.
- Do not guess FQBN. Detect the chip first, then map to the correct board ID: `esp32:esp32:esp32` (classic), `esp32:esp32:esp32s3` (S3), `esp32:esp32:esp32c3` (C3), etc.
- Do not guess serial port. Detect connected boards before compiling/flashing. If multiple boards are connected, ask the user which one to target.
- Preserve existing `platform.local.txt`, `boards.local.txt`, and custom partition CSV files. Do not silently replace them.
- If the user asks only to "flash" or "upload", detect the connected board first. Do not assume the previous board is still connected.
- Treat an empty board-detection result as inconclusive, not proof that no board is connected. Check OS device manager and try a different USB cable.
- If hardware behavior is not verified on a connected board, say that validation stopped at compile or flash level. Do not claim "it works" based only on successful compilation.

## Board-Specific Pin Caution

### ESP32 (classic, Xtensa dual-core)

- GPIO6–GPIO11 are connected to the SPI flash chip. **Never** use them for GPIO.
- GPIO34–GPIO39 are input-only. Do not use `pinMode(pin, OUTPUT)` on these.
- GPIO0, GPIO2, GPIO5, GPIO12, GPIO15 are strapping pins. Avoid using them for outputs that must be in a known state at boot. GPIO12 must be low at boot for correct flash voltage (internal pull-down is default).
- GPIO1 (TX0) and GPIO3 (RX0) are used for USB-serial (REPL / upload). Repurposing them breaks serial upload and debug output.
- Onboard LED is typically GPIO2 on most dev boards, but verify per board.

### ESP32-S3 (Xtensa LX7 dual-core)

- **Flash/PSRAM pins depend on board design**:
  - Boards with **Octal PSRAM** (e.g. ESP32-S3-WROOM-1-N16R8): GPIO26–GPIO32 are used for Octal SPI Flash/PSRAM (SPICS1/SPIHD/SPIWP/SPICS0/SPICLK/SPIQ/SPID). **Do not use GPIO26–32.** GPIO6–GPIO11 are available as normal GPIO on these boards.
  - Boards with **Quad PSRAM/Flash**: GPIO6–GPIO11 are used for SPI flash. Do not use.
- GPIO19 and GPIO20 are USB D-/D+ when USB-Serial/JTAG is enabled. Do not use for GPIO if using USB serial.
- GPIO0, GPIO3, GPIO45, GPIO46 are strapping pins. **In normal SPI boot (GPIO0 high) GPIO46 is ignored.** It only has to be low/floating to enter the serial bootloader, so do not drive it high "for safety" — and do not assume it is read at boot. It has an internal **weak pull-down** (GPIO0 has a weak pull-up; low at reset = download mode). GPIO0 is the BOOT button on most dev boards.
- GPIO22–GPIO25 do not exist on QFN56 package.
- **GPIO48 WS2812 vs PSRAM trade-off** (ESP32-S3-WROOM-1-N16R8): GPIO48 carries the onboard WS2812 RGB LED and is also the IO-MUX function SPICLK_N. **Verified on this board**: with `PSRAM=opi` the WS2812 does not light; with `PSRAM=disabled` it works via Adafruit_NeoPixel. So treat it as an either/or:
  - **Default**: enable OPI PSRAM (`PSRAM=opi`) for 8MB extra RAM — the onboard WS2812 is then unavailable (observed on hardware).
  - **If the project needs the onboard RGB LED**: disable PSRAM (`PSRAM=disabled`) and use Adafruit_NeoPixel on GPIO48.
  - Choose based on project requirements. Do not silently disable PSRAM; explain the trade-off.
  - For projects that need both PSRAM and an LED, use an external LED on another GPIO pin.
  - Note: GPIO47 is the matching SPICLK_P IO-MUX function, but nothing on this board has shown it to be reserved — do **not** claim GPIO47 is unusable without testing it. Only GPIO48's WS2812 conflict is verified.
- GPIO46 is silkscreened **LOG** on these boards (confirmed on the ESP32-S3-N16R8 pinout) — it is the strapping pin associated with ROM log output. This does not contradict the boot-mode rule above: the LOG function is why the pin is labelled that way, while for *boot mode selection* it is simply not read in normal SPI boot.
- ESP32-S3-N16R8 = 16MB Flash + 8MB Octal PSRAM. Select `ESP32S3 Dev Module` with PSRAM = OPI PSRAM. Recommended FQBN: `esp32:esp32:esp32s3:PSRAM=opi,USBMode=hwcdc,CDCOnBoot=cdc`.
- **`CDCOnBoot=cdc` is mandatory for serial output on the native USB port.** `USBMode=hwcdc` alone does not map `Serial` onto USB: with the default `CDCOnBoot=Disabled`, `Serial` is still `HardwareSerial` (UART0 → GPIO43/44), so the port stays completely silent with no build error. Do not conclude "the sketch didn't run / the board is broken" before checking this.
- ADC: **ADC1 = GPIO1–GPIO10** (CH0–CH9), **ADC2 = GPIO11–GPIO20** (CH0–CH9), i.e. ADC2 channel = GPIO number − 11. Do not confuse this with the classic ESP32 map (ADC1 = GPIO32–39).
  - **ADC2 is also used by WiFi — exactly like the classic ESP32.** ESP-IDF documents that `adc2_get_raw()` reading **may fail between `esp_wifi_start()` and `esp_wifi_stop()`**. Prefer ADC1 whenever WiFi may be active. Do not claim S3 lifts this restriction.
  - GPIO0 and GPIO21 have **no** ADC function. GPIO14 / GPIO15 / GPIO16 all **do** (ADC2_CH3 / CH4 / CH5) — do not strip them from the pin table.
  - 11 dB attenuation saturates near **3.1 V**, not 3.3 V (measurable range 0–3100 mV).

### ESP32-C3 (RISC-V single-core)

- GPIO11 and GPIO12 are strapping pins.
- GPIO18/19 are USB D-/D+ when USB serial is enabled.
- Onboard LED is typically GPIO8 on official dev kits.

## Project Shape Checks

- Simple projects keep most logic in one `.ino` file. It is acceptable to make narrowly scoped edits there.
- Multi-file projects may have `src/`, `lib/`, or multiple `.ino` / `.cpp` / `.h` files. Identify ownership boundaries before adding peripherals.
- Library dependencies are declared in the sketch via `#include`. Check installed libraries with `arduino-cli lib list`. Do not assume a library is installed; install it if missing.
- For WiFi/Bluetooth projects, confirm the selected board variant has the required radio (all ESP32 family have WiFi+BT except some minimized modules).
- For timing-critical code, confirm whether delays come from `delay()`, `millis()` polling, hardware timer interrupts, or FreeRTOS tasks before changing periods.

## FreeRTOS Awareness

ESP32 Arduino runs on top of FreeRTOS. If the project uses `xTaskCreate`, `xQueueSend`, `xSemaphoreTake`, `loopTask`, or `portMUX_TYPE`:

- Respect existing task priorities and core affinities. Do not move tasks between cores without understanding the impact.
- Keep ISRs short. Use `portENTER_CRITICAL` / `portEXIT_CRITICAL` for shared variable access.
- Do not call `delay()` inside an ISR. There is no ISR-safe sleep — you cannot block in an ISR at all. Defer the work: notify a task (`xTaskNotifyFromISR` + `vTaskNotifyGiveFromISR`), give a semaphore (`xSemaphoreGiveFromISR`), or set a flag and return.
- `loop()` runs in `loopTask` on core 1 (classic) / core 0 (S3). Blocking `loop()` with long operations prevents WiFi/BT background tasks from running.

## Ambiguous Requests

If the user omits important hardware parameters, do not silently choose risky values.

- For low-risk defaults (LED pin, baud rate), use this skill's `examples/` or common dev board defaults, then tell the user which defaults were applied.
- For important parameters (WiFi SSID/password, I2C address, SPI CS pin, UART pins, PWM channel), ask before editing and offer a concrete recommendation.
- Important missing parameters include: pin number, peripheral instance, I2C address, SPI mode/CS, UART baud/pins, PWM frequency/duty, ADC channel/attenuation, WiFi credentials.

## External Modules And Hardware Debugging

When asked to drive an external module, sensor, display, motor, or custom board:

- Ask for the module datasheet, pin map, supply voltage, logic level, communication protocol, and key parameters when not available.
- Verify wiring before blaming code: power, ground, pull-ups (I2C needs 4.7kΩ), level shifting (3.3V vs 5V), reset/enable pins, boot mode, chip select, UART TX/RX crossover.
- ESP32 GPIO is **3.3V only**. Do not connect 5V signals directly to GPIO inputs.
- If repeated attempts fail but compile/flash/code logic look correct, explicitly raise the possibility of wiring, power, module mode, datasheet mismatch, damaged hardware, or wrong test procedure.
- Separate "firmware looks correct" from "hardware proved correct".

## Reference Selection

Read references only when needed:

- `references/project_workflows.md`: arduino-cli setup, FQBN mapping, compile/flash commands, project structure, library management, partition tables.
- `references/arduino_esp32_api.md`: GPIO, analogWrite (LEDC), WiFi, Bluetooth, I2C, SPI, UART, ADC, timer interrupts, common API patterns and pitfalls.
- `references/hardware_validation_notes.md`: verified board lessons, pin cautions, flash/reset behavior, serial upload troubleshooting.
- `references/board_esp32s3_n16r8.md`: complete hardware reference for the ESP32-S3-WROOM-1-N16R8 board — full pinout (both headers), onboard WS2812 (GPIO48) vs PSRAM trade-off, restricted pins, strapping, ADC/touch, Arduino FQBN settings.
- `references/debugging.md`: serial monitor, crash decoder (GDB stub), ESP exception decoder, common crash causes, stack overflow diagnosis.

Use `examples/` as one source for reusable tested patterns. Prefer `scripts/list_examples.py` to inspect available examples before opening individual files.

## Examples

Each reusable example should contain:

```text
examples/<name>/
├─ <name>.ino
└─ README.md
```

Do not require users to drop full Arduino projects into `examples/`. Keep examples minimal and self-contained.

When applying an example to a user project:

- Treat skill examples as proven references, not mandatory project templates.
- Copy only the needed code pattern, library include, or debugging lesson.
- Preserve the user's existing file layout and naming.
- Prefer the user's local style when it conflicts with an example.
- Install required libraries with `arduino-cli lib install "<name>"` before compiling.

## Tools

Run bundled scripts with Python 3.10 or newer. `serial_monitor.py` additionally requires `pyserial`; if import fails, tell the user to run `python -m pip install pyserial`. Arduino IDE / arduino-cli and the ESP32 core remain external dependencies and are not installed by this skill.

- `python scripts/detect_board.py`: read-only connected-board detection using `arduino-cli board list` and `esptool chip_id`. Reports chip model, port, MAC, Flash/PSRAM, USB mode. An empty result is explicitly inconclusive.
- `python scripts/check_arduino_project.py <project-dir> [--chip esp32|esp32s3]`: static project check for `.ino` entrypoint, library includes vs installed libs, common mistakes (missing `setup()`/`loop()`, using input-only pins as output, etc.). Pin rules are **chip-specific** and chosen via `--chip` (default `auto`, inferred from the project sources). If the chip cannot be determined the pin checks are skipped rather than run against the wrong chip's rules — e.g. GPIO6–11 are flash pins on classic ESP32 but are free GPIO on ESP32-S3.
- `python scripts/arduino_build.py <project-dir> --fqbn <fqbn>`: compile wrapper around `arduino-cli compile`. Captures warnings and errors separately.
- `python scripts/arduino_upload.py <project-dir> --port <port> --fqbn <fqbn>`: flash wrapper. Verifies the port is present before uploading.
- `python scripts/serial_monitor.py --port <port> --baud 115200 --duration 10`: read serial output for a fixed duration. Useful for verifying `Serial.println()` output after flash.
- `python scripts/list_examples.py`: list packaged examples from `examples/*/README.md`.

## Flash Backend

Before flashing, run:

```text
python scripts/detect_board.py
```

Confirm the detected port and chip match the intended target. If multiple boards are connected or detection is unknown, stop and ask the user.

The verified flash path is `arduino-cli upload`:

```text
arduino-cli upload -p <port> --fqbn <fqbn> <project-dir>
```

For ESP32-S3 with USB-Serial/JTAG, the port may change after upload (the device re-enumerates). The script handles this by re-detecting after flash.

If upload fails with "port busy", close the serial monitor and any other program holding the port (Thonny, PuTTY, VOFA+, etc.), then retry.

If upload fails with "wrong boot mode" or "invalid head of packet", hold the BOOT button, press RST, then release BOOT before retrying. Some boards require manual boot mode entry.

## Debug Backend

Primary debug is serial output. Use `Serial.begin(115200)` in `setup()` and `Serial.println()` for state reporting.

For crash diagnosis:

- ESP32 Arduino prints a crash dump to serial at 115200 baud. Capture it with `serial_monitor.py`.
- Use the ESP Exception Decoder (Arduino IDE → Tools → ESP Exception Decoder) or `arduino-cli` with the `.elf` file to decode backtraces.
- Common crash causes: stack overflow (large local arrays), use-after-free, NULL pointer dereference, ISR called `delay()`, WiFi called from ISR.

For interactive debugging, Arduino IDE 2.x has a built-in debugger for ESP32-S3 with USB-Serial/JTAG (no external probe needed). This skill does not automate GDB debugging; ask the user to use the IDE debugger for step-by-step work.

## Validation Levels

Report validation levels separately:

- source / static inspection
- compile success (with warnings listed separately)
- flash tool success
- serial output observed
- physical board behavior (LED, relay, sensor reading, etc.)

Do not report hardware behavior as verified unless it was observed on connected hardware.
