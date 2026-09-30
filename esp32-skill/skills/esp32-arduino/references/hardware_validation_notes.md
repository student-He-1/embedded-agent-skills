# Hardware Validation Notes

Verified lessons from real ESP32 / ESP32-S3 boards. These are empirical observations, not theoretical.

## Verified Environment

Validated combinations:

### ESP32 classic (CP2102 USB-UART)
- Chip: ESP32-D0WD-V3 (Xtensa dual-core 240MHz)
- USB bridge: CP2102 (VID_10C4 PID_EA60)
- Serial: COM3 (typical)
- Onboard LED: GPIO2 (verified controllable in Arduino)
- Arduino core: 3.3.10-cn
- Verified (Arduino): compile, flash, GPIO2 blink, serial output

### ESP32-S3-N16R8 (native USB)
- Chip: ESP32-S3 (QFN56, revision v0.2)
- Flash: 16MB
- PSRAM: 8MB Octal (embedded)
- USB: USB-Serial/JTAG (native, no external bridge)
- Serial: COM6 (typical, may re-enumerate after reset)
- Arduino core: 3.3.10-cn
- Verified: compile, flash, serial output, WS2812 RGB LED (GPIO48, with PSRAM disabled)
- **Working FQBN**: `esp32:esp32:esp32s3:PSRAM=opi,USBMode=hwcdc,CDCOnBoot=cdc` (use `PSRAM=disabled` instead when driving the onboard WS2812). `CDCOnBoot=cdc` is mandatory — see the serial monitor notes below.
- **Onboard WS2812 RGB LED on GPIO48**: This board (ESP32-S3-WROOM-1-N16R8) has a WS2812 RGB LED wired to GPIO48. However, GPIO48 is also SPICLK_N for Octal PSRAM. When OPI PSRAM is enabled (Tools → PSRAM → OPI PSRAM), GPIO48 is claimed by the PSRAM peripheral and the WS2812 **will not light up**. To use the onboard RGB LED:
  - Set Tools → PSRAM → **Disabled**
  - Use Adafruit_NeoPixel library on GPIO48, type NEO_GRB + NEO_KHZ800
  - Trade-off: loses 8MB PSRAM
- The red power LED and blue serial TX indicator are separate from the WS2812 and are not user-controllable.
- **Octal SPI pins**: GPIO26–GPIO32 are used for Octal Flash/PSRAM (SPICS1/SPIHD/SPIWP/SPICS0/SPICLK/SPIQ/SPID). Do not use them. GPIO6–GPIO11 are available as normal GPIO on this board.

## Board Detection

`detect_board.py` uses `arduino-cli board list` + `esptool chip_id`.

- If `arduino-cli board list` shows a port but no board name, the chip is still detectable via esptool.
- If esptool fails with "invalid head of packet", the board may need manual boot mode (hold BOOT, press RST).
- ESP32-S3 with USB-Serial/JTAG may show as "USB Serial Device" in Windows Device Manager.
- CP2102 boards require the Silicon Labs CP210x driver. CH340 boards require CH340 driver.

## Flash and Reset Behavior

### Upload process
1. esptool opens the serial port
2. Toggles DTR/RTS to reset the chip into download mode
3. Reads chip ID and features
4. Erases and writes bootloader, partitions, app
5. Verifies via hash
6. Hard resets via RTS

### After upload
- The board automatically resets and runs the new firmware
- ESP32-S3 may re-enumerate the USB serial port (same COM number usually)
- Wait 1–2 seconds before opening serial monitor

### Manual boot mode
If auto-reset fails:
1. Hold BOOT button
2. Press RST/EN
3. Release RST
4. Release BOOT
5. Retry upload

## Serial Upload Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Port busy / Permission denied | Another program holds the port | Close serial monitor, Thonny, PuTTY, VOFA+ |
| Wrong boot mode / invalid head | Auto-reset failed | Manual boot mode (BOOT+RST) |
| Could not open port | Board disconnected or bad cable | Check cable (data, not power-only), reconnect |
| Timed out waiting for packet | Wrong baud or board not in download mode | Lower upload speed, manual boot mode |
| COM port disappears after upload | S3 USB re-enumeration | Wait 2s, refresh port list |

## Pin Validation Lessons

### ESP32 classic
- GPIO2 is the most common onboard LED pin (NodeMCU, DevKit)
- GPIO2 is also a strapping pin — must be high at boot for normal boot (internal pull-up handles this)
- GPIO0 must be high at boot (low = download mode). Don't drive it low at boot.
- GPIO12 must be low at boot (internal pull-down) for correct flash voltage. Driving it high at boot can cause boot failure.
- GPIO1/3 are UART0 — using them for GPIO breaks serial upload and debug.

### ESP32-S3
- **GPIO48 WS2812 + PSRAM conflict (verified)**: GPIO48 has a WS2812 RGB LED and is the SPICLK_N IO-MUX function. With OPI PSRAM enabled the WS2812 does not light; with `PSRAM=disabled` Adafruit_NeoPixel drives it correctly. Record only what was measured — the official ESP-IDF GPIO summary table does **not** list GPIO47/GPIO48 as reserved (it flags GPIO26–32 and, for octal parts, GPIO33–37, plus GPIO19/20). So: GPIO48 is unusable as a WS2812/data line in this PSRAM configuration, and **GPIO47 must not be assumed reserved**.
- GPIO26–GPIO32 are Octal SPI Flash/PSRAM pins — do not use on N16R8 boards.
- GPIO6–GPIO11 are available as normal GPIO on Octal PSRAM boards (unlike Quad PSRAM boards).
- GPIO19/20 are USB D-/D+ — do not use for GPIO when USB serial is active.
- **GPIO46 in normal boot mode (GPIO0 high) is ignored** (Espressif esptool docs: "In normal boot mode (GPIO0 high), GPIO46 is ignored"). It must be left floating or driven low only to *enter the serial bootloader*, and it has an internal **weak pull-down**, not a pull-up. Do not document it as "must be high".
- GPIO0 is BOOT button — low at boot = download mode.

### External LED verification
When onboard LED is unavailable or uncertain:
1. Connect LED anode (long leg) to a GPIO pin via 220Ω resistor
2. Connect LED cathode (short leg) to GND
3. Use `digitalWrite(pin, HIGH)` to turn on
4. Test with blink sketch

## Power Considerations

- ESP32 draws up to 500mA during WiFi transmit. USB port can usually supply this.
- ESP32-S3 with PSRAM may draw more peak current.
- If brownout resets occur during WiFi, use a powered USB hub or external 5V supply.
- 3.3V regulator on dev boards typically supplies 500mA–1A.
- Do not power external sensors/modules from the 3.3V pin if they draw >100mA.

## Serial Monitor Notes

- Default baud: 115200 (most common)
- Boot ROM output is at 115200 on ESP32-S3
- Crash dumps are at 115200
- If serial output is garbled, check baud rate match
- If only `ESP-ROM:esp32s3-...` appears but no app output, the app may have crashed before `Serial.begin()` or `setup()` didn't reach `Serial.println()`
- **ESP32-S3 native USB shows nothing at all: check `CDCOnBoot` first.** `USBMode=hwcdc` only selects the USB-Serial/JTAG controller; it does not map `Serial` onto it. With the default `CDCOnBoot=Disabled`, `Serial` remains `HardwareSerial` (UART0 → GPIO43/44), so `Serial.println()` never reaches the USB port and the build reports no error at all. Use `CDCOnBoot=cdc`.
- **Do not use `serial_monitor.py --reset` on ESP32-S3 native USB.** The DTR/RTS toggle is meant for a classic USB-UART bridge; on S3 it drives the native USB lines and drops the chip into `waiting for download` (observed `rst:0x15 (USB_UART_CHIP_RESET),boot:0x20 (DOWNLOAD(USB/UART0))`), after which the app stops running and the port stays silent. Re-flash (upload ends with a hard reset) to recover.
- Add `delay(1000)` after `Serial.begin()` to give the monitor time to connect
- On S3 native USB, `Serial.write()` blocks for up to ~20 × `tx_timeout_ms` when the host is not reading. Call `Serial.setTxTimeoutMs(0)` after `Serial.begin()` so serial logging can never stall `setup()`/`loop()`.

## Validation Levels

Always report which level was reached:

1. **Source inspection** — code reviewed, no obvious errors
2. **Compile success** — `arduino-cli compile` returns 0
3. **Flash success** — `arduino-cli upload` returns 0, hash verified
4. **Serial output observed** — `Serial.println()` output visible in monitor
5. **Physical behavior verified** — LED blinks, sensor reads, motor moves, etc.

Do not claim "it works" unless level 5 is reached. If only compile/flash succeeded, say "compiled and flashed successfully; hardware behavior not yet verified."
