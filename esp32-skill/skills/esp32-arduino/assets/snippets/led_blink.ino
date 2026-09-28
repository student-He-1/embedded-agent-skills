// LED 闪烁片段 — 复制到你的项目中
// 使用前修改 LED_PIN 为你的实际引脚
#define LED_PIN 2

void ledBlinkSetup() {
  pinMode(LED_PIN, OUTPUT);
}

void ledBlinkLoop() {
  static unsigned long lastToggle = 0;
  static bool state = false;
  if (millis() - lastToggle >= 500) {
    lastToggle = millis();
    state = !state;
    digitalWrite(LED_PIN, state ? HIGH : LOW);
  }
}

// 使用方法：
// void setup() { ledBlinkSetup(); }
// void loop() { ledBlinkLoop(); }
