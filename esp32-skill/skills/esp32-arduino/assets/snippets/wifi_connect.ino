// WiFi 连接片段 — 复制到你的项目中
#include <WiFi.h>

bool wifiConnect(const char* ssid, const char* password, int timeoutMs = 15000) {
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < timeoutMs) {
    delay(300);
  }

  return WiFi.status() == WL_CONNECTED;
}

// 使用方法：
// if (wifiConnect("your-ssid", "your-password")) {
//   Serial.println(WiFi.localIP());
// } else {
//   Serial.println("WiFi failed");
// }
