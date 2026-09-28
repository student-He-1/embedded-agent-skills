# Debugging ESP32 Arduino Projects

Use this when diagnosing crashes, serial issues, WiFi problems, or unexpected behavior.

## Serial Debugging

Primary debugging method. Add `Serial.println()` at key points.

```cpp
void setup() {
  Serial.begin(115200);
  delay(1000);  // wait for monitor to connect
  Serial.println("Setup started");

  // ... your init code ...

  Serial.println("Setup complete");
}

void loop() {
  static unsigned long lastPrint = 0;
  if (millis() - lastPrint > 1000) {
    lastPrint = millis();
    Serial.printf("Loop running, free heap: %d\n", ESP.getFreeHeap());
  }
}
```

### Useful debug functions

```cpp
ESP.getFreeHeap()       // free heap memory
ESP.getHeapSize()       // total heap
ESP.getMaxAllocHeap()   // largest free block
ESP.getChipModel()      // chip model string
ESP.getFlashChipSize()  // flash size in bytes
ESP.getPsramSize()      // PSRAM size
ESP.getCpuFreqMHz()     // CPU frequency
millis()                // milliseconds since boot
```

### Serial monitor tips

- Baud rate must match `Serial.begin(baud)`
- If output is garbled, check baud rate
- If no output, check that `Serial.begin()` is called and the correct port is selected
- On native USB (S3), add `delay(1000)` after `Serial.begin()` for monitor to connect
- `while (!Serial)` blocks forever on native USB if no monitor opens — avoid or add timeout

## Crash Diagnosis

### Reading crash dumps

When ESP32 crashes, it prints a dump to serial at 115200 baud:

```
Guru Meditation Error: Core  1 panic'ed (LoadProhibited). Exception was unhandled.
Core  1 register dump:
PC      : 0x400d1234  PS      : 0x00060330  A0      : 0x800d1abc  A1      : 0x3ffb1f00
...
ELF file SHA256: ...
```

Key fields:
- **Exception cause**: `LoadProhibited` (null pointer), `StoreProhibited`, `InstrFetchProhibited`, `Stack canary`, etc.
- **PC**: Program Counter where crash occurred
- **Backtrace**: function call chain

### Decoding crashes

**Method 1: Arduino IDE ESP Exception Decoder**
- Tools → ESP Exception Decoder
- Paste the crash dump
- Select the compiled `.elf` file (in build cache)

**Method 2: Command line with xtensa-esp32-elf-gdb**

```powershell
$gdb = "C:\Users\<user>\AppData\Local\Arduino15\packages\esp32\tools\xtensa-esp32-elf-gcc\*\bin\xtensa-esp32-elf-gdb.exe"
$elf = "C:\Users\<user>\AppData\Local\arduino\sketches\<hash>\<sketch>.ino.elf"
& $gdb -batch -ex "bt" -ex "info registers" $elf
```

### Common crash causes

| Exception | Likely Cause | Fix |
|-----------|-------------|-----|
| LoadProhibited / StoreProhibited | NULL pointer dereference, use-after-free | Check pointers before use, validate array indices |
| InstrFetchProhibited | Corrupted function pointer, bad ISR | Check function pointers, ISR registration |
| Stack canary / Stack overflow | Large local arrays, deep recursion | Use `static` or `malloc`, increase stack size |
| Cache disabled but cached memory accessed | ISR in flash without IRAM_ATTR | Mark ISR with `IRAM_ATTR` |
| Brownout detector | Power supply too weak | Use better power supply, disable brownout (not recommended) |
| Integer divide by zero | Division by zero in code | Check divisor before division |
| LoadStoreAlignment | Unaligned memory access | Use `memcpy` for unaligned data |

### Stack overflow

ESP32 Arduino `loop()` task has ~8KB stack. Large local arrays will overflow:

```cpp
// BAD — 4KB on stack, may overflow
void loop() {
  char buffer[4096];
  // ...
}

// GOOD — static allocation
static char buffer[4096];
void loop() {
  // ...
}
```

Check free stack:
```cpp
Serial.printf("Free stack: %d\n", uxTaskGetStackHighWaterMark(NULL));
```

## WiFi Debugging

### Connection failures

```cpp
WiFi.begin(ssid, password);
int attempts = 0;
while (WiFi.status() != WL_CONNECTED && attempts < 20) {
  delay(500);
  Serial.printf("WiFi status: %d, attempt %d\n", WiFi.status(), attempts++);
}
```

Status codes:
- `WL_IDLE_STATUS` (0): not trying
- `WL_NO_SSID_AVAIL` (1): SSID not found
- `WL_SCAN_COMPLETED` (2): scan done
- `WL_CONNECTED` (3): connected
- `WL_CONNECT_FAILED` (4): wrong password
- `WL_DISCONNECTED` (6): disconnected

### Common WiFi issues

- **Wrong password**: check case, special characters
- **2.4GHz only**: ESP32 does NOT support 5GHz WiFi
- **Signal too weak**: move closer, use external antenna
- **AP isolation**: router may isolate clients
- **DHCP failure**: try static IP
- **WiFi + ADC2 conflict**: ADC2 pins unavailable when WiFi is on (classic ESP32)

## I2C Debugging

### I2C scanner

```cpp
#include <Wire.h>

void setup() {
  Wire.begin(21, 22);
  Serial.begin(115200);
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.printf("I2C device found at 0x%02X\n", addr);
    }
  }
}
```

### Common I2C issues

- **No pull-ups**: add 4.7kΩ resistors on SDA/SCL
- **Wrong pins**: SDA/SCL swapped or wrong GPIO
- **5V device on 3.3V bus**: need level shifter
- **Bus lockup**: device holds SDA low; reset device or use I2C recovery
- **Address conflict**: two devices with same address

## Upload Debugging

See `hardware_validation_notes.md` for upload troubleshooting table.

### Automatic self-healing in arduino_upload.py

The bundled upload script retries and verifies automatically:

- **Auto retry on transient failures**: on `port busy`, `wrong boot mode`,
  `failed to connect`, `timed out waiting for packet`, or `no serial data`,
  it retries up to 3 times with a 2 s pause. Boot-mode failures print the
  BOOT+RST hint between attempts.
- **Post-flash re-enumeration check**: after a successful upload it waits 2 s
  and re-runs `arduino-cli board list` to confirm the board came back online
  (the port may change on S3 native USB-Serial/JTAG).
- `serial_monitor.py` classifies open failures as `busy` (close the holding
  program) or `missing` (check port name / cable) with actionable advice.

Manual recovery (BOOT+RST, cable reseat) is only needed after all retries
fail.

### Verbose upload

```powershell
arduino-cli upload -p COM6 --fqbn esp32:esp32:esp32s3 --verbose <project-dir>
```

### esptool direct

```powershell
$esptool = "C:\Users\<user>\AppData\Local\Arduino15\packages\esp32\tools\esptool_py\*\esptool.exe"
& $esptool --port COM6 chip_id
& $esptool --port COM6 flash_id
& $esptool --port COM6 erase_flash
```

## Interactive Debugging (S3 only)

ESP32-S3 with USB-Serial/JTAG supports debugging without an external probe:

1. In Arduino IDE: Tools → Upload Mode → "UART0 / Hardware CDC"
2. Tools → USB Mode → "Hardware CDC and JTAG"
3. Use the IDE debugger (Sketch → Debug) or GDB

This skill does not automate GDB debugging. For step-by-step debugging, use the Arduino IDE built-in debugger.

## When to Ask the User

Stop and ask if:
- The same crash occurs after 3+ code changes
- Hardware behavior contradicts the code (e.g., LED off but pin is HIGH)
- A library fails to compile with unclear errors
- The board is unresponsive after flash (may need manual boot mode recovery)
- Multiple boards are connected and the target is ambiguous
