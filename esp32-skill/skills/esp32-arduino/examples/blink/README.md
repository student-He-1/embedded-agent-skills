# Blink Example

Minimal GPIO output verification. Blinks an LED at 1Hz.

## Hardware

- **ESP32 classic**: onboard LED on GPIO2 (most dev boards)
- **ESP32-S3**: many core boards have no user LED. Connect an external LED:
  - LED anode (long leg) → 220Ω resistor → GPIO2
  - LED cathode (short leg) → GND
- Modify `LED_PIN` in the sketch to match your wiring

## Build & Flash

```powershell
# 0. Detect the board and port first — never copy a port number from a doc
python scripts\detect_board.py

# Compile (S3 needs the full FQBN: --board esp32s3 alone omits CDCOnBoot=cdc,
# which makes the native-USB serial port silent with no error)
python scripts\arduino_build.py examples\blink --fqbn "esp32:esp32:esp32s3:PSRAM=opi,USBMode=hwcdc,CDCOnBoot=cdc"

# Flash (use the port detect_board.py reported)
python scripts\arduino_upload.py examples\blink --port <PORT> --fqbn "esp32:esp32:esp32s3:PSRAM=opi,USBMode=hwcdc,CDCOnBoot=cdc"
```

For a classic ESP32, `--board esp32` is fine (`CDCOnBoot` only matters on S3/C3
native-USB boards).

## Expected Behavior

- LED blinks on/off every 500ms
- Serial monitor (115200) shows "Blink started on GPIO2"

## Validation Level

- Compile: verified
- Flash: verified on ESP32 classic and on ESP32-S3 (native USB-Serial/JTAG)
- Hardware: LED blink **observed on ESP32 classic (GPIO2)**. On ESP32-S3 core
  boards this example needs an external LED — the onboard WS2812 sits on
  **GPIO48**, which this sketch does not drive (and which is unavailable while
  OPI PSRAM is enabled), so the S3 hardware run did not exercise the onboard LED.
