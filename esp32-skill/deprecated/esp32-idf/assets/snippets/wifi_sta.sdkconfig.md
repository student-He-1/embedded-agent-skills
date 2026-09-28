# WiFi STA — sdkconfig + Code Snippet

## Use Case

Connect the ESP32 to a WiFi network as a station (STA), obtain an IP via DHCP, and handle disconnect/reconnect.

## sdkconfig Keys

```text
CONFIG_ESP_WIFI_ENABLED=y
CONFIG_ESP_WIFI_STA_DISCONNECTED_PM_ENABLE=n
CONFIG_ESP_WIFI_NVS_ENABLED=y
CONFIG_LWIP_DHCP_DOES_ARP_CHECK=y
```

- `CONFIG_ESP_WIFI_ENABLED=y`: Enable WiFi stack (required).
- WiFi requires NVS: ensure `CONFIG_NVS_ENABLED=y` (default).
- For low power, enable `CONFIG_ESP_WIFI_STA_DISCONNECTED_PM_ENABLE=y` and use modem sleep.

## Code Pattern

```c
#include "nvs_flash.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

static const char *TAG = "wifi";
static EventGroupHandle_t wifi_event_group;
#define WIFI_CONNECTED_BIT BIT0
#define WIFI_FAIL_BIT      BIT1

static int s_retry_num = 0;
#define MAX_RETRY 5

static void event_handler(void* arg, esp_event_base_t event_base,
                          int32_t event_id, void* event_data) {
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        if (s_retry_num < MAX_RETRY) {
            esp_wifi_connect();
            s_retry_num++;
            ESP_LOGI(TAG, "retry to connect to the AP");
        } else {
            xEventGroupSetBits(wifi_event_group, WIFI_FAIL_BIT);
        }
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t* event = (ip_event_got_ip_t*) event_data;
        ESP_LOGI(TAG, "got ip:" IPSTR, IP2STR(&event->ip_info.ip));
        s_retry_num = 0;
        xEventGroupSetBits(wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

void wifi_init_sta(const char *ssid, const char *password) {
    wifi_event_group = xEventGroupCreate();

    ESP_ERROR_CHECK(nvs_flash_init());
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &event_handler, NULL, NULL);
    esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &event_handler, NULL, NULL);

    wifi_config_t wifi_config = {0};
    strncpy((char *)wifi_config.sta.ssid, ssid, sizeof(wifi_config.sta.ssid) - 1);
    strncpy((char *)wifi_config.sta.password, password, sizeof(wifi_config.sta.password) - 1);
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    EventBits_t bits = xEventGroupWaitBits(wifi_event_group,
            WIFI_CONNECTED_BIT | WIFI_FAIL_BIT, pdFALSE, pdFALSE, portMAX_DELAY);

    if (bits & WIFI_CONNECTED_BIT) {
        ESP_LOGI(TAG, "Connected to SSID:%s", ssid);
    } else if (bits & WIFI_FAIL_BIT) {
        ESP_LOGE(TAG, "Failed to connect to SSID:%s", ssid);
    }
}
```

## Required Component Dependencies

In `main/CMakeLists.txt`:

```cmake
idf_component_register(
    SRCS "main.c"
    INCLUDE_DIRS "."
    REQUIRES nvs_flash esp_wifi esp_event esp_netif
)
```

## Notes

- Always call `nvs_flash_init()` before `esp_wifi_init()`. WiFi stores calibration data in NVS.
- Register event handlers **before** `esp_wifi_start()` to avoid missing the `WIFI_EVENT_STA_START` event.
- Use an event group to synchronize connection status between the event handler and application code.
- WiFi uses ~100 KB of RAM. Monitor free heap with `esp_get_free_heap_size()`.
- Do not call `esp_wifi_connect()` directly from the `WIFI_EVENT_STA_DISCONNECTED` handler without retry limiting — it can cause a tight loop.
- For production, store WiFi credentials in NVS rather than hardcoding. Use `nvs` to read/write them.
- ESP32 supports 2.4 GHz only (802.11 b/g/n). It does NOT support 5 GHz.
