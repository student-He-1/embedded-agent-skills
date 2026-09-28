# uart_events — UART Event-Driven Receive with Echo

A verified ESP-IDF example that uses the UART driver's event queue for asynchronous serial reception. Received data is echoed back to the sender. Includes an LED heartbeat task and a "reset" command.

## What It Demonstrates

- `uart_driver_install()` with RX/TX ring buffers and an event queue
- A dedicated task processing `UART_DATA`, `UART_FIFO_OVF`, `UART_BUFFER_FULL` events
- Proper overflow recovery (flush + queue reset)
- Pattern detection (`\n`)
- Multi-task FreeRTOS structure (UART task + LED task)
- `uart_write_bytes()` for transmission
- Software reset via `esp_restart()`

## Files

```
uart_events/
├── CMakeLists.txt
├── sdkconfig.defaults
├── manifest.json
├── README.md
└── main/
    ├── CMakeLists.txt
    └── main.c
```

## Build and Flash

```powershell
idf.py set-target esp32s3
idf.py build
idf.py -p COM6 flash monitor
```

## Expected Output

```
I (311) uart_events: uart_events starting
I (311) uart_events: Free heap: 245000 bytes
I (315) uart_events: UART0 initialized at 115200 baud, 8N1
I (315) uart_events: Type characters to echo. Send 'reset' to restart.
I (315) uart_events: Initialization complete, tasks running
I (315) uart_events: UART event task started
```

When you type `hello` in the serial monitor:

```
I (5231) uart_events: RX (5 bytes): hello
hello
```

When you type `reset`:

```
I (8123) uart_events: RX (5 bytes): reset
reset
W (8123) uart_events: Reset command received, restarting...
I (29) boot: ESP-IDF v5.3 ...
```

## Customize

- **UART instance**: Change `UART_NUM` to `UART_NUM_1` or `UART_NUM_2`. For non-default pins, call `uart_set_pin()`.
- **Baud rate**: Change `UART_BAUD`.
- **Buffer sizes**: Adjust `UART_RX_BUF` and `UART_TX_BUF` based on expected data rates.
- **LED pin**: Change `LED_PIN` in `main.c`.
- **Add commands**: Extend the `UART_DATA` handler with more string comparisons.

## Key Design Decisions

1. **Event-driven, not polling**: The UART task blocks on `xQueueReceive()` and only wakes when data arrives. This is more efficient than polling `uart_read_bytes()` in a loop.
2. **Ring buffer in driver**: `uart_driver_install()` allocates RX/TX ring buffers. The ISR fills the RX buffer; the task reads from it. No data loss at moderate baud rates.
3. **Overflow handling**: `UART_FIFO_OVF` and `UART_BUFFER_FULL` events trigger a flush + queue reset to recover.
4. **Task separation**: UART processing and LED heartbeat are separate tasks with different priorities. The UART task (priority 10) is higher than the LED task (priority 5).

## Troubleshooting

- **No echo**: Verify you're sending data to the correct COM port. UART0 is connected to the CP2102 on most boards.
- **Garbage characters**: Baud rate mismatch. Ensure both sides use 115200 8N1.
- **Buffer full warnings**: Increase `UART_RX_BUF` or reduce data rate. The default 4096 bytes handles typical interactive use.
- **Task watchdog timeout**: The UART task blocks on `xQueueReceive()` which is fine. If you add long operations in the event handler, move them to a lower-priority task.
