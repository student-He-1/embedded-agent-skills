# uart_echo — UART Echo

Receives data on UART1 and echoes it back. Use this to verify UART communication and wiring.

## Wiring

| ESP32 Pin | USB-TTL Adapter |
|---|---|
| GPIO17 (TX) | RX |
| GPIO16 (RX) | TX |
| GND | GND |

**Important**: TX connects to RX, RX connects to TX (crossover). Do not connect TX-to-TX.

UART0 (GPIO1/GPIO3) is used for the REPL and is connected to the CP2102. This example uses UART1 to avoid conflicts.

## Files

```
uart_echo/
├── main.py
├── manifest.json
└── README.md
```

## Upload and Run

```powershell
mpremote connect COM3 fs cp main.py :main.py
mpremote connect COM3 exec "import machine; machine.soft_reset()"
```

## Test

1. Open a serial terminal to the USB-TTL adapter at 115200 baud.
2. You should see: `UART echo ready`
3. Type something — it will be echoed back.
4. The REPL (UART0) will log: `RX (N bytes): ...`

## Customize

- **Pins**: Change `TX_PIN` and `RX_PIN`. UART1 can use most GPIO pins.
- **Baud**: Change `BAUD` (common: 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600).
- **UART instance**: `UART_NUM = 2`. On the classic ESP32 the UART2 default pins are **TX=GPIO17 / RX=GPIO16**; pass `tx=`/`rx=` to remap to other pins. (Caveat: GPIO34–39 are input-only and have **no internal pull-up**, so they cannot be UART TX and make a poor RX without an external pull-up. Prefer the defaults.)

## Troubleshooting

- **No data received**: Check TX/RX crossover. MCU TX → adapter RX, MCU RX → adapter TX.
- **Garbage characters**: Baud rate mismatch. Ensure both sides use 115200 8N1.
- **No output at all**: Check power (3.3V), ground, and that the USB-TTL adapter is working.
- **REPL output mixed with UART**: This is normal — REPL is on UART0 (CP2102), UART1 is separate.
