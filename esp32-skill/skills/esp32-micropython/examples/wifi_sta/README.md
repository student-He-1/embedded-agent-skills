# wifi_sta — WiFi Station Connection

Connects the ESP32 to a 2.4GHz WiFi network as a station (STA). Prints IP configuration and signal strength.

## Before You Start

Edit `main.py` and set your WiFi credentials:

```python
WIFI_SSID = "your_wifi_name"
WIFI_PASSWORD = "your_wifi_password"
```

**Note**: ESP32 only supports 2.4GHz WiFi (802.11 b/g/n). It does NOT support 5GHz. If you have a dual-band router, ensure the 2.4GHz SSID is separate or enabled.

## Files

```
wifi_sta/
├── main.py
├── manifest.json
└── README.md
```

## Upload and Run

```powershell
mpremote connect COM3 fs cp main.py :main.py
mpremote connect COM3 exec "import machine; machine.soft_reset()"
```

## Expected Output

```
WiFi STA example starting
Connecting to WiFi: MyNetwork
  Attempt 1/20... status=1
  Attempt 2/20... status=1
WiFi connected!
  IP:      192.168.1.105
  Subnet:  255.255.255.0
  Gateway: 192.168.1.1
  DNS:     192.168.1.1
  RSSI:    -45 dBm
Done.
```

The onboard LED (GPIO2) will blink 5 times quickly on successful connection.

## WiFi Status Codes

| Status | Meaning |
|---|---|
| 0 | IDLE (no connection, no attempt) |
| 1 | CONNECTING |
| 2 | WRONG_PASSWORD |
| 3 | NO_AP_FOUND |
| 4 | CONNECT_FAIL |
| 5 | GOT_IP (connected) |
| 255 | IDLE after disconnect |

## Next Steps

Once connected, you can:

### HTTP Request

```python
import urequests
response = urequests.get("http://api.example.com/data")
print(response.json())
response.close()
```

### MQTT

```python
from umqtt.simple import MQTTClient
client = MQTTClient("esp32", "broker.example.com")
client.connect()
client.publish("esp32/status", "online")
```

### Scan Networks

```python
import network
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
for net in wlan.scan():
    print(net[0].decode(), net[3], "dBm")
```

## Troubleshooting

- **Status 2 (WRONG_PASSWORD)**: Double-check the password (case-sensitive).
- **Status 3 (NO_AP_FOUND)**: SSID not found. Check spelling and that it's a 2.4GHz network.
- **Status 4 (CONNECT_FAIL)**: Router rejected connection. Check MAC filtering, router logs.
- **Always times out**: Signal too weak, or 5GHz-only network. Move closer to router, use 2.4GHz.
- **MemoryError during WiFi**: WiFi uses ~100KB RAM. Close other connections or use `gc.collect()`.
- **Board resets during WiFi**: Power supply issue. Use a better USB cable or powered hub.
