# empty_project — Minimal ESP-IDF Blink

A minimal ESP-IDF project that blinks an LED. Use this as:

- A baseline to verify your toolchain, flashing, and serial monitor work.
- A starting point for new projects.
- A reference for the minimum required files in an ESP-IDF project.

## Files

```
empty_project/
├── CMakeLists.txt        # Project-level: includes IDF, sets project name
├── sdkconfig.defaults    # Non-default sdkconfig overrides
├── manifest.json         # Skill metadata (used by list_examples.py)
├── README.md
└── main/
    ├── CMakeLists.txt    # Component-level: registers source files
    └── main.c            # Application code
```

## Build and Flash

```powershell
# 1. Set target chip (do this once, or when changing chips)
idf.py set-target esp32s3

# 2. Build
idf.py build

# 3. Flash and monitor (replace COM6 with your port)
idf.py -p COM6 flash monitor
```

Exit monitor with `Ctrl+]`.

## Expected Serial Output

```
I (29) boot: ESP-IDF v5.3 ...
I (0) cpu_start: App cpu up.
...
I (311) empty: empty_project starting
I (311) empty: Free heap: 250000 bytes
I (311) empty: LED ON
I (811) empty: LED OFF
I (1311) empty: LED ON
...
```

## Customize

- **LED pin**: Change `LED_PIN` in `main/main.c`. Common values:
  - ESP32-S3-DevKitC-1: GPIO48 is WS2812 (needs LEDC/RMT driver, not simple GPIO). Use GPIO2 or an external LED.
  - ESP32-DevKitC / NodeMCU: GPIO2 (onboard LED).
  - ESP32-C3-DevKitM-1: GPIO8 (onboard LED).
- **Blink speed**: Change the `vTaskDelay(pdMS_TO_TICKS(500))` values.
- **Log level**: Use `ESP_LOGI`, `ESP_LOGW`, `ESP_LOGE`, `ESP_LOGD`.

## Troubleshooting

- **LED doesn't blink**: Verify the LED pin matches your board. Some boards have the LED on a different pin or use a WS2812 addressable LED.
- **No serial output**: Check the COM port, baud rate (115200 default), and that you closed other serial programs.
- **Flash fails**: See `references/debug_backends.md` for common esptool errors.
