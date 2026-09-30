# Hardware Validation Notes (STM32F407VET6 board — verified)

These are measured facts from this specific board + J-Link OB. Trust them over
generic STM32 advice.

## Debug / probe

- Probe: **J-Link OB**, USB VID_1366 PID_0105, board-integrated.
- **SWD only.** The on-board W25Qxx flash takes PB3/PB4/PB5 (SPI1) + PA15(CS),
  which are the default JTAG pins. JTAG cannot work; always use SWD
  (PA13 SWDIO / PA14 SWCLK).
- ⚠️ **SWD speed: 500 kHz is the verified-stable rate.** At 1000/4000 kHz the
  flash/erase step fails with `Verification of RAMCode failed @ 0x20000000` /
  `Failed to download RAMCode`. SRAM itself is fine (manual `w4` writes to
  0x20000000 / 0x20010000 / CCM 0x2001C000 read back correctly). The failure is
  high-speed SWD timing. Keep `--speed 500`.
- At high speed / bad state you may also see intermittent "CPU seems to be kept
  in reset forever", `halt` failures, and PC reading Flash ASCII bytes
  (e.g. 0x412F6F72). Recovery: slow down to 500 kHz, reset-and-halt, and if
  needed unplug the board USB for a few seconds.

## Serial

- **J-Link CDC = USART1 (PA9 TX / PA10 RX)**, 115200 8N1. Confirmed by capturing
  the graduation project's boot string. The **COM number is machine-specific**
  (`COM16` on the machine where this was measured) — always get it from
  `python scripts/detect_probe.py`, never assume it.
- The graduation project prints `LED Control Ready! Send R/G/Y` only ~1.5 s
  after reset (after a beep). If a monitor shows nothing, press RESET and wait.
- No USB-to-UART bridge on the Type-C port (D+/D- go to PA12/PA11 = USB OTG FS).

## Pins

- On-board user LED **D2 = PA1, active low**. D1 = power LED (not controllable).
- User button **S1 = PA0 (WKUP)**, external 1k pull-up, pressed = low.
- HSE = 8 MHz (PH0/PH1); **HSE bring-up was not verified** — examples use HSI.
- W25Qxx SPI flash on PB3/4/5 + PA15; SD card on SDIO (PC8-12, PD2);
  TFT header P2 on PB13/PB15/PB12/PB14/PC5, backlight PB1 (TIM3_CH4).

## Objective on-board verification without serial

When firmware has no UART output (e.g. LED examples), read GPIO ODR over SWD:

```text
mem32 0x40020014 1      # GPIOA->ODR; PA0=bit0, PA1=bit1, PA3=bit3
```

Sampling repeatedly shows which pins toggle. This proved the RGY flow
(`0x01 -> 0x02 -> 0x08` cycles) without seeing the board.

## Per-example validation level

| Example | Build | Flash | Observed on board |
|---------|-------|-------|-------------------|
| blink   | OK    | not flashed separately | none (superseded by rgy_flow) |
| rgy_flow| OK    | OK    | **verified**: ODR 0x01/0x02/0x08 cycle (R=PA0,Y=PA1,G=PA3). PA1 is driven **high** here to light the external module, which holds on-board D2 **off** — see `examples/rgy_flow/README.md` |
| uart_echo | OK  | not flashed | none (needs a live serial session on the detected port) |
| pwm_led | OK    | not flashed | none |

The user's private reference project (not in this repo) is **read-only** reference;
never build into, write, or flash over it.
