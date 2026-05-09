# ═══════════════════════════════════════════════════════════════
# main_v1.py — Version 1: Basic hardware test
# The very first version. No WiFi, no location detection.
# Just tests that the RGB LED, buzzer, and OLED all work,
# and simulates notifications with hardcoded test triggers.
# ═══════════════════════════════════════════════════════════════

import network, urequests, utime, ujson
from machine import Pin, PWM, I2C
import ssd1306

# ── RGB LED pins (common cathode) ─────────────────────────────
led_r = PWM(Pin(13))
led_g = PWM(Pin(14))
led_b = PWM(Pin(15))
for led in [led_r, led_g, led_b]:
    led.freq(1000)

# ── Buzzer ─────────────────────────────────────────────────────
buzzer = PWM(Pin(16))
buzzer.duty_u16(0)

# ── OLED via I2C ───────────────────────────────────────────────
i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# ── WiFi credentials ───────────────────────────────────────────
WIFI_SSID = "YOUR_WIFI_NAME"
WIFI_PASS = "YOUR_WIFI_PASSWORD"

def set_rgb(r, g, b):
    led_r.duty_u16(int(r / 255 * 65535))
    led_g.duty_u16(int(g / 255 * 65535))
    led_b.duty_u16(int(b / 255 * 65535))

def led_off():
    set_rgb(0, 0, 0)

def beep(freq=1000, duration_ms=200):
    buzzer.freq(freq)
    buzzer.duty_u16(32768)
    utime.sleep_ms(duration_ms)
    buzzer.duty_u16(0)

# Colors for each location mode
COLORS = {
    "home":   (0,   255, 0),    # green
    "work":   (128, 0,   255),  # purple
    "travel": (0,   100, 255),  # blue
    "alert":  (255, 0,   0),    # red
    "off":    (0,   0,   0),    # off
}

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASS)
    oled.fill(0)
    oled.text("Connecting WiFi...", 0, 0)
    oled.show()
    set_rgb(255, 165, 0)
    timeout = 15
    while not wlan.isconnected() and timeout > 0:
        utime.sleep(1)
        timeout -= 1
    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        oled.fill(0)
        oled.text("WiFi OK", 0, 0)
        oled.text(ip, 0, 16)
        oled.show()
        beep(1200, 100)
        return True
    else:
        set_rgb(255, 0, 0)
        oled.fill(0)
        oled.text("WiFi FAILED", 0, 0)
        oled.show()
        return False

def get_location():
    try:
        resp = urequests.get("http://ip-api.com/json", timeout=8)
        data = resp.json()
        resp.close()
        city    = data.get("city", "")
        country = data.get("country", "")
        region  = data.get("regionName", "")
        return city, region, country
    except:
        return None, None, None

def classify_location(city, region, country):
    HOME_CITY   = "Honolulu"
    HOME_REGION = "Hawaii"
    if city == HOME_CITY and region == HOME_REGION:
        return "home"
    elif country == "United States":
        return "travel"
    else:
        return "travel"

APP_RULES = {
    "home": [
        "Messages", "Instagram", "YouTube", "Email", "News"
    ],
    "work": [
        "Email", "Slack", "Calendar", "Teams"
    ],
    "travel": [
        "Messages", "Maps", "Email", "Translate"
    ],
}

def should_notify(app_name, location_mode):
    allowed = APP_RULES.get(location_mode, [])
    return app_name in allowed

def show_notification(app, message, location_mode):
    r, g, b = COLORS.get(location_mode, (255, 255, 255))
    set_rgb(r, g, b)
    oled.fill(0)
    oled.text(app[:16], 0, 0)
    oled.text(message[:16], 0, 16)
    oled.text(message[16:32], 0, 28)
    oled.text("[" + location_mode + "]", 0, 48)
    oled.show()
    beep(1000, 150)
    utime.sleep_ms(100)
    beep(1200, 100)
    utime.sleep(5)
    led_off()
    oled.fill(0)
    oled.show()

def trigger(app, message, location_mode):
    if should_notify(app, location_mode):
        show_notification(app, message, location_mode)
    else:
        set_rgb(20, 20, 20)
        utime.sleep_ms(200)
        led_off()

# ── Main loop with SIMULATED notifications ─────────────────────
# NOTE: These are hardcoded test triggers. In later versions
# these are replaced by real notifications from bridge.py
def main():
    if not connect_wifi():
        return
    utime.sleep(2)

    location_mode = "home"
    last_location_check = 0
    LOCATION_INTERVAL = 300

    while True:
        now = utime.time()
        if now - last_location_check > LOCATION_INTERVAL:
            city, region, country = get_location()
            if city:
                location_mode = classify_location(city, region, country)
                oled.fill(0)
                oled.text("Location:", 0, 0)
                oled.text(city[:16], 0, 16)
                oled.text(location_mode, 0, 32)
                oled.show()
                r, g, b = COLORS[location_mode]
                set_rgb(r, g, b)
                utime.sleep(2)
                led_off()
            last_location_check = now

        # Simulated notifications — replaced in v3 with real bridge
        trigger("Email",     "New message",   location_mode)
        utime.sleep(10)
        trigger("Instagram", "New like",      location_mode)
        utime.sleep(10)
        trigger("Slack",     "Reply in #dev", location_mode)
        utime.sleep(30)

main()
