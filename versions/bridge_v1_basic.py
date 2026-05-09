# ═══════════════════════════════════════════════════════════════
# bridge_v1.py — Version 1: First working bridge
# First attempt at the Mac-side bridge. Had several issues:
# - Used curly/smart quotes from macOS autocorrect which
#   caused SyntaxError on every run until fixed in settings
# - Instagram login failed due to 2FA — removed in later version
# - All services polled at the same fixed interval
# - No "skip existing" logic so it flooded old notifications
#   on first run
# ═══════════════════════════════════════════════════════════════

import imaplib, email, threading, time, requests, feedparser
import discord

# ── Config ─────────────────────────────────────────────────────
PICO_IP        = "168.105.119.9"   # University WiFi IP (first working test)
PICO_PORT      = 80
GMAIL_ADDRESS  = "your@gmail.com"
GMAIL_APPPASS  = "your_app_password_no_spaces"
DISCORD_TOKEN  = "your_discord_token"
SUBSTACK_FEEDS = [
    "https://plumpits.substack.com/feed",
    "https://roseistheart.substack.com/feed",
]
CHECK_INTERVAL = 60  # Single interval for all services

def notify_pico(app, message):
    try:
        requests.post(
            f"http://{PICO_IP}:{PICO_PORT}/notify",
            json={"app": app, "message": message},
            timeout=5
        )
        print(f"Sent to Pico: {app} - {message}")
    except Exception as e:
        print(f"Pico unreachable: {e}")

# ── Gmail ──────────────────────────────────────────────────────
# BUG: No initialization check — floods ALL unread emails on
# first run. Fixed in v2 with gmail_initialized flag.
seen_gmail = set()

def check_gmail():
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_ADDRESS, GMAIL_APPPASS)
        mail.select("inbox")
        _, data = mail.search(None, "UNSEEN")
        for uid in data[0].split():
            if uid in seen_gmail:
                continue
            seen_gmail.add(uid)
            _, msg_data = mail.fetch(uid, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            sender = msg["From"][:30]
            notify_pico("Gmail", f"From: {sender}")
        mail.logout()
    except Exception as e:
        print(f"Gmail error: {e}")

# ── Substack ───────────────────────────────────────────────────
# BUG: No initialization check — notifies all existing posts
# on first run. Fixed in v2 with substack_initialized flag.
seen_substack = set()

def check_substack():
    for feed_url in SUBSTACK_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:3]:
                uid = entry.get("id", entry.title)
                if uid in seen_substack:
                    continue
                seen_substack.add(uid)
                notify_pico("Substack", entry.title[:30])
        except Exception as e:
            print(f"Substack error: {e}")

# ── Discord ────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f"Discord connected as {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        preview = message.content[:30]
        notify_pico("Discord", f"{message.author.name}: {preview}")

def run_discord():
    bot.run(DISCORD_TOKEN)

# ── Polling loop — single interval for everything ─────────────
# Upgraded in v2 to use separate timers per service
def polling_loop():
    while True:
        print("Checking services...")
        check_gmail()
        check_substack()
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    print("Bridge starting...")
    threading.Thread(target=polling_loop, daemon=True).start()
    threading.Thread(target=run_discord, daemon=True).start()
    while True:
        time.sleep(60)
