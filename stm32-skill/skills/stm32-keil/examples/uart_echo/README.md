# uart_echo — USART1 echo

Echo every byte received on USART1 back to the sender.

## Pins
| Signal | Pin | Note |
|--------|-----|------|
| USART1_TX | PA9 | routed to J-Link CDC |
| USART1_RX | PA10 | routed to J-Link CDC |

Baud **115200 8N1**. On this board USART1 is the on-board J-Link CDC = **COM16**.

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
python scripts/serial_monitor.py --port COM16 --baud 115200 --duration 6 --send A
```
Expect: banner on boot, then the bytes you send echoed back.

## Validation level
- Compile: OK (0 error, 0 warning).
- Flash / on-board: not yet flashed in the skill harness (needs a live COM16 session).
