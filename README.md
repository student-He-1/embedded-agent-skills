<div align="center">

<img src="assets/logo.svg" alt="Embedded Agent Skill" width="720">

# 嵌入式开发 Agent Skill

**让 AI Agent 真正参与嵌入式开发闭环：检测硬件 → 静态检查 → 编译 → 烧录 → 串口/实机验证。**

覆盖 STM32（Keil MDK）与 ESP32（Arduino / MicroPython）两条主线，
面向 Trae、Claude Code、Codex、Cursor、Continue、OpenCode 等 CLI / 编辑器 Agent。

</div>

---

## 演示视频

🎬 **[点击观看：嵌入式 Agent Skill 演示视频](https://pan.baidu.com/s/1yGIPYhUJqhO-DaqGTHXv7g?pwd=Q3R7)**

> 提取码 `Q3R7`（链接已内置；若页面仍提示输入提取码，请手动填写）

---

## 包含的 Skill

| 技能包 | Skill | 状态 | 适用场景 |
| --- | --- | --- | --- |
| **stm32-skill** | [`stm32-keil`](stm32-skill/skills/stm32-keil/) | ✅ 已实机验证 | STM32F407VET6（Cortex-M4F），Keil MDK-uVision / AC5，J-Link SWD |
| **esp32-skill** | [`esp32-arduino`](esp32-skill/skills/esp32-arduino/) | ✅ 主力，已实机验证 | ESP32 全系列，Arduino 框架（`.ino`），arduino-cli |
| | [`esp32-micropython`](esp32-skill/skills/esp32-micropython/) | ⚠️ 部分验证（仅 blink） | ESP32，MicroPython 固件，mpremote |
| | ~~esp32-idf~~ | ❌ 已弃用，勿用 | 原 ESP-IDF 路线，留档于 `esp32-skill/deprecated/` |

---

## 设计原则

### 1. 验证分级 —— 绝不夸大

每个 skill 都把结论拆成五级，并明确禁止跨级下结论：

```
source / static inspection  →  compile success  →  flash tool success
      →  serial output observed  →  physical board behavior observed
```

**编译通过 ≠ 能用。** 这是 agent 做硬件任务时最容易犯的错。

### 2. 只读边界明确

- 不手改编译产物（`Objects/`、`*.o`、`*.hex`、`.uvoptx` 等），一律重新编译生成
- 不手改 HAL / CMSIS / ESP-IDF 内核源码，确需改动时先说明理由并征询
- 保护 CubeMX 的 `USER CODE BEGIN/END` 区域
- 用户标记为只读的参考工程绝不写入、编译或烧录

### 3. 关键参数不猜

芯片型号、外设实例、引脚、I2C 地址、串口号、FQBN 一律从工程文件与实际探测中读取，
不靠记忆推断。信息不足时停下并给出具体建议，而不是悄悄选一个"看起来合理"的值。

### 4. 工具路径跨盘符探测

不写死盘符。查找顺序统一为：

```
命令行参数  →  环境变量  →  常见安装位置（跨盘符）  →  PATH
```

支持的环境变量：

| 变量 | 用途 |
| --- | --- |
| `UV4_PATH` | Keil `UV4.exe` 路径 |
| `ARDUINO_CLI_PATH` | arduino-cli 可执行文件路径 |
| `ARDUINO_DIRECTORIES_DATA` | Arduino 数据目录（core / esptool 所在位置）|

---

## 安装

每个 skill 都是标准的 **Agent Skill**：一个包含 `SKILL.md` 的目录
（YAML frontmatter 带 `name` + `description`），同级附带
`scripts/`、`references/`、`examples/`、`assets/`。

**安装方式统一为：把需要的 skill 目录整个复制到你所使用 Agent 的 skills 目录下。**

| Agent | 常见 skills 目录 |
| --- | --- |
| Trae | `%USERPROFILE%\.trae-cn\skills\<skill-name>\` |
| Claude Code | `~/.claude/skills/<skill-name>/` |
| Codex / 其他兼容 Agent | `~/.agents/skills/<skill-name>/` |

Windows PowerShell 示例：

```powershell
# 以 esp32-arduino 为例，目标目录按上表替换
$dest = "$env:USERPROFILE\.claude\skills\esp32-arduino"
New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
Copy-Item -Recurse -Force .\esp32-skill\skills\esp32-arduino $dest
```

**三个要点**：

1. 上表是常见位置，**请以你所用 Agent 的官方文档为准**；若该 Agent 支持项目级 skills，
   也可放进工作区的 skills 目录。
2. 复制的是 **skill 目录本身**（目录里直接就是 `SKILL.md`），不要多套一层，
   否则 Agent 扫不到 `SKILL.md`。
3. 若不确定 skills 目录在哪，也可以不做"安装"——直接把 skill 目录路径告诉 Agent，
   让它读取 `SKILL.md` 即可工作。

---

## 运行环境

各 skill 的工具链均为**外部依赖**，本仓库不自带安装：

| 用途 | 需要安装 |
| --- | --- |
| 全部 | Python 3.10+ |
| 串口工具 | `python -m pip install pyserial` |
| STM32 | Keil MDK-uVision + STM32F4xx DFP；J-Link / ST-Link / DAPLink 及其驱动 |
| ESP32 Arduino | Arduino IDE 或 `arduino-cli` + `esp32:esp32` core |
| ESP32 MicroPython | `mpremote`（或 Thonny）|

---

## 仓库结构

```
嵌入式skill/
├─ LICENSE
├─ README.md
├─ .gitignore
├─ assets/logo.svg      # README 顶部的动态 logo（纯 CSS 动画）
├─ stm32-skill/
│   ├─ 硬件信息_F407VET6开发板.md
│   └─ skills/stm32-keil/
│       ├─ SKILL.md          # Skill 入口：工作流 / 核心规则 / 引脚约束
│       ├─ SETUP.md          # 环境与构建说明
│       ├─ scripts/          # detect_probe / check_keil_project / keil_build
│       │                    #   / stm32_flash / serial_monitor / list_examples
│       ├─ references/       # 工程结构 / HAL API / 实机验证笔记 / 调试
│       ├─ examples/         # blink / rgy_flow / uart_echo / pwm_led
│       └─ assets/snippets/
└─ esp32-skill/
    ├─ README.md
    ├─ skills/
    │   ├─ esp32-arduino/    # SKILL.md + scripts + references + examples + assets
    │   └─ esp32-micropython/
    └─ deprecated/
        └─ esp32-idf/        # 已弃用，未验证成功，仅作留档
```

---

## 快速使用

在工程目录中直接告诉 Agent，例如：

```text
请使用 stm32-keil skill，读取当前 Keil 工程配置，
把用户 LED（PA1，低电平点亮）改成 1 Hz 闪烁，编译并烧录后做串口验证。
```

```text
请使用 esp32-arduino skill，探测当前连接的板子，
为 GPIO2 配置 LED 闪烁，编译烧录后做串口验证。
```

Agent 会按 `检测硬件 → 静态检查 → 编译 → 烧录 → 串口验证` 执行，
并在每一步明确报告当前处于哪一个验证级别。

---

## 硬件实测结论

| 目标 | 结论 |
| --- | --- |
| STM32F407VET6 + J-Link OB（SWD）| ✅ 烧录验证通过；**起始速率必须 500 kHz**（1000 kHz+ 报 `Verification of RAMCode failed`）。脚本默认从 500 kHz 起，失败会自动降到 200/100/50 kHz 重试 |
| STM32 `rgy_flow` 流水灯 | ✅ 实机验证（ODR `0x01→0x02→0x08` 循环）|
| STM32 `blink` / `uart_echo` / `pwm_led` | 编译通过，未单独实机烧录 |
| ESP32 经典款（CP2102）| ✅ 编译 / 烧录 / GPIO2 闪烁 / 串口 |
| ESP32-S3（WROOM-1-N16R8）| ✅ 编译 / 烧录 / 串口；板载 WS2812(GPIO48) 需禁用 PSRAM |
| ESP32-C3 | 脚本兼容，未实机验证 |
| MicroPython `blink` | ✅ 实机验证（固件 **1.11.0**）；`uart_echo` / `wifi_sta` **未实机验证**（见各自 `manifest.json`） |

> **端口号（COMx）与工具安装路径均因机器而异**，请以 `detect_probe.py` /
> `detect_board.py` 的探测结果为准；文档与示例中的端口号仅作格式示例。

---

## 许可

[MIT License](LICENSE)
