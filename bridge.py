# ═══════════════════════════════════════════════════════════════
# bridge.py — Notification Bridge for Raspberry Pi Pico W
# Runs on your Mac. Checks Gmail, Substack, Discord and sends
# notifications to your Pico W over your home WiFi network.
#
# Run with:
#   source ~/pico-bridge/bin/activate
#   python3 ~/bridge.py
#
# Required packages:
#   pip install instagrapi discord.py feedparser requests flask
# ═══════════════════════════════════════════════════════════════

# ── Standard Python libraries ──────────────────────────────────
import imaplib        # For connecting to Gmail via IMAP protocol
import email          # For reading and parsing email content
import threading      # For running Gmail, Substack, Discord at same time
import time           # For waiting between checks

# ── Third party libraries (installed via pip) ──────────────────
import requests       # For sending HTTP requests to the Pico W
import feedparser     # For reading Substack RSS feeds
import discord        # For connecting to Discord as a bot

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION — Edit these values to match your setup
# ═══════════════════════════════════════════════════════════════

# The IP address of your Pico W — shown on OLED screen at startup
# This changes every time the Pico connects to a new WiFi network
PICO_IP   = ["..."] #enter IP
PICO_PORT = 80

# Your Gmail address and App Password (no spaces in app password)
# Get an App Password at: myaccount.google.com > Security > App Passwords
GMAIL_ADDRESS = "..." #enter SSID
GMAIL_APPPASS = "..." #enter PASS

# Your Discord bot token
# Get this from: discord.com/developers > Your App > Bot > Reset Token
DISCORD_TOKEN = "your_discord_token"
WATCHED_SERVER_IDS = [""]
WATCHED_CHANNELS = [""]
# List of Substack RSS feeds you want notifications from
# Format: https://newslettername.substack.com/feed
SUBSTACK_FEEDS = [
    "https://plumpits.substack.com/feed",
    "https://roseistheart.substack.com/feed",
    "https://celestemdavis.substack.com/feed",
    "https://theweeklyscrapbook.substack.com/feed",
    "https://designmom.substack.com/feed",
    "https://personalscriptures.substack.com/feed",
    "https://hasifff.substack.com/feed",
    "https://leftbrainmystic.substack.com/feed",
    "https://apoorvaasraghavan.substack.com/feed",
    "https://risquebyjenna.substack.com/feed"
]

# How often to check Gmail (seconds)
GMAIL_INTERVAL = 15

# How often to check Substack (seconds)
SUBSTACK_INTERVAL = 120

# ═══════════════════════════════════════════════════════════════
# SEND TO PICO W
# Sends a notification to the Pico W over HTTP
# The Pico receives this and triggers the LED, buzzer, and OLED
# ═══════════════════════════════════════════════════════════════

def notify_pico(app, message):
    try:
        requests.post(
            f"http://{PICO_IP}:{PICO_PORT}/notify",
            json={"app": app, "message": message},
            timeout=5
        )
        print(f"Sent to Pico: {app} - {message}")
    except Exception as e:
        # Pico might be temporarily unreachable — just log and continue
        print(f"Pico unreachable: {e}")

# ═══════════════════════════════════════════════════════════════
# GMAIL
# Connects to Gmail via IMAP and checks for new unread emails
# On first run it skips all existing unread emails so you only
# get notified about emails that arrive after the bridge starts
# ═══════════════════════════════════════════════════════════════

gmail_initialized = False   # Tracks if we have done the first run yet
seen_gmail = set()          # Stores email IDs we have already seen

def check_gmail():
    global gmail_initialized
    try:
        # Connect to Gmail's IMAP server with SSL encryption
        mail = imaplib.IMAP4_SSL("imap.gmail.com")

        # Log in with your Gmail address and App Password
        mail.login(GMAIL_ADDRESS, GMAIL_APPPASS)

        # Select the inbox folder to check
        mail.select("inbox")

        # Search for all unread emails
        _, data = mail.search(None, "UNSEEN")
        uids = data[0].split()

        if not gmail_initialized:
            # First run — just record all existing unread emails
            # so we don't flood you with old notifications
            for uid in uids:
                seen_gmail.add(uid)
            gmail_initialized = True
            print(f"Gmail ready — {len(uids)} existing unread emails skipped")
        else:
            # Normal run — check for emails we haven't seen before
            for uid in uids:
                if uid in seen_gmail:
                    continue   # Already seen this one, skip it
                seen_gmail.add(uid)

                # Fetch the full email content
                _, msg_data = mail.fetch(uid, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])

                # Get the sender name/address (truncated to 30 chars for OLED)
                sender = msg["From"][:30]
                notify_pico("Gmail", f"From: {sender}")

        # Always log out cleanly
        mail.logout()

    except Exception as e:
        print(f"Gmail error: {e}")

# ═══════════════════════════════════════════════════════════════
# SUBSTACK
# Reads RSS feeds from your Substack subscriptions
# On first run it skips all existing posts so you only get
# notified about new posts published after the bridge starts
# ═══════════════════════════════════════════════════════════════

substack_initialized = False   # Tracks if we have done the first run yet
seen_substack = set()          # Stores post IDs we have already seen

def check_substack():
    global substack_initialized
    for feed_url in SUBSTACK_FEEDS:
        try:
            # Fetch and parse the RSS feed for this Substack
            feed = feedparser.parse(feed_url)

            # Check the most recent 10 posts in this feed
            for entry in feed.entries[:10]:
                # Use the post ID or title as a unique identifier
                uid = entry.get("id", entry.title)

                if not substack_initialized:
                    # First run — just record all existing posts, dont notify
                    seen_substack.add(uid)
                else:
                    if uid in seen_substack:
                        continue   # Already seen this post, skip it
                    # New post found — add to seen and notify Pico
                    seen_substack.add(uid)
                    notify_pico("Substack", entry.title[:30])

        except Exception as e:
            print(f"Substack error for {feed_url}: {e}")

    if not substack_initialized:
        print(f"Substack ready — {len(seen_substack)} existing posts skipped")
        substack_initialized = True

# ═══════════════════════════════════════════════════════════════
# DISCORD
# Runs a Discord bot that watches for messages where you are
# mentioned or direct messages sent to you
# ═══════════════════════════════════════════════════════════════

# Set up the bot with permission to read message content
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    # Fires when the bot successfully connects to Discord
    print(f"Discord connected as {bot.user}")

@bot.event
async def on_message(message):
    # Fires every time a message is sent in any server the bot is in

    # Ignore messages sent by the bot itself
    if message.author == bot.user:
        return

   # Check each condition that should trigger a notification
    is_dm              = isinstance(message.channel, discord.DMChannel)
    is_mention         = bot.user.mentioned_in(message)
    is_watched_server  = (message.guild is not None and
                          message.guild.id == WATCHED_SERVER_IDS)
    is_watched_channel = message.channel.name in WATCHED_CHANNELS

    # Notify if any of the above conditions are true
    if is_dm or is_mention or (is_watched_server and is_watched_channel):
        preview = message.content[:30]  # Truncate message to fit OLED
        notify_pico("Discord", f"{message.author.name}: {preview}")

def run_discord():
    # Starts the Discord bot — this runs forever in its own thread
    bot.run(DISCORD_TOKEN)

# ═══════════════════════════════════════════════════════════════
# POLLING LOOP
# Runs in its own thread, repeatedly checks Gmail and Substack
# on separate timers so each service has its own check interval
# Discord runs separately since it is event based not polled
# ═══════════════════════════════════════════════════════════════

def polling_loop():
    gmail_timer = 0
    substack_timer = 0

    while True:
        now = time.time()

        # Check Gmail every GMAIL_INTERVAL seconds
        if now - gmail_timer > GMAIL_INTERVAL:
            check_gmail()
            gmail_timer = now

        # Check Substack every SUBSTACK_INTERVAL seconds
        if now - substack_timer > SUBSTACK_INTERVAL:
            check_substack()
            substack_timer = now

        # Sleep briefly before checking timers again
        time.sleep(5)

# ═══════════════════════════════════════════════════════════════
# START EVERYTHING
# Launches Gmail/Substack polling and Discord bot in parallel
# Each runs in its own thread so they don't block each other
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Bridge starting...")

    # Start Gmail and Substack polling in a background thread
    threading.Thread(target=polling_loop, daemon=True).start()

    # Start Discord bot in a background thread
    threading.Thread(target=run_discord, daemon=True).start()

    # Keep the main thread alive so the background threads keep running
    while True:
        time.sleep(60)
