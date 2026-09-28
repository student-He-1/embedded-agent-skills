# WiFi STA Example

Connect to a WiFi router as a station (STA), obtain IP address, and monitor connection.

## Configuration

Edit these lines in `wifi_sta.ino`:

```cpp
const char* WIFI_SSID = "your-ssid";
const char* WIFI_PASSWORD = "your-password";
```

## Build & Flash

```powershell
python scripts\arduino_build.py examples\wifi_sta --board esp32s3
python scripts\arduino_upload.py examples\wifi_sta --port <PORT> --board esp32s3
```

## Expected Output

```
=== WiFi STA Example ===
Connecting to: your-ssid
......
WiFi connected!
IP address: 192.168.1.100
RSSI: -45 dBm
MAC: AA:BB:CC:DD:EE:FF
Channel: 6
Connected, RSSI: -45 dBm, free heap: 250000
```

## Notes

- ESP32 supports **2.4GHz only** — does NOT support 5GHz WiFi
- If connection fails, check SSID (case-sensitive), password, and router settings
- WiFi uses ~50KB of heap; monitor with `ESP.getFreeHeap()`
- ADC2 pins are unavailable when WiFi is on (ESP32 classic only)
- For production, store credentials in `Preferences` (NVS) instead of hardcoding

## Validation Level

- Compile: verified
- Flash: verified
- Hardware: WiFi connection requires user's actual network credentials to verify
