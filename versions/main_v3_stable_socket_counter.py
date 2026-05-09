# ═══════════════════════════════════════════════════════════════
# main_v3.py — Version 3: Stable socket + notification counter
# Fixed the connection crash from v2 by using smaller 256-byte
# receive buffers and adding connection timeouts. Also added
# the notification counter display on the OLED so you can see
# how many unread notifications you have per app.
# ═══════════════════════════════════════════════════════════════

import network, urequests, utime, ujson
from machine import Pin, PWM, I2C
import ssd1306
import socket

# ── Hardware setup ─────────────────────────────────────────────
led_r = PWM(Pin(13))
led_g = PWM(Pin(14))
led_b = PWM(Pin(15))
for led in [led_r, led_g, led_b]:
    led.freq(1000)

buzzer = PWM(Pin(16))
buzzer.duty_u16(0)

i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

WIFI_SSID = "UHM"
WIFI_PASS = ""

COLORS = {
    "home":       (0,   255, 0),
    "university": (128, 0,   255),
    "travel":     (0,   100, 255),
    "alert":      (255, 0,   0),
    "off":        (0,   0,   0),
}

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
        utime.sleep(3)
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
        return data.get("city",""), data.get("regionName",""), data.get("country","")
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
    "home":       ["Gmail", "Instagram", "Substack", "Discord"],
    "university": ["Gmail", "Discord"],
    "travel":     ["Gmail", "Discord"],
}

def should_notify(app_name, location_mode):
    return app_name in APP_RULES.get(location_mode, [])

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

# ── Notification counter — new in v3 ──────────────────────────
counts = {"Gmail": 0, "Substack": 0, "Discord": 0, "Instagram": 0}

def update_oled_counts():
    oled.fill(0)
    oled.text("Notifications:", 0, 0)
    y = 14
    for app, count in counts.items():
        if count > 0:
            oled.text(f"{app}: {count}", 0, y)
            y += 12
    if all(v == 0 for v in counts.values()):
        oled.text("No new alerts", 0, 24)
    oled.show()

# ── Stable HTTP server — fixed from v2 ────────────────────────
# Key fixes:
# - Reduced recv buffer from 1024 to 256 bytes
# - Added conn.settimeout(3) so reads don't hang
# - Send HTTP response BEFORE processing to avoid timeouts
# - Added s.settimeout(10) on the server socket
def start_server():
    if not connect_wifi():
        return

    global location_mode
    location_mode = "home"
    last_location_check = 0
    LOCATION_INTERVAL = 300

    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)
    s.settimeout(10)  # NEW: server timeout so loop doesn't hang

    update_oled_counts()

    while True:
        try:
            conn, addr = s.accept()
            request = b""
            conn.settimeout(3)  # NEW: connection timeout
            try:
                while True:
                    chunk = conn.recv(256)  # FIXED: 256 not 1024
                    if not chunk:
                        break
                    request += chunk
            except:
                pass
            conn.send(b"HTTP/1.1 200 OK\r\n\r\nOK")  # Respond first
            conn.close()
            if b"{" in request:
                start = request.index(b"{")
                payload = ujson.loads(request[start:])
                app = payload.get("app", "")
                msg = payload.get("message", "")
                if app in counts:
                    counts[app] += 1
                trigger(app, msg, location_mode)
                update_oled_counts()
        except OSError:
            pass

        now = utime.time()
        if now - last_location_check > LOCATION_INTERVAL:
            city, region, country = get_location()
            if city:
                location_mode = classify_location(city, region, country)
            last_location_check = now

start_server()
