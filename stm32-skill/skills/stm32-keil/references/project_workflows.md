# Project Workflows (Keil MDK-uVision, AC5)

Verified toolchain: **AC5** (ARMCC V5.06 update 6), DFP `Keil.STM32F4xx_DFP 3.1.1`.
The Keil install path is machine-specific; `keil_build.py` resolves `UV4.exe`
from `--uv4`, then `UV4_PATH`, then common install locations, then `PATH`.

## Project layout (HAL / CubeMX)

```text
<project>/
├─ Core/Inc/   main.h, stm32f4xx_hal_conf.h, stm32f4xx_it.h
├─ Core/Src/   main.c, stm32f4xx_hal_msp.c, stm32f4xx_it.c, system_stm32f4xx.c
├─ Drivers/
│  ├─ CMSIS/Include/               core_cm4.h, cmsis_*.h
│  ├─ CMSIS/Device/ST/STM32F4xx/Include/  stm32f4xx.h (top wrapper!),
│  │                                            stm32f407xx.h, system_stm32f4xx.h
│  └─ STM32F4xx_HAL_Driver/Inc(+Legacy) and Src/
└─ MDK-ARM/
   ├─ <name>.uvprojx     build/link entrypoint (XML)
   ├─ <name>.uvoptx      IDE state (probe/debug; auto-generated, do not hand-edit)
   ├─ startup_stm32f407xx.s
   ├─ <name>/            build output (Objects: .o/.crf, .axf, .hex, .map)
   └─ <name>_build.log
```

Critical: the top-level device header is **`stm32f4xx.h`**; it `#include`s
`stm32f407xx.h` based on the `STM32F407xx` macro. Copying only
`stm32f407xx.h` without `stm32f4xx.h` causes ~79 errors
`cannot open source input file "stm32f4xx.h"`.

## uvprojx XML essentials

- `Targets/Target/TargetName`
- `TargetCommonOption`: `OutputDirectory`, `OutputName`, `CreateHexFile`
- `TargetArmAds/Cads`: `Optim` (AC5: 0=Default,1=-O0,2=-O1,3=-O2,4=-O3),
  `VariousControls/Define`, `VariousControls/IncludePath`
- `Groups/Group`: `<GroupName>`, `<Files>/<File>` with `FileType`
  (1=C, 2=ASM) and `FilePath` (relative to MDK-ARM)
- Memory: IROM/IROM1 at 0x08000000 size 0x80000 (512K); IRAM 0x20000000
  112K + CCM 0x2001C000 16K.
- Required defines: `USE_HAL_DRIVER,STM32F407xx`.

`.uvoptx` holds the debugger probe/DLL/SWD protocol and is auto-generated the
first time the project is opened in Keil. It is not needed for command-line
build/flash.

## Command-line build

```text
<UV4.exe> -b <abs>\<name>.uvprojx -j0 -o <abs>\build.log
```

- `-b` = build changed, `-r` = rebuild all, `-j0` = no dialogs, `-o` = log file.
- Return codes: 0 clean, 1 warnings, 2 errors, 3 cannot write target,
  11 project not found, 12 device unsupported, 15 file read error, 20 device error.
- The skill wraps this in `scripts/keil_build.py`.

## Command-line flash (J-Link, SWD)

J-Link Commander (`C:\Program Files (x86)\SEGGER\JLink\JLink.exe`) via a
temporary CommanderScript. Use an **ASCII-only copy of the hex** on
`%TEMP%` (the project path may contain non-ASCII chars).

Verified working script (speed 500 kHz on this board — see hardware notes):

```text
device STM32F407VE
si SWD
speed 500
connect
halt
erase
loadfile "<ascii path>.hex"
r
g
exit
```

- `erase` wipes the chip (also removes stale code above the image); `loadfile`
  programs + verifies. `r` resets, `g` starts.
- The skill wraps this in `scripts/stm32_flash.py <project-dir>`.

## HAL templates are not compiled

`stm32f4xx_hal_*_template.c` (msp_template, timebase_*_template) must NOT be
added to a group — they reference disabled modules and fail to compile. Either
exclude them in the build, or delete them from `Src/`.

## Build/flash loop

1. `scripts/check_keil_project.py <project-dir>`
2. `scripts/keil_build.py <project-dir>`  (add `--rebuild` after big changes)
3. `scripts/stm32_flash.py <project-dir>`
4. Verify: serial (`serial_monitor.py`) and/or on-board observation.
