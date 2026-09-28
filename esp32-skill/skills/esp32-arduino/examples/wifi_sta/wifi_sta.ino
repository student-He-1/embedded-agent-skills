/*
 * WiFi STA — ESP32 Arduino
 * 连接 WiFi 路由器，获取 IP 地址
 *
 * 使用前请修改 WIFI_SSID 和 WIFI_PASSWORD
 */

#include <WiFi.h>

// ====== 配置区域 ======
const char* WIFI_SSID = "your-ssid";        // 改成你的 WiFi 名称
const char* WIFI_PASSWORD = "your-password"; // 改成你的 WiFi 密码
// ====================

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("=== WiFi STA Example ===");
  Serial.printf("Connecting to: %s\n", WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("WiFi connected!");
    Serial.printf("IP address: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("RSSI: %d dBm\n", WiFi.RSSI());
    Serial.printf("MAC: %s\n", WiFi.macAddress().c_str());
    Serial.printf("Channel: %d\n", WiFi.channel());
  } else {
    Serial.println("WiFi connection failed!");
    Serial.printf("Status: %d\n", WiFi.status());
    Serial.println("Check SSID, password, and that the network is 2.4GHz (not 5GHz).");
  }
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    static unsigned long lastCheck = 0;
    if (millis() - lastCheck > 5000) {
      lastCheck = millis();
      Serial.printf("Connected, RSSI: %d dBm, free heap: %d\n",
                    WiFi.RSSI(), ESP.getFreeHeap());
    }
  } else {
    // 尝试重连
    static unsigned long lastRetry = 0;
    if (millis() - lastRetry > 10000) {
      lastRetry = millis();
      Serial.println("Reconnecting...");
      WiFi.reconnect();
    }
  }
}
