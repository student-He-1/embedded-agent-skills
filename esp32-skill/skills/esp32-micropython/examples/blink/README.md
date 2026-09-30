# blink — LED Blink

Minimal MicroPython example that blinks an LED on GPIO2. Use this to verify your toolchain, file upload, and board work correctly.

## Files

```
blink/
├── main.py        # Blink application
├── manifest.json  # Skill metadata
└── README.md
```

## Upload and Run

```powershell
# Upload to board
mpremote connect COM3 fs cp main.py :main.py

# Reset to run (or press Ctrl+D in REPL)
mpremote connect COM3 exec "import machine; machine.soft_reset()"
```

Or use the skill's file manager:

```powershell
python scripts/mp_file_manager.py upload examples\blink --port COM3 --reset
```

## Expected Behavior

- The LED on **GPIO2** blinks on/off every 500 ms.
  On a classic ESP32 DevKit that is the onboard LED; on **ESP32-S3 the onboard
  WS2812 is on GPIO48 and this example will not light it** (see the pin list
  below), so wire an external LED to GPIO2 or change `LED_PIN`.
- `main.py` produces **no serial output** — it only drives the pin. Observe the
  LED, or check the pin with
  `mpremote connect COM3 exec "from machine import Pin; print(Pin(2).value())"`.

## Customize

- **LED pin**: Change `LED_PIN` in `main.py`. Common values:
  - ESP32 DevKit / NodeMCU: GPIO2
  - ESP32-C3-DevKitM: GPIO8
  - ESP32-S3-DevKitC: GPIO48 is WS2812 (not a regular LED — use RMT/LEDC driver)
- **Blink speed**: change the two `time.sleep(0.5)` values in `main.py` (seconds).

## Troubleshooting

- **LED doesn't blink**: Verify the LED pin matches your board. Test with `mpremote connect COM3 exec "from machine import Pin; Pin(2, Pin.OUT).on()"`.
- **No REPL after upload**: main.py has an infinite loop. Press Ctrl+C to interrupt, or reset and quickly press Ctrl+C to break into REPL.
- **File not found**: Run `mpremote connect COM3 fs ls` to verify main.py was uploaded.
