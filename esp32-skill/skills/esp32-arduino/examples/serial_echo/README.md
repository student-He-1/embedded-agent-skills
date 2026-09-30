# Serial Echo Example

Serial communication verification. Echoes received text back to the serial monitor.

## Features

- Echoes any text received via serial
- Reports byte count of received input
- Special commands:
  - `info` — prints chip model, CPU freq, free heap, flash size
  - `reset` — software reset the board

## Build & Flash

```powershell
# 0. Detect the board and port first — never copy a port number from a doc
python scripts\detect_board.py

# S3 needs CDCOnBoot=cdc or the native-USB serial port stays silent (no error).
# The echo below can only be observed if that option is set.
python scripts\arduino_build.py examples\serial_echo --fqbn "esp32:esp32:esp32s3:PSRAM=opi,USBMode=hwcdc,CDCOnBoot=cdc"
python scripts\arduino_upload.py examples\serial_echo --port <PORT> --fqbn "esp32:esp32:esp32s3:PSRAM=opi,USBMode=hwcdc,CDCOnBoot=cdc"
```

## Usage

1. Open serial monitor at 115200 baud
2. Type text and press Enter
3. Board echoes it back with byte count
4. Type `info` for system information
5. Type `reset` to reboot

## Expected Output

```
=== Serial Echo Ready ===
Type something and press Enter:
Received (5 bytes): hello
Received (4 bytes): info
Chip: ESP32-S3
CPU: 240 MHz
Free heap: 280000 bytes
Flash: 16777216 bytes
```

## Validation Level

- Compile: verified
- Flash: verified
- Hardware: serial echo verified on ESP32-S3 via USB-Serial/JTAG
