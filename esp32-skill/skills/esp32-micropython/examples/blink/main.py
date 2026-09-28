# blink - LED blink example
# Compatible with MicroPython 1.x (use value() and time.sleep() for broad compatibility)
from machine import Pin
import time

LED_PIN = 2  # Onboard LED on most ESP32 DevKit / NodeMCU boards

led = Pin(LED_PIN, Pin.OUT)

while True:
    led.value(1)
    time.sleep(0.5)
    led.value(0)
    time.sleep(0.5)
