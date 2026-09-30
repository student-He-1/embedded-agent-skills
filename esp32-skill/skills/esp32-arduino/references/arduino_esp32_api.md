# Arduino ESP32 API Reference

Use this when writing or modifying ESP32 Arduino code. Covers GPIO, PWM (LEDC), WiFi, Bluetooth, I2C, SPI, UART, ADC, timers, and common pitfalls.

## GPIO

### Basic digital I/O

```cpp
pinMode(2, OUTPUT);
digitalWrite(2, HIGH);
digitalWrite(2, LOW);
int state = digitalRead(4);
```

### Pin restrictions

**ESP32 classic:**
- GPIO6–11: SPI flash, never use
- GPIO34–39: input only (no OUTPUT, no pull-up/down)
- GPIO0, 2, 5, 12, 15: strapping pins (affect boot mode)
- GPIO1/3: UART0 (serial upload/debug)

**ESP32-S3:**
- Flash/PSRAM pins depend on board design:
  - Octal PSRAM boards (e.g. N16R8): **GPIO26–32** are Octal SPI Flash/PSRAM (SPICS1/SPIHD/SPIWP/SPICS0/SPICLK/SPIQ/SPID). Do not use. GPIO6–11 are available.
  - Quad PSRAM boards: GPIO6–11 are SPI flash. Do not use.
- GPIO19/20: USB D-/D+ (when USB serial enabled)
- GPIO0, 3, 45, 46: strapping pins
- GPIO22–25: do not exist on QFN56
- **GPIO48**: WS2812 RGB LED on many S3 boards, and the SPICLK_N IO-MUX function. With OPI PSRAM enabled the WS2812 does not light (verified on N16R8); disable PSRAM to use the LED. Do not extend this to GPIO47 (SPICLK_P) — no evidence it is reserved.

### Interrupts

```cpp
volatile int counter = 0;

void IRAM_ATTR isr() {
  counter++;
}

void setup() {
  pinMode(4, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(4), isr, FALLING);
}
```

- ISR must be marked `IRAM_ATTR` on ESP32
- Keep ISRs short — no `delay()`, no `Serial.print()`, no WiFi calls
- Use `volatile` for variables shared with ISR
- `portENTER_CRITICAL` / `portEXIT_CRITICAL` for multi-word shared variables

## PWM / LEDC

ESP32 Arduino core 3.x uses the LEDC peripheral for PWM. `analogWrite()` is deprecated.

```cpp
const int LED_PIN = 2;
const int LEDC_CHANNEL = 0;
const int LEDC_FREQ = 5000;
const int LEDC_RESOLUTION = 8;  // 0-255

void setup() {
  ledcSetup(LEDC_CHANNEL, LEDC_FREQ, LEDC_RESOLUTION);
  ledcAttachPin(LED_PIN, LEDC_CHANNEL);
}

void loop() {
  for (int duty = 0; duty <= 255; duty++) {
    ledcWrite(LEDC_CHANNEL, duty);
    delay(10);
  }
}
```

- 16 channels (0–15) on ESP32 classic, 8 on S3
- Resolution: 1–16 bits
- Frequency: depends on resolution (higher res = lower max freq)
- Servo: use `ESP32Servo` library or LEDC at 50Hz with 16-bit resolution

## WiFi

### STA mode (connect to router)

```cpp
#include <WiFi.h>

const char* ssid = "your-ssid";
const char* password = "your-password";

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("WiFi connected");
  Serial.println(WiFi.localIP());
}
```

### AP mode (access point)

```cpp
WiFi.softAP("ESP32-AP", "password");
IPAddress ip = WiFi.softAPIP();
```

### HTTP client

```cpp
#include <HTTPClient.h>

HTTPClient http;
http.begin("https://api.example.com/data");
int code = http.GET();
if (code > 0) {
  String payload = http.getString();
}
http.end();
```

### WiFi pitfalls

- Don't call WiFi functions from an ISR
- `WiFi.begin()` is non-blocking; poll `WiFi.status()`
- Use `WiFi.setAutoReconnect(true)` for automatic reconnection
- WiFi and Bluetooth share the radio — using both may reduce throughput
- Don't hardcode credentials in shared code; use `Preferences` or a config file

## Bluetooth

### Serial Bluetooth

```cpp
#include "BluetoothSerial.h"
BluetoothSerial SerialBT;

void setup() {
  SerialBT.begin("ESP32-BT");
}

void loop() {
  if (SerialBT.available()) {
    Serial.write(SerialBT.read());
  }
}
```

### BLE (Bluetooth Low Energy)

```cpp
#include <BLEDevice.h>
#include <BLEServer.h>

BLEServer* pServer;

void setup() {
  BLEDevice::init("ESP32-BLE");
  pServer = BLEDevice::createServer();
  BLEService* pService = pServer->createService("0000ffe0-0000-1000-8000-00805f9b34fb");
  pService->start();
  BLEAdvertising* pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->start();
}
```

## I2C

```cpp
#include <Wire.h>

void setup() {
  Wire.begin(21, 22);  // SDA, SCL (default SDA=21, SCL=22 on classic)
  // On S3: Wire.begin(8, 9) or any available pins
}

void writeRegister(uint8_t addr, uint8_t reg, uint8_t value) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

uint8_t readRegister(uint8_t addr, uint8_t reg) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom(addr, (uint8_t)1);
  return Wire.read();
}
```

- I2C requires 4.7kΩ pull-up resistors on SDA/SCL (many modules include them)
- ESP32 is 3.3V — do not connect 5V I2C devices directly without level shifting
- Scan I2C bus: use an I2C scanner sketch to find device addresses
- On ESP32-S3, default I2C pins may differ; specify explicitly

## SPI

```cpp
#include <SPI.h>

const int CS_PIN = 5;

void setup() {
  SPI.begin(18, 19, 23, CS_PIN);  // SCK, MISO, MOSI, SS
  pinMode(CS_PIN, OUTPUT);
}

void transfer(uint8_t* data, size_t len) {
  digitalWrite(CS_PIN, LOW);
  SPI.transfer(data, len);
  digitalWrite(CS_PIN, HIGH);
}
```

- HSPI (VSPI) default: SCK=18, MISO=19, MOSI=23, SS=5
- SPI pins are flexible on ESP32 (GPIO matrix), but use default for best performance
- SPI flash uses GPIO6–11 — never conflict

## UART / Serial

```cpp
// Serial0 (USB-serial) is always available
Serial.begin(115200);

// Serial1 (UART1) on custom pins
Serial1.begin(9600, SERIAL_8N1, 16, 17);  // RX, TX

// Serial2 (UART2) on classic ESP32 only
Serial2.begin(9600, SERIAL_8N1, 25, 26);
```

- ESP32 classic: 3 UARTs (Serial, Serial1, Serial2)
- ESP32-S3: 3 UARTs (Serial is USB-Serial/JTAG, Serial1, Serial2)
- UART pins are flexible (GPIO matrix)
- `Serial.flush()` waits for TX to complete
- Use `Serial.available()` and `Serial.read()` in loop, avoid blocking

## ADC

```cpp
int raw = analogRead(34);  // 0-4095 (12-bit default)
float voltage = raw * (3.3 / 4095.0);
```

- ADC1 pins: GPIO32–39 (classic), GPIO1–GPIO10 (S3, CH0–CH9)
- ADC2 pins: GPIO0, 2, 4, 12–15, 25–27 (classic) — **not available when WiFi is on**
- Input range: do not exceed 3.3V on any ADC pin
- Attenuation: `analogSetPinAttenuation(pin, ADC_11db)` gives the widest range.
  Note 11 dB saturates at roughly **3.1V**, not 3.3V — values near the rail clip
- ADC is non-linear near 0V and the top of the range; calibrate for precision
- On S3, ADC2 is **GPIO11–GPIO20** (ADC2 channel = GPIO number − 11) and, like the
  classic ESP32, **it is also used by WiFi**: ESP-IDF documents that
  `adc2_get_raw()` may fail between `esp_wifi_start()` and `esp_wifi_stop()`.
  Prefer ADC1 (`GPIO1–GPIO10`) whenever WiFi may be active. GPIO0 and GPIO21 have
  no ADC function on S3; GPIO14/15/16 are ADC2_CH3/CH4/CH5.

## Timers

### Ticker (simple periodic callback)

```cpp
#include <Ticker.h>
Ticker timer;

void onTimer() {
  // do something periodically
}

void setup() {
  timer.attach_ms(100, onTimer);  // every 100ms
}
```

### Hardware timer interrupt

```cpp
hw_timer_t* timer = NULL;
volatile int interruptCounter = 0;

void IRAM_ATTR onTimer() {
  interruptCounter++;
}

void setup() {
  timer = timerBegin(0, 80, true);  // 80MHz prescaler → 1MHz
  timerAttachInterrupt(timer, &onTimer, true);
  timerAlarmWrite(timer, 1000000, true);  // 1 second
  timerAlarmEnable(timer);
}
```

## EEPROM / Preferences

```cpp
#include <Preferences.h>
Preferences prefs;

void setup() {
  prefs.begin("my-app", false);  // namespace, read-only=false
  prefs.putString("ssid", "my-wifi");
  String ssid = prefs.getString("ssid", "default");
  prefs.end();
}
```

- `Preferences` uses NVS (Non-Volatile Storage) — preferred over EEPROM
- EEPROM library is emulated on flash; use `EEPROM.begin(size)` and `EEPROM.commit()`
- Don't write to flash frequently (wear leveling has limits)

## File System

```cpp
#include <LittleFS.h>

void setup() {
  LittleFS.begin(true);  // true = format if failed
  File f = LittleFS.open("/data.txt", "w");
  f.println("hello");
  f.close();
}
```

- LittleFS: preferred for ESP32 Arduino 3.x
- SPIFFS: older, still supported but deprecated
- SD card: use `SD.h` with SPI
- Upload files via IDE: Tools → ESP32 LittleFS Data Upload (requires plugin)

## Common Pitfalls

1. **`analogWrite()` deprecated** — use LEDC API on core 3.x
2. **GPIO34–39 as output** — input only on classic ESP32
3. **WiFi + ADC2 conflict** — ADC2 unavailable when WiFi is on (classic)
4. **`delay()` in ISR** — will crash; there is no ISR-safe delay. Defer work with `xTaskNotifyFromISR` / `xSemaphoreGiveFromISR`, or set a flag
5. **Large local arrays** — stack overflow; use `static` or `malloc`
6. **`while(!Serial)` on native USB** — blocks forever if no monitor opens
7. **5V on GPIO** — ESP32 is 3.3V only; will damage the pin
8. **I2C without pull-ups** — bus will hang; add 4.7kΩ resistors
9. **Forgetting `Wire.begin()`** — I2C won't work without it
10. **`String` concatenation in loop** — heap fragmentation; use fixed buffers
