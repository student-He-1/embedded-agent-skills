# MicroPython API Reference (ESP32)

Use this when writing or modifying MicroPython code for ESP32. Covers the most commonly used modules and patterns.

## machine Module

### Pin (GPIO)

```python
from machine import Pin

# Output
led = Pin(2, Pin.OUT)
led.on()              # Set high
led.off()             # Set low
led.value(1)          # Set explicitly
led.toggle()          # Toggle (MicroPython 1.17+)

# Input
btn = Pin(0, Pin.IN)                     # Floating input
btn_pu = Pin(0, Pin.IN, Pin.PULL_UP)     # With internal pull-up
btn_pd = Pin(0, Pin.IN, Pin.PULL_DOWN)   # With internal pull-down
btn.value()                              # Read (0 or 1)

# Interrupt
btn.irq(trigger=Pin.IRQ_FALLING, handler=callback)
# trigger options: IRQ_RISING, IRQ_FALLING, IRQ_LOW_LEVEL, IRQ_HIGH_LEVEL
```

**Pin numbering**: Use GPIO numbers, not physical pin numbers. For example, physical pin 13 on a 30-pin DevKit may be GPIO14.

### UART

```python
from machine import UART

# UART1 on pins TX=17, RX=16
uart = UART(1, baudrate=115200, tx=17, rx=16)
uart.init(baudrate=9600, bits=8, parity=None, stop=1)  # Reconfigure

uart.write("hello\r\n")
uart.writebytes([0x01, 0x02, 0x03])

data = uart.read()            # Read all available bytes (or None)
data = uart.read(10)          # Read up to 10 bytes
line = uart.readline()        # Read until newline
char = uart.readchar()        # Read single character (-1 if none)

uart.any()                    # Number of bytes available
uart.flush()                  # Wait for TX to complete
```

**UART0** is typically connected to the USB-UART (REPL). Using UART0 for custom communication will disable REPL. Use UART1 or UART2 for peripherals.

### Timer

```python
from machine import Timer

tim = Timer(0)
tim.init(period=1000, mode=Timer.PERIODIC, callback=lambda t: print("tick"))
# period in milliseconds
# mode: Timer.PERIODIC or Timer.ONE_SHOT

tim.deinit()  # Stop and free timer
```

Timer IDs: 0-3 (ESP32). Timer callbacks run in interrupt context — keep them short.

### PWM (LED / Servo / Motor)

```python
from machine import Pin, PWM

pwm = PWM(Pin(2), freq=1000, duty=512)
# freq: 1 Hz - 40 MHz (ESP32)
# duty: 0-1023 (10-bit resolution on ESP32)

pwm.duty(256)       # 25% duty cycle
pwm.freq(50)        # Change frequency (servo: 50 Hz)
pwm.deinit()        # Disable PWM
```

**Servo control** (50 Hz, duty 40-115 for 0-180 degrees on most servos):
```python
servo = PWM(Pin(13), freq=50)
servo.duty(40)   # ~0 degrees
servo.duty(77)   # ~90 degrees
servo.duty(115)  # ~180 degrees
```

### ADC (Analog Input)

```python
from machine import ADC, Pin

adc = ADC(Pin(34))
adc.atten(ADC.ATTN_0DB)      # 0-1.0V (default)
adc.atten(ADC.ATTN_2_5DB)    # 0-1.3V
adc.atten(ADC.ATTN_6DB)      # 0-2.0V
adc.atten(ADC.ATTN_11DB)     # 0-3.3V (most common)

adc.width(ADC.WIDTH_12BIT)   # 0-4095 (default)
adc.width(ADC.WIDTH_10BIT)   # 0-1023

val = adc.read()             # Raw value
volts = val * 3.3 / 4095     # Convert to voltage (with 11dB atten)
```

**Input-only pins** (ESP32 classic): GPIO34, 35, 36, 39 — no pull-up/down, output not supported.

### I2C

```python
from machine import I2C, Pin

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
# I2C ID: 0 or 1 on ESP32
# freq: standard 100000, fast 400000

devices = i2c.scan()                    # Returns list of 7-bit addresses
i2c.writeto(0x3C, b"\x00\xAF")          # Write to device
data = i2c.readfrom(0x3C, 16)           # Read 16 bytes
i2c.readfrom_mem(0x3C, 0x00, 16)        # Read from memory address
i2c.writeto_mem(0x3C, 0x00, b"\xAF")    # Write to memory address
```

Common I2C addresses: 0x3C (SSD1306 OLED), 0x48 (ADS1115), 0x68 (MPU6050/DS3231), 0x76 (BME280).

**Pull-up resistors**: I2C requires 4.7K pull-ups on SDA and SCL. Some modules have them built in.

### SPI

```python
from machine import SPI, Pin

spi = SPI(1, baudrate=10000000, sck=Pin(18), mosi=Pin(23), miso=Pin(19))
# SPI ID: 1 or 2 (SPI0 is used by flash)
# baudrate: up to 80 MHz (ESP32)

cs = Pin(5, Pin.OUT, value=1)
cs.off()
spi.write(b"\x01\x02\x03")
data = spi.read(4)
data = spi.read(4, write=0xFF)  # Read while writing 0xFF
cs.on()
```

### RTC (Deep Sleep)

```python
import machine

# Deep sleep for 10 seconds
machine.deepsleep(10000)  # milliseconds

# Wake from deep sleep
if machine.reset_cause() == machine.DEEPSLEEP_RESET:
    print("Woke from deep sleep")

# Wake from pin (ext0)
rtc = machine.RTC()
rtc.wake_on_ext0(pin=Pin(0, Pin.IN), level=0)
```

### WDT (Watchdog Timer)

```python
from machine import WDT
wdt = WDT(timeout=5000)  # 5 second timeout
wdt.feed()               # Reset watchdog (must call regularly)
# If not fed within timeout, hardware reset occurs
```

## network Module (WiFi)

### Station Mode (Connect to WiFi)

```python
import network

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect("SSID", "PASSWORD")

# Wait for connection
while not wlan.isconnected():
    pass

print("Connected:", wlan.ifconfig())
# Returns (ip, subnet, gateway, dns)

wlan.disconnect()
wlan.active(False)
```

### Access Point Mode

```python
import network

ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid="ESP32-AP", password="12345678")
print("AP IP:", ap.ifconfig()[0])
```

### Scan Networks

```python
import network
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
nets = wlan.scan()
for ssid, bssid, channel, rssi, authmode, hidden in nets:
    print(f"{ssid.decode()} channel={channel} rssi={rssi}")
```

## urequests / HTTP

```python
import urequests

# GET
response = urequests.get("http://api.example.com/data")
data = response.json()
response.close()

# POST
response = urequests.post("http://api.example.com/data",
                          json={"sensor": 23.5})
print(response.status_code)
response.close()
```

Always call `response.close()` to free memory.

## MQTT (umqtt.simple)

```python
from umqtt.simple import MQTTClient

client = MQTTClient("esp32_client", "broker.example.com", port=1883)
client.connect()

def callback(topic, msg):
    print(f"Received: {topic} = {msg}")

client.set_callback(callback)
client.subscribe("esp32/command")

# Publish
client.publish("esp32/temperature", "23.5")

# Check for messages (non-blocking)
client.check_msg()

client.disconnect()
```

## uasyncio (Async)

```python
import uasyncio as asyncio
from machine import Pin

async def blink():
    led = Pin(2, Pin.OUT)
    while True:
        led.toggle()
        await asyncio.sleep_ms(500)

async def read_sensor():
    while True:
        # read sensor
        await asyncio.sleep(1)

async def main():
    task1 = asyncio.create_task(blink())
    task2 = asyncio.create_task(read_sensor())
    await asyncio.gather(task1, task2)

asyncio.run(main())
```

## Common Pitfalls

1. **GPIO6-11 are for SPI flash** — never use them.
2. **GPIO34-39 are input-only** — no output, no pull-up/down.
3. **GPIO0 is boot strapping** — pulling it low at reset enters download mode.
4. **UART0 is REPL** — using it for custom communication breaks the REPL.
5. **PWM duty is 0-1023** on ESP32 (10-bit), not 0-100 or 0-255.
6. **ADC is non-linear** — especially near 0V and 3.3V. Calibrate for accuracy.
7. **I2C needs pull-ups** — 4.7K on SDA/SCL.
8. **time.sleep() blocks everything** — use `uasyncio.sleep()` in async code.
9. **Memory is limited** — avoid large strings, use `gc.collect()` periodically.
10. **Interrupt callbacks are restricted** — no `time.sleep()`, no `print()` in production, minimal allocation.
