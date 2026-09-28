# wifi_sta - WiFi station connection example
# Target: ESP32 (classic)
# Change WIFI_SSID and WIFI_PASSWORD below, then upload.

import network
import time
import machine

# === Configuration ===
WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
# =====================

print("WiFi STA example starting")

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# Disconnect if already connected
if wlan.isconnected():
    wlan.disconnect()

print(f"Connecting to WiFi: {WIFI_SSID}")
wlan.connect(WIFI_SSID, WIFI_PASSWORD)

# Wait for connection with timeout
max_attempts = 20
attempt = 0
while not wlan.isconnected() and attempt < max_attempts:
    attempt += 1
    print(f"  Attempt {attempt}/{max_attempts}... status={wlan.status()}")
    time.sleep(1)

if wlan.isconnected():
    ip, subnet, gateway, dns = wlan.ifconfig()
    print("WiFi connected!")
    print(f"  IP:      {ip}")
    print(f"  Subnet:  {subnet}")
    print(f"  Gateway: {gateway}")
    print(f"  DNS:     {dns}")
    print(f"  RSSI:    {wlan.status('rssi')} dBm")

    # Blink LED to indicate success
    led = machine.Pin(2, machine.Pin.OUT)
    for _ in range(5):
        led.on()
        time.sleep_ms(100)
        led.off()
        time.sleep_ms(100)
else:
    print(f"Failed to connect after {max_attempts} seconds")
    print(f"Final status: {wlan.status()}")
    print("Check SSID, password, and that the network is 2.4GHz (ESP32 does not support 5GHz)")

print("Done. Use wlan.isconnected() to check connection status in your app.")
