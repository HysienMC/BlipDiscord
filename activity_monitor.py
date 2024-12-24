# activity_monitor.py
import time
import requests
import logging
import os
from collections import defaultdict
from datetime import datetime
from dotenv import load_dotenv
import sqlite3

# Load environment variables (make sure to create a .env file with your webhook URL)
load_dotenv()

# Constants for attack thresholds and time frame
MAX_FAILED_ATTEMPTS = 5
TIME_FRAME = 60  # in seconds
BLOCK_TIME = 300  # in seconds (rate-limiting block time)
ALERT_THRESHOLD = 3  # Number of alerts before flagging
COMMAND_USAGE_LIMIT = 10  # Max times a command can be used in a time period by a single user

# Webhook URL for sending notifications (loaded from environment variable)
DISCORD_WEBHOOK_URL = os.getenv("https://discord.com/api/webhooks/1317362655761272902/78p0BWj7z8et8XBcb9JTUnpDrXXP8XkUFGqHuS7zM3hJSoXnnnNB8c0_CxCih3tOzr1p")

# Store activity logs to track command attempts
activity_log = []
failed_attempts = defaultdict(list)

# Set up basic logging to a file
logging.basicConfig(filename='bot_activity.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Create SQLite Database for storing logs
conn = sqlite3.connect('bot_activity.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS activity_log (
                    user_ip TEXT,
                    command TEXT,
                    success BOOLEAN,
                    timestamp REAL)''')
conn.commit()

def send_discord_notification(message):
    """Send a notification message to the Discord channel using the webhook."""
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
        response.raise_for_status()  # Will raise an error for HTTP codes 4xx/5xx
        print("Notification sent successfully.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending Discord notification: {e}")

def log_activity(user_ip, command, success):
    """Log command attempts, including whether the command was successful."""
    timestamp = time.time()
    # Store activity in SQLite database
    cursor.execute("INSERT INTO activity_log (user_ip, command, success, timestamp) VALUES (?, ?, ?, ?)",
                   (user_ip, command, success, timestamp))
    conn.commit()

    # Log the activity to a file as well
    log_message = f"User IP: {user_ip}, Command: {command}, Success: {success}"
    logging.info(log_message)

def handle_failed_attempt(user_ip):
    """Handle failed attempt and check if rate limiting is necessary."""
    current_time = time.time()
    failed_attempts[user_ip].append(current_time)

    # Clean up old failed attempts (more than BLOCK_TIME ago)
    failed_attempts[user_ip] = [timestamp for timestamp in failed_attempts[user_ip] if current_time - timestamp < BLOCK_TIME]
    
    if len(failed_attempts[user_ip]) >= MAX_FAILED_ATTEMPTS:
        # Block user for a set time if failed attempts exceed the limit
        print(f"User {user_ip} is rate-limited for 5 minutes.")
        return True
    return False

def detect_brute_force(user_ip):
    """Check if a user has failed enough attempts to trigger an alert."""
    failed_attempts_for_user = [entry for entry in activity_log if entry['user_ip'] == user_ip and not entry['success']]
    return len(failed_attempts_for_user) >= MAX_FAILED_ATTEMPTS

def send_alert(user_ip, command):
    """Send an alert when suspicious activity (e.g., hacking attempt) is detected."""
    message = f"🚨 **Bot code tampering detected!** 🚨\n\n" \
              f"**User IP:** {user_ip}\n" \
              f"**Command:** {command}\n" \
              f"**Timestamp:** {datetime.now()}\n" \
              f"⚡ **Someone's trying to hack the bot!** ⚡\n\n" \
              f"👀 Check the code and logs ASAP!"
    send_discord_notification(message)

def send_startup_notification():
    """Send an initial notification when the bot starts."""
    message = f"🎉 **Bot is now online and monitoring for suspicious activity!** 🎉\n\n" \
              f"⚡ **Ready to rock and roll!** ⚡"
    send_discord_notification(message)

def get_geo_location(ip):
    """Fetch the geolocation of the given IP address."""
    access_key = os.getenv("IPSTACK_ACCESS_KEY")
    url = f"http://api.ipstack.com/{ip}?access_key={access_key}"
    
    try:
        response = requests.get(url)
        data = response.json()
        location = data.get('location', {})
        return location.get('country_name', 'Unknown')
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching geolocation for {ip}: {e}")
        return 'Unknown'

def handle_command(user_ip, command, success):
    """Handle incoming commands, logging and triggering alerts if necessary."""
    log_activity(user_ip, command, success)
    
    # Block the user if rate-limited
    if handle_failed_attempt(user_ip):
        print(f"Rate limit exceeded for IP {user_ip}")
        return

    # If the command failed and is suspicious, alert the admins
    if not success:
        if detect_brute_force(user_ip):
            send_alert(user_ip, command)
        else:
            print(f"Failed attempt from IP: {user_ip} for command: {command}")

def bot_command(user_ip, command):
    """Simulate command execution, determining success or failure."""
    success = command == "valid_command"  # Adjust this for your actual command validation logic
    handle_command(user_ip, command, success)

def track_command_usage(user_ip, command):
    """Track the frequency of commands used by an IP address."""
    current_time = time.time()
    # Check how many times the user has used the command recently
    user_command_attempts = [entry for entry in activity_log if entry['user_ip'] == user_ip and entry['command'] == command]
    recent_attempts = [attempt for attempt in user_command_attempts if current_time - attempt['timestamp'] < TIME_FRAME]

    if len(recent_attempts) >= COMMAND_USAGE_LIMIT:
        send_discord_notification(f"⚠️ User {user_ip} has exceeded the command usage limit for '{command}' command.")
        return True
    return False

def check_bot_health():
    """Simple health check to ensure bot is operational."""
    try:
        response = requests.get(DISCORD_WEBHOOK_URL)
        response.raise_for_status()
        print("Bot health check passed.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Health check failed: {e}")

# Entry point when the bot starts
if __name__ == "__main__":
    send_startup_notification()  # Notify on bot startup

    # Periodically check bot health (can be set in a loop or cron job)
    check_bot_health()

    # Example commands (replace with actual user inputs and logic)
    bot_command("192.168.1.1", "invalid_command")  # Simulate invalid command
    bot_command("192.168.1.1", "valid_command")   # Simulate valid command
