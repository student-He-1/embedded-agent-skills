# UART Basic — MicroPython Snippet

## Use Case

Basic UART communication: initialize, send, and receive data.

## Code (UART1, not UART0/REPL)

```python
from machine import UART
import time

uart = UART(1, baudrate=115200, tx=17, rx=16)
uart.init(bits=8, parity=None, stop=1)

# Send
uart.write("Hello from ESP32\r\n")

# Non-blocking receive
while True:
    if uart.any():
        data = uart.read()
        if data:
            print("RX:", data)
            uart.write(data)  # Echo
    time.sleep_ms(10)
```

## Read line

```python
line = uart.readline()  # Reads until \n, or None if timeout
if line:
    print(line.decode().strip())
```

## Read fixed number of bytes

```python
data = uart.read(10)  # Read up to 10 bytes (may return fewer)
```

## UART Pin Assignments (ESP32 Classic)

| UART | Default TX | Default RX | Notes |
|---|---|---|---|
| UART0 | GPIO1 | GPIO3 | Connected to CP2102 (REPL). Avoid using for peripherals. |
| UART1 | GPIO10 | GPIO9 | Conflict with SPI flash on many modules. Remap to other pins. |
| UART2 | GPIO17 | GPIO16 | Free to use. |

You can remap UART1/UART2 to almost any GPIO via the `tx=` and `rx=` parameters.

## Notes

- UART0 is the REPL console. Using it for custom communication breaks `print()` and REPL access.
- Always cross TX/RX: MCU TX → peripheral RX, MCU RX → peripheral TX.
- Common baud rates: 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600.
- `uart.any()` returns the number of bytes available (non-blocking).
- `uart.read()` without argument reads all available bytes.
- Use `uart.flush()` to wait for TX to complete.
- For RS485, add a direction control pin and toggle it before/after writing.
