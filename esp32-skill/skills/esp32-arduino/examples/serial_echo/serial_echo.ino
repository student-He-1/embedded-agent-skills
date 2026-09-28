/*
 * Serial Echo — ESP32 Arduino
 * 串口回显，验证串口通信
 * 收到什么就发回什么，同时打印接收到的字节数
 */

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("=== Serial Echo Ready ===");
  Serial.println("Type something and press Enter:");
}

void loop() {
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();

    if (input.length() > 0) {
      Serial.print("Received (");
      Serial.print(input.length());
      Serial.print(" bytes): ");
      Serial.println(input);

      // 特殊命令
      if (input == "info") {
        Serial.printf("Chip: %s\n", ESP.getChipModel());
        Serial.printf("CPU: %d MHz\n", ESP.getCpuFreqMHz());
        Serial.printf("Free heap: %d bytes\n", ESP.getFreeHeap());
        Serial.printf("Flash: %d bytes\n", ESP.getFlashChipSize());
      } else if (input == "reset") {
        Serial.println("Resetting...");
        delay(500);
        ESP.restart();
      }
    }
  }
}
