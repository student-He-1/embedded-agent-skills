---
name: esp32-micropython
description: Tool-neutral CLI agent rules for Espressif ESP32 development with MicroPython. Use when an agent needs to inspect or modify MicroPython projects, manage files on the board flash filesystem, run code via REPL, use machine/pin/uart/timer/wifi APIs, flash MicroPython firmware with esptool, or work on interactive embedded firmware for ESP32, ESP32-S2/S3, ESP32-C3/C6, ESP32-H2.
---

# ESP32 MicroPython Agent Skill

Use this skill for Espressif ESP32 firmware projects written in MicroPython. It is intended for Claude Code, OpenCode, OpenClaw, Continue, Cursor, Codex, and similar CLI/editor agents. The primary tool is `mpremote` for board interaction, with `esptool.py` for firmware flashing.

## Default Workflow

1. Locate the project files: `boot.py`, `main.py`, `lib/`, and any local `.py` modules. Identify the target board and serial port.
2. Run `python scripts/detect_board.py` to find the connected ESP32, confirm MicroPython version, and list the board filesystem.
3. Read `boot.py` and `main.py` on the board (or in the local project) to understand the current startup behavior.
4. Inspect local project files for imports, pin assignments, and hardware dependencies.
5. Modify the smallest relevant `.py` file. Preserve unrelated code, comments, and existing structure.
6. Upload changed files to the board with `mpremote fs put <local> <remote>` or use `mpremote run <file>` for one-off testing.
7. Verify behavior via REPL output, serial monitor, or physical observation (LED, sensor, etc.).
8. If the board is unresponsive, use `mpremote` soft-reset (`Ctrl+D`) or hardware reset, then re-check.

## Core Rules

- Treat `main.py` as the application entry point — it runs automatically after `boot.py` on every boot.
- Treat `boot.py` as the startup configuration script — use it for minimal hardware init, network setup, or path configuration. Keep it short.
- Do not modify MicroPython firmware files (`_boot.py`, `_webrepl.py`, etc.) unless the user explicitly asks.
- Preserve the board filesystem layout. Do not delete files the user created unless asked.
- Use `mpremote fs ls` before uploading to avoid overwriting existing files without checking.
- Do not guess pin numbers. Read the existing code, board schematic, or ask the user. Common ESP32 LED pins: GPIO2 (DevKit/NodeMCU), GPIO48 (S3 WS2812), GPIO8 (C3).
- Do not assume every ESP32 board has the same pinout. ESP32, ESP32-S2/S3, and ESP32-C3/C6 have different GPIO layouts.
- If the user asks only to "run" or "test", do not silently overwrite `main.py`. Use `mpremote run <file>` for one-off execution, or upload to a temporary filename.
- Treat an empty board-detector result as inconclusive, not proof that no board is connected. Check USB connections, drivers (CP2102/CH340), and try `Get-PnpDevice -PresentOnly -Class Ports` on Windows.
- If hardware behavior is not verified on a connected board, say that validation stopped at code review or REPL execution level.

## MicroPython Project Structure

A typical MicroPython project on the board flash filesystem:

```text
/
├── boot.py          # Runs first on every boot (minimal config)
├── main.py          # Runs after boot.py (main application)
├── lib/             # Third-party or custom modules
│   ├── ssd1306.py
│   ├── umqtt/
│   │   └── simple.py
│   └── ...
├── config.py        # User config (WiFi credentials, pins, etc.)
└── data/            # Data files (optional)
```

Local project structure mirrors the board filesystem. When uploading, preserve the relative paths:

```text
my_project/
├── boot.py
├── main.py
├── lib/
│   └── ssd1306.py
└── config.py
```

Upload with:
```powershell
mpremote connect COM3 fs cp boot.py :boot.py
mpremote connect COM3 fs cp main.py :main.py
mpremote connect COM3 fs cp lib/ssd1306.py :lib/ssd1306.py
```

## mpremote Quick Reference

```powershell
# Connect and enter REPL (exit with Ctrl+X)
mpremote connect COM3

# Run a local script on the board (does not save it)
mpremote connect COM3 run main.py

# Execute a single expression
mpremote connect COM3 exec "import machine; print(machine.freq())"

# List board files
mpremote connect COM3 fs ls

# Upload a file
mpremote connect COM3 fs cp local.py :local.py

# Download a file
mpremote connect COM3 fs cp :main.py main.py

# Delete a file
mpremote connect COM3 fs rm :old_file.py

# Create directory
mpremote connect COM3 fs mkdir lib

# Soft reset (Ctrl+D equivalent)
mpremote connect COM3 exec "import machine; machine.soft_reset()"

# Hard reset
mpremote connect COM3 exec "import machine; machine.reset()"
```

## Common MicroPython APIs

### GPIO

```python
from machine import Pin

led = Pin(2, Pin.OUT)        # Output
led.on()                     # High
led.off()                    # Low
led.value(1)                 # Set explicitly
btn = Pin(0, Pin.IN, Pin.PULL_UP)  # Input with pull-up
btn.value()                  # Read (0 or 1)
```

### UART

```python
from machine import UART
uart = UART(1, baudrate=115200, tx=17, rx=16)
uart.write("hello\r\n")
data = uart.read()            # Read all available
line = uart.readline()        # Read until newline
```

### Timer

```python
from machine import Timer
tim = Timer(0)
tim.init(period=1000, mode=Timer.PERIODIC, callback=lambda t: print("tick"))
tim.deinit()
```

### PWM (LED dimming / servo)

```python
from machine import Pin, PWM
pwm = PWM(Pin(2), freq=1000, duty=512)  # 0-1023 duty
pwm.duty(256)                             # 25% brightness
```

### ADC

```python
from machine import ADC, Pin
adc = ADC(Pin(34))
adc.atten(ADC.ATTN_11DB)   # 0-3.3V range
val = adc.read()           # 0-4095
```

### WiFi (STA mode)

```python
import network
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect("SSID", "PASSWORD")
while not wlan.isconnected():
    pass
print(wlan.ifconfig())
```

### I2C

```python
from machine import I2C, Pin
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
i2c.scan()                      # List device addresses
i2c.writeto(0x3C, b"\x00\xAF")  # Write to device
data = i2c.readfrom(0x3C, 16)   # Read from device
```

### SPI

```python
from machine import SPI, Pin
spi = SPI(1, baudrate=10000000, sck=Pin(18), mosi=Pin(23), miso=Pin(19))
cs = Pin(5, Pin.OUT, value=1)
cs.off()
spi.write(b"\x01\x02\x03")
cs.on()
```

## Board-Specific Pin Caution

When the user explicitly says the board is a generic ESP32 DevKit / NodeMCU with CP2102:

- **GPIO0** is the boot strapping pin (low = download mode). Do not use it for ordinary output unless the user accepts boot risk.
- **GPIO1 / GPIO3** are UART0 TX/RX, connected to CP2102. Repurposing them breaks serial console and REPL.
- **GPIO6-GPIO11** are connected to the SPI flash chip on most modules. Never use these.
- **GPIO34-GPIO39** are input-only (no internal pull-up/pull-down).
- For ESP32-S3: GPIO19/GPIO20 are built-in USB-JTAG; GPIO0/GPIO46 are strapping pins.
- For ESP32-C3: GPIO18/GPIO19 are USB-JTAG and also UART0.

If the user asks to use a special pin, remind them of the caveat first.

## Interrupts And Callbacks

- Use `Pin.irq()` for GPIO interrupts. Keep the callback short — no `time.sleep()`, no `print()` in production (it works but can cause issues).
- Timer callbacks also run in interrupt context. Keep them short.
- Use `micropython.schedule()` to defer work from an ISR to the main loop.
- Do not allocate memory inside interrupt handlers if avoidable (can cause `MemoryError`).

```python
from machine import Pin
import micropython

def callback(pin):
    micropython.schedule(do_work, pin)  # Defer to main loop

def do_work(pin):
    print("Button pressed on", pin)

btn = Pin(0, Pin.IN, Pin.PULL_UP)
btn.irq(trigger=Pin.IRQ_FALLING, handler=callback)
```

## FreeRTOS / Async In MicroPython

MicroPython on ESP32 runs on FreeRTOS but exposes a simpler API:

- Use `uasyncio` for cooperative multitasking (recommended over `_thread`).
- `_thread` is available but limited — use only for simple background tasks.
- `time.sleep()` blocks the entire thread. Use `uasyncio.sleep()` in async code.
- Do not create more than 2-3 threads with `_thread` — stack is limited.

```python
import uasyncio as asyncio

async def blink():
    led = Pin(2, Pin.OUT)
    while True:
        led.toggle()
        await asyncio.sleep_ms(500)

asyncio.run(blink())
```

## External Modules And Libraries

- Pure Python libraries go in `lib/`.
- Some libraries have MicroPython-specific versions (e.g., `umqtt.simple`, `urequests`).
- Use `mpremote mip install <package>` to install packages from micropython.org.
- For Adafruit CircuitPython libraries, check MicroPython compatibility first — not all work directly.
- If a library is too large for the flash filesystem, consider freezing it into firmware (requires building custom firmware).

## Flashing MicroPython Firmware

If the board does not have MicroPython or needs an update:

1. Download firmware from https://micropython.org/download/ (select your chip: ESP32, ESP32-S3, ESP32-C3, etc.)
2. Erase flash: `esptool.py --port COM3 erase_flash`
3. Flash firmware: `esptool.py --port COM3 --baud 460800 write_flash -z 0x1000 esp32-20240101-v1.22.1.bin`
4. Reset the board and verify with `mpremote connect COM3 exec "import sys; print(sys.implementation)"`

For **ESP32-S3 and ESP32-C3**, the firmware is written at offset **`0x0`**, not
`0x1000` — use the exact offset given on the firmware's download page for your
chip. Getting this wrong leaves the board apparently dead until you erase and
re-flash (it is recoverable in download mode, but easy to misdiagnose).

## Ambiguous Requests

If the user omits important parameters, do not silently choose risky values.

- For low-risk defaults, use this skill's `examples/` or common MicroPython patterns, then tell the user which defaults were applied.
- For important parameters, ask before editing and offer a concrete recommendation.
- Important missing parameters include: GPIO pin, UART baud/pins, I2C SDA/SCL pins, SPI CS pin, WiFi SSID/password, MQTT broker/topic, PWM frequency/duty, ADC channel/attenuation, and external-module power/logic levels.

## External Modules And Hardware Debugging

When asked to drive an external module, sensor, motor driver, servo, display, radio, or custom board:

- Ask for the module datasheet, pin map, supply voltage, logic level, communication protocol, and key parameters when not available.
- Verify wiring assumptions before blaming code: power, ground, pull-ups (I2C needs 4.7K), level shifting (ESP32 is 3.3V, not 5V tolerant), reset/enable pins, UART TX/RX crossover, SPI mode/CS, and shared pins.
- ESP32 GPIO is **3.3V only and not 5V tolerant**.
- If repeated attempts fail but code logic looks correct, explicitly raise the possibility of wiring, power, module mode, datasheet mismatch, damaged hardware, or wrong test procedure.
- Separate "code looks correct" from "hardware proved correct".

## Reference Selection

Read references only when needed:

- `references/project_workflows.md`: MicroPython project structure, mpremote usage, file management, boot.py/main.py, firmware flashing.
- `references/micropython_api.md`: machine module API reference (Pin, UART, Timer, PWM, ADC, I2C, SPI, WiFi), common patterns and pitfalls.
- `references/hardware_validation_notes.md`: verified ESP32 lessons, CP2102 serial, boot mode, flash layout, pin constraints, real-board caveats.
- `references/debugging.md`: REPL debugging, mpremote, serial monitor, common errors, crash recovery, filesystem issues.

Use `examples/` as one source for reusable tested patterns. Prefer `scripts/list_examples.py` to inspect available examples.

## Examples

Each reusable example should contain:

```text
examples/<name>/
├── main.py           # Main application code
├── boot.py           # Optional boot config
├── lib/              # Required modules (if any)
├── manifest.json     # Skill metadata
└── README.md         # Description, wiring, usage
```

When applying an example to a user project:

- Treat skill examples as proven references, not mandatory templates.
- Copy only the needed code patterns, pin assignments, or module usage.
- Preserve the user's existing file layout and naming.
- Prefer the user's local style when it conflicts with an example.

## Tools

Run bundled scripts with Python 3.10 or newer. Requires `mpremote` (`pip install mpremote`) and `pyserial` (installed with mpremote). `esptool.py` is needed only for firmware flashing.

- `python scripts/detect_board.py`: detect connected ESP32, confirm MicroPython version, list board filesystem.
- `python scripts/check_mp_project.py <project-dir>`: static check of local MicroPython project files.
- `python scripts/mp_file_manager.py upload <project-dir> --port COM3`: upload project files to board. (Subcommands: `upload`, `list`, `reset`, `download`; add `--dry-run` to preview or `--reset` to soft-reset afterwards.)
- `python scripts/serial_monitor.py --list`: list serial ports and exit.
- `python scripts/serial_monitor.py -p COM3 -b 115200 [--duration N]`: open the
  serial monitor. **`--duration` defaults to `0` = run forever** — always pass
  `--duration` (e.g. `--duration 10`) in an automated verify step, or it will
  block the workflow. Extra flags: `--timestamp`, `--no-ansi`, `--send TEXT`,
  `--send-line`, `--send-hex "01 02"`.
  (Note: the three `serial_monitor.py` copies are **not** interchangeable. STM32 uses
  a fixed 10 s default and `--send` / `--send-newline` / `--send-hex`. The Arduino
  copy also defaults to 10 s but has **no send flags at all** — only
  `--port --baud --duration --timestamp --reset --list`. Only this MicroPython copy
  has `--send-line` and a `0 = forever` default.)
- `python scripts/list_examples.py`: list packaged examples.

## Safety Rules

- Debug actions can halt the CPU and disturb real-time behavior. Warn the user before resetting a board that controls motors, power stages, or moving mechanisms.
- Do not mass-erase flash unless the user explicitly asks — it destroys all files on the board.
- Do not overwrite `main.py` without backing up or confirming — a broken `main.py` can make the board unresponsive at boot.
- If the board becomes unresponsive after a bad `main.py`, connect via REPL and press Ctrl+C quickly after reset to interrupt boot, then fix or delete `main.py`.
- Do not flash firmware without confirming the chip model — flashing the wrong firmware can brick the board (usually recoverable via re-flash in download mode).
