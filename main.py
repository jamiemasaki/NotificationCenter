# ═══════════════════════════════════════════════════════════════
# main.py — Runs on the Raspberry Pi Pico W
# Connects to WiFi, detects location by IP address range,
# listens for notifications from bridge.py over HTTP,
# and displays them on the OLED, RGB LED, and buzzer.
# ═══════════════════════════════════════════════════════════════

# ── Imports ────────────────────────────────────────────────────
import network    # For WiFi connection
import urequests  # For making HTTP requests (IP geolocation)
import utime      # For sleep/timing functions
import ujson      # For parsing JSON from bridge.py
import socket     # For running the HTTP server
from machine import Pin, PWM, I2C  # For controlling hardware pins
import ssd1306    # For the OLED display

# ═══════════════════════════════════════════════════════════════
# HARDWARE SETUP
# ═══════════════════════════════════════════════════════════════

# ── RGB LED (common cathode, one pin per color) ────────────────
led_r = PWM(Pin(13))   # Red channel on GPIO 13
led_g = PWM(Pin(14))   # Green channel on GPIO 14
led_b = PWM(Pin(15))   # Blue channel on GPIO 15

# Set PWM frequency to 1000Hz for all three LED channels
for led in [led_r, led_g, led_b]:
    led.freq(1000)

# ── Buzzer ─────────────────────────────────────────────────────
buzzer = PWM(Pin(16))  # Passive buzzer on GPIO 16
buzzer.duty_u16(0)     # Start with buzzer off

# ── OLED Display (128x64 pixels via I2C) ───────────────────────
i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=400000)  # I2C on GP0/GP1
utime.sleep_ms(100)                                  # Wait for I2C bus to stabilize
oled = ssd1306.SSD1306_I2C(128, 64, i2c)            # Create OLED object

# ═══════════════════════════════════════════════════════════════
# RGB LED AND BUZZER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def set_rgb(r, g, b):
    # Set LED color using values 0-255 for each channel
    # Converts to 16-bit duty cycle (0-65535) that PWM needs
    led_r.duty_u16(int(r / 255 * 65535))
    led_g.duty_u16(int(g / 255 * 65535))
    led_b.duty_u16(int(b / 255 * 65535))

def led_off():
    # Turn off the RGB LED completely
    set_rgb(0, 0, 0)

def beep(freq=1000, duration_ms=200):
    # Play a beep sound on the buzzer
    # freq controls the pitch, duration_ms controls how long
    buzzer.freq(freq)
    buzzer.duty_u16(32768)      # 50% duty cycle = audible volume
    utime.sleep_ms(duration_ms) # Wait for the beep to finish
    buzzer.duty_u16(0)          # Turn buzzer off

# ── Colors for each location mode ─────────────────────────────
# Each location gets a different LED color so you can tell
# at a glance which location mode is active
COLORS = {
    "home":       (0,   255, 0),   # Green
    "university": (128, 0,   255), # Purple
    "dorm":       (0,   255, 150), # Teal
    "work":       (255, 100, 0),   # Orange
    "travel":     (0,   100, 255), # Blue
    "alert":      (255, 0,   0),   # Red
    "off":        (0,   0,   0),   # Off
}

# ═══════════════════════════════════════════════════════════════
# WIFI CONNECTION
# Scans for available networks and tries each known network
# in order until one connects successfully
# ═══════════════════════════════════════════════════════════════

# List of known WiFi networks — add more as needed
# Format: ("NetworkName", "password")  use "" for no password
WIFI_NETWORKS = [
    ("lifenetwork 2.4", "echanboy01$"),  # Enter Home WiFi
    ("UHM", ""),                          # University WiFi
]

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)  # Set up as WiFi client
    wlan.active(True)                     # Turn on the WiFi radio

    # Show scanning message on OLED while searching
    oled.fill(0)
    oled.text("Scanning WiFi...", 0, 0)
    oled.show()
    set_rgb(255, 165, 0)  # Orange LED = connecting

    # Get list of all WiFi networks currently in range
    available = [net[0].decode() for net in wlan.scan()]
    print("Available networks:", available)

    # Try each known network that is currently visible
    for ssid, password in WIFI_NETWORKS:
        if ssid in available:

            # Show which network we are trying to connect to
            oled.fill(0)
            oled.text("Trying:", 0, 0)
            oled.text(ssid[:16], 0, 16)  # Truncate long names to fit OLED
            oled.show()

            # Attempt to connect to this network
            wlan.connect(ssid, password)

            # Wait up to 15 seconds for connection
            timeout = 15
            while not wlan.isconnected() and timeout > 0:
                utime.sleep(1)
                timeout -= 1

            if wlan.isconnected():
                # Connection successful — show IP address on OLED
                ip = wlan.ifconfig()[0]
                oled.fill(0)
                oled.text("WiFi OK", 0, 0)
                oled.text(ssid[:16], 0, 16)
                oled.text(ip, 0, 32)      # Show IP so you can update bridge.py
                oled.show()
                utime.sleep(3)            # Keep IP visible for 3 seconds
                beep(1200, 100)           # Short beep to confirm connection
                return True
            else:
                # This network failed, disconnect and try the next one
                wlan.disconnect()

    # No known networks were found or connected
    set_rgb(255, 0, 0)   # Red LED = failed
    oled.fill(0)
    oled.text("WiFi FAILED", 0, 0)
    oled.text("No known", 0, 16)
    oled.text("networks found", 0, 28)
    oled.show()
    return False

# ═══════════════════════════════════════════════════════════════
# IP GEOLOCATION
# Calls ip-api.com to find out what city/country the Pico is in
# based on the public IP address of the WiFi network
# ═══════════════════════════════════════════════════════════════

def get_location():
    try:
        # Make a request to the free IP geolocation API
        resp = urequests.get("http://ip-api.com/json", timeout=8)
        data = resp.json()   # Parse the JSON response
        resp.close()         # Close connection to free memory

        # Extract the location fields we need
        city    = data.get("city", "")
        country = data.get("country", "")
        region  = data.get("regionName", "")
        return city, region, country
    except:
        # If the request fails return empty strings
        return None, None, None

def classify_location(city, region, country):
    # Get the Pico's current local IP address
    wlan = network.WLAN(network.STA_IF)
    ip = wlan.ifconfig()[0]

    # Split IP into 4 parts for easy comparison
    # e.g. "192.168.50.141" becomes ["192", "168", "50", "141"]
    parts = ip.split(".")

    # ── Match IP range to a location ───────────────────────────
    # Different WiFi networks give different IP ranges
    # Check the OLED at startup to find your exact IP range

    if parts[0] == "192" and parts[1] == "168" and parts[2] == "50":
        return "home"         # Home WiFi IP range

    elif parts[0] == "168" and parts[1] == "105":
        return "university"   # UHM university network IP range

    elif parts[0] == "10" and parts[1] == "0":
        return "dorm"         # Dorm network IP range

    elif parts[0] == "172" and parts[1] == "16":
        return "work"         # Work network IP range

    elif country == "United States":
        return "travel"       # Unknown US network = travelling

    else:
        return "travel"       # Outside the US = travelling

# ═══════════════════════════════════════════════════════════════
# APP NOTIFICATION RULES
# Controls which apps can send notifications at each location
# Only apps in the allowed list will trigger LED/buzzer/OLED
# ═══════════════════════════════════════════════════════════════

APP_RULES = {
    "home": [
        "Gmail", "Instagram", "Substack", "Discord"
    ],
    "university": [
        "Gmail", "Discord"          # Only school apps on campus
    ],
    "dorm": [
        "Gmail", "Instagram", "Substack", "Discord"
    ],
    "work": [
        "Gmail", "Discord"
    ],
    "travel": [
        "Gmail", "Discord"          # Minimal notifications while travelling
    ],
}

def should_notify(app_name, location_mode):
    # Check if this app is allowed at the current location
    allowed = APP_RULES.get(location_mode, [])  # Get allowed list for location
    return app_name in allowed                   # Return True if app is allowed

# ═══════════════════════════════════════════════════════════════
# NOTIFICATION DISPLAY
# Shows the notification on OLED, lights the LED, and beeps
# ═══════════════════════════════════════════════════════════════

def show_notification(app, message, location_mode):
    # First flash the location color briefly so you know where you are
    r_loc, g_loc, b_loc = COLORS.get(location_mode, (255, 255, 255))
    set_rgb(r_loc, g_loc, b_loc)
    utime.sleep_ms(500)   # Show location color for half a second
    led_off()
    utime.sleep_ms(200)   # Brief pause between colors

    # Then light up white to show the notification
    set_rgb(255, 255, 255)

    # Display notification details on OLED
    oled.fill(0)
    oled.text(app[:16], 0, 0)         # App name on line 1
    oled.text(message[:16], 0, 16)    # First 16 chars of message on line 2
    oled.text(message[16:32], 0, 28)  # Next 16 chars on line 3
    oled.text("[" + location_mode + "]", 0, 48)  # Location mode on line 4
    oled.show()

    # Play a two tone beep to alert you
    beep(1000, 150)        # First beep at 1000Hz
    utime.sleep_ms(100)    # Short gap between beeps
    beep(1200, 100)        # Second beep at higher pitch

    utime.sleep(5)   # Keep notification visible for 5 seconds
    led_off()        # Turn off LED — stays off until next notification
    oled.fill(0)     # Clear the OLED
    oled.show()

def trigger(app, message, location_mode):
    if should_notify(app, location_mode):
        # App is allowed at this location — show full notification
        show_notification(app, message, location_mode)
    else:
        # App is blocked at this location — flash dim white silently
        set_rgb(20, 20, 20)    # Very dim white flash
        utime.sleep_ms(200)
        led_off()

# ═══════════════════════════════════════════════════════════════
# NOTIFICATION COUNTER DISPLAY
# Shows a running count of notifications per app on the OLED
# Updates every time a new notification arrives
# ═══════════════════════════════════════════════════════════════

# Track how many notifications received per app
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
        utime.sleep_ms(500)  # Debounce delay
        update_oled_counts()

# ═══════════════════════════════════════════════════════════════
# MAIN HTTP SERVER
# Listens for incoming notifications from bridge.py over WiFi
# Updates location every 5 minutes and shows IP on startup
# ═══════════════════════════════════════════════════════════════

def start_server():
    # Connect to WiFi first — stop if connection fails
    if not connect_wifi():
        return

    # Show IP address on OLED so you can update bridge.py
    wlan = network.WLAN(network.STA_IF)
    ip = wlan.ifconfig()[0]
    oled.fill(0)
    oled.text("Pico W Ready", 0, 0)
    oled.text(ip, 0, 16)               # Display IP address
    oled.text("Update bridge.py ^", 0, 32)
    oled.show()
    utime.sleep(3)    # Keep IP visible for 3 seconds

    # Set default location
    global location_mode
    location_mode = "home"
    LOCATION_INTERVAL = 300  # Check location every 5 minutes

    # Check location immediately on startup
    city, region, country = get_location()
    if city:
        location_mode = classify_location(city, region, country)
        oled.fill(0)
        oled.text("Location:", 0, 0)
        oled.text(location_mode, 0, 16)
        oled.show()
        r, g, b = COLORS.get(location_mode, (255, 255, 255))
        set_rgb(r, g, b)   # Flash LED in location color
        utime.sleep(2)
        led_off()
    last_location_check = utime.time()

    # ── Set up the HTTP server ──────────────────────────────────
    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow reuse of port
    s.bind(addr)      # Bind to the address
    s.listen(1)       # Listen for incoming connections
    s.settimeout(10)  # Timeout after 10 seconds if no connection

    # Show the notification counter screen
    update_oled_counts()

    # ── Main loop — keep running forever ───────────────────────
    while True:
        try:
            # Wait for an incoming connection from bridge.py
            conn, addr = s.accept()
            request = b""
            conn.settimeout(3)  # Timeout if data stops coming

            # Read all incoming data in 256 byte chunks
            try:
                while True:
                    chunk = conn.recv(256)
                    if not chunk:
                        break       # No more data
                    request += chunk
            except:
                pass  # Timeout or connection closed — that's ok

            # Send a response back to bridge.py to confirm receipt
            conn.send(b"HTTP/1.1 200 OK\r\n\r\nOK")
            conn.close()  # Close the connection

            # Parse the JSON notification data from the request body
            if b"{" in request:
                start = request.index(b"{")             # Find start of JSON
                payload = ujson.loads(request[start:])  # Parse JSON
                app = payload.get("app", "")            # Get app name
                msg = payload.get("message", "")        # Get message text

                # Increment the counter for this app
                if app in counts:
                    counts[app] += 1

                # Trigger LED/buzzer/OLED if allowed at this location
                trigger(app, msg, location_mode)

                # Update the notification counter on OLED
                update_oled_counts()

        except OSError:
            pass  # No connection received in timeout window — keep looping

        # Check if reset button was pressed
        check_button()

        # ── Location refresh ───────────────────────────────────
        # Every 5 minutes check if location has changed
        now = utime.time()
        if now - last_location_check > LOCATION_INTERVAL:
            city, region, country = get_location()
            if city:
                location_mode = classify_location(city, region, country)

                # Show the new location briefly on OLED
                oled.fill(0)
                oled.text("Location:", 0, 0)
                oled.text(location_mode, 0, 16)
                r, g, b = COLORS.get(location_mode, (255, 255, 255))
                set_rgb(r, g, b)   # Flash LED in location color
                utime.sleep(2)
                led_off()

                # Return to notification counter screen
                update_oled_counts()

            last_location_check = now  # Reset the timer

# ── Start the server ───────────────────────────────────────────
start_server()
