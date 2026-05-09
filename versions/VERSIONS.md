# Version History

This folder shows the progression of the project from first prototype to final build. Each version fixed real bugs or added new features discovered during testing.

---

## main.py versions

### v1 — Simulated notifications (`main_v1_simulated_notifications.py`)
The very first working version. Hardware was all connected and the OLED, RGB LED, and buzzer all worked. Location detection via ip-api.com was working too. But notifications were completely fake — hardcoded `trigger()` calls at the bottom of the loop that fired on a timer. No connection to any real apps yet.

**What worked:** Hardware, WiFi connection, geolocation, location-based filtering  
**What was missing:** Real notifications, HTTP server

---

### v2 — HTTP server (`main_v2_http_server.py`)
Added a real HTTP server so the Pico could receive notifications from `bridge.py` running on the Mac. This was a huge step — the two devices could now talk to each other.

**Problem discovered:** The socket was receiving data in 1024-byte chunks which caused memory crashes on the Pico. Bridge.py was sending notifications faster than the Pico could handle, causing `Connection reset by peer` errors. The OLED would show "Waiting for notifications..." and never update.

**What worked:** Basic HTTP communication  
**Bug:** Socket crash under load

---

### v3 — Stable socket + notification counter (`main_v3_stable_socket_counter.py`)
Fixed the socket crash by reducing the receive buffer to 256 bytes and adding connection timeouts. Added the notification counter display on the OLED so you can see how many unread notifications you have per app without picking up your phone.

**Fixes:** 256-byte recv buffer, `conn.settimeout(3)`, `s.settimeout(10)`, send HTTP response before processing  
**New feature:** OLED notification counter

---

### v4 — Multi-WiFi + IP-based location (`main_v4_multi_wifi_ip_location.py`)
Two big upgrades to make the device truly portable:

1. **Multi-WiFi scanning** — instead of one hardcoded network, the Pico now scans for all available networks and tries each known one in order. Add any network to `WIFI_NETWORKS` and it connects automatically.

2. **IP-based location detection** — the original version used city/country names from ip-api.com, but both home and university are in Honolulu so they looked the same. Switched to checking the local IP address range instead, which uniquely identifies each network.

Also fixed the OLED EIO error discovered during testing by adding a 100ms delay after I2C initialization.

**New features:** Multi-WiFi auto-connect, IP range location detection  
**Bug fixed:** OLED EIO startup crash

---

### Final — Full build (`../main.py`)
Added the reset button (GP12) to clear notification counts, improved the location display at startup, and cleaned up all the code with full comments. This is the version in the root of the repo.

---

## bridge.py versions

### v1 — Basic bridge (`bridge_v1_basic.py`)
First attempt at the Mac-side server. Got Gmail, Substack, and Discord all connected. Several issues:

- **Smart quotes bug** — macOS autocorrect was replacing `"` with curly `"` in nano, causing `SyntaxError: invalid character '"'` on every run. Fixed by disabling smart quotes in System Settings → Keyboard.
- **Old notification flood** — no initialization logic meant every existing unread email and Substack post fired as a notification on first run.
- **Single poll interval** — Gmail, Substack checked at same rate even though they update at very different speeds.
- **Instagram 2FA** — Instagram blocked automated login because of two-factor authentication. Removed from final build.

---

### Final — Full bridge (`../bridge.py`)
Added `gmail_initialized` and `substack_initialized` flags so existing notifications are skipped on first run. Split into separate timers for Gmail (every 15s) and Substack (every 2min). Removed Instagram. Full comments added throughout.

---

## Key lessons learned

| Problem | Root cause | Fix |
|---|---|---|
| OLED EIO crash | I2C bus not ready at startup | Added 100ms delay before init |
| Socket crash | 1024-byte recv buffer too large for Pico | Reduced to 256 bytes + timeouts |
| Smart quote SyntaxError | macOS autocorrect in nano | Disabled smart quotes in System Settings |
| Old emails flooding | No first-run initialization | Added `initialized` flags |
| Pico IP changes | DHCP assigns new IP on each connection | Display IP on OLED at startup |
| Home vs university same city | ip-api.com returns same city | Switch to local IP range detection |
| Instagram 2FA | Automated login blocked | Removed Instagram from bridge |
