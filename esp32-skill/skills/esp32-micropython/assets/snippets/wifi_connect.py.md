# WiFi Station Connect — MicroPython Snippet

## Use Case

Connect to a 2.4GHz WiFi network and obtain an IP address via DHCP.

## Code

```python
import network
import time

SSID = "your_wifi"
PASSWORD = "your_password"

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)

while not wlan.isconnected():
    time.sleep(0.5)
    print(".", end="")

print("\nConnected:", wlan.ifconfig())
```

## With timeout and status reporting

```python
import network
import time

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect("SSID", "PASSWORD")

for attempt in range(20):
    if wlan.isconnected():
        break
    print(f"Connecting... attempt {attempt+1}, status={wlan.status()}")
    time.sleep(1)

if wlan.isconnected():
    ip, subnet, gateway, dns = wlan.ifconfig()
    print(f"IP: {ip}, RSSI: {wlan.status('rssi')} dBm")
else:
    print(f"Failed. Status: {wlan.status()}")
```

## WiFi Status Codes

| Code | Meaning |
|---|---|
| 0 | IDLE |
| 1 | CONNECTING |
| 2 | WRONG_PASSWORD |
| 3 | NO_AP_FOUND |
| 4 | CONNECT_FAIL |
| 5 | GOT_IP (connected) |
| 255 | IDLE after disconnect |

## Notes

- ESP32 supports 2.4GHz only (802.11 b/g/n). No 5GHz.
- WiFi uses ~100KB RAM. Call `gc.collect()` if memory is tight.
- WiFi credentials are case-sensitive.
- For production, store credentials in a separate `config.py` file, not hardcoded in main.py.
- Use `wlan.config('mac')` to get the MAC address.
- `wlan.scan()` returns available networks: `(ssid, bssid, channel, rssi, authmode, hidden)`.
