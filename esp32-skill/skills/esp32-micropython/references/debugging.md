# Debugging MicroPython on ESP32

Use this reference when debugging MicroPython code, REPL issues, crashes, filesystem problems, or unresponsive boards.

## REPL Debugging

The REPL (Read-Eval-Print Loop) is your primary debugging tool. Access it via:

```powershell
mpremote connect COM3
# or
python scripts/serial_monitor.py -p COM3 -b 115200
# or Thonny's shell pane
```

### REPL Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+C` | Interrupt running program |
| `Ctrl+D` | Soft reset (re-run boot.py + main.py) |
| `Ctrl+E` | Paste mode (for multi-line code) |
| `Ctrl+X` | Exit mpremote REPL |
| `Ctrl+A` | Raw REPL mode (mpremote internal) |

### Print Debugging

```python
print("Value:", x)
print("Type:", type(x))
print("Dir:", dir(x))
```

For structured debugging:
```python
import sys
def debug(msg):
    print(f"[DEBUG] {msg}")
    sys.stdout.flush()  # Ensure output is flushed immediately
```

### Exception Handling

```python
try:
    risky_operation()
except Exception as e:
    print("Error:", e)
    import sys
    sys.print_exception(e)  # Prints full traceback
```

## Recovering from a Bad main.py

If `main.py` crashes on boot or has an infinite loop that prevents REPL access:

### Method 1: Interrupt boot

1. Open serial connection (Thonny or mpremote).
2. Press RESET on the board.
3. Immediately press `Ctrl+C` repeatedly (or hold it) until you see the `>>>` prompt.
4. Once at REPL:
   ```python
   import uos
   uos.remove('main.py')   # Delete the bad file
   # Or rename it:
   # uos.rename('main.py', 'main_bad.py')
   ```
5. Press `Ctrl+D` to reset. The board will boot to REPL with no main.py.

### Method 2: Safe boot (if available)

Some MicroPython builds support safe boot by holding GPIO0 (BOOT button) during reset. This skips main.py. Check your firmware documentation.

### Method 3: Re-flash firmware

If all else fails:
```powershell
python -m esptool --port COM3 erase_flash
python -m esptool --port COM3 --baud 460800 write_flash -z 0x1000 firmware.bin
```
This erases everything, including your files. Back up first if possible.

## Common Errors

### MemoryError

MicroPython on ESP32 has limited RAM (~150 KB usable heap). Causes:
- Large strings or bytearrays
- Many imported modules
- Unclosed network connections
- Memory fragmentation

Fixes:
```python
import gc
gc.collect()  # Force garbage collection
print(gc.mem_free())  # Check free memory
```
- Use `bytearray` instead of string concatenation in loops.
- Close connections: `response.close()`, `client.disconnect()`.
- Avoid loading large files into memory; process in chunks.
- Use `sys.path` to import modules from `/lib` instead of embedding large code in main.py.

### OSError: [Errno 104] ECONNRESET

WiFi connection was reset. Causes:
- Router disconnected the client
- MQTT broker closed the connection
- WiFi signal too weak

Fixes:
- Add reconnection logic with retry and backoff.
- Check WiFi signal strength: `wlan.status('rssi')`.
- Keep MQTT `keepalive` short (30-60 seconds) and call `check_msg()` regularly.

### OSError: [Errno 113] EHOSTUNREACH / ECONNABORTED

Cannot reach the server. Causes:
- Not connected to WiFi
- Wrong IP/hostname
- DNS resolution failed

Fixes:
- Check `wlan.isconnected()` before making requests.
- Use IP address instead of hostname to rule out DNS issues.
- Verify the server is reachable from another device on the same network.

### TypeError: function takes N positional arguments but M were given

API mismatch. MicroPython APIs sometimes differ from CPython. Check:
- `machine.Pin(pin, mode, pull)` — pull is the 3rd argument, not keyword.
- `I2C(id, scl, sda, freq)` — keyword arguments work in recent versions.
- `UART(id, baudrate, tx, rx)` — some builds require positional args.

### ImportError: module not found

- The module is not in `/lib` or the root directory.
- Check `sys.path`: `import sys; print(sys.path)` — should include `['', '/lib']`.
- Upload the module: `mpremote connect COM3 fs cp module.py :lib/module.py`
- Some CPython modules don't exist in MicroPython (e.g., `requests` → use `urequests`).

### ValueError: invalid Pin

- Using a pin number that doesn't exist or is restricted.
- GPIO6-11 are not available (SPI flash).
- GPIO34-39 cannot be output.
- Check the pin list in `hardware_validation_notes.md`.

### Hard Fault / Guru Meditation

This is a low-level crash, usually caused by:
- Accessing a null pointer (C-level, rare in pure Python).
- Stack overflow in an interrupt or thread.
- Hardware issue (power, flash corruption).

Fixes:
- Reset and check `machine.reset_cause()`.
- If it happens consistently, simplify the code to find the trigger.
- Re-flash the firmware (flash may be corrupted).
- Check power supply (brownouts cause hard faults).

## Serial Monitor Tips

```powershell
# Basic monitor
python scripts/serial_monitor.py -p COM3 -b 115200

# With timestamps
python scripts/serial_monitor.py -p COM3 -b 115200 --timestamp

# Send a test string
python scripts/serial_monitor.py -p COM3 -b 115200 --send "hello" --send-line --duration 3

# Send hex bytes
python scripts/serial_monitor.py -p COM3 -b 115200 --send-hex "01 02 03"
```

### Capturing Boot Log

To see the full boot log (including any errors in boot.py/main.py):
1. Open the serial monitor.
2. Press RESET on the board.
3. Observe the output from the very beginning.

MicroPython boot output looks like:
```
ets Jun  8 2016 00:22:57
rst:0x1 (POWERON_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)
...
MicroPython v1.22.1 on 2024-01-01; ESP32 module with ESP32
Type "help()" for more information.
>>>
```

If you see a traceback after "MicroPython..." but before ">>>", it's from boot.py or main.py.

## File System Issues

### File not found after upload

- Check the remote path: `mpremote connect COM3 fs ls`
- Make sure you uploaded to the correct location (root vs /lib).
- Case sensitivity: `MyModule.py` and `mymodule.py` are different.

### Cannot delete file

- File may be in use (imported by running code).
- Reset the board first, then delete.
- Directory must be empty before `rmdir`.

### Filesystem corruption

If files disappear or become garbled:
- Flash may be worn (ESP32 flash has ~100,000 write cycles).
- Power loss during write can corrupt the filesystem.
- Fix: re-flash firmware (which reformats the filesystem). Back up files first.

## Performance Profiling

```python
import time

start = time.ticks_ms()
# ... code to profile ...
elapsed = time.ticks_diff(time.ticks_ms(), start)
print(f"Elapsed: {elapsed} ms")
```

For memory profiling:
```python
import gc
gc.collect()
before = gc.mem_free()
# ... code ...
gc.collect()
after = gc.mem_free()
print(f"Memory used: {before - after} bytes")
```

## When To Stop And Ask The User

Stop and ask before continuing if:
- The board is unresponsive after multiple recovery attempts.
- You need to erase flash (destroys all user files).
- The code controls motors, power electronics, or moving mechanisms and a reset could be dangerous.
- The WiFi/MQTT credentials are missing or incorrect.
- The pin assignment conflicts with a strapping pin or SPI flash.
- The error is a hard fault with no clear code-level cause (may be hardware).
