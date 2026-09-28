# FreeRTOS And ESP-IDF Runtime Rules

Use this when changing C/C++ runtime code, interrupts, timing, WiFi/Bluetooth, NVS, or external-module behavior in ESP-IDF projects.

## Initialization Order

ESP-IDF applications start from `app_main()` (not `main()`). The system has already initialized FreeRTOS, flash, and default handlers before `app_main` runs.

Typical initialization order:

```c
void app_main(void) {
    // 1. NVS flash (required for WiFi, BT, and many drivers)
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        nvs_flash_erase();
        nvs_flash_init();
    }

    // 2. Event loop (for WiFi/BT events)
    esp_event_loop_create_default();

    // 3. Peripheral drivers (GPIO, UART, SPI, I2C, etc.)

    // 4. WiFi / Bluetooth (if used)

    // 5. Application tasks
    xTaskCreate(my_task, "my_task", 4096, NULL, 5, NULL);
}
```

Do not call `nvs_flash_init()` after `esp_wifi_start()` — WiFi requires NVS to be initialized first.

## FreeRTOS Task Rules

- Use `xTaskCreate()` or `xTaskCreatePinnedToCore()` for tasks.
- Stack size is in **words** (4 bytes each), not bytes. `4096` = 16 KB.
- ESP32 dual-core chips can pin tasks: `xTaskCreatePinnedToCore(func, name, stack, arg, prio, &handle, 0)` for core 0, `1` for core 1.
- WiFi and BT protocol stacks run on core 0 by default. Pin heavy application tasks to core 1 to avoid interference.
- Use `vTaskDelay(pdMS_TO_TICKS(ms))` for delays. Do not use raw tick numbers — they depend on `CONFIG_FREERTOS_HZ`.
- Never call `vTaskDelay()` inside an ISR. Use `vTaskDelayFromISR()` or, better, defer work to a task.

Common stack sizes:

| Task type | Stack size (words) |
|---|---|
| Simple GPIO/LED task | 2048 (8 KB) |
| UART processing task | 4096 (16 KB) |
| WiFi application task | 8192 (32 KB) |
| MQTT/HTTP task | 8192-16384 (32-64 KB) |
| JSON parsing / TLS | 16384+ (64 KB+) |

If a task crashes with `Stack canary watchpoint triggered`, increase the stack size.

## Interrupt Service Routines (ISRs)

- ISRs must be marked with `IRAM_ATTR` if they need to run while flash is disabled (e.g., during SPI flash operations).
- Keep ISRs short. Do not call `printf`, `vTaskDelay`, blocking I/O, or complex logic in an ISR.
- Use `xSemaphoreGiveFromISR()`, `xTaskNotifyFromISR()`, or `xQueueSendFromISR()` to wake a task for deferred processing.
- GPIO interrupts: use `gpio_isr_handler_add()` with `gpio_install_isr_service()`. Do not use `gpio_intr_config` directly for shared interrupts.
- UART interrupts: prefer `uart_driver_install()` with event queue over raw UART ISRs.

```c
// Good: defer work to a task
static void IRAM_ATTR gpio_isr_handler(void* arg) {
    uint32_t gpio_num = (uint32_t)arg;
    xSemaphoreGiveFromISR(gpio_sem, NULL);
}

static void gpio_task(void* arg) {
    while (1) {
        if (xSemaphoreTake(gpio_sem, portMAX_DELAY)) {
            // Do the actual work here
            process_button();
        }
    }
}
```

## Queues, Semaphores, and Event Groups

- Use `xQueueCreate()` for data passing between tasks/ISRs.
- Use `xSemaphoreCreateBinary()` / `xSemaphoreCreateMutex()` for synchronization.
- Use `EventGroupHandle_t` for multiple event bits (e.g., WiFi connected + MQTT connected).
- For WiFi/BT system events, use the ESP event loop: `esp_event_handler_register(WIFI_EVENT, ...)`.
- Do not use `vTaskSuspendAll()`/`xTaskResumeAll()` around long operations — it disables the scheduler.

## WiFi Rules

```c
// WiFi STA mode minimal flow
wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
esp_wifi_init(&cfg);
esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL);
esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL);
esp_wifi_set_mode(WIFI_MODE_STA);
wifi_config_t wifi_config = {
    .sta = {
        .ssid = "MY_SSID",
        .password = "MY_PASSWORD",
    },
};
esp_wifi_set_config(WIFI_IF_STA, &wifi_config);
esp_wifi_start();
esp_wifi_connect();
```

- Always call `nvs_flash_init()` before `esp_wifi_init()`.
- Register event handlers before `esp_wifi_start()`.
- Handle `WIFI_EVENT_STA_DISCONNECTED` with retry logic (backoff).
- Do not call `esp_wifi_connect()` from the event handler directly — use a task or timer.
- WiFi uses about 100 KB of RAM. Ensure sufficient heap (`esp_get_free_heap_size()`).
- For low-power applications, use WiFi modem sleep or Light Sleep.

## Bluetooth Rules

- Classic Bluetooth (BT) and BLE can be enabled separately or together via sdkconfig.
- `CONFIG_BTDM_CTRL_MODE_BLE_ONLY=y` for BLE only (saves RAM).
- `CONFIG_BTDM_CTRL_MODE_BTDM=y` for dual mode (uses more RAM).
- BLE uses the NimBLE or Bluedroid stack. NimBLE is lighter and recommended for new projects.
- Initialize BT after NVS and event loop.
- Do not use WiFi and BT simultaneously if not needed — both share the 2.4 GHz radio and antenna.

## NVS (Non-Volatile Storage)

```c
nvs_handle_t handle;
nvs_open("storage", NVS_READWRITE, &handle);
nvs_set_u32(handle, "counter", value);
nvs_commit(handle);  // Must commit to persist
nvs_get_u32(handle, "counter", &value);
nvs_close(handle);
```

- Always call `nvs_commit()` after writes.
- NVS keys are limited to 15 characters.
- NVS namespace is limited to 15 characters.
- Use `nvs_flash_erase()` only when the NVS partition is corrupted or version mismatch.
- Do not store large data in NVS — use a filesystem (FAT/LittleFS) partition for that.

## Delay And Timing

- `vTaskDelay(pdMS_TO_TICKS(ms))` — task delay (yields CPU).
- `esp_rom_delay_us(us)` — microsecond busy-wait (blocks CPU, use sparingly).
- `ets_delay_us(us)` — legacy microsecond delay.
- `esp_timer` — high-resolution timer (microsecond), can be one-shot or periodic.
- `gptimer` — general-purpose hardware timer (ESP-IDF v5.x).
- For periodic control loops, use `esp_timer` or a hardware timer ISR, not `vTaskDelay` in a tight loop.

## Common Mistakes

- Calling `vTaskDelay(1000)` instead of `vTaskDelay(pdMS_TO_TICKS(1000))` — 1000 ticks at 100 Hz = 10 seconds, not 1 second.
- Starting WiFi without `nvs_flash_init()`.
- Using `printf()` in an ISR — can crash or block.
- Forgetting `nvs_commit()` after NVS writes.
- Allocating too-small task stacks (stack overflow causes crash with canary watchpoint).
- Pinning all tasks to core 0, starving WiFi/BT.
- Calling blocking functions from `app_main()` without creating a task — `app_main()` itself is a task with limited stack.
- Not handling `WIFI_EVENT_STA_DISCONNECTED` — WiFi will never reconnect.
- Using `GPIO_NUM_0` or `GPIO_NUM_46` as output — these are boot strapping pins and can prevent the chip from booting.
- Connecting 5V signals to ESP32 GPIO — not 5V tolerant, can damage the chip.

## External Modules

For sensors, displays, motor drivers, servos, radios, or custom modules:

- Collect the datasheet, schematic or wiring table, voltage levels, protocol, address/mode pins, reset/enable pins, and required timing before writing a driver.
- ESP32 GPIO is **3.3V only and not 5V tolerant**. Use level shifters for 5V modules.
- Verify wiring: power, ground, pull-ups (I2C requires 4.7K pull-ups on SDA/SCL), level shifting, reset/enable, boot strapping pins, UART TX/RX crossover, SPI CS/ mode, and shared pins.
- If repeated firmware attempts fail but sdkconfig, build, flash, and logic look correct, ask the user to verify wiring, power, module mode, address pins, chip select, UART crossover, pull-ups, and test procedure.
