# ESP32 Arduino Skill — 开发环境与构建说明

本 skill 让 AI/命令行走通 ESP32 / ESP32-S3 / ESP32-C3 的 Arduino 框架
完整开发闭环：检测板子 → 检查工程 → 编译 → 串口烧录 → 串口验证。

## 1. 硬件要求

| 项目 | 说明 |
|------|------|
| 开发板 | ESP32（Xtensa 双核）/ ESP32-S3（RISC-V 双核）/ ESP32-C3（RISC-V 单核） |
| 连接 | USB 数据线（注意：很多"充电线"只有电源没有数据线） |
| 串口 | 板载 USB-Serial（CP210x/CH340）或 S3 原生 USB-Serial/JTAG |

> 端口号（COMx）因机器而异，请以 `detect_board.py` 探测结果为准。

> 不同芯片的 strapping 引脚、Flash/PSRAM 引脚、USB 引脚差异很大，
> 具体见 SKILL.md 的 "Board-Specific Pin Caution"。

## 2. 软件要求

| 工具 | 说明 |
|------|------|
| Arduino IDE 或 arduino-cli | 编译/上传工具链 |
| ESP32 Arduino core | `esp32:esp32`（通过 Board Manager 安装） |
| Python | 3.10+，需 `pyserial` |
| pyserial | `python -m pip install pyserial` |

arduino-cli 可独立安装，也可使用 Arduino IDE 自带的
`arduino-cli.exe`（在 IDE 安装目录的
`resources\app\lib\backend\resources\` 下）。

## 3. 安装与配置

### 3.1 安装 arduino-cli 和 ESP32 core

```powershell
# 如果用独立 arduino-cli，先确保它在 PATH
arduino-cli version

# 添加 ESP32 板支持 URL（首次）
arduino-cli config init
arduino-cli config add board_manager.additional_urls `
  https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json

# 安装 ESP32 core
arduino-cli core update-index
arduino-cli core install esp32:esp32
```

### 3.2 验证板子连接

```powershell
python scripts/detect_board.py
```

应列出芯片型号、COM 口、MAC、Flash/PSRAM 大小。空结果是
"inconclusive"（可能是数据线/驱动问题，不是"没接"）。

### 3.3 路径配置

两个工具都不会写死盘符，按「环境变量 → 常见安装位置 → PATH」的顺序探测。

**arduino-cli**：

1. 环境变量 `ARDUINO_CLI_PATH`（显式指定，优先级最高）
2. Arduino IDE 内置的 `arduino-cli.exe`，逐个探测以下位置：
   - `%LOCALAPPDATA%\Programs\Arduino IDE\`
   - `%PROGRAMFILES%\Arduino IDE\`、`%PROGRAMFILES(X86)%\Arduino IDE\`
   - `C:` ~ `G:` 各盘根的 `Program Files\Arduino IDE\` 与 `Arduino IDE\`
     （IDE 常被装到非系统盘，故遍历盘符而不写死）
   实际文件在 `<IDE 安装目录>\resources\app\lib\backend\resources\arduino-cli.exe`
3. PATH 中的 `arduino-cli`

**esptool**：

1. 环境变量 `ARDUINO_DIRECTORIES_DATA` 指向的数据目录
2. 系统默认数据目录（Windows：`%LOCALAPPDATA%\Arduino15`；Linux/macOS：`~/.arduino15`）
3. PATH

实际文件在 `<数据目录>\packages\esp32\tools\esptool_py\<版本>\esptool.exe`。

> **数据目录被迁移过（例如自定义到其他盘）时，务必设置 `ARDUINO_DIRECTORIES_DATA`**，
> 否则脚本只能回退到 PATH 查找，`esptool chip-id` / `flash_id` 会降级不可用。

## 4. 目录结构

```
esp32-arduino/
├─ SKILL.md                  # skill 入口（工作流/规则/引脚约束）
├─ SETUP.md                  # 本文档
├─ scripts/
│  ├─ detect_board.py        # 只读探测板子（chip/port/MAC/Flash）
│  ├─ check_arduino_project.py  # 静态检查 .ino 工程
│  ├─ arduino_build.py       # 编译（arduino-cli compile 封装）
│  ├─ arduino_upload.py      # 上传（自动重试+烧后复检）
│  ├─ serial_monitor.py      # 固定时长串口捕获
│  └─ list_examples.py       # 列出自带例程
├─ references/
│  ├─ project_workflows.md
│  ├─ arduino_esp32_api.md
│  ├─ hardware_validation_notes.md
│  ├─ debugging.md
│  └─ board_esp32s3_n16r8.md   # ESP32-S3-N16R8 板子专属信息
├─ examples/                 # 自带例程（.ino + README）
└─ assets/
```

## 5. 快速开始

```powershell
# 1. 探测板子
python scripts/detect_board.py

# 2. 检查工程
python scripts/check_arduino_project.py examples/<name>

# 3. 编译（FQBN 根据芯片选择）
python scripts/arduino_build.py examples/<name> --fqbn esp32:esp32:esp32s3

# 4. 上传（自动重试+烧后重新枚举检测）
python scripts/arduino_upload.py examples/<name> --port <PORT> --fqbn esp32:esp32:esp32s3

# 5. 串口验证
python scripts/serial_monitor.py --port <PORT> --baud 115200 --duration 6
```

### FQBN 速查

| 芯片 | FQBN |
|------|------|
| ESP32 (classic) | `esp32:esp32:esp32` |
| ESP32-S3 | `esp32:esp32:esp32s3` |
| ESP32-C3 | `esp32:esp32:esp32c3` |

S3 带 Octal PSRAM 的模块（如 N16R8）选 `ESP32S3 Dev Module` 并在
`--build-property` 中设置 PSRAM=opi。

## 6. GitHub 推送

### 推荐 .gitignore

```gitignore
# Arduino build cache
**/build/
**/*.bin
**/*.elf
**/*.hex
**/*.map
**/*.partitions.bin
**/*.bootloader.bin
AppData/.../sketches/

# Python
__pycache__/
*.pyc

# OS / editor
Thumbs.db
.DS_Store
*.swp
```

> `.ino` 源码、脚本、文档、例程纳入版本控制；编译产物和 Arduino 全局
> packages 目录忽略。

### 推送步骤

```powershell
cd <skill-root>
git init
git add .
git commit -m "esp32-arduino skill"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

## 7. 已知限制

- 交互式 GDB 调试未自动化（S3 可用 Arduino IDE 内置调试器）。
- WiFi/Bluetooth 凭据需用户提供，skill 不硬编码。
- 外部模块（传感器/显示屏）需用户提供接线和型号。
- ESP32-S3 原生 USB 上传后端口可能变化，脚本会重新枚举检测。
