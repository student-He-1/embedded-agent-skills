# Debug Backends

Use this reference when the user asks the agent to flash or debug a connected ESP32 board. Keep esptool-flash and OpenOCD/GDB as separate backends.

Before selecting a backend for an unspecified device, run:

```powershell
python scripts\detect_esp_device.py
python scripts\check_idf_project.py <project-dir>
```

Device detection is read-only. Do not flash when multiple devices are connected, detection is unknown, or the physical chip conflicts with the project target until the user confirms the intended port and chip.

Zero detected devices is an inconclusive result. Before saying that no board is connected, inspect OS serial ports and USB PnP devices. A CP2102 or CH340 USB-UART bridge may expose only a virtual COM port. On Windows:

```powershell
Get-PnpDevice -PresentOnly | Where-Object { $_.Class -eq 'Ports' }
python scripts\detect_esp_device.py --no-identify
```

## esptool Flash Backend

This is the standard flashing path for all ESP32 projects. It works with any USB-UART bridge (CP2102, CH340, FTDI) and the built-in USB-Serial-JTAG.

### Automated Flashing (skill helper)

```powershell
# Auto-detect port and chip, flash the project
python scripts\esp_flash.py <project-dir>

# Specify port
python scripts\esp_flash.py <project-dir> --port COM6

# Specify chip and baud
python scripts\esp_flash.py <project-dir> --port COM6 --chip esp32s3 --baud 921600

# Erase flash first
python scripts\esp_flash.py <project-dir> --port COM6 --erase

# Dry run (print command without executing)
python scripts\esp_flash.py <project-dir> --dry-run
```

### Manual esptool Commands

```powershell
# Identify chip (read-only)
esptool.py --port COM6 chip_id

# Read MAC address
esptool.py --port COM6 read_mac

# Flash full ESP-IDF image
esptool.py --chip esp32s3 --port COM6 --baud 460800 write_flash --flash_mode dio --flash_freq 80m --flash_size detect --verify 0x0 build\bootloader\bootloader.bin 0x8000 build\partition_table\partition-table.bin 0x10000 build\my_project.bin

# Flash only the app (bootloader and partitions unchanged)
esptool.py --chip esp32s3 --port COM6 --baud 460800 write_flash 0x10000 build\my_project.bin

# Erase entire flash
esptool.py --port COM6 erase_flash

# Erase a specific region
esptool.py --port COM6 erase_region 0x9000 0x6000

# Read flash content
esptool.py --port COM6 read_flash 0x0 0x400000 flash_backup.bin

# Verify flashed image
esptool.py --port COM6 verify_flash 0x10000 build\my_project.bin
```

### Flash Offsets Reference

| Offset | Content |
|---|---|
| `0x0` | Bootloader (2nd stage) |
| `0x8000` | Partition table |
| `0x9000` | NVS data (default) |
| `0xe000` | OTA data initial (if OTA partition table) |
| `0xf000` | PHY init data |
| `0x10000` | Application (factory, default single-app) |

These offsets come from the partition table. Always check `partitions.csv` or `build/flash_args` for the actual offsets.

### Flashing Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `Failed to connect to ESP32: No serial data received` | Wrong port, board not powered, wrong boot mode | Check port, USB cable, try manual boot mode (hold BOOT + press RESET) |
| `A fatal error occurred: Could not open COM6` | Port occupied or doesn't exist | Close other serial programs, check Device Manager |
| `Invalid head of packet` | Baud rate too high, noisy USB connection | Lower baud to 115200, use shorter USB cable |
| `Flash download failed` | Wrong flash mode/size, power issue | Use `--flash_mode dio --flash_size detect`, check power |
| `Timed out waiting for packet header` | Auto-download circuit not working | Use manual boot mode |
| `Wrong chip id` | sdkconfig target doesn't match physical chip | Run `esptool chip_id`, set correct `--chip` |

## OpenOCD / GDB Debug Backend

Use this backend for source-level debugging, breakpoints, register inspection, and core dump analysis. Requires an MSPM0? No — an ESP32-capable OpenOCD build (bundled with ESP-IDF).

### Prerequisites

- OpenOCD with ESP32 support (comes with ESP-IDF: `$IDF_PATH/tools/openocd-esp32/`)
- `xtensa-esp-elf-gdb` (Xtensa chips) or `riscv32-esp-elf-gdb` (RISC-V chips)
- A JTAG interface: built-in USB-JTAG (S3/C3) or external (FT2232, J-Link, etc.)

### Built-in USB-JTAG (ESP32-S3/C3)

No external hardware needed. Connect USB to the USB-JTAG port (GPIO19/GPIO20 on S3, GPIO18/GPIO19 on C3).

```powershell
# Start OpenOCD (one terminal)
openocd -f interface/esp_usb_jtag.cfg -f target/esp32s3.cfg

# In another terminal, start GDB
xtensa-esp-elf-gdb build\my_project.elf
```

Inside GDB:

```gdb
target remote :3333
monitor reset halt
break app_main
continue
next
step
print variable_name
backtrace
monitor reg
monitor reset run
quit
```

### External JTAG Adapter

For classic ESP32 or when built-in USB-JTAG pins are used for other purposes:

```powershell
# FT2232H (common in cheap JTAG adapters)
openocd -f interface/ftdi/esp32_devkitj_v1.cfg -f target/esp32.cfg

# J-Link
openocd -f interface/jlink.cfg -c "transport select jtag" -f target/esp32s3.cfg

# CMSIS-DAP / DAPLink
openocd -f interface/cmsis-dap.cfg -c "transport select jtag" -f target/esp32s3.cfg
```

JTAG pin connections (classic ESP32):

| ESP32 Pin | JTAG Signal |
|---|---|
| GPIO3 | TCK |
| GPIO9 | TDO |
| GPIO10 | TDI |
| GPIO5 | TMS |
| GND | GND |
| 3.3V | VTG (sense, not power) |

Note: On classic ESP32, GPIO9/GPIO10 are often used for SPI flash. JTAG may not work on modules with integrated flash unless those pins are broken out. Use ESP32-S3/C3 with built-in USB-JTAG for the easiest debug experience.

### OpenOCD Helper Script

The skill provides `openocd_debug.py` (when implemented) for common operations:

```powershell
# Probe connection (read-only, brief halt then resume)
python scripts\openocd_debug.py <project-dir> probe

# Flash via OpenOCD
python scripts\openocd_debug.py <project-dir> flash

# Read registers
python scripts\openocd_debug.py <project-dir> registers

# Run to a symbol breakpoint
python scripts\openocd_debug.py <project-dir> run-to-symbol --symbol app_main
```

### GDB Tips

- Load symbols: `file build/my_project.elf`
- Set breakpoint at function: `break function_name`
- Set breakpoint at line: `break main.c:42`
- Watch variable: `watch variable_name` (hardware watchpoint, limited count)
- View threads: `info threads`
- Switch thread: `thread 2`
- View FreeRTOS tasks: `xtensa-esp-elf-gdb` with ESP-IDF provides `freertos` commands if OpenOCD is configured with `-c 'set ESP32_ONLYCPU 1'`
- Detach without stopping: `detach` then `quit`

### Debug Safety

- Debug actions can halt the CPU and disturb real-time behavior. Warn the user before halting a motor, power stage, or time-sensitive control loop.
- Prefer UART logging (`ESP_LOGI`) or logic analyzer capture when non-intrusive observation is enough.
- `probe` and `registers` briefly halt the CPU without resetting, then resume.
- `run-to-symbol` intentionally resets and runs to the breakpoint.
- Do not run parallel OpenOCD sessions against one target.
- If the target appears flash-encrypted or secured, stop and ask the user for the encryption key or recovery procedure.

## Panic Handler And Backtrace Decoding

When the ESP32 crashes, the panic handler prints register state and a backtrace to the serial console. This is the first debugging tool — no JTAG needed.

### Automatic Decoding with idf.py monitor

```powershell
idf.py -p COM6 monitor
```

If the ELF file exists in `build/`, `idf.py monitor` automatically decodes backtrace addresses to function names and line numbers.

### Manual Decoding

```powershell
# Xtensa chips (ESP32, S2, S3)
xtensa-esp-elf-addr2line -pfiaC -e build\my_project.elf 0x42001234 0x42005678

# RISC-V chips (C3, C6, H2)
riscv32-esp-elf-addr2line -pfiaC -e build\my_project.elf 0x42001234
```

### Common Exception Causes

| Exception | Meaning | Common Cause |
|---|---|---|
| `StoreProhibited` | Write to invalid address | NULL pointer dereference, stack overflow, use-after-free |
| `LoadProhibited` | Read from invalid address | NULL pointer, array out of bounds |
| `InstrFetchProhibited` | Execute invalid address | Corrupted function pointer, stack smash |
| `IllegalInstruction` | Invalid CPU instruction | Flash corruption, wrong binary, stack overflow |
| `LoadStoreAlignment` | Unaligned memory access | Misaligned pointer on Xtensa (RISC-V handles this) |
| `DoubleException` | Exception within exception handler | Severe corruption, stack overflow |

## Core Dump Analysis

ESP-IDF can save a core dump to flash or UART on crash. Enable in sdkconfig:

```text
CONFIG_ESP_COREDUMP_ENABLE_TO_FLASH=y
CONFIG_ESP_COREDUMP_DATA_FORMAT_ELF=y
```

Analyze with:

```powershell
idf.py coredump-info
# or
python $env:IDF_PATH\components\esptool_py\esptool\esptool.py --chip esp32s3 --port COM6 read_flash 0x9000 0x6000 coredump.bin
python $env:IDF_PATH\components\espcoredump\espcoredump.py info_corefile -c coredump.bin build\my_project.elf
```

## When To Stop

Stop and ask the user before continuing if:

- The detected chip does not match the project's `CONFIG_IDF_TARGET`.
- The board controls motors, high-power outputs, or moving mechanisms and the next step will halt the CPU.
- Flashing would overwrite firmware the user did not ask to replace.
- The target is flash-encrypted or secured and the key is unknown.
- OpenOCD files are present but the user appears to be using esptool only, or vice versa.
- Multiple serial devices are connected and the correct port is ambiguous.
