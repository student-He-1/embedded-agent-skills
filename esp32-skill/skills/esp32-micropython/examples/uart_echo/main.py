# uart_echo - UART echo example
# Target: ESP32 (classic), UART1 on TX=17, RX=16
# UART0 is used for REPL (connected to CP2102), so we use UART1 for this demo.
# Connect a USB-TTL adapter to GPIO17 (TX) and GPIO16 (RX), cross TX/RX.

from machine import UART
import time

# UART1 configuration
UART_NUM = 1
TX_PIN = 17
RX_PIN = 16
BAUD = 115200

uart = UART(UART_NUM, baudrate=BAUD, tx=TX_PIN, rx=RX_PIN)
uart.init(baudrate=BAUD, bits=8, parity=None, stop=1)

print(f"UART echo starting on UART{UART_NUM}: TX=GPIO{TX_PIN}, RX=GPIO{RX_PIN} @ {BAUD} baud")
print("Send data to the ESP32, it will echo it back.")

# Send a test string
uart.write("UART echo ready\r\n")

while True:
    if uart.any():
        data = uart.read()
        if data:
            try:
                text = data.decode("utf-8")
                print(f"RX ({len(data)} bytes): {text.strip()}")
            except:
                print(f"RX ({len(data)} bytes): {data}")
            # Echo back
            uart.write(data)
    time.sleep_ms(10)
