/*
 * empty_project - Minimal ESP-IDF blink example
 *
 * Blinks an LED on GPIO2 (adjust LED_PIN for your board).
 * Target: any ESP32 chip (set with `idf.py set-target <chip>`)
 *
 * Build:
 *   idf.py set-target esp32s3
 *   idf.py build
 *   idf.py -p COM6 flash monitor
 */

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_log.h"

static const char *TAG = "empty";

/* Change this to match your board's LED pin.
 * Common pins:
 *   ESP32-S3-DevKitC-1: GPIO48 (WS2812, not regular LED) or GPIO2
 *   ESP32-DevKitC:      GPIO2
 *   NodeMCU-32S:        GPIO2
 *   ESP32-C3-DevKitM:   GPIO8 (onboard LED)
 */
#define LED_PIN 2

void app_main(void)
{
    ESP_LOGI(TAG, "empty_project starting");
    ESP_LOGI(TAG, "Free heap: %lu bytes", esp_get_free_heap_size());

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
        ESP_LOGI(TAG, "LED ON");
        vTaskDelay(pdMS_TO_TICKS(500));

        gpio_set_level(LED_PIN, 0);
        ESP_LOGI(TAG, "LED OFF");
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}
