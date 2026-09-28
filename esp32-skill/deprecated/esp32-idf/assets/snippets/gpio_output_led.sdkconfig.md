# GPIO Output LED — sdkconfig + Code Snippet

## Use Case

Drive a single LED from a GPIO pin. This is the minimal hardware-validation pattern for any new ESP32 board.

## sdkconfig Keys

No special sdkconfig keys are needed for basic GPIO. The GPIO driver is always available.

If using an LED on a strapping pin (GPIO0, GPIO46 on S3), ensure the external circuit does not interfere with boot mode.

## Code Pattern

```c
#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define LED_PIN 2

void app_main(void) {
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << LED_PIN),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&io_conf);

    while (1) {
        gpio_set_level(LED_PIN, 1);
        vTaskDelay(pdMS_TO_TICKS(500));
        gpio_set_level(LED_PIN, 0);
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}
```

## Common LED Pins by Board

| Board | LED Pin | Type |
|---|---|---|
| ESP32-DevKitC / NodeMCU | GPIO2 | Regular LED |
| ESP32-S3-DevKitC-1 | GPIO48 | WS2812 (needs RMT/LEDC, not GPIO) |
| ESP32-C3-DevKitM-1 | GPIO8 | Regular LED |
| ESP32-S2-Saola | GPIO4 | Regular LED (RGB) |
| Generic / custom | Any free GPIO | External LED + resistor |

## Notes

- Always use a current-limiting resistor (220-470 ohms) in series with the LED.
- ESP32 GPIO is 3.3V. Do not connect 5V LEDs directly without a resistor.
- For WS2812/addressable LEDs, use the RMT peripheral or LEDC, not `gpio_set_level()`.
- `gpio_set_level()` is non-blocking and safe to call from tasks. Do not call from ISRs unless the ISR is in IRAM.
