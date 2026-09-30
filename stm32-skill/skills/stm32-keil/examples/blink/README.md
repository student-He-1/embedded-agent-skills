# blink — on-board LED blink

Blinks the on-board user LED D2 on **PA1** (active low), ~1 s period.

## Pins
| Signal | Pin | Note |
|--------|-----|------|
| D2 user LED | PA1 | active **low** (drive low to light) |

> PA1 is also the pin the `rgy_flow` example uses for its external yellow LED,
> where it is driven **high** — so that example holds D2 *off*. If you wire
> anything else to PA1 you are sharing the pin with the on-board LED circuit.

Clock: HSI 16 MHz, PLL off.

## Build
```
python scripts/keil_build.py examples/blink
```

## Flash (SWD, 500 kHz)
```
python scripts/stm32_flash.py examples/blink
```

## Verify
D2 toggles about once per second.

## Validation level
- Compile: OK (0 error, 0 warning).
- Flash / on-board: not separately flashed (the GPIO/build/flash path is covered
  by rgy_flow, which was verified on hardware).
