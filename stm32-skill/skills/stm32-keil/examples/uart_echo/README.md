# uart_echo — USART1 echo

Echo every byte received on USART1 back to the sender.

## Pins
| Signal | Pin | Note |
|--------|-----|------|
| USART1_TX | PA9 | routed to J-Link CDC |
| USART1_RX | PA10 | routed to J-Link CDC |

Baud **115200 8N1**. On this board USART1 is the on-board J-Link CDC. The port
number is machine-specific — get it from `python scripts/detect_probe.py`
(it happened to be `COM16` on the machine where this example was written).

## What it does
1. After reset, prints a banner over USART1.
2. Waits for one byte (`HAL_UART_Receive`, blocking) and sends it straight back.
3. Repeat.

Clock: HSI 16 MHz, PLL off.

## Build
```
python scripts/keil_build.py examples/uart_echo
```

## Flash (SWD, 500 kHz — do not raise the speed)
```
python scripts/stm32_flash.py examples/uart_echo
```

## Verify
```
python scripts/serial_monitor.py --port <PORT> --baud 115200 --duration 6 --send A
```
Get `<PORT>` from `python scripts/detect_probe.py` (machine-specific — do not
copy the port from earlier examples).
Expect: banner on boot, then the bytes you send echoed back.

## Validation level
- Compile: OK (0 error, 0 warning).
- Flash / on-board: **not flashed in the skill harness** — needs a live serial session.
