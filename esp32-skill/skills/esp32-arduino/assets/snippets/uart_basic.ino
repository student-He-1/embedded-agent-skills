// UART 基础片段 — 复制到你的项目中
// ESP32 有 3 个硬件串口：Serial (UART0), Serial1 (UART1), Serial2 (UART2)
// Serial 通常用于 USB 调试，Serial1/Serial2 用于外接模块

// 初始化 Serial1，指定 RX/TX 引脚
void uart1Begin(int rxPin, int txPin, int baud = 9600) {
  Serial1.begin(baud, SERIAL_8N1, rxPin, txPin);
}

// 发送数据
void uart1Send(const char* data) {
  Serial1.print(data);
}

// 读取一行（以 \n 结尾）
String uart1ReadLine() {
  if (Serial1.available()) {
    return Serial1.readStringUntil('\n');
  }
  return "";
}

// 使用方法：
// void setup() {
//   Serial.begin(115200);
//   uart1Begin(16, 17, 9600);  // RX=GPIO16, TX=GPIO17
//   uart1Send("AT\r\n");
// }
//
// void loop() {
//   String line = uart1ReadLine();
//   if (line.length() > 0) Serial.println(line);
// }
