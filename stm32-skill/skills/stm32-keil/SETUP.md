# STM32 Keil Skill — 开发环境与构建说明

本 skill 让 AI/命令行走通 STM32F407VET6 的完整开发闭环：检测调试器 →
静态检查工程 → 命令行编译 → SWD 烧录 → 串口/实机验证。

## 1. 硬件要求

| 项目 | 说明 |
|------|------|
| 主控板 | STM32F407VET6（Cortex-M4F，512KB Flash，192KB SRAM，LQFP100） |
| 调试器 | J-Link OB（板载）或 J-Link / ST-Link / DAPLink（SWD 模式） |
| 串口 | J-Link CDC（物理接 USART1 PA9/PA10），端口号由 `detect_probe.py` 探测 |
| 供电 | USB Type-C（5V，板载 LDO 转 3.3V） |

> 本板关键约束：**SWD 必须 500 kHz**；JTAG 不可用（W25Qxx 占用
> PB3/PB4/PB5/PA15）；无板载 USB-TTL 桥（TypeC 直连 USB OTG FS）。

## 2. 软件要求

| 工具 | 版本 / 路径 |
|------|---------------------------|
| Keil MDK-uVision | `UV4.exe`（安装路径因机器而异，脚本跨盘符探测；可用 `UV4_PATH` 覆盖） |
| 编译器 | ARMCC V5.06 update 6（**AC5**，工程 uAC6=0） |
| DFP | Keil.STM32F4xx_DFP 3.1.1 |
| J-Link Software | `C:\Program Files (x86)\SEGGER\JLink\JLink.exe`（Commander V6.46c） |
| Python | 3.10+，需 `pyserial` |
| pyserial | `python -m pip install pyserial` |

Keil、DFP、J-Link 是外部依赖，本 skill 不自带安装。

## 3. 安装与配置

1. 安装 Keil MDK-uVision 5，安装 STM32F4xx DFP（Pack Installer）。
2. 安装 SEGGER J-Link Software and Documentation Pack。
3. 安装 Python 3.10+，执行 `python -m pip install pyserial`。
4. 用 USB 线连接开发板，确认设备管理器出现：
   - `J-Link driver`（调试器）
   - `JLink CDC UART Port (COMx)`（串口）
5. 验证：`python scripts/detect_probe.py` 应列出 J-Link 及其 CDC 串口（记录该端口号备用）。

### 路径配置

查找顺序为「环境变量 → 常见安装位置 → PATH」，不写死盘符。

**UV4**（`keil_build.py`）：

1. `--uv4 <path>` 命令行参数
2. 环境变量 `UV4_PATH`
3. 常见安装位置，逐个探测：
   - `%LOCALAPPDATA%\Keil_v5\`、`%PROGRAMFILES%\Keil_v5\`
   - `C:` ~ `G:` 各盘根的 `Keil_v5\`、`AppData\Local\Keil_v5\`、`Program Files\Keil_v5\`
   （Keil 常被装到非系统盘，也可能在用户目录下，故遍历盘符）
4. PATH 中的 `UV4.exe`

**JLink**（`stm32_flash.py`）：`%PROGRAMFILES%\SEGGER\JLink\` 等常见位置，回退 PATH。

需要自定义时，优先用环境变量 `UV4_PATH`。

## 4. 目录结构

```
stm32-keil/
├─ SKILL.md                  # skill 入口（工作流/规则/引脚约束）
├─ SETUP.md                  # 本文档
├─ scripts/
│  ├─ detect_probe.py        # 只读探测调试器/串口
│  ├─ check_keil_project.py  # 静态检查 uvprojx
│  ├─ keil_build.py          # 命令行编译（UV4 封装）
│  ├─ stm32_flash.py         # SWD 烧录（自动降速重试+读回验证）
│  ├─ serial_monitor.py      # 固定时长串口捕获
│  └─ list_examples.py       # 列出自带例程
├─ references/
│  ├─ project_workflows.md   # Keil 工程结构/命令行
│  ├─ stm32_hal_api.md       # HAL API 模式与坑
│  ├─ hardware_validation_notes.md  # 本板实测教训
│  └─ debugging.md           # 调试/自修机制
├─ examples/
│  ├─ blink/                 # 板载 LED 闪烁
│  ├─ rgy_flow/              # RGY 流水灯（已实机验证）
│  ├─ uart_echo/             # USART1 回显
│  └─ pwm_led/               # TIM2 PWM 呼吸灯
└─ assets/snippets/          # 可复用代码片段
```

## 5. 快速开始

```powershell
# 1. 探测调试器和串口
python scripts/detect_probe.py

# 2. 静态检查工程（可用自带例程或你自己的工程）
python scripts/check_keil_project.py examples/rgy_flow

# 3. 编译
python scripts/keil_build.py examples/rgy_flow

# 4. 烧录（自动 500kHz、自动降速重试、烧后读回验证）
python scripts/stm32_flash.py examples/rgy_flow

# 5. 串口验证（端口号用 detect_probe.py 探测，下同）
python scripts/serial_monitor.py --port <PORT> --baud 115200 --duration 6
```

实际开发的工程建议放在独立工作区，不要混进 skill 目录。

## 6. GitHub 推送

### 推荐 .gitignore

```gitignore
# Keil build outputs
**/Objects/
**/Listings/
**/*.o
**/*.crf
**/*.d
**/*.axf
**/*.hex
**/*.bin
**/*.map
**/*.lst
**/*_build.log
**/*.uvoptx
**/*.uvguix.*
**/DebugConfig/

# Python
__pycache__/
*.pyc

# OS / editor
Thumbs.db
.DS_Store
*.swp
```

> `.uvprojx`、源码、脚本、文档、例程框架（Core/、Drivers/、startup）
> 应纳入版本控制；编译产物和 IDE 状态文件忽略。

### 推送步骤

```powershell
cd <skill-root>
git init
git add .
git commit -m "stm32-keil skill: full build/flash/verify loop"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

## 7. 已知限制

- HSE 8MHz 起振未验证，例程统一用 HSI 16MHz。
- uart_echo / pwm_led / blink 已编译通过但未单独实机烧录验证
  （rgy_flow 已实机验证，覆盖了 GPIO/编译/烧录路径）。
- USB CDC 虚拟串口、传感器例程待后续扩展。
- 用户标记为只读的参考工程不在本仓库内，仅可在本地作为只读样本使用。
