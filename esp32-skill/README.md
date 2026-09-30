<div align="center">

# ESP32 Agent Skill

**让 AI Agent 真正参与 ESP32 的工程构建、烧录与串口验证。**

面向嵌入式开发，适用于 Trae、Claude Code、Codex、Cursor、Continue、OpenCode 等
CLI / 编辑器 Agent。参考 TI MSPM0 skill 模式构建。

</div>

## 包含的 Skill

| Skill | 目录 | 状态 | 适用场景 |
| --- | --- | --- | --- |
| **esp32-arduino** | `skills/esp32-arduino/` | ✅ 主力，已实机验证 | Arduino 框架（`.ino`），arduino-cli / Arduino IDE |
| **esp32-micropython** | `skills/esp32-micropython/` | ⚠️ 部分验证（仅 blink） | MicroPython 固件，mpremote 文件管理 |
| ~~esp32-idf~~ | `deprecated/esp32-idf/` | ❌ 已弃用，勿用 | 原 ESP-IDF 路线，安装受阻、未验证成功 |

> **`deprecated/` 下的内容仅供留档，未经实机验证，请勿安装或调用。**

## 核心能力

| 能力 | 能解决什么问题 |
| --- | --- |
| **自动探测板子** | 识别芯片型号、串口、MAC、Flash/PSRAM、USB 模式（arduino-cli + esptool） |
| **工程静态检查** | 校验 `.ino` 入口、库依赖，推断目标芯片（`--chip`，默认从源码自动识别）并按芯片区分引脚规则（S3 的 GPIO6~11 不再误报）|
| **自动构建与烧录** | 固化 `arduino-cli compile` / `upload` 工作流，含烧后重新枚举检测 |
| **串口闭环验证** | 固定时长串口捕获、可选发送，用于实机确认行为 |
| **例程复用** | 自带最小例程（GPIO / 串口 / WiFi），**每个例程的验证级别在 `manifest.json` 与本表中单独标注** |
| **引脚避坑** | 各芯片 strapping、Flash/PSRAM 占用、输入专用引脚的明确约束 |

## 安装

每个 skill 都是标准的 **Agent Skill**：一个包含 `SKILL.md` 的目录
（YAML frontmatter 带 `name` + `description`），同级附带
`scripts/`、`references/`、`examples/`、`assets/`。

**安装方式：把需要的 skill 目录整个复制到你所使用 Agent 的 skills 目录下。**

| Agent | 常见 skills 目录 |
| --- | --- |
| Trae | `%USERPROFILE%\.trae-cn\skills\<skill-name>\` |
| Claude Code | `~/.claude/skills/<skill-name>/` |
| Codex / 其他兼容 Agent | `~/.agents/skills/<skill-name>/` |

Windows PowerShell 示例：

```powershell
# 目标目录按上表替换
$dest = "$env:USERPROFILE\.claude\skills\esp32-arduino"
New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
Copy-Item -Recurse -Force .\skills\esp32-arduino $dest
```

**三个要点**：

1. 上表是常见位置，**请以你所用 Agent 的官方文档为准**；若该 Agent 支持项目级 skills，
   也可放进工作区的 skills 目录。
2. 复制的是 **skill 目录本身**（目录里直接就是 `SKILL.md`），不要多套一层，
   否则 Agent 扫不到 `SKILL.md`。
3. 若不确定 skills 目录在哪，也可以不做"安装"——直接把 skill 目录路径告诉 Agent，
   让它读取 `SKILL.md` 即可工作。

### 运行环境

- Python 3.10 或更高版本
- 串口工具需要 `pyserial`：`python -m pip install pyserial`
- 需要 Arduino IDE 或独立 `arduino-cli`，以及 `esp32:esp32` core
- ESP32 core 与库需用户自行安装，本 skill 不自带

## 快速使用

在 ESP32 工程目录中直接告诉 Agent：

```text
请使用 esp32-arduino skill，探测当前连接的板子，
为 GPIO2 配置 LED 闪烁，编译并烧录后做串口验证。
```

也可以针对现有工程继续开发：

```text
请使用 esp32-arduino skill，保留现有工程结构，
检查库依赖并编译，然后告诉我烧录命令。
```

Agent 会按 `检测板子 → 静态检查 → 编译 → 烧录 → 串口验证` 的顺序执行，
并明确区分「编译通过」「烧录成功」「实机行为已验证」三个层级。

## 目录结构

```
skills/esp32-arduino/
├─ SKILL.md                       # Skill 入口：工作流 / 核心规则 / 引脚约束
├─ SETUP.md                       # 开发环境与构建说明
├─ scripts/
│  ├─ detect_board.py             # 只读探测板子（chip/port/MAC/Flash/PSRAM）
│  ├─ check_arduino_project.py    # 静态检查 .ino 工程
│  ├─ arduino_build.py            # 编译（arduino-cli compile 封装）
│  ├─ arduino_upload.py           # 上传（自动重试 + 烧后复检）
│  ├─ serial_monitor.py           # 固定时长串口捕获
│  └─ list_examples.py            # 列出自带例程
├─ references/
│  ├─ project_workflows.md        # arduino-cli 工作流、FQBN、库管理
│  ├─ arduino_esp32_api.md        # GPIO/PWM/WiFi/I2C/SPI/UART/ADC
│  ├─ board_esp32s3_n16r8.md      # ESP32-S3-WROOM-1-N16R8 完整硬件参考
│  ├─ hardware_validation_notes.md# 板级验证经验
│  └─ debugging.md                # 串口监控、崩溃解码
├─ examples/                      # 自带例程（.ino + README）
│  ├─ blink/                      # LED 闪烁
│  ├─ serial_echo/                # 串口回显
│  └─ wifi_sta/                   # WiFi 连接
└─ assets/snippets/               # 可复用代码片段
```

## 内置例程

| 例程 | 内容 | 验证级别 |
| --- | --- | --- |
| `blink` | LED 周期闪烁，验证 GPIO / 编译 / 烧录 / 串口 | 编译 ✅、烧录 ✅、**实机 LED 闪烁 ✅**（经典 ESP32 GPIO2；S3 需外接 LED） |
| `serial_echo` | 串口回显，验证 UART 收发 | 编译 ✅、烧录 ✅、**实机串口回显 ✅**（ESP32-S3 原生 USB） |
| `wifi_sta` | STA 模式连接 WiFi | 编译 ✅；**未实机验证**（需真实 SSID/密码） |

> MicroPython 三个例程的验证级别见各自目录下的 `manifest.json`
> （仅 `blink` 已实机验证）。

## 使用前须知

- **端口号因机器而异**，烧录前先跑 `detect_board.py`，不要照抄文档中的示例端口。
- 烧录前确认串口号和芯片型号与板子一致；多板连接时必须确认目标。
- 串口测试前关闭 VOFA+、Arduino IDE 串口监视器等占用同一串口的软件。
- ESP32 GPIO 为 **3.3V 且不耐 5V**，连接 5V 模块需电平转换。
- GPIO0 / GPIO46（S3）等为启动 strapping 引脚，避免普通输出使用。
- 不确定硬件行为时应明确区分「代码/构建验证通过」与「真实板级验证通过」。

## 参考资料

- [Arduino-ESP32 文档](https://docs.espressif.com/projects/arduino-esp32/en/latest/)
- [ESP32 技术参考手册](https://www.espressif.com/en/support/documents/technical-documents)
- [arduino-cli 文档](https://arduino.github.io/arduino-cli/)

## 开源协议

MIT License
