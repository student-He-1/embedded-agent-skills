---
name: stm32-keil
description: Agent rules for STM32F407VET6 (STM32F4, Cortex-M4F) firmware development with Keil MDK-uVision and the ARMCC/ARMCLANG toolchain. Use when an agent needs to create, inspect, modify, build, flash, or debug STM32 Keil projects (.uvprojx), work with HAL/LL/source-code libraries, manage SWD probes (J-Link/ST-Link/DAPLink), configure GPIO/UART/SPI/I2C/TIM/ADC/PWM/DMA/USB, or validate hardware behavior through serial or on-board observation.
---

# STM32 Keil Agent Skill

Use this skill for STM32F407VET6 firmware projects built with Keil MDK-uVision. It is intended for CLI/editor agents that participate in the full development loop: **detect probe → inspect project → compile → flash → serial/on-board verify**. The primary chip is STM32F407VET6 (Cortex-M4F, 168 MHz, 512 KB Flash, 192 KB SRAM, LQFP100); F407VGT6 is pin-compatible (1 MB Flash only).

## Default Workflow

1. Detect the connected probe and serial ports: `python scripts/detect_probe.py`. Identify probe type (J-Link / ST-Link / DAPLink), its VCP/CDC COM port, and serial number.
2. Locate the project entrypoint `.uvprojx` (and the matching `.uvoptx`). Run `python scripts/check_keil_project.py <project-dir-or-uvprojx>` for static validation.
3. Read the device, macros, include paths, source groups, scatter/memory settings, and configured debug probe from the project. Do not assume them.
4. Modify only the requested source surface (user code). Preserve unrelated code, CubeMX `USER CODE` regions, comments, copyright headers, and project layout.
5. Compile: `python scripts/keil_build.py <project-dir-or-uvprojx>`. Report warnings separately from errors.
6. Flash: `python scripts/stm32_flash.py <project-dir>`. The script finds the built `.hex` under the project, selects the backend from the detected probe, and always uses SWD at 500 kHz. Confirm the target before flashing.
7. Verify: capture serial with `python scripts/serial_monitor.py --port <port> --baud 115200 --duration 6`, and/or observe the physical board. Distinguish "compiled/flashed" from "hardware behavior verified".

## Core Rules

- The `.uvprojx` is the project entrypoint; the scatter file (`.sct`, or the auto-generated memory layout from on-chip memories) is the link-time truth source. The `.ioc` is the CubeMX configuration source when present.
- Editable surface: user application sources (`Core/Src`, `Core/Inc`, and user-added files), including `main.c` `USER CODE` regions, `stm32f4xx_hal_msp.c`, and `MX_*_Init` definitions.
- Do not hand-edit build outputs or IDE state: `Objects/`, `Listings/`, the output target folder, `*.o`, `*.axf`, `*.hex`, `*.map`, `*.crf`, `*.lst`, `*.uvoptx`, `*.uvguix.*`. Regenerate by building.
- Do not hand-edit the HAL/LL driver sources under `Drivers/STM32F4xx_HAL_Driver/`, CMSIS device files, or installed Pack contents. If a change there seems required, explain why and ask the user.
- Do not guess the chip, peripheral instance, or pin. Read the project and the device header (`stm32f407xx.h`). Peripheral instances (`USART1`, `I2C1`, `TIM2`...) and pin mappings come from the source, not from memory.
- Detect the probe before flashing. Do not assume J-Link vs ST-Link vs DAPLink. If multiple probes are connected or detection is ambiguous, stop and ask the user.
- Treat an empty detection result as inconclusive, not as "nothing connected". Check Windows Device Manager, the USB data cable, probe drivers, and board power.
- Do not silently change the chip variant, the debug probe, the interface (SWD/JTAG), or the compiler optimization level. If a change is needed, state it and confirm.
- If hardware behavior was not observed on a connected board, say validation stopped at compile or flash level. Never claim "it works" from a successful build alone.
- Respect read-only reference projects the user marks as off-limits: read them to learn patterns, never write, build into, or flash over them.

## Board-Specific Pin Caution (STM32F407VET6 board)

Pin assignments below are confirmed from the board schematic; on-board vs external wiring is noted. Verify against the actual board silkscreen before driving a pin.

### Debug and core pins
- **SWD**: PA13 = SWDIO, PA14 = SWCLK. Never reconfigure these.
- **JTAG is unavailable on this board**: the on-board W25Qxx SPI flash uses PB3 (SPI1_SCK), PB4 (SPI1_MISO), PB5 (SPI1_MOSI), and PA15 (F_CS) — the default JTDO/JNTRST/JTDI pins. Always connect probes in **SWD mode**; JTAG mode will fail.
- HSE crystal = **8 MHz** (PH0/PH1); LSE = 32.768 kHz (PC14/PC15).
- BOOT0 has a 10K pull-down (main Flash boot) and is routed to the SWD header pin 1; BOOT1 = PB2 with a 10K pull-down.
- NRST has a reset button; VBAT feeds the RTC coin-cell (CR2032).

### On-board LED and button
- **D1 = power LED** (always on when powered, not MCU controlled).
- **D2 = user LED on PA1**: anode to 3V3 via 1K, cathode to PA1 — **active low** (drive PA1 low to turn on).
- **User button S1 on PA0 (WKUP)**: 1K external pull-up — **pressed = low**, released = high.

### USB (Type-C)
- Type-C D+/D- connect to **PA12/PA11 = USB OTG FS** (via 0R). There is **no USB-to-UART bridge** on this port. Use it for USB CDC virtual serial / USB device firmware, not for raw UART.

### Other on-board devices
- **W25Qxx SPI flash**: PB3/PB4/PB5 (SPI1 remap, AF5), CS = PA15; WP and HOLD tied high.
- **SD card (SDIO)**: PC8=D0, PC9=D1, PC10=D2, PC11=D3, PD2=CMD, PC12=CLK.
- **TFT header P2 (SPI display)**: pin3=PB15, pin4=PB13, pin5=PB12, pin6=PB14, pin7=PC5, pin8=PB1 (backlight, TIM3_CH4). Confirm CS/DC/RES mapping with the display example.
- Two 23x2 expansion headers (P3/P4) break out 3V3/5V/GND and free IOs for external modules.

### Clock note
Skill examples default to **HSI 16 MHz, PLL off** (SYSCLK/AHB 16 MHz, APB1 4 MHz, APB2 8 MHz, flash latency 0) — the verified-reliable path on this board. HSE 8 MHz + PLL → 168 MHz is possible but HSE bring-up is unverified here. Always read `SystemClock_Config()` before assuming the clock speed, as it affects baud timing and timer prescalers.

## Project Shape Checks

- Identify the firmware style: **HAL** project (CubeMX layout: `Core/`, `Drivers/STM32F4xx_HAL_Driver/`, `.ioc`), **LL**, SPL (standard peripheral library), or register-only. HAL and SPL must not be mixed blindly.
- CubeMX projects keep generated code; preserve `USER CODE BEGIN/END` markers — user edits live only inside them and regenerating overwrites everything else.
- Multi-file projects may add groups and folders (e.g. `Core/Src/lcd/`). Determine ownership before adding a peripheral; avoid duplicating an init that already exists.
- Confirm macros (`USE_HAL_DRIVER`, `STM32F407xx`), include paths, and that every source in a group exists on disk.
- Check whether the project uses MicroLIB (`useUlib`): printf retargeting differs between MicroLIB and the standard library.
- For timing code, determine whether delays use `HAL_Delay`/SysTick, polling, timer interrupts, or an RTOS before changing periods.

## Ambiguous Requests

If important hardware parameters are omitted, do not silently choose risky values.

- Low-risk defaults (user LED pin PA1 active-low, 115200 8N1) may follow this skill's examples; state the defaults applied.
- Important parameters require confirmation with a concrete recommendation: pin number, peripheral instance, UART pins/baud, SPI CS/mode, I2C address, PWM timer/channel/frequency, ADC channel, USB class, and external module wiring.

## External Modules And Hardware Debugging

When driving an external module, sensor, display, motor, or custom board:

- Ask for the datasheet, pin map, supply voltage, logic level, protocol, and key parameters when unavailable.
- Verify wiring before blaming code: power, ground, pull-ups (I2C ~4.7k), level shifting (MCU is **3.3 V only** — never feed 5 V directly to a GPIO), reset/enable, boot mode, chip select, and UART TX/RX crossover.
- If repeated attempts fail while the build and code logic look correct, explicitly consider wiring, power, module mode, a datasheet mismatch, damaged hardware, or the wrong test procedure.
- Keep "firmware looks correct" separate from "hardware proved correct".

## Serial Backends

This board has no on-board USB-to-UART bridge. Use serial in this order:

1. **J-Link CDC (current, verified)**: the J-Link OB exposes a CDC UART port (run `python scripts/detect_probe.py` to get the actual port number — it is machine-specific and not fixed). It is physically wired to USART1 (PA9 TX / PA10 RX). Use 115200 8N1. This is the primary serial channel for build/debug verification.
2. **USB CDC virtual serial**: firmware over USB OTG FS (PA11/PA12, Type-C) enumerates a new COM port with no extra adapter.
3. **USART1 + external USB-TTL (reserved extension)**: supported by the scripts/examples for when an adapter is available; do not assume one is present today.

Close any program holding the port (Keil debug session, PuTTY, another monitor) before opening it.

## Flash Backend

Before flashing, run `python scripts/detect_probe.py` and confirm the probe and target. Multiple probes or an unknown result means stop and ask.

- **J-Link (verified path)** via a CommanderScript:
  ```
  device STM32F407VE
  si SWD
  speed 500
  connect
  halt
  erase
  loadfile <ascii-copy>.hex
  r
  g
  exit
  ```
  Speed **500 kHz** is mandatory on this board — 1000 kHz+ fails with
  `Verification of RAMCode failed @ 0x20000000`. The hex is copied to an
  ASCII-only temp path first (project paths may contain non-ASCII chars).
- **ST-LINK (extension)**: `ST-LINK_CLI.exe -c SWD UR -P <firmware>.hex -Rst`.
- **DAPLink (extension)**: drag-and-drop MSD or pyOCD/OpenOCD per the installed toolchain.
- Always SWD (JTAG is unavailable). Flash algorithm for this device: `STM32F4xx_512.FLM` at 0x08000000, size 0x80000.

If flashing fails, check: SWD wiring, target power (VTref), that the port/probe is not busy, BOOT0 level, and that the firmware is built for the correct device.

## Debug Backend

- Primary runtime feedback is serial (J-Link CDC / USB CDC). Initialize the UART at 115200 and print state/errors.
- **J-Link RTT** is available over SWD with no extra wiring for fast debug prints; use it when serial is inconvenient.
- For crashes, capture the fault and analyze HardFault via stacked LR/PC and CFSR/HFSR/BFAR/MMFAR; see `references/debugging.md`.
- Common issues: program runs only under the debugger or not after reset (Option Bytes / BOOT pins), no printf output (retarget/MicroLIB/clock), clock/PLL misconfiguration, and `assert_failed` traps.
- This skill does not automate interactive GDB step debugging; use the Keil debugger for that.

## Reference Selection

Read references only when needed:

- `references/project_workflows.md`: Keil project structure, `.uvprojx`/`.uvoptx`, HAL vs SPL vs register projects, RTE/Pack management, command-line build and flash.
- `references/stm32_hal_api.md`: GPIO, UART (incl. printf retarget), TIM/PWM/input capture, ADC, I2C/SPI, clock tree, NVIC/SysTick, DMA, USB.
- `references/hardware_validation_notes.md`: verified board lessons, pins, flash/reset behavior, per-example validation level.
- `references/debugging.md`: HardFault analysis, probe connection failures, RTT, common build/runtime errors.

Use `examples/` as tested references; run `python scripts/list_examples.py` before opening individual files.

## Examples

Each example ships a minimal buildable Keil project plus a README (pins, build/flash steps, expected behavior, validation level):

```text
examples/<name>/
├─ README.md
└─ minimal Keil project / sources
```

- `blink`: user LED (PA1) periodic toggle — validates GPIO, build, flash.
- `rgy_flow`: external RGY LEDs (R=PA0, Y=PA1, G=PA3) running light — **fully verified on board** (ODR 0x01/0x02/0x08 cycle).
- `uart_echo`: USART1 serial echo with printf retarget.
- `pwm_led`: TIM2_CH2 (PA1) breathing LED — validates TIM/PWM.

When applying an example, copy only the needed pattern; preserve the user's layout and local style.

## Tools

Run bundled scripts with Python 3.10+ (pyserial required for serial tools; if missing: `python -m pip install pyserial`). Keil, the DFP, J-Link/ST-Link software, and probe drivers are external dependencies not installed by this skill.

- `python scripts/detect_probe.py [--json]`: read-only probe/serial enumeration (PnP + pyserial). Empty result is explicitly inconclusive.
- `python scripts/check_keil_project.py <project-dir-or-uvprojx> [--json]`: static checks for device, source groups/files, include paths, macros, memory/scatter settings, optimization, and configured probe.
- `python scripts/keil_build.py <project-dir-or-uvprojx>`: wraps `UV4.exe -b ... -j0 -o build.log`; separates warnings from errors and maps UV4 return codes.
- `python scripts/stm32_flash.py <project-dir> [--probe jlink|stlink|daplink] [--speed 500]`: locates the built `.hex`, flashes via the detected probe over SWD (500 kHz default), resets and runs.
- `python scripts/serial_monitor.py --port <PORT> --baud 115200 --duration 6 [--send TEXT]`: fixed-duration serial capture, optional transmit. `<PORT>` comes from `detect_probe.py` and is machine-specific.
- `python scripts/list_examples.py`: lists packaged examples from `examples/*/README.md`.

### UV4 command-line return codes
`UV4.exe -b <project>.uvprojx -j0 -o build.log`: 0 = clean, 1 = warnings, 2+ = errors, 3 = cannot write target, 11 = project file not found, 12 = device not supported, 15 = file read error, 20 = device error.

## Validation Levels

Report validation levels separately and never overstate them:

- source / static inspection
- compile success (warnings listed separately)
- flash tool success
- serial output observed (port identified)
- physical board behavior observed (LED, relay, sensor reading, display, etc.)

Hardware behavior is "verified" only when observed on connected hardware.
