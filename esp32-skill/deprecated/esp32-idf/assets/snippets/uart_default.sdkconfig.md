# UART Default — sdkconfig + Code Snippet

## Use Case

Basic UART communication at 115200 8N1, typically UART0 connected to the CP2102 USB-UART bridge for serial console and flashing.

## sdkconfig Keys

```text
CONFIG_ESP_CONSOLE_UART_DEFAULT=y
CONFIG_ESP_CONSOLE_UART_BAUDRATE=115200
CONFIG_UART_ISR_IN_IRAM=y
```

- `CONFIG_ESP_CONSOLE_UART_DEFAULT=y`: Route console output to UART0 (default pins).
- `CONFIG_ESP_CONSOLE_UART_BAUDRATE=115200`: Console baud rate.
- `CONFIG_UART_ISR_IN_IRAM=y`: Keep UART ISR in IRAM for reliability during flash operations.

For built-in USB-Serial-JTAG (ESP32-S3/C3) instead of UART0:

```text
CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y
# CONFIG_ESP_CONSOLE_UART_DEFAULT is not set
```

## Code Pattern (Event-Driven)

```c
#include "driver/uart.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

#define UART_NUM     UART_NUM_0
#define UART_BAUD    115200
#define RX_BUF       4096
#define TX_BUF       2048
#define QUEUE_SIZE   20

static QueueHandle_t uart_queue;

static void uart_event_task(void *pvParameters) {
    uart_event_t event;
    uint8_t data[1024];
    for (;;) {
        if (xQueueReceive(uart_queue, &event, portMAX_DELAY)) {
            if (event.type == UART_DATA) {
                int len = uart_read_bytes(UART_NUM, data, event.size, pdMS_TO_TICKS(100));
                if (len > 0) {
                    /* Process data */
                    uart_write_bytes(UART_NUM, (const char *)data, len); /* echo */
                }
            }
        }
    }
}

void init_uart(void) {
    uart_config_t cfg = {
        .baud_rate = UART_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    uart_driver_install(UART_NUM, RX_BUF, TX_BUF, QUEUE_SIZE, &uart_queue, 0);
    uart_param_config(UART_NUM, &cfg);
    /* UART0 uses default pins; for other UARTs:
       uart_set_pin(UART_NUM, TX_PIN, RX_PIN, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE); */
    xTaskCreate(uart_event_task, "uart_event", 4096, NULL, 10, NULL);
}
```

## Default UART Pins

| Chip | UART0 TX | UART0 RX |
|---|---|---|
| ESP32 (classic) | GPIO1 | GPIO3 |
| ESP32-S2 | GPIO43 | GPIO44 |
| ESP32-S3 | GPIO43 | GPIO44 |
| ESP32-C3 | GPIO20 | GPIO21 (or GPIO18/19 USB-JTAG) |
| ESP32-C6 | GPIO16 | GPIO17 |

## Notes

- UART0 is connected to the CP2102 on most dev boards. Do not reassign its pins if you need serial console or auto-download.
- `uart_driver_install()` allocates ring buffers. The RX buffer should be large enough for bursts of data.
- Always use `pdMS_TO_TICKS()` for timeouts in `uart_read_bytes()`.
- For simple blocking transmit without the driver, `ets_printf()` or `ESP_LOGx()` works for console output.
- The UART event task should have sufficient stack (4096 words minimum) and higher priority than application tasks.
