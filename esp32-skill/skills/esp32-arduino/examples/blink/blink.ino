/*
 * Blink — ESP32 Arduino
 * 闪烁 LED，验证基本 GPIO 输出
 *
 * 引脚配置：
 * - ESP32 classic (NodeMCU/DevKit): GPIO2 (板载LED)
 * - ESP32-S3: 很多核心板没有用户LED，请外接 LED 到任意 GPIO + GND（串联220Ω电阻）
 * - 修改 LED_PIN 为你的实际引脚
 */

#define LED_PIN 2  // 根据你的板子修改

void setup() {
  pinMode(LED_PIN, OUTPUT);
  Serial.begin(115200);
  delay(1000);
  Serial.printf("Blink started on GPIO%d\n", LED_PIN);
}

void loop() {
  digitalWrite(LED_PIN, HIGH);
  delay(500);
  digitalWrite(LED_PIN, LOW);
  delay(500);
}
