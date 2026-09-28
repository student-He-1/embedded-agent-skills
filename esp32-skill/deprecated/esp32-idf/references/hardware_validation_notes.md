# Hardware Validation Notes

Use this for verified ESP32-S3 lessons, CP2102 serial, boot mode, flash voltage, built-in USB-JTAG, and real-board caveats.

## Verified Environment

Validated combination:

- Board: Generic ESP32-S3-DevKitC-1 (or compatible)
- USB-UART: Silicon Labs CP2102 (VID_10C4 PID_EA60)
- SDK: ESP-IDF v5.3 LTS
- Compiler: xtensa-esp-elf (ESP-IDF bundled)
- Flash tool: esptool.py (bundled with ESP-IDF)
- Validated peripherals: GPIO LED blink, UART0, WiFi STA, LEDC PWM, SPI
- Validated clock: CPU 240 MHz (default), flash 80 MHz DIO

Other boards (ESP32 classic, ESP32-C3, ESP32-S2), USB-UART chips (CH340, FTDI), and SDK versions may work, but are not guaranteed by these notes.

## CP2102 USB-UART Notes

The CP2102 is a USB-to-UART bridge commonly found on ESP32 dev boards.

- Windows driver: Silicon Labs CP210x VCP driver. Install from https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers
- On Windows, appears as `COMx` in Device Manager under "Ports (COM & LPT)".
- The CP2102 connects to ESP32 UART0 (GPIO1 TX, GPIO3 RX on classic ESP32; GPIO43 TX, GPIO44 RX on ESP32-S3).
- Auto-download circuit: most dev boards use the CP2102's RTS/DTR signals to automatically reset the ESP32 and pull GPIO0 low for download mode. If auto-download fails, manually hold BOOT (GPIO0) and press RESET, then release BOOT.
- Baud rates: 115200 is standard for serial monitor. Flashing can use 460800 or 921600.
- If the CP2102 COM port appears but esptool cannot connect, check:
  1. The board is powered (USB cable may be charge-only).
  2. The correct COM port is selected.
  3. No other program (serial monitor, VOFA+, etc.) is using the port.
  4. The CP2102 driver is correctly installed (not a generic "USB Serial" driver).

## Boot Mode And Strapping Pins

ESP32 chips sample strapping pins at reset to determine boot mode.

### ESP32-S3 Strapping Pins

| Pin | Function | Notes |
|---|---|---|
| GPIO0 | Boot mode | Low = download/flash mode, High = SPI boot (normal) |
| GPIO46 | Boot mode | Must be high for normal SPI boot |
| GPIO3 | JTAG source | Low = USB-JTAG, High = external JTAG |
| GPIO4 | Voltage | Flash voltage selection (usually don't touch) |

### Classic ESP32 Strapping Pins

| Pin | Function | Notes |
|---|---|---|
| GPIO0 | Boot mode | Low = download, High = SPI boot |
| GPIO2 | Boot mode | Must match flash mode (usually high) |
| GPIO5 | Boot mode | Must be high for normal boot |
| GPIO12 | Flash voltage | Low = 3.3V flash (most boards), High = 1.8V |
| GPIO15 | Boot mode | Must be high for normal boot |

**Critical:** Do not use strapping pins as ordinary GPIO outputs unless you accept the boot risk. If you must use them, ensure their state at reset is correct (use external pull-ups/downs).

### Manual Download Mode

If auto-download fails:

1. Press and hold the BOOT button (GPIO0 low).
2. Press and release the RESET button (EN/RST low then high).
3. Release BOOT.
4. The chip is now in download mode. Run esptool.

## Flash Voltage And Size

- Most ESP32 modules use 3.3V SPI flash.
- Some modules use 1.8V flash (e.g., ESP32-WROOM-32E with certain flash chips). GPIO12 (classic) or GPIO4 (S3) selects the voltage at boot.
- If the wrong flash voltage is selected, the chip will not boot or will crash randomly.
- Common flash sizes: 4 MB (most dev boards), 8 MB, 16 MB.
- Set flash size in sdkconfig: `CONFIG_ESPTOOLPY_FLASHSIZE_4MB=y`.
- If unsure, use `--flash_size detect` in esptool to auto-detect.

## Built-in USB-JTAG (ESP32-S3 / C3)

ESP32-S3 and ESP32-C3 have a built-in USB Serial/JTAG controller, eliminating the need for an external JTAG adapter.

### ESP32-S3 USB-JTAG Pins

| Pin | Function |
|---|---|
| GPIO19 | USB D- |
| GPIO20 | USB D+ |

- Connect a USB cable directly to GPIO19/GPIO20 (through a USB connector).
- Appears as a composite device: one serial port (for console) + one JTAG interface.
- In sdkconfig, set `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y` to route console output to the USB-JTAG serial port.
- OpenOCD config: `interface/esp_usb_jtag.cfg` + `target/esp32s3.cfg`.
- Do not use GPIO19/GPIO20 for other purposes if you rely on built-in USB-JTAG.

### ESP32-C3 USB-JTAG Pins

| Pin | Function |
|---|---|
| GPIO18 | USB D- |
| GPIO19 | USB D+ |

Same as S3. Note: GPIO18/GPIO19 are also UART0 pins by default on C3.

## UART Pin Assignments

### ESP32-S3

| UART | Default TX | Default RX |
|---|---|---|
| UART0 | GPIO43 | GPIO44 |
| UART1 | Any GPIO | Any GPIO |

UART0 is connected to the CP2102 on most dev boards. Do not reassign UART0 pins if you need serial console and auto-download.

### Classic ESP32

| UART | Default TX | Default RX |
|---|---|---|
| UART0 | GPIO1 | GPIO3 |
| UART1 | GPIO10 | GPIO9 (often used for flash) |
| UART2 | GPIO17 | GPIO16 |

UART0 is connected to USB-UART. UART1 pins conflict with SPI flash on many modules — use UART2 instead or remap UART1 to other pins.

## GPIO Output Current

- ESP32 GPIO can source/sink up to ~40 mA per pin (absolute max), but recommended is ~20 mA.
- Do not drive LEDs directly without a current-limiting resistor (220-470 ohms typical).
- Do not drive motors, relays, or high-power devices directly from GPIO — use a transistor, MOSFET, or driver IC.
- GPIO is 3.3V logic. Use level shifters for 5V peripherals.

## Reset And Boot Log

After flashing, the ESP32 should print a boot log on the serial console at 115200 baud:

```
ESP-ROM:esp32s3-20210327
Build:Mar 27 2021
rst:0x1 (POWERON),boot:0x8 (SPI_FAST_FLASH_BOOT)
SPIWP:0xee
mode:DIO, clock div:1
load:0x3fce3808,len:0x43c
load:0x403c9700,len:0xbe4
load:0x403cc700,len:0x2a38
entry 0x403c98d4
I (29) boot: ESP-IDF v5.3 2nd stage bootloader
I (29) boot: compile time ...
I (29) boot: chip revision: v0.1
...
```

If you see:
- `rst:0x10 (RTCWDT_RTC_RESET)` — watchdog reset, likely a crash or infinite loop.
- `boot:0x0` — wrong boot mode, check strapping pins.
- `flash read err, 1000` — flash communication error, check flash voltage/size/mode.
- `Guru Meditation Error` — CPU exception, use `addr2line` to decode the backtrace.

## Decoding Crashes (Backtrace)

When the ESP32 crashes, it prints a backtrace:

```
Guru Meditation Error: Core  0 panic'ed (StoreProhibited). Exception was unhandled.
Core 0 register dump:
...
ELF file SHA256: ...
Backtrace: 0x42001234:0x3fceb560 0x42005678:0x3fceb590
```

Decode with:

```powershell
# ESP-IDF provides a tool
idf.py monitor

# Or manually with addr2line
xtensa-esp-elf-addr2line -pfiaC -e build\my_project.elf 0x42001234 0x42005678
```

`idf.py monitor` automatically decodes backtraces if the ELF file is present.

## Power Supply Notes

- ESP32-S3 at full WiFi TX can draw up to 500 mA peak.
- A weak USB port or long/thin USB cable can cause brownouts during WiFi transmission.
- Symptoms of insufficient power: random resets during WiFi, `brownout detector` reset, flash read errors.
- Use a powered USB hub or external 5V power supply if brownouts occur.
- Add a 100 uF electrolytic capacitor across 5V/GND near the module if power is marginal.
- The CP2102 is powered from USB; the ESP32 module may be powered from USB or an external regulator.

## Common Hardware Pitfalls

1. **Charge-only USB cable**: The cable has power wires but no data wires. The board powers on but no COM port appears. Use a data cable.
2. **Wrong COM port**: Multiple USB-serial devices may be connected. Use `detect_esp_device.py` to identify the right one.
3. **Port occupied**: Another program (VOFA+, Arduino IDE serial monitor, putty) has the COM port open. Close it before flashing.
4. **Boot button stuck**: If GPIO0 is held low, the chip always enters download mode and never runs the app.
5. **5V on GPIO**: Kills the pin or the whole chip. Always level-shift.
6. **Floating strapping pins**: Ensure strapping pins have defined levels at reset. Most dev boards have pull-ups/downs.
7. **Missing NVS partition**: If the partition table lacks an NVS partition, `nvs_flash_init()` fails and WiFi/BT won't start.
8. **Flash mode mismatch**: If sdkconfig says QIO but the module only supports DIO, the chip won't boot. Use DIO as the safe default.
