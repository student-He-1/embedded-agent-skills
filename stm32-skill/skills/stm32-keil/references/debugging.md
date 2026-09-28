# Debugging STM32F4 Keil Projects

## HardFault

When the chip faults, read these over SWD (halt first):

- `0xE000ED28` CFSR (configurable fault status)
- `0xE000ED2C` HFSR (hard fault status)
- Stacked PC/LR on the stack (look at the faulting instruction).

Common causes on F4: NULL pointer / bad array index, stack overflow (deep call
chain or large locals), unaligned access, calling an unimplemented weak handler
that jumps to garbage, clock misconfiguration before Flash latency is set, and
using an interrupt vector before `SCB->VTOR` points at Flash.

Symptom that is NOT a fault: program stuck in `Error_Handler`
(`while(1){}` with interrupts off). Check what called it — usually a clock
init timeout (HSE won't start) or a HAL init that returned HAL_ERROR.

## Probe connection problems (seen on this board)

| Symptom | Likely cause / fix |
|---------|--------------------|
| `Verification of RAMCode failed @ 0x20000000` | SWD too fast. Use **speed 500**. |
| `CPU seems to be kept in reset forever` / can't halt | Bad reset/SWD state. Reset-and-halt (`r`+`halt`), slow to 500, or unplug board USB for ~5 s and retry. |
| PC reads ASCII garbage (e.g. 0x412F6F72) / `CPU is not halted` | Not actually attached to the core; halt cleanly first. Read Flash (0x08000000) and SP to confirm a real connection. |
| `Could not connect to target` | Check board power (VTref ~3.3 V), SWD wires, BOOT0 level, another session holding the probe. |
| Program runs under debugger but not after reset | Option bytes / BOOT0 / clock that depends on debugger state; check `SystemClock_Config`. |

## Automatic self-healing in stm32_flash.py

The bundled flash script no longer requires manual intervention for the common
high-speed / RAMCode failures:

- **Auto slowdown retry**: on `RAMCode failed`, `kept in reset`, a connect
  failure, or a bad post-flash readback, it automatically steps down the SWD
  speed (500 → 200 → 100 → 50 kHz) and retries. Only if every speed fails
  does it report an error.
- **Post-flash vector-table readback**: after `loadfile` it reads
  `0x08000000` (initial SP) and `0x08000004` (Reset_Handler) and checks
  `SP ∈ [0x20000000, 0x2002FFFF]` and `Reset_Handler ∈ [0x08000000,
  0x0807FFFF]` with the Thumb bit set. A bad readback also triggers a slower
  retry (high-speed reads can be unreliable even when loadfile reports OK).
- `serial_monitor.py` classifies open failures as `busy` (close the program
  holding the port) or `missing` (check the port name / cable) with
  actionable advice.

Manual BOOT+RST, cable checks, or a power cycle are still needed only after
all retries are exhausted.

Verify a healthy connection by reset-and-halt and reading the vector table:

```text
r
halt
mem32 0x08000000 2     # [0]=initial SP (≈0x2000xxxx), [1]=Reset_Handler (0x0800xxxx, odd = Thumb)
```

If SP/Reset_Handler are sane, the image booted; then `g` to run.

## Build errors

- `cannot open source input file "stm32f4xx.h"` -> missing the top device
  wrapper header (see project_workflows.md).
- Undefined references to RTC/timer functions in `*_template.c` -> HAL template
  files got compiled; exclude/delete them.
- Undefined `HAL_EXTI_*` / linker errors -> a GPIO/EXTI init needs the EXTI
  driver source in the build group.
- Warnings as errors / `#5` -> include paths or defines (`USE_HAL_DRIVER`,
  `STM32F407xx`) wrong.

## No printf / serial output

- Confirm the UART instance/pins (USART1 = PA9/PA10 here) and baud 115200. The CDC port number is machine-specific; get it from `detect_probe.py`.
- Confirm `fputc` retarget matches MicroLIB vs standard library.
- Confirm the system clock — baud generation depends on it.
- The boot string may only print once after reset; press reset and wait.
- J-Link RTT is a no-extra-wiring alternative for debug prints.

## Flash does not take effect

- Ensure you flashed the right `.hex` (check OutputName).
- BOOT0 must be low (main Flash boot) to run the new firmware.
- After a failed high-speed flash, do a full `erase` then re-flash at 500 kHz
  to clear stale/half-written code.
