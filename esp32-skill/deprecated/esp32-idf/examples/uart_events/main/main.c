/*
 * uart_events - UART event-driven receive with echo
 *
 * Uses the ESP-IDF UART driver with an event queue to receive data
 * asynchronously, then echoes it back. Also blinks an LED as a heartbeat.
 *
 * UART0 is used (connected to CP2102 USB-UART on most dev boards).
 * Default pins: TX=GPIO43, RX=GPIO44 on ESP32-S3 (UART0 default).
 *
 * Build:
 *   idf.py set-target esp32s3
 *   idf.py build
 *   idf.py -p COM6 flash monitor
 *
 * Test: type characters in the serial monitor; they will be echoed back.
 *       Send "reset" to trigger a soft reset.
 */

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "driver/uart.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_system.h"
#include <string.h>

static const char *TAG = "uart_events";

/* --- Configuration --- */
#define UART_NUM        UART_NUM_0
#define UART_BAUD       115200
#define UART_TX_BUF     2048
#define UART_RX_BUF     4096
#define UART_QUEUE_SIZE 20
#define RX_BUF_SIZE     1024

/* LED heartbeat pin (adjust for your board) */
#define LED_PIN         2

/* --- Globals --- */
static QueueHandle_t uart_queue = NULL;
static uint8_t rx_buffer[RX_BUF_SIZE];

/* --- UART Event Task --- */
static void uart_event_task(void *pvParameters)
{
    uart_event_t event;
    size_t buffered_size;

    ESP_LOGI(TAG, "UART event task started");

    for (;;) {
        /* Wait for UART event (block indefinitely) */
        if (xQueueReceive(uart_queue, (void *)&event, portMAX_DELAY)) {
            bzero(rx_buffer, RX_BUF_SIZE);

            switch (event.type) {
            case UART_DATA:
                /* Data received; read it from the driver ring buffer */
                {
                    int len = uart_read_bytes(UART_NUM, rx_buffer,
                                              event.size, pdMS_TO_TICKS(100));
                    if (len > 0) {
                        rx_buffer[len] = '\0';
                        ESP_LOGI(TAG, "RX (%d bytes): %s", len, rx_buffer);

                        /* Echo back */
                        uart_write_bytes(UART_NUM, (const char *)rx_buffer, len);
                        uart_write_bytes(UART_NUM, "\r\n", 2);

                        /* Simple command: "reset" triggers software reset */
                        if (strncmp((const char *)rx_buffer, "reset", 5) == 0) {
                            ESP_LOGW(TAG, "Reset command received, restarting...");
                            vTaskDelay(pdMS_TO_TICKS(500));
                            esp_restart();
                        }
                    }
                }
                break;

            case UART_FIFO_OVF:
                ESP_LOGW(TAG, "HW FIFO overflow");
                uart_flush_input(UART_NUM);
                xQueueReset(uart_queue);
                break;

            case UART_BUFFER_FULL:
                ESP_LOGW(TAG, "Ring buffer full");
                uart_flush_input(UART_NUM);
                xQueueReset(uart_queue);
                break;

            case UART_BREAK:
                ESP_LOGI(TAG, "UART break detected");
                break;

            case UART_PARITY_ERR:
                ESP_LOGW(TAG, "Parity error");
                break;

            case UART_FRAME_ERR:
                ESP_LOGW(TAG, "Frame error");
                break;

            case UART_PATTERN_DET:
                uart_get_buffered_data_len(UART_NUM, &buffered_size);
                ESP_LOGI(TAG, "Pattern detected, %d bytes buffered", (int)buffered_size);
                break;

            default:
                ESP_LOGI(TAG, "UART event type: %d", event.type);
                break;
            }
        }
    }
}

/* --- LED Heartbeat Task --- */
static void led_task(void *pvParameters)
{
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
        vTaskDelay(pdMS_TO_TICKS(100));
        gpio_set_level(LED_PIN, 0);
        vTaskDelay(pdMS_TO_TICKS(900));
    }
}

/* --- app_main --- */
void app_main(void)
{
    ESP_LOGI(TAG, "uart_events starting");
    ESP_LOGI(TAG, "Free heap: %lu bytes", esp_get_free_heap_size());

    /* Configure UART */
    uart_config_t uart_config = {
        .baud_rate = UART_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };

    ESP_ERROR_CHECK(uart_driver_install(
        UART_NUM,
        UART_RX_BUF,     /* RX ring buffer */
        UART_TX_BUF,     /* TX ring buffer */
        UART_QUEUE_SIZE, /* event queue size */
        &uart_queue,     /* event queue handle */
        0                /* interrupt flags */
    ));

    ESP_ERROR_CHECK(uart_param_config(UART_NUM, &uart_config));

    /* Use default UART0 pins (no need to call uart_set_pin for UART0)
     * For other UART instances or custom pins:
     *   uart_set_pin(UART_NUM, TX_PIN, RX_PIN, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
     */

    /* Optional: detect a pattern (e.g., newline) */
    uart_enable_pattern_det_baud_intr(UART_NUM, '\n', 1, 9, 0, 0);
    uart_pattern_queue_reset(UART_NUM, UART_QUEUE_SIZE);

    ESP_LOGI(TAG, "UART%d initialized at %d baud, 8N1", UART_NUM, UART_BAUD);
    ESP_LOGI(TAG, "Type characters to echo. Send 'reset' to restart.");

    /* Create tasks */
    xTaskCreate(uart_event_task, "uart_event", 4096, NULL, 10, NULL);
    xTaskCreate(led_task, "led_heartbeat", 2048, NULL, 5, NULL);

    /* app_main can exit; the created tasks keep running */
    ESP_LOGI(TAG, "Initialization complete, tasks running");
}
