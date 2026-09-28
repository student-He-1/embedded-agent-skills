# blink — on-board LED blink

Blinks the on-board user LED D2 on **PA1** (active low), ~1 s period.

## Pins
| Signal | Pin | Note |
|--------|-----|------|
| D2 user LED | PA1 | active **low** (drive low to light) |

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
