# MicroPython Project Workflows

Use this when managing MicroPython projects, uploading files, using mpremote, or flashing firmware.

## Project Structure

A MicroPython project is a collection of `.py` files that mirror the board's flash filesystem:

```text
my_project/
├── boot.py           # Runs first on boot (minimal config)
├── main.py           # Runs after boot.py (main application)
├── config.py         # User configuration (WiFi, pins, etc.)
└── lib/              # Custom / third-party modules
    ├── ssd1306.py
    └── umqtt/
        └── simple.py
```

### boot.py

- Runs on every boot, including wake from deepsleep.
- Keep it minimal — hardware init, network setup, path configuration.
- If `boot.py` crashes, `main.py` will not run.
- Common contents:

```python
# boot.py
import machine
import sys
sys.path.append('/lib')
# Optional: enable webrepl
# import webrepl
# webrepl.start()
```

### main.py

- Runs automatically after `boot.py`.
- This is where your application lives.
- If `main.py` has an infinite loop, REPL is not accessible until you interrupt (Ctrl+C) or reset.
- For development, consider putting code in a separate module and importing it from `main.py`, so you can test via REPL without rebooting.

## mpremote Usage

`mpremote` is the official MicroPython command-line tool. Install with `pip install mpremote`.

### Connection

```powershell
# Connect to a specific port and enter REPL
mpremote connect COM3

# Auto-detect (connects to first found device)
mpremote connect auto
```

Exit REPL with `Ctrl+X` (or `Ctrl+]` on some terminals). In REPL:
- `Ctrl+C` — interrupt running program
- `Ctrl+D` — soft reset
- `Ctrl+E` — paste mode

### File Operations

```powershell
# List files on board
mpremote connect COM3 fs ls

# List with details (size, date)
mpremote connect COM3 fs ls -l

# Upload a file
mpremote connect COM3 fs cp main.py :main.py

# Upload to a subdirectory
mpremote connect COM3 fs cp lib/ssd1306.py :lib/ssd1306.py

# Download a file
mpremote connect COM3 fs cp :main.py main_backup.py

# Delete a file
mpremote connect COM3 fs rm :old_file.py

# Create directory
mpremote connect COM3 fs mkdir lib

# Remove directory (must be empty)
mpremote connect COM3 fs rmdir lib
```

### Running Code

```powershell
# Run a local script without saving it
mpremote connect COM3 run test.py

# Run and then enter REPL
mpremote connect COM3 run test.py --no-follow

# Execute a one-liner
mpremote connect COM3 exec "import machine; print(machine.freq())"

# Execute multi-line code
mpremote connect COM3 exec "
from machine import Pin
led = Pin(2, Pin.OUT)
led.on()
print('LED on')
"
```

### Installing Packages

```powershell
# Install from micropython.org
mpremote connect COM3 mip install ssd1306
mpremote connect COM3 mip install github:user/repo

# Install to a specific path
mpremote connect COM3 mip install --target /lib ssd1306
```

### Resetting

```powershell
# Soft reset (re-runs boot.py and main.py)
mpremote connect COM3 exec "import machine; machine.soft_reset()"

# Hard reset (power-cycle equivalent)
mpremote connect COM3 exec "import machine; machine.reset()"
```

## Uploading a Full Project

Use the skill's file manager:

```powershell
# Dry run (show what would be uploaded)
python scripts/mp_file_manager.py upload C:\path\to\project --port COM3 --dry-run

# Actual upload
python scripts/mp_file_manager.py upload C:\path\to\project --port COM3

# Upload and reset
python scripts/mp_file_manager.py upload C:\path\to\project --port COM3 --reset
```

Or manually with mpremote:

```powershell
cd C:\path\to\project
mpremote connect COM3 fs cp boot.py :boot.py
mpremote connect COM3 fs cp main.py :main.py
mpremote connect COM3 fs mkdir lib
mpremote connect COM3 fs cp lib/ssd1306.py :lib/ssd1306.py
```

## Flashing MicroPython Firmware

### Download Firmware

Go to https://micropython.org/download/ and select your chip:
- ESP32 (classic): `esp32-*.bin`
- ESP32-S3: `esp32s3-*.bin`
- ESP32-C3: `esp32c3-*.bin`
- ESP32-C6: `esp32c6-*.bin`

### Flash Steps

```powershell
# 1. Erase flash (recommended for fresh install)
python -m esptool --port COM3 erase_flash

# 2. Flash firmware (offset 0x1000 for classic ESP32)
python -m esptool --port COM3 --baud 460800 write_flash -z 0x1000 esp32-20240101-v1.22.1.bin

# 3. Verify
python -m mpremote connect COM3 exec "import sys; print(sys.implementation)"
```

### ESP32-S3 Note

For ESP32-S3 with built-in USB-JTAG, the flash offset may be `0x0`. Check the download page for your specific firmware. If flashing fails at `0x1000`, try `0x0`.

### Recovery from Bad Firmware

If the board won't boot after flashing:
1. Hold BOOT (GPIO0) and press RESET to enter download mode.
2. Re-run `erase_flash` and `write_flash`.
3. If using a board with USB-JTAG (S3/C3), you may need to use the USB-JTAG port instead of the UART port for flashing.

## Thonny Integration

Thonny is a popular GUI for MicroPython development:

- **Interpreter**: Set to "MicroPython (ESP32)" in Run > Select interpreter.
- **Port**: Select the COM port (e.g., COM3).
- **File browser**: View > Files to see local and board files side by side.
- **Upload**: Right-click a local file > "Upload to /"
- **Download**: Right-click a board file > "Download to..."
- **REPL**: The shell pane is the MicroPython REPL.

Thonny and mpremote can coexist, but don't have both connected to the same COM port simultaneously.

## Validation Chain

1. **Static check**: `python scripts/check_mp_project.py <project-dir>`
2. **Board detection**: `python scripts/detect_board.py`
3. **Upload**: `python scripts/mp_file_manager.py upload <dir> --port COM3`
4. **Run / test**: `mpremote connect COM3 run main.py` or reset and observe
5. **Serial monitor**: `python scripts/serial_monitor.py -p COM3 -b 115200 --timestamp`

Report validation levels separately:
- Static code review (syntax, imports, pins)
- REPL execution (code runs without exception)
- File upload successful
- Physical board behavior observed (LED, sensor, serial output)
