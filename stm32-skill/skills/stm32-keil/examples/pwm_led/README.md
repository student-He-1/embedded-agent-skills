# pwm_led — breathing LED (TIM2_CH2 = PA1)

Hardware PWM ramps the duty cycle up and down to fade the on-board user LED.

## Pins
| Signal | Pin | Note |
|--------|-----|------|
| TIM2_CH2 | PA1 | on-board user LED D2, **active LOW** |

Because D2 is active low, higher duty = dimmer, but the ramp still gives a
smooth breathing fade.

## Timer math (HSI 16 MHz path)
- APB1 = 4 MHz, timer clock = 8 MHz (APB prescaler != 1 -> x2).
- PSC = 7  -> 1 MHz tick.
- ARR = 999 -> 1 kHz PWM.
- Duty sweeps 0..999 with `step = 8` every 5 ms, so one direction takes
  ~125 steps ≈ 0.63 s.

## Build
```
python scripts/keil_build.py examples/pwm_led
```

## Flash (SWD, 500 kHz)
```
python scripts/stm32_flash.py examples/pwm_led
```

## Verify
D2 should breathe (brighten/dim) continuously. No serial output.

## Validation level
- Compile: OK (0 error, 0 warning).
- Flash / on-board: **not flashed in the skill harness** — PWM output not observed on hardware.
