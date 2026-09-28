# LED Blink — MicroPython Snippet

## Use Case

Blink an LED from a GPIO pin. The minimal hardware-validation pattern.

## Code

```python
from machine import Pin
import time

LED_PIN = 2  # Adjust for your board

led = Pin(LED_PIN, Pin.OUT)

while True:
    led.on()
    time.sleep_ms(500)
    led.off()
    time.sleep_ms(500)
```

## One-liner test (REPL)

```python
from machine import Pin
Pin(2, Pin.OUT).on()   # LED on
Pin(2, Pin.OUT).off()  # LED off
```

## Common LED Pins

| Board | LED Pin | Type |
|---|---|---|
| ESP32 DevKit / NodeMCU | GPIO2 | Regular LED |
| ESP32-C3-DevKitM | GPIO8 | Regular LED |
| ESP32-S3-DevKitC | GPIO48 | WS2812 (needs RMT, not Pin.OUT) |
| ESP32-S2-Saola | GPIO4 | Regular LED |

## Notes

- Always use a current-limiting resistor (220-470 ohms) for external LEDs.
- ESP32 GPIO is 3.3V. Do not connect 5V.
- `time.sleep_ms()` is preferred over `time.sleep()` for short delays.
- For PWM dimming, use `machine.PWM` instead of `Pin.OUT`.
