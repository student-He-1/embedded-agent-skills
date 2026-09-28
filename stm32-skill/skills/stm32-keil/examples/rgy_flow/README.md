# rgy_flow — RGY Running Light (流水灯)

Three-color running light on the STM32F407VET6 board. The lit color moves
**Red → Yellow → Green** in a loop, one color on at a time.

## Hardware wiring

| Color  | STM32 pin | Notes                                    |
|--------|-----------|------------------------------------------|
| Red    | PA0       | active **high** (common-cathode module)  |
| Yellow | PA1       | active high (also on-board LED D2 net)   |
| Green  | PA3       | active high (graduation board: buzzer)   |

Default polarity is active **high**, matching the graduation-project RGB
module. For a common-anode (active-low) module, edit in `Core/Src/main.c`:

```c
#define LED_LEVEL_ON   GPIO_PIN_RESET
#define LED_LEVEL_OFF  GPIO_PIN_SET
```

## Clock

HSI 16 MHz, PLL off (the same reliable clock path as the graduation project):
SYSCLK/AHB = 16 MHz, APB1 = 4 MHz, APB2 = 8 MHz, Flash latency 0. The flow
timing is clock-independent, so HSI is sufficient and avoids the unverified
HSE.

## Build

```text
python scripts/keil_build.py examples/rgy_flow
```

Add `--rebuild` for a clean rebuild. Expected: 0 errors, 0 warnings; the HEX is
`examples/rgy_flow/MDK-ARM/rgy_flow/rgy_flow.hex`.

## Flash

```text
python scripts/stm32_flash.py examples/rgy_flow
```

The script uses J-Link over SWD. The verified-stable SWD rate on this board is
**500 kHz** (the default); at 1000 kHz+ the J-Link RAMCode verify can fail.
Flashing replaces the firmware on the chip; on-disk projects are untouched.

## Verify

- Visually: Red → Yellow → Green repeats (~300 ms each).
- Objective: with the program running, read `GPIOA->ODR` (0x40020014) over SWD;
  the low bits cycle through `0x01` (R), `0x02` (Y), `0x08` (G).

## Customization

- Speed: change `LED_STEP_MS` in `main.c`.
- Pin order / pins: edit the `LEDS[]` table.
- Cumulative "water" effect (R → R+Y → R+Y+G → off): replace the main loop so
  each step turns on the next LED without clearing the previous ones, then clear
  all after the last.
