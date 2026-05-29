# PicoAlert — Location-Aware Notification Circuit

A portable notification device built with the Raspberry Pi Pico W that filters Gmail, Discord, and Substack alerts based on your real time location. Instead of checking your phone every few minutes, PicoAlert lights up, beeps, and shows you what's worth your attention — depending on where you are.

---

## What it does

- Detects your location automatically using your WiFi network's IP address range
- Filters notifications by location — only work apps at university, everything at home
- Shows notifications on a 128x64 OLED display with app name and message preview
- Lights an RGB LED in a different color for each location
- Plays a two-tone buzzer alert for allowed notifications
- Displays a running count of unread notifications per app
- Resets counts with a physical button press
- Connects automatically to multiple known WiFi networks

---

## Hardware

All components from the SunFounder Kepler Kit for Raspberry Pi Pico W:

| Component | Pin |
|---|---|
| RGB LED — Red | GP13 (330Ω resistor) |
| RGB LED — Green | GP14 (330Ω resistor) |
| RGB LED — Blue | GP15 (330Ω resistor) |
| Passive Buzzer | GP16 |
| OLED SDA | GP0 |
| OLED SCL | GP1 |
| Reset Button | GP12 |
| Power | USB power bank or 3×AA batteries → VSYS (pin 39) |

---

## System Architecture

```
┌─────────────────────────────────┐
│         bridge.py (Mac)         │
│                                 │
│  Gmail ──┐                      │
│  Discord ─┼──► filters ──► HTTP POST ──► Pico W
│  Substack ┘   by location       │
└─────────────────────────────────┘
                                   │
                         ┌─────────▼──────────┐
                         │   main.py (Pico W) │
                         │                    │
                         │  OLED + LED + Buzzer│
                         └────────────────────┘
```

The bridge server runs on your Mac and handles all API authentication. It sends lightweight HTTP POST requests to the Pico W over your local WiFi. The Pico W runs a simple HTTP server, checks the notification against location rules, and triggers the hardware outputs.

---

## Location modes

| Location | LED color | Allowed apps |
|---|---|---|
| Home | Green | Gmail, Substack, Discord |
| University | Purple | Gmail, Discord |
| Travel | Teal | Gmail, Substack, Discord |

Location is detected by matching the Pico W's local IP address against known network ranges. Edit `classify_location()` in `main.py` to match your networks.

---

## Files

| File | Runs on | Purpose |
|---|---|---|
| `main.py` | Pico W (via Thonny) | HTTP server, hardware control, location detection |
| `bridge.py` | Mac (Terminal) | Polls Gmail, Substack, Discord and sends to Pico |
| `ssd1306.py` | Pico W (via Thonny) | OLED display driver |

---

## Setup

### 1 — Pico W setup
1. Open Thonny and connect your Pico W
2. Upload `main.py` and `ssd1306.py` to the Pico W
3. Edit `WIFI_NETWORKS` in `main.py` with your WiFi name and password
4. Edit `classify_location()` with your actual IP ranges
5. Run `main.py` — the OLED will show the IP address at startup

### 2 — Mac bridge setup
```bash
# Create virtual environment
python3 -m venv ~/pico-bridge
source ~/pico-bridge/bin/activate

# Install dependencies
pip install discord.py feedparser requests

# Edit bridge.py with your credentials
nano ~/bridge.py

# Run the bridge
python3 ~/bridge.py
```

### 3 — Gmail App Password
1. Go to myaccount.google.com
2. Security → 2-Step Verification → App Passwords
3. Create one named "Pico" and copy the 16-character code
4. Paste it into `GMAIL_APPPASS` in `bridge.py` (no spaces)

### 4 — Discord bot
1. Go to discord.com/developers/applications
2. Create a new application → Add a Bot
3. Enable "Message Content Intent" under Privileged Gateway Intents
4. Copy the bot token into `DISCORD_TOKEN` in `bridge.py`
5. Use OAuth2 URL Generator to invite the bot to your server

### 5 — Update Pico IP
Every time the Pico connects to a new WiFi network it gets a new IP. The IP is shown on the OLED at startup — update `PICO_IP` in `bridge.py` to match.

---

## Running

Keep two things running at the same time:

**Terminal (Mac):**
```bash
source ~/pico-bridge/bin/activate
python3 ~/bridge.py
```

**Thonny (Pico W):**
- Run `main.py`

---

## Wiring diagram

```
Pico W          Component
──────────────────────────
GP0  ──────────  OLED SDA
GP1  ──────────  OLED SCL
3.3V ──────────  OLED VCC
GND  ──────────  OLED GND

GP13 ─── 330Ω ─  RGB LED Red
GP14 ─── 330Ω ─  RGB LED Green
GP15 ─── 330Ω ─  RGB LED Blue
GND  ──────────  RGB LED GND (common cathode)

GP16 ──────────  Buzzer +
GND  ──────────  Buzzer -

GP12 ──────────  Button (other leg to GND)

VSYS (pin 39) ── Power bank / 3×AA positive
GND  (pin 38) ── Power bank / 3×AA negative
```

---

## Challenges

- **OLED I2C timing error** — The SSD1306 would fail on startup with an EIO error. Fixed by adding a 100ms delay after I2C initialization before calling the display constructor.
- **macOS smart quotes** — Editing in nano caused macOS to auto-replace `"` with curly quotes `"` which broke Python. Fixed by disabling smart quotes in System Settings → Keyboard.
- **Pico IP changes** — The Pico gets a new IP every time it connects to WiFi. Solved by displaying the IP on the OLED at startup.
- **Instagram 2FA** — Instagram's two-factor authentication blocked automated login. Instagram notifications were removed from the final build.

---

## Skills used

MicroPython · Raspberry Pi Pico W · I2C communication · PWM hardware control · HTTP client-server networking · IP geolocation · IMAP email · RSS feed parsing · Discord bot API · Python · SSD1306 OLED display · RGB LED control · Passive buzzer · Embedded systems debugging · Multi-WiFi auto-connection · GitHub

---

## Built with

SunFounder Kepler Kit for Raspberry Pi Pico W · Python 3.9 · MicroPython · Claude (AI assistant for debugging and architecture)
