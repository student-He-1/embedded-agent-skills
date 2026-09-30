# Board: ESP32-S3-WROOM-1-N16R8

ESP32-S3 开发板完整硬件信息（依据官方引脚图整理，已实机验证）。

## 核心参数

| 项目 | 参数 |
|------|------|
| 模组型号 | ESP32-S3-WROOM-1-N16R8 |
| 芯片 | ESP32-S3，QFN56，revision v0.2 |
| 内核 | 32-bit Xtensa LX7 双核 @240MHz |
| Flash | 16MB SPI Flash |
| PSRAM | 8MB **Octal PSRAM**（外接） |
| SRAM | 512KB（其中 16KB 在 RTC 域） |
| ROM | 384KB |
| WiFi | 2.4GHz IEEE 802.11 b/g/n，Station/AP/AP+Station |
| 蓝牙 | Bluetooth 5.0 (BLE) |
| GPIO | 45 个可编程 |
| 外设 | 4×SPI、3×UART、2×I2C、2×I2S、RMT、LED PWM、USB-OTG、TWAI、2×12bit ADC、14×触摸、LCD接口、DVP、ULP 超低功耗协处理器 |
| 硬件加速 | AI 指令加速（轻量语音/图像识别） |

## 板载资源

| 资源 | 引脚/说明 |
|------|-----------|
| **WS2812 RGB LED** | **GPIO48**（NEO_GRB）。注意与 OPI PSRAM 冲突，见下 |
| BOOT 按键 | GPIO0（拉低进入下载模式） |
| RST/EN 按键 | 复位 |
| USB 接口 | **双 USB-C** |
| 红色 LED | 电源指示灯（常亮，不可控） |
| 蓝色 LED | 串口 TX 指示灯（不可控） |
| LOG 标识 | GPIO46 |
| USB 串口 | 原生 USB-Serial/JTAG（无外部桥接芯片） |

## GPIO48 WS2812 vs PSRAM（已验证）

GPIO48 同时是 WS2812 数据线和 Octal PSRAM 的 **SPICLK_N**，二者不能同时使用（编译时选择）：

- **启用 OPI PSRAM**（`PSRAM=opi`，默认推荐）：8MB PSRAM 可用，**板载 WS2812 不亮**
- **禁用 PSRAM**（`PSRAM=disabled`）：可用 Adafruit_NeoPixel 驱动 WS2812（已验证红绿蓝循环），代价是失去 8MB PSRAM
- 两者都要：外接 LED 到其他可用 GPIO

## 禁用/受限引脚

| 引脚 | 限制 |
|------|------|
| **GPIO26–GPIO32** | Octal SPI Flash/PSRAM 专用（SPICS1/SPIHD/SPIWP/SPICS0/SPICLK/SPIQ/SPID），**禁止用作普通 IO** |
| **GPIO33–GPIO37** | 八线（Octal）器件时接 `SPIIO4~SPIIO7 / SPIDQS`。ESP-IDF 明确标注：内嵌 ESP32-S3R8/S3R8V 的板子**不推荐**他用。本板未实测，但请优先避开这几个脚 |
| **GPIO48** | 板载 WS2812；IO-MUX 上同时是 SPICLK_N。**实测**：启用 OPI PSRAM 时 WS2812 点不亮，禁用 PSRAM 才可用（详见上文） |
| GPIO19 / GPIO20 | 原生 USB D- / D+，使用 USB 串口时不可用作 GPIO |
| GPIO22–GPIO25 | QFN56 封装上不存在 |
| GPIO0 | BOOT 按键，Strapping，拉低=下载模式 |
| GPIO45 / GPIO46 | Strapping 引脚。GPIO46 内部为**弱下拉**：仅进入串口下载模式时须为低/悬空，**正常 SPI 启动（GPIO0 高）时被忽略** |

> 注意：本板使用 Octal SPI，**GPIO6–GPIO11 可作为普通 GPIO 使用**（Quad SPI 板才占用 6–11）。
> GPIO47 常被引用为 SPICLK_P，但本板未验证它被占用 —— 在实测之前不要把它写进"禁用引脚"。
> 注意：板子丝印会把每个引脚的**复用功能名**都印出来（例如 GPIO9 印 `FSPIHD/SUBSPIHD/TOUCH9`），
> 所以"丝印上写着 SPICLK_P/N"只说明那是它的一个复用功能，**不等于**该引脚被 PSRAM 占用。

## Strapping 引脚

- **GPIO0**：启动时低 = 下载模式；高 = SPI Flash 启动
- **GPIO45**：启动配置（VDD_SPI 电压选择）
- **GPIO46**：内部**弱下拉**。仅进入串口下载模式时须为低/悬空；**正常 SPI 启动（GPIO0 高）时被忽略**，不需要拉高

启动时这些引脚不要用外部电路强制拉到非默认电平。

## ADC / 触摸

- **ADC1**：GPIO1–GPIO10（CH0–CH9），WiFi 开启时仍可用，优先使用
- **ADC2**：GPIO11–GPIO20（CH0–CH9），通道号 = GPIO 号 − 11。**ADC2 同样被 WiFi 占用**：ESP-IDF 明确说明 `adc2_get_raw()` 在 `esp_wifi_start()` 到 `esp_wifi_stop()` 期间**可能读取失败** —— 这一点和经典 ESP32 一样，WiFi 开启时不要依赖 ADC2
- **有 ADC 的引脚**：GPIO1–GPIO20 连续排布（GPIO14/15/16 = ADC2_CH3/CH4/CH5）；**GPIO0、GPIO21 没有 ADC 功能**
- 分辨率 12bit，`analogSetPinAttenuation(pin, ADC_11db)` 为最大量程；
  注意 11 dB 档实际满量程约 **3.1V**（0–3100mV），接近 3.3V 处会饱和截断
- 触摸通道：TOUCH1–TOUCH14（GPIO1–14 中多个引脚）

## 完整引脚分配

### 左侧排针（从上到下）

| 引脚 | 主要功能 |
|------|----------|
| 3V3 | 电源（×3） |
| RST | 复位/EN |
| GPIO4 | ADC1_3 / TOUCH4 / RTC |
| GPIO5 | ADC1_4 / TOUCH5 / RTC |
| GPIO6 | ADC1_5 / TOUCH6 / RTC |
| GPIO7 | ADC1_6 / TOUCH7 / RTC |
| GPIO15 | ADC2_4 / U0RTS / RTC / XTAL_32K_P |
| GPIO16 | ADC2_5 / U0CTS / RTC / XTAL_32K_N |
| GPIO17 | ADC2_6 / U1TXD / RTC / CLK_OUT3 |
| GPIO18 | ADC2_7 / U1RXD / RTC / CLK_OUT1 |
| GPIO8 | ADC1_7 / TOUCH8 / RTC |
| GPIO46 | LOG（ROM 日志相关 strapping 引脚；正常启动时不参与启动模式判断） |
| GPIO3 | JTAG / ADC1_2 / TOUCH3 / RTC（Strapping：JTAG 信号源选择） |
| GPIO9 | ADC1_8 / TOUCH9 / FSPIHD |
| GPIO10 | ADC1_9 / TOUCH10 / FSPICS0 |
| GPIO11 | ADC2_0 / TOUCH11 / FSPIID |
| GPIO12 | ADC2_1 / TOUCH12 / FSPICLK |
| GPIO13 | ADC2_2 / TOUCH13 / FSPIQ |
| GPIO14 | ADC2_3 / TOUCH14 / FSPIWP（ADC2 通道号 = GPIO 号 − 11） |
| 5V0 | 5V 电源 |
| GND | 地 |

### 右侧排针（从上到下）

| 引脚 | 主要功能 |
|------|----------|
| GND | 地 |
| GPIO43 | U0TXD / CLK_OUT1 |
| GPIO44 | U0RXD / CLK_OUT2 |
| GPIO1 | ADC1_0 / TOUCH1 / RTC |
| GPIO2 | ADC1_1 / TOUCH2 / RTC |
| GPIO42 | MTMS |
| GPIO41 | MTDI / CLK_OUT1 |
| GPIO40 | MTDO / CLK_OUT2 |
| GPIO39 | MTCK / CLK_OUT3 / SUBSPICS1 |
| GPIO38 | FSPIWP / SUBFSPIWP |
| GPIO37 | SPIDQS / FSPIQ / SUBFSPIQ |
| GPIO36 | FSPIIO7 / FSPICLK / SUBSPICLK |
| GPIO35 | SPIIO6 / FSPID / SUBSPID |
| GPIO0 | BOOT / VSPICLK |
| GPIO45 | VSPI |
| GPIO48 | **SPICLK_N / RGB LED(WS2812)** |
| GPIO47 | SPICLK_P |
| GPIO21 | RTC |
| GPIO20 | USB_D+ / U1CTS / ADC2_9 / CLK_OUT1 |
| GPIO19 | USB_D- / U1RTS / ADC2_8 / CLK_OUT2 |
| GND | 地 |

> ⚠️ **两张引脚表列的是排针丝印上的复用功能名，不等于该脚可以随便用。**
> 例如 **GPIO35/36/37** 丝印写着 `SPIIO6 / FSPIIO7 / SPIDQS`，那正是八线 PSRAM 的
> `SPIIO4~SPIIO7 / SPIDQS` 信号，按 ESP-IDF 的说明应优先避开（见上文"禁用/受限引脚"）；
> GPIO48 的 `SPICLK_N / RGB LED` 与 OPI PSRAM 也是二选一（已实测）。

## Arduino 配置

- **Board**：`ESP32S3 Dev Module`
- **FQBN**：`esp32:esp32:esp32s3`
- **PSRAM**：`OPI PSRAM`（默认，启用 8MB）
- **USB Mode**：`Hardware CDC and JTAG`（`USBMode=hwcdc`）
- **USB CDC On Boot**：`Enabled`（`CDCOnBoot=cdc`）
- **Upload Mode**：UART0 / USB-Serial-JTAG
- 常用完整 FQBN：
  - 启用 PSRAM：`esp32:esp32:esp32s3:PSRAM=opi,USBMode=hwcdc,CDCOnBoot=cdc`
  - 禁用 PSRAM（用板载 RGB）：`esp32:esp32:esp32s3:PSRAM=disabled,USBMode=hwcdc,CDCOnBoot=cdc`

> **`CDCOnBoot=cdc` 不能省（已实测踩坑）**
>
> `USBMode=hwcdc` 只决定 USB 控制器以 USB-Serial/JTAG 方式工作，**真正决定 `Serial` 映射到哪里的是 `CDCOnBoot`**。
> 它的默认值是 `Disabled`，此时 `Serial` 仍然是 `HardwareSerial`（UART0 → GPIO43/44），
> `Serial.println()` 完全不会出现在原生 USB 串口上，表现为串口监视器一行输出都没有，
> 而且**编译期没有任何报错**，很容易误判成"程序没跑 / 板子坏了"。
> 只有加上 `CDCOnBoot=cdc`，`Serial` 才映射为 `HWCDC`，输出才会走 USB。
>
> 顺带一个相关坑：`Serial.setTxTimeoutMs(0)` 只有在 `Serial` 是 `HWCDC` 时才有这个成员；
> 若 `CDCOnBoot` 没开，`Serial` 是 `HardwareSerial`，这行会直接编译报错
> `'class HardwareSerial' has no member named 'setTxTimeoutMs'`——反过来也可以用它来判断当前映射。

## 已验证项

- 编译、烧录、Hash 校验 ✅
- 串口启动信息（115200）✅
- GPIO48 WS2812：禁用 PSRAM 后红→绿→蓝循环 ✅
- 启用 OPI PSRAM 时 WS2812 不亮（GPIO48 被占用）✅

## 供电

- WiFi 发射峰值约 500mA，普通 USB 口可提供
- 出现 brownout 复位时用有源 USB Hub 或外部 5V 供电
- 3.3V 引脚一般可提供 500mA–1A，勿从 3.3V 给 >100mA 的外设供电
