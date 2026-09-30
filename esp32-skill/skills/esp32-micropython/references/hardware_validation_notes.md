# Hardware Validation Notes

Use this for verified ESP32 lessons, CP2102 serial, boot mode, flash layout, pin constraints, and real-board caveats.

## Verified Environment

Validated combination:

- Board: Generic ESP32 DevKit / NodeMCU-32S
- Chip: ESP32-D0WD-V3 (Xtensa dual-core, 240 MHz, WiFi+BT)
- USB-UART: Silicon Labs CP2102 (VID_10C4 PID_EA60), COM3
- MicroPython: v1.11.0 (Python 3.4 compatible)
- Flash: ~2 MB filesystem (4 MB flash total)
- Validated: GPIO LED blink (GPIO2), UART, WiFi STA, I2C OLED
- Crystal: 40 MHz

Other boards (ESP32-S3, ESP32-C3, ESP32-S2), USB-UART chips (CH340, FTDI), and MicroPython versions may work, but are not guaranteed by these notes.

## CP2102 USB-UART Notes

- Windows driver: Silicon Labs CP210x VCP driver. If the board shows as "CP210x USB to UART Bridge" in Device Manager with a COM port, it's working.
- If it shows as "USB Serial" with a yellow warning triangle, install the driver from https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers
- The CP2102 connects to ESP32 UART0 (GPIO1 TX, GPIO3 RX).
- Auto-download: Most DevKits use the CP2102's RTS/DTR signals to automatically reset the ESP32 and pull GPIO0 low for flashing. If auto-download fails, manually hold BOOT and press RESET.
- Baud rates: REPL and serial monitor at 115200. Flashing can use 460800 or 921600.
- If the COM port appears but mpremote can't connect:
  1. Close Thonny, Arduino IDE, VOFA+, or any program using that COM port.
  2. Press the RESET button on the board, then immediately try connecting.
  3. Check that MicroPython firmware is installed (not a C firmware).

## Boot Mode And Strapping Pins (ESP32 Classic)

| Pin | Function | Notes |
|---|---|---|
| GPIO0 | Boot mode | Low = download/flash mode, High = normal boot (SPI flash) |
| GPIO2 | Boot mode | Must be high for normal boot (usually has external pull-up) |
| GPIO5 | Boot mode | Must be high for normal boot |
| GPIO12 | Flash voltage | Low = 3.3V flash (most modules), High = 1.8V flash |
| GPIO15 | Boot mode | Must be high for normal boot |

**Critical:** Do not use these pins as outputs unless you accept boot risk. If you must, ensure external pull resistors set the correct level at reset.

### Manual Download Mode

If auto-flash fails:
1. Press and hold BOOT (GPIO0 low).
2. Press and release RESET (EN low then high).
3. Release BOOT.
4. The chip is now in download mode. Run esptool or mpremote.

## GPIO Pin Constraints (ESP32 Classic)

| Pins | Status | Notes |
|---|---|---|
| GPIO0-5 | Usable with caution | GPIO0, 2, 5 are strapping pins |
| GPIO6-11 | **Do not use** | Connected to SPI flash chip |
| GPIO12-19 | Usable | GPIO12 is strapping (flash voltage) |
| GPIO21-23 | Usable | Common for I2C (21=SDA, 22=SCL), SPI |
| GPIO25-27 | Usable | DAC-capable (25, 26) |
| GPIO32-39 | Input only (34-39) | 32, 33 are RTC GPIO; 34-39 have no pull-up/down |
| GPIO1, 3 | UART0 | Connected to CP2102, used for REPL |

### Input-Only Pins

GPIO34, 35, 36, 39 are input-only:
- Cannot be configured as output.
- No internal pull-up or pull-down.
- Good for analog sensors (ADC) and buttons (with external pull-up).

### LED Pin

- Most ESP32 DevKits / NodeMCU boards have an onboard LED on **GPIO2**.
- Some boards use GPIO5 or GPIO16.
- ESP32-S3-DevKitC uses GPIO48 for a WS2812 addressable LED (not a regular LED — needs RMT/LEDC, not `Pin.OUT`).
- ESP32-C3-DevKitM uses GPIO8.

Always verify with the board schematic or test with `Pin(n, Pin.OUT).on()`.

## Flash Layout

Typical 4 MB flash layout for MicroPython (classic ESP32):

| Offset | Size | Content |
|---|---|---|
| 0x1000 | ~28 KB | Bootloader (second stage) |
| 0x8000 | 4 KB | Partition table |
| 0x9000 | 4 KB | NVS |
| 0x10000 | ~1.4 MB | MicroPython application (firmware) |
| ~0x170000 | ~1 MB | FAT filesystem (where your .py files live) |
| 0x3F0000 | 4 KB | phy_init (RF calibration data) |

> These offsets are the classic-ESP32 ones (`write_flash -z 0x1000 ...`).
> **ESP32-S3 and ESP32-C3 builds flash the application at `0x0` instead** —
> use the offset printed on the firmware's download page for your chip.
> The filesystem is mounted at `/`. Files you upload go here.

Check free space:
```python
import uos
fs = uos.statvfs('/')
free_kb = fs[0] * fs[3] // 1024
total_kb = fs[0] * fs[2] // 1024
print(f"{free_kb} KB free / {total_kb} KB total")
```

## Power Supply

- ESP32 at full WiFi TX can draw up to **500 mA peak**.
- A weak USB port or long/thin cable causes brownouts during WiFi transmission.
- Symptoms: random resets during WiFi, "guru meditation" errors, flash read failures.
- Use a powered USB hub or external 5V supply if brownouts occur.
- Add a 100 uF capacitor across 5V/GND near the module if power is marginal.
- The CP2102 is powered from USB; the ESP32 module may be powered from USB or an onboard regulator (AMS1117-3.3).

## Reset Behavior

After uploading a new `main.py`, reset the board to run it:
- Soft reset: `Ctrl+D` in REPL, or `machine.soft_reset()` — re-runs boot.py and main.py.
- Hard reset: Press RESET button, or `machine.reset()` — full power-on reset.
- If `main.py` crashes on boot, you may not be able to access REPL. To recover:
  1. Connect via serial (Thonny or mpremote).
  2. Press RESET, then immediately press Ctrl+C repeatedly to interrupt boot.
  3. Once at `>>>` prompt, fix or delete `main.py`:
     ```python
     import uos
     uos.remove('main.py')
     ```
  4. Reset and try again.

## Common Hardware Pitfalls

1. **Charge-only USB cable**: The cable has power but no data wires. The board powers on but no COM port appears. Use a data cable.
2. **Wrong COM port**: Multiple USB-serial devices may be connected. Use `detect_board.py` to identify.
3. **Port occupied**: Thonny, VOFA+, serial monitor, or another mpremote session has the port open. Close it.
4. **Boot button stuck**: If GPIO0 is held low, the chip always enters download mode and never runs main.py.
5. **5V on GPIO**: Kills the pin or chip. ESP32 is 3.3V and not 5V tolerant. Always level-shift.
6. **Floating strapping pins**: Ensure GPIO0, 2, 5, 12, 15 have defined levels at reset. Most DevKits have pull resistors.
7. **I2C without pull-ups**: SDA/SCL need 4.7K pull-ups to 3.3V. Many modules have them built in; bare wires don't.
8. **UART TX/RX crossover**: MCU TX connects to adapter RX, MCU RX connects to adapter TX. If it's not working, swap them.
9. **WiFi not connecting**: Check SSID (case-sensitive), password, 2.4GHz only (ESP32 doesn't support 5GHz), and signal strength.
10. **Out of memory**: Large strings or many imports can cause MemoryError. Use `gc.collect()` and delete unused objects.

## MicroPython Firmware Version Check

```python
import sys
print(sys.implementation)  # (name='micropython', version=(1, 22, 1))
print(sys.version)         # 3.4.0 (Python compatibility version)
print(sys.platform)        # esp32
```

If `sys.implementation` shows a different name (e.g., 'cpython'), you're not running on the board — you're running on the PC.
