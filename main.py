#Imports and Pin Set Up
import network, urequests, utime, ujson
from machine import Pin, PWM, I2C
import ssd1306


# --- RGB LED pins (common cathode) ---
led_r = PWM(Pin(13))
led_g = PWM(Pin(14))
led_b = PWM(Pin(15))
for led in [led_r, led_g, led_b]:
    led.freq(1000)

# --- Buzzer ---
buzzer = PWM(Pin(16))
buzzer.duty_u16(0)

# --- OLED via I2C ---
i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=400000)
utime.sleep_ms(100)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# --- WiFi credentials ---
# WIFI_SSID = "lifenetwork 2.4"
# WIFI_PASS = "echanboy01$"

# Button to reset notification counts
button = Pin(12, Pin.IN, Pin.PULL_UP)


#RGB LED and Buzzer
def set_rgb(r, g, b):
    # Values 0-255, converts to 16-bit duty cycle
    led_r.duty_u16(int(r / 255 * 65535))
    led_g.duty_u16(int(g / 255 * 65535))
    led_b.duty_u16(int(b / 255 * 65535))

def led_off():
    set_rgb(0, 0, 0)

def beep(freq=1000, duration_ms=200):
    buzzer.freq(freq)
    buzzer.duty_u16(32768)   # 50% duty = loud enough
    utime.sleep_ms(duration_ms)
    buzzer.duty_u16(0)

# Predefined colors for each location mode
COLORS = {
    "home":   (0,   255, 0),    # green
    "university":   (128, 0,   255),  # purple
    "travel": (0,   100, 255),  # blue
    "alert":  (255, 0,   0),    # red
    "off":    (0,   0,   0),    # off
}



#Wifi Connection
# List of known WiFi networks
WIFI_NETWORKS = [
    ("lifenetwork 2.4", "echanboy01$"),
    ("UHM", "")
]

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    oled.fill(0)
    oled.text("Scanning WiFi...", 0, 0)
    oled.show()
    set_rgb(255, 165, 0)  # orange while connecting

    # Scan for available networks
    available = [net[0].decode() for net in wlan.scan()]
    print("Available networks:", available)

    # Try each known network that is visible
    for ssid, password in WIFI_NETWORKS:
        if ssid in available:
            oled.fill(0)
            oled.text("Trying:", 0, 0)
            oled.text(ssid[:16], 0, 16)
            oled.show()
            wlan.connect(ssid, password)
            timeout = 15
            while not wlan.isconnected() and timeout > 0:
                utime.sleep(1)
                timeout -= 1
            if wlan.isconnected():
                ip = wlan.ifconfig()[0]
                oled.fill(0)
                oled.text("WiFi OK", 0, 0)
                oled.text(ssid[:16], 0, 16)
                oled.text(ip, 0, 32)
                oled.show()
                utime.sleep(3)
                beep(1200, 100)
                return True
            else:
                wlan.disconnect()

    # No known network found
    set_rgb(255, 0, 0)
    oled.fill(0)
    oled.text("WiFi FAILED", 0, 0)
    oled.text("No known", 0, 16)
    oled.text("networks found", 0, 28)
    oled.show()
    return False


#IP Location
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
    
    # ── Get current IP address ───────────────────────────────
    wlan = network.WLAN(network.STA_IF)
    ip = wlan.ifconfig()[0]
    
    # Split IP into parts so we can check the range
    # e.g. "192.168.50.141" becomes ["192", "168", "50", "141"]
    parts = ip.split(".")
    
    # ── IP range based location detection ───────────────────
    # Edit these to match your actual IP ranges
    # To find your IP range, check what the OLED shows when
    # connected to each network — the first 2-3 numbers matter
    
    # Home WiFi — usually 192.168.x.x
    if parts[0] == "192" and parts[1] == "168" and parts[2] == "50":
        return "home"
    
    # University WiFi — UHM network
    elif parts[0] == "168" and parts[1] == "105":
        return "university"
    
    # Dorm network — edit to match your dorm IP range
    elif parts[0] == "10" and parts[1] == "0":
        return "dorm"
    
    # Work network — edit to match your work IP range
    elif parts[0] == "172" and parts[1] == "16":
        return "work"
    
    # Anywhere else in the US
    elif country == "United States":
        return "travel"
    
    
    # Outside the US
    else:
        return "travel"
    

#App Filter
# Define which apps are allowed per location mode
APP_RULES = {
    "home": [
        "Gmail", "Instagram", "Substack", "Discord"
    ],
    "university": [
        "Gmail", "Discord"
    ],
    "dorm": [
        "Gmail", "Instagram", "Substack", "Discord"
    ],
    "travel": [
        "Gmail", "Discord"
    ],
}

def should_notify(app_name, location_mode):
    allowed = APP_RULES.get(location_mode, [])
    return app_name in allowed



#Display
def show_notification(app, message, location_mode):
    r, g, b = COLORS.get(location_mode, (255, 255, 255))
    set_rgb(r, g, b)
    oled.fill(0)
    oled.text(app[:16], 0, 0)        # app name (max 16 chars)
    oled.text(message[:16], 0, 16)   # line 1
    oled.text(message[16:32], 0, 28) # line 2
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
        # Silently blocked — flash dim white briefly
        set_rgb(20, 20, 20)
        utime.sleep_ms(200)
        led_off()
        
        
        
#Main
import socket, ujson

# Notification counters
counts = {"Gmail": 0, "Substack": 0, "Discord": 0, "Instagram": 0}

def update_oled_counts():
    oled.fill(0)
    oled.text("Notifications:", 0, 0)  # Header line
    y = 14  # Starting y position for first app count

    for app, count in counts.items():
        if count > 0:
            oled.text(f"{app}: {count}", 0, y)  # Show app and count
            y += 12                               # Move down for next line

    # If no notifications yet show a placeholder message
    if all(v == 0 for v in counts.values()):
        oled.text("No new alerts", 0, 24)

    oled.show()

# ── Button to reset notification counts ───────────────────────
button = Pin(12, Pin.IN, Pin.PULL_UP)  # Reset button on GP12
      


def check_button():
    # Button is pulled up so it reads False when pressed
    if not button.value():
        counts["Gmail"] = 0
        counts["Substack"] = 0
        counts["Discord"] = 0
        counts["Instagram"] = 0
        oled.fill(0)
        oled.text("Counts cleared!", 0, 24)
        oled.show()
        beep(800, 100)
        utime.sleep_ms(500)  # debounce delay
        update_oled_counts()


def start_server():
    if not connect_wifi():
        return

    wlan = network.WLAN(network.STA_IF)
    ip = wlan.ifconfig()[0]
    oled.fill(0)
    oled.text("Pico W Ready", 0, 0)
    oled.text(ip, 0, 16)
    oled.show()
    utime.sleep(3)
    update_oled_counts()

    global location_mode
    location_mode = "home"
    LOCATION_INTERVAL = 300

    # Check location immediately on startup
    city, region, country = get_location()
    if city:
        location_mode = classify_location(city, region, country)
        oled.fill(0)
        oled.text("Location:", 0, 0)
        oled.text(location_mode, 0, 16)
        oled.show()
        r, g, b = COLORS.get(location_mode, (255, 255, 255))
        set_rgb(r, g, b)
        utime.sleep(2)
        led_off()
    last_location_check = utime.time()

    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)
    s.settimeout(10)

    update_oled_counts()

    while True:
        try:
            conn, addr = s.accept()
            request = b""
            conn.settimeout(3)
            try:
                while True:
                    chunk = conn.recv(256)
                    if not chunk:
                        break
                    request += chunk
            except:
                pass
            conn.send(b"HTTP/1.1 200 OK\r\n\r\nOK")
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
        
        check_button()
        
        now = utime.time()
        if now - last_location_check > LOCATION_INTERVAL:
            city, region, country = get_location()
            if city:
                location_mode = classify_location(city, region, country)
            last_location_check = now

start_server()

