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
# Compile
python scripts\arduino_build.py examples\blink --board esp32s3

# Flash
python scripts\arduino_upload.py examples\blink --port COM6 --board esp32s3
```

## Expected Behavior

- LED blinks on/off every 500ms
- Serial monitor (115200) shows "Blink started on GPIO2"

## Validation Level

- Compile: verified
- Flash: verified
- Hardware: GPIO2 output verified on ESP32 classic; external LED required for S3 core boards without onboard LED
