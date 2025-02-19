import discord
from discord.ext import commands
import logging
from discord.ui import Button, View
import threading
from flask import Flask, render_template, jsonify
import os
import time
import subprocess
import sys
import pytz
from logging.handlers import RotatingFileHandler
from werkzeug.serving import make_server
import os
import signal
from discord.ext import commands
import asyncio
import logging
import requests
from collections import defaultdict
import atexit
import psutil
import telebot
from collections import deque
import re
import smtplib
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from activity_monitor import handle_command , bot_command
import datetime
from dotenv import load_dotenv

API_KEY = "22065cd45848ad155db7e0b4"
BASE_URL = "https://v6.exchangerate-api.com/v6"
# Define log file first before using it
LOG_FILE = 'bot_logs.log'

load_dotenv()

discord_token = os.getenv("DISCORD_TOKEN")

TARGET_CHANNEL_ID = 1138060679803318292

# Define the test channel ID and the rules channel ID
TEST_CHANNEL_ID = 1320331443095732264
RULES_CHANNEL_ID = 1138113210239680573


message_counts = defaultdict(int)
daily_activity = defaultdict(int)
channel_activity = defaultdict(int)

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.guild_messages = True
intents.voice_states = True  # Enable voice state intents to monitor voice channel chats


spam_threshold = 5  # Number of messages considered spam within the time window
time_window = 10  # Time window in seconds for detecting spam
anti_spam_cache = defaultdict(list)

# Use RotatingFileHandler for logs
file_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=10 * 1024 * 1024,
    backupCount=5)  # 10MB max size per file, 5 backups
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Define a list of suspicious keywords or patterns
SUSPICIOUS_KEYWORDS = [
    "free nitro", "discord nitro", "gift", "steam-gift", "click here", "giveaway", "earn money",
    "quick money", "crypto", "bit.ly", "tinyurl", "grabify"
]
SUSPICIOUS_DOMAINS = [
    "grabify.link", "iplogger.org", "youshouldclickthis.com", "freenitro.com", "nitrofree.xyz"
]

# Regex pattern to detect URLs
URL_PATTERN = re.compile(r"(https?://\S+)")

# Add file handler to the logger
logging.getLogger().addHandler(file_handler)

# Initialize logging with basic configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Print to console
        file_handler  # Save to file with rotation
    ])

# Function to get system stats (CPU, memory, uptime)
def get_system_stats():
    cpu_usage = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    uptime = str(datetime.now() - datetime.fromtimestamp(psutil.boot_time()))
    return cpu_usage, memory, uptime

# Initialize Flask app
app = Flask(__name__)

# Global variable to track bot status
bot_online = False
start_time = time.time()
notifications_enabled = True
monitoring = True
admin_channel_id = 1300777697617645611  # Admin ID
patterns_file = "patterns.txt"
senders_file = "senders.txt"

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s]: %(message)s",
    handlers=[
        logging.FileHandler("bot_debug.log"),  # Log to a file
        logging.StreamHandler()               # Log to console
    ]
)

# Load the status cog
initial_extensions = ['status']

# Load and save analytics data
def load_data():
    try:
        with open("analytics.json", "r") as f:
            data = json.load(f)
            message_counts.update(data["message_counts"])
            daily_activity.update(data["daily_activity"])
            channel_activity.update(data["channel_activity"])
    except FileNotFoundError:
        pass

def save_data():
    with open("analytics.json", "w") as f:
        json.dump({
            "message_counts": message_counts,
            "daily_activity": daily_activity,
            "channel_activity": channel_activity
        }, f)

def restart_bot(reason=None):
    """Function to restart the bot with detailed logging."""
    try:
        # Record the time when the restart is initiated
        restart_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())

        # Log the restart initiation with detailed info
        reason_message = f"Reason: {reason}" if reason else "No specific reason provided."
        logging.info(
            f"Bot restart initiated at {restart_time}. {reason_message}")

        # Optional delay to allow the system to clean up resources
        time.sleep(1)  # Allow a brief moment before the restart

        # Log the restart command being executed
        restart_command = [sys.executable] + sys.argv
        logging.info(f"Executing restart command: {restart_command}")

        # Perform the restart
        logging.info("Restarting bot...")
        os.execv(sys.executable, restart_command)

    except Exception as e:
        # Log any failure to restart the bot
        logging.error(f"Failed to restart bot at {restart_time}. Error: {e}")
        raise  # Re-raise exception to handle it further up the call stack if needed


@app.route('/')
def home():
    """Simple endpoint for uptime monitoring with better UI"""
    if bot_online:
        return render_template(
            'index.html')  # Load the UI when the bot is online
    else:
        return render_template(
            'bot_offline.html'
        )  # Load the offline page when the bot is offline


@app.route('/status')
def status():
    """JSON response for UpTimeRobot"""
    if bot_online:
        return jsonify(status="OK"), 200
    else:
        return jsonify(status="Offline"), 200


def run_flask():
    """Function to run the Flask web server in a separate thread"""
    app.run(host="0.0.0.0", port=8080)


bot_start_time = time.time()



@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Shutdown the Flask app safely"""
    logging.info("Shutting down Flask app...")
    os.kill(os.getpid(), signal.SIGINT)
    return jsonify(status="Shutting down"), 200


@app.route('/health')
def health_check():
    """Health check endpoint to monitor bot's health"""
    return jsonify(status="OK", message="Bot is running"), 200


# Initialize bot with a command prefix
intents = discord.Intents.default()
intents.message_content = True  # To read messages' content
intents.members = True  # To access member information if needed
bot = commands.Bot(command_prefix='.', intents=intents)

# Kabayan Horizons SMP3
ANNOUNCER_CHANNEL_ID = 1138060680457625733  # Announcement channel id
COMMAND_CHANNEL_ID = 1320331443095732264  # Blip-commands channel id

# Your Discord user ID or username
ALLOWED_USER_ID = 123456789012345678
# List of allowed usernames
ALLOWED_USERNAMES = [
    "hysienmc", "klenty.1", "maple.qtt.official", "imlost_7", "zxysoo",
    "kcorejola1193", "izumi_7854"
]


def is_admin(request):
    return request.headers.get('X-Admin') == 'true'


@app.route('/admin/update_users', methods=['POST'])
def update_users():
    """Update the list of allowed users via the web interface."""

    # Check if the user is an admin
    if not is_admin(request):
        logging.warning("Unauthorized access attempt to /admin/update_users")
        return jsonify({
            "status": "error",
            "message": "Unauthorized access"
        }), 403

    # Get the data sent in the POST request (assuming JSON format)
    data = request.json
    if not data or "users" not in data:
        return jsonify({
            "status": "error",
            "message": "No users provided in request"
        }), 400

    new_users = data.get("users", [])

    # Validate the new users list (ensure it's a list of strings)
    if not isinstance(new_users, list):
        return jsonify({
            "status": "error",
            "message": "Users must be provided as a list"
        }), 400

    # Filter out duplicate users (avoid adding users that are already in the list)
    duplicate_users = [user for user in new_users if user in ALLOWED_USERNAMES]
    if duplicate_users:
        return jsonify({
            "status":
            "error",
            "message":
            f"Duplicate users found: {', '.join(duplicate_users)}"
        }), 400

    # Add the new users to the allowed usernames list
    ALLOWED_USERNAMES.extend(new_users)

    # Log the update
    logging.info(f"Updated allowed usernames: {ALLOWED_USERNAMES}")

    # Return a success response
    return jsonify({
        "status": "success",
        "message": "Users updated successfully"
    }), 200

# Utility function to load patterns
async def load_patterns():
    try:
        with open(patterns_file, "r") as f:
            return [line.strip() for line in f.readlines()]
    except FileNotFoundError:
        return []

# Utility function to load sender IDs
async def load_senders():
    try:
        with open(senders_file, "r") as f:
            return [int(line.strip()) for line in f.readlines()]
    except FileNotFoundError:
        return []

# Permissions checker
def has_permissions(channel, perms):
    bot_member = channel.guild.me
    bot_permissions = channel.permissions_for(bot_member)
    return all(getattr(bot_permissions, perm, False) for perm in perms)

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    await bot.change_presence(activity=discord.Game(name="Monitoring messages..."))

def process_command(user_ip, command):
    """Process incoming commands and handle success or failure."""
    success = command == "valid_command"  # Simulate valid command logic
    handle_command(user_ip, command, success)

# Simulate command usage
process_command("192.168.1.1", "invalid_command")  # Invalid command (simulate failure)
process_command("192.168.1.1", "valid_command") 



# A simple check to see if the user has the required role or is the server owner
def has_permission(ctx):
    logging.debug(
        f"Checking permissions for {ctx.author.name} ({ctx.author.id})")

    # Check for specific user ID or allowed usernames
    if ctx.author.id == ALLOWED_USER_ID or ctx.author.name in ALLOWED_USERNAMES:
        logging.debug(
            f"User {ctx.author.name} has permission (explicit ID or username)")
        return True

    # Check if the user has admin/moderator roles
    roles = [role.name for role in ctx.author.roles]
    if any(role in ['Admin', 'Moderator'] for role in roles):
        logging.debug(f"User {ctx.author.name} has permission (role-based)")
        return True

    logging.debug(f"User {ctx.author.name} does not have permission")
    return False

@bot.event
async def on_message(message):
    """Detect and delete messages with suspicious links."""
    # Ignore messages from the bot itself
    if message.author.bot:
        return

    # Search for URLs in the message
    urls = re.findall(URL_PATTERN, message.content)

    if urls:
        # Check if any URLs are suspicious
        for url in urls:
            if any(keyword in url.lower() for keyword in SUSPICIOUS_KEYWORDS) or \
               any(domain in url.lower() for domain in SUSPICIOUS_DOMAINS):
                await message.delete()  # Delete the suspicious message
                await message.channel.send(
                    f"⚠️ {message.author.mention}, your message contained a suspicious link and has been removed."
                )
                # Optionally notify moderators (replace with your moderator role ID)
                mod_role = discord.utils.get(message.guild.roles, name="Moderator")
                if mod_role:
                    await message.channel.send(
                        f"🚨 Suspicious link detected from {message.author.mention}: {url}\n"
                        f"Ping {mod_role.mention} for review."
                    )
                return

    # Process other bot commands
    await bot.process_commands(message)

# Example command to whitelist links (optional)
@bot.command(name="whitelist")
@commands.has_permissions(manage_messages=True)
async def whitelist(ctx, link: str):
    """Allow moderators to whitelist a link."""
    if link not in SUSPICIOUS_DOMAINS:
        SUSPICIOUS_DOMAINS.append(link)
        await ctx.send(f"✅ The link `{link}` has been added to the whitelist.")
    else:
        await ctx.send(f"⚠️ The link `{link}` is already in the whitelist.")


@bot.event
async def on_message(message):
    """Track user messages to prevent spam."""
    if message.author.bot:
        return

    user_id = str(message.author.id)
    current_time = time.time()
    time_limit = 5  # Allow 5 messages per 10 seconds

    if user_id not in user_messages:
        user_messages[user_id] = deque()
    
    # Remove messages that are older than the time limit
    while user_messages[user_id] and user_messages[user_id][0] < current_time - 10:
        user_messages[user_id].popleft()

    user_messages[user_id].append(current_time)

    if len(user_messages[user_id]) > time_limit:
        await message.delete()
        await message.channel.send(f"{message.author.mention}, please stop spamming!")
    else:
        await bot.process_commands(message)

# Command to send a manual announcement with @everyone, file attachment, and Discord invite link
@bot.command(name='announce')
async def announce(ctx, *, message: str):
    logging.debug(
        f"Command invoked by {ctx.author.name} ({ctx.author.id}) in channel {ctx.channel.name} ({ctx.channel.id})"
    )

    # Ensure the command is used in the correct channel
    if ctx.channel.id != COMMAND_CHANNEL_ID:
        await ctx.send(
            f"This command can only be used in the Command channel (ID: {COMMAND_CHANNEL_ID})."
        )
        return

    # Check if the user has permission
    if not has_permission(ctx):
        await ctx.send(
            f"You do not have permission to use this command. Your ID is {ctx.author.id} and username is {ctx.author.name}."
        )
        return

    # Ask for confirmation before proceeding
    await ctx.send(
        "Are you sure you want to send this announcement? Please confirm by clicking the buttons below."
    )

    # Create confirmation buttons
    button_yes = Button(label="Yes", style=discord.ButtonStyle.green)
    button_no = Button(label="No", style=discord.ButtonStyle.red)

    # Create the view and add buttons
    async def on_yes(interaction):
        # Disable the buttons once clicked
        button_yes.disabled = True
        button_no.disabled = True

        # Update the view to reflect disabled state
        await interaction.response.edit_message(view=view)

        announcement_channel = bot.get_channel(ANNOUNCER_CHANNEL_ID)
        if announcement_channel:
            # Check if bot has the permissions to send messages and mention @everyone
            if not announcement_channel.permissions_for(ctx.guild.me).send_messages:
                await interaction.followup.send(
                    "The bot does not have permission to send messages in the Announcer channel.",
                    ephemeral=True
                )
                return
            if not announcement_channel.permissions_for(ctx.guild.me).mention_everyone:
                await interaction.followup.send(
                    "The bot does not have permission to mention @everyone in the Announcer channel.",
                    ephemeral=True
                )
                return

            # Ask if the user wants to attach a file or include a Discord invite link
            await ctx.send(
                "Do you want to attach a file or include a Discord invite link? Reply with 'file', 'invite', or 'none'."
            )

            def check(msg):
                return msg.author == ctx.author and msg.channel == ctx.channel

            try:
                response = await bot.wait_for('message', check=check, timeout=60)
                if response.content.lower() == 'file':
                    await ctx.send("Please upload the file you want to attach.")

                    file_msg = await bot.wait_for('message', check=check, timeout=60)
                    if file_msg.attachments:
                        file = await file_msg.attachments[0].to_file()
                        await announcement_channel.send(f"@everyone {message}", file=file)
                        await interaction.followup.send(
                            f"Announcement with file attachment sent to {announcement_channel.mention}.",
                            ephemeral=True
                        )
                    else:
                        await interaction.followup.send(
                            "No file was attached. Sending announcement without a file.",
                            ephemeral=True
                        )
                        await announcement_channel.send(f"@everyone {message}")
                elif response.content.lower() == 'invite':
                    invite = await ctx.channel.create_invite(max_age=3600, max_uses=1)
                    await announcement_channel.send(f"@everyone {message}\n\nJoin us: {invite.url}")
                    await interaction.followup.send(
                        f"Announcement with invite link sent to {announcement_channel.mention}.",
                        ephemeral=True
                    )
                else:
                    await announcement_channel.send(f"@everyone {message}")
                    await interaction.followup.send(
                        f"Announcement sent to {announcement_channel.mention}.",
                        ephemeral=True
                    )
            except asyncio.TimeoutError:
                await interaction.followup.send(
                    "No response received. Sending announcement without additional content.",
                    ephemeral=True
                )
                await announcement_channel.send(f"@everyone {message}")

    async def on_no(interaction):
        # Disable the buttons once clicked
        button_yes.disabled = True
        button_no.disabled = True

        # Update the view to reflect disabled state
        await interaction.response.edit_message(view=view)

        await interaction.followup.send("Announcement was canceled.", ephemeral=True)

    button_yes.callback = on_yes
    button_no.callback = on_no

    view = View()
    view.add_item(button_yes)
    view.add_item(button_no)

    # Send message with the buttons
    await ctx.send(
        "Please confirm your action by clicking one of the buttons below.",
        view=view
    )



@bot.command()
async def spoiler(ctx, *, message: str):
    """Send a spoiler announcement to both the current channel and a specific announcement channel."""
    
    # Channel ID of the announcement channel (replace with your actual channel ID)
    announcement_channel_id = 1304717111356293152 
    
    # Create the spoiler message
    spoiler_message = f"||{message}||"
    
    # Send the spoiler message to the current channel (where the command was used)
    await ctx.send(spoiler_message)
    
    # Fetch the announcement channel by ID
    announcement_channel = bot.get_channel(announcement_channel_id)
    
    # Ensure the channel exists and is valid
    if announcement_channel:
        # Create an embed for a more structured message
        embed = discord.Embed(title="Spoiler Alert!", description=spoiler_message, color=discord.Color.red())
        embed.set_footer(text="Spoiler content. Click to reveal!")
        
        # Send the spoiler embed to the announcement channel
        await announcement_channel.send(embed=embed)
    else:
        # If the channel ID is incorrect or the bot can't find the channel
        await ctx.send("Couldn't find the announcement channel. Please check the channel ID.")

# Bot event to track messages
@bot.event
async def on_message(message):
    if not message.author.bot:
        # Track user activity
        message_counts[str(message.author.id)] += 1

        # Track daily activity
        today = datetime.date.today().isoformat()
        daily_activity[today] += 1

        # Track channel activity
        channel_activity[str(message.channel.id)] += 1

    await bot.process_commands(message)
    
# Display analytics command
@bot.command(name="analytics")
async def show_analytics(ctx):
    """Display server analytics."""
    # Get most active user
    if message_counts:
        most_active_user_id = max(message_counts, key=message_counts.get)
        most_active_user = await bot.fetch_user(int(most_active_user_id))
        most_active_user_msg = f"{most_active_user.mention} ({message_counts[most_active_user_id]} messages)"
    else:
        most_active_user_msg = "No activity tracked yet."

    # Get most active channel
    if channel_activity:
        most_active_channel_id = max(channel_activity, key=channel_activity.get)
        most_active_channel = bot.get_channel(int(most_active_channel_id))
        most_active_channel_msg = f"{most_active_channel.mention} ({channel_activity[most_active_channel_id]} messages)"
    else:
        most_active_channel_msg = "No activity tracked yet."

    # Total messages today
    today = datetime.date.today().isoformat()
    messages_today = daily_activity.get(today, 0)

    # Embed Design
    embed = discord.Embed(title="📊 Server Analytics", color=discord.Color.green())
    embed.add_field(name="👤 Most Active User", value=most_active_user_msg, inline=False)
    embed.add_field(name="📅 Messages Today", value=str(messages_today), inline=False)
    embed.add_field(name="💬 Most Active Channel", value=most_active_channel_msg, inline=False)
    embed.add_field(name="📈 Total Messages Tracked", value=str(sum(message_counts.values())), inline=False)
    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url)
    embed.timestamp = datetime.datetime.utcnow()

    await ctx.send(embed=embed)

# Save analytics data periodically and on shutdown
atexit.register(save_data)

@bot.command(name='command')
async def list_commands(ctx):
    """Lists all available commands for the bot."""

    commands_list = [
        "Here are the available commands for **KabayanX** Bot:\n"
        "Use `.command` followed by the command name to invoke it.\n"
        "For more detailed information on a specific command, use `.help <command>`.\n"
        "\n",
        "**📢 Announcement Commands:**",
        "`.announce <message>`: Send an announcement to the Announcer Channel.",
        "**📝 Information Commands:**",
        "`.userinfo [user]`: Get detailed information about a user (e.g., account creation date, server join date, etc.).",
        "`.logs [lines]`: View the latest logs (default 15 lines).",
        "`.codes`: Display KabayanX code's text file.",
        "`.uptime`: Check the bot's uptime and start time.",
        "`.status`: Check if the bot is online or offline.",
        "`.avatar [user]`: Get the avatar of a user (use `.avatar` for your own).",
        "`.serverinfo`: Get detailed information about the server (e.g., member count, channels, boosts, etc.).",
        "`.invitebot`: Get the invite link to add the bot to another server.",
        "`.motd`: Display the message of the day (e.g., motivational quotes, announcements).",
        "**🕒 Scheduling Commands:**",
        "`.schedule <HH:MM> <message>`: Schedule a message to be sent at a specific time.",
        "**💵 Utility Commands:**",
        "`.convert <amount> <from_currency> <to_currency>`: Convert currency from one type to another.",
        "**📚 Wiki Command:**",
        "`.wiki <search_term>`: Get a Wikipedia summary of a specific topic (e.g., `.wiki Quantum mechanics`).",
        "**📊 Analytics Commands:**",
        "`.analytics`: View server activity, most active users, and other engagement metrics.",
        "**❓ Help Commands:**",
        "`.helpme`: Show this help menu.",
        "`.help <command>`: Get more detailed information on a specific command.",
        "\n**📑 New Command Rules:**",
        "`.rules`: Display the server rules.",
    ]

    # Sending the formatted message
    await ctx.send("\n".join(commands_list))




# Handle the restart command
@bot.command(name='restart')
async def restart(ctx, *, reason: str = "No reason provided"):
    """Command to restart the bot (admin only) with a reason"""
    if not has_permission(ctx):
        await ctx.send("You do not have permission to restart the bot.")
        return

    # Get the current time for when the restart is initiated
    restart_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())

    # Log the restart initiation with time and reason
    logging.info(f"Bot restart initiated at {restart_time}. Reason: {reason}. Restart requested by {ctx.author}.")

    # Send message to the user that the bot is restarting with the reason
    await ctx.send(f"Bot is restarting... Reason: {reason} (Requested by {ctx.author})")

    try:
        # Optional: Delay before restarting, allowing time for the message to be sent
        await asyncio.sleep(2)

        # Log the restart process
        restart_command = [sys.executable] + sys.argv
        logging.info(f"Executing restart command: {restart_command}")

        # Perform the bot restart
        logging.info("Restarting bot...")
        os.execv(sys.executable, restart_command)

    except Exception as e:
        # Log any failure to restart
        logging.error(f"Failed to restart bot at {restart_time}. Error: {e}")
        await ctx.send(f"Failed to restart bot. Error: {e}")

# On bot ready event to send a message after restart
@bot.event
async def on_ready():
    """Send a message after the bot restarts and comes back online"""
    # Make sure to replace this with your actual channel ID
    channel = bot.get_channel(1300777697617645611)

    if channel:
        await channel.send("Bot restarted successfully! I am now online.")

    logging.info(f"Bot has successfully restarted and is now online.")
    
    # Set the bot's activity to "Listening to .helpme"
    activity = discord.Activity(type=discord.ActivityType.listening, name='.helpme')
    await bot.change_presence(activity=activity)

@bot.command()
async def convert(ctx, amount: float, from_currency: str, to_currency: str):
    try:
        # API Request
        url = f"{BASE_URL}/{API_KEY}/pair/{from_currency.upper()}/{to_currency.upper()}"
        response = requests.get(url)
        data = response.json()

        # Check if the request was successful
        if data["result"] == "success":
            rate = data["conversion_rate"]
            converted_amount = amount * rate
            await ctx.send(
                f"{amount} {from_currency.upper()} is approximately {converted_amount:.2f} {to_currency.upper()}."
            )
        else:
            await ctx.send(
                "Invalid currency code or API error. Please try again.")
    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")

@bot.event
async def on_member_join(member):
    # Define the channel where you want to send the welcome message
    welcome_channel_id = 1298602400273272873  # Replace with your channel ID
    channel = bot.get_channel(welcome_channel_id)

    if channel is not None:
        # Create an embed message
        embed = discord.Embed(
            title="Welcome to the Server!",
            color=discord.Color.green()
        )

        # Add the user's profile picture at the top
        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)

        # Add user's name in bold
        embed.add_field(name="\u200b", value=f"**{member.name}**", inline=False)

        # Add user details
        embed.add_field(
            name="User Info",
            value=(
                f"**Joined Discord:** {member.created_at.strftime('%B %d, %Y')}\n"
                f"**Joined Server:** {member.joined_at.strftime('%B %d, %Y') if member.joined_at else 'Unknown'}"
            ),
            inline=False
        )

        # Add a warm welcome message
        embed.add_field(
            name="Welcome!",
            value=f"We're thrilled to have you here, {member.mention}! Feel free to explore the server and make yourself at home.",
            inline=False
        )

        embed.set_footer(text="Enjoy your stay and have fun!")

        # Send the embed message to the channel
        await channel.send(embed=embed)
    else:
        print("Welcome channel not found.")

@bot.event
async def on_ready():
    print("="*30)
    print(f"🤖 Bot is now online!")
    print(f"✅ Logged in as: {bot.user.name}")
    print(f"🆔 Bot ID: {bot.user.id}")
    print("="*30)
    await bot.change_presence(activity=discord.Game(name="Monitoring messages..."))

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Anti-spam detection
    now = asyncio.get_event_loop().time()
    anti_spam_cache[message.author.id].append(now)

    # Remove timestamps outside the time window
    anti_spam_cache[message.author.id] = [timestamp for timestamp in anti_spam_cache[message.author.id] if now - timestamp <= time_window]

    if len(anti_spam_cache[message.author.id]) > spam_threshold:
        await message.channel.send(f"{message.author.mention}, you are sending messages too quickly. Please slow down.")
        await message.delete()
        return

    # Anti-mention spam detection
    if message.mention_everyone:
        await message.delete()
        await message.channel.send(f"Message from {message.author.mention} containing mass mentions was deleted.")
        return

    await bot.process_commands(message)

@bot.command()
async def delete(ctx):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You do not have the necessary permissions to use this command.")
        return

    await ctx.send("Starting to monitor and delete hidden messages. This may take some time...")

    async def monitor_and_delete():
        global monitoring
        while monitoring:
            patterns = await load_patterns()
            senders = await load_senders()

            for channel in ctx.guild.text_channels:
                if not has_permissions(channel, ["view_channel", "read_message_history", "manage_messages"]):
                    print(f"Insufficient permissions for channel: {channel.name}")
                    continue
                try:
                    async for message in channel.history(limit=None, oldest_first=True):
                        if message.author.id in senders and any(pattern in message.content for pattern in patterns):
                            await message.delete()
                            logging.info(f"Deleted message: {message.content} from {message.author} in channel: {channel.name}")
                except discord.Forbidden:
                    print(f"Permission denied for channel: {channel.name}")
                except discord.HTTPException as e:
                    print(f"Error occurred in channel {channel.name}: {e}")

            notification_channel = ctx.guild.get_channel(admin_channel_id)
            if notifications_enabled and notification_channel:
                await notification_channel.send(
                    "Monitoring is active. Deleted suspicious messages as needed."
                )

            await asyncio.sleep(10)  # Check every 10 seconds

    bot.loop.create_task(monitor_and_delete())

    await ctx.send("Monitoring for messages has started.")

@bot.command()
async def stop_monitoring(ctx):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You don't have permissions to stop monitoring.")
        return

    global monitoring
    monitoring = False
    await ctx.send("Monitoring has been stopped.")

@bot.command()
async def add_pattern(ctx, *, pattern):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You don't have permissions to add patterns.")
        return

    with open(patterns_file, "a") as f:
        f.write(pattern + "\n")
    await ctx.send(f"Pattern `{pattern}` has been added.")

@bot.command()
async def add_sender(ctx, sender_id: int):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You don't have permissions to add sender IDs.")
        return

    with open(senders_file, "a") as f:
        f.write(str(sender_id) + "\n")
    await ctx.send(f"Sender ID `{sender_id}` has been added.")

@bot.command()
async def toggle_notifications(ctx, enable: bool):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You don't have permissions to toggle notifications.")
        return

    global notifications_enabled
    notifications_enabled = enable
    status = "enabled" if enable else "disabled"
    await ctx.send(f"Notifications have been {status}.")

# Command to view logs
@bot.command(name='logs')
async def view_logs(ctx, lines: int = 15):
    """Command to view the latest logs."""
    if not has_permission(ctx):
        await ctx.send("You do not have permission to view the logs.")
        return

    try:
        # Read the last few lines of the log file
        with open(LOG_FILE, 'r') as log_file:
            logs = log_file.readlines()

        # Display the requested number of log lines
        if len(logs) < lines:
            lines = len(logs)
        latest_logs = ''.join(logs[-lines:])
        if latest_logs.strip():
            await ctx.send(f"```\n{latest_logs}\n```")
        else:
            await ctx.send("The logs are empty.")

    except FileNotFoundError:
        await ctx.send("Log file not found. No logs available.")
    except Exception as e:
        logging.error(f"Error while retrieving logs: {e}")
        await ctx.send(f"An error occurred while retrieving logs: {e}")


@bot.command(name='codes')
async def display_codes(ctx):
    """Command to send the KabayanX code's text file."""
    try:
        # Check if the file exists
        if os.path.exists('kabayanx_codes.txt'):
            # Send the file to the user
            await ctx.send("Here is the KabayanX code file:",
                           file=discord.File('kabayanx_codes.txt'))
        else:
            await ctx.send("Error: `kabayanx_codes.txt` file not found.")

    except Exception as e:
        await ctx.send(f"An error occurred: {e}")

@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild  # Get the server (guild) info
    owner = guild.owner
    created_at = guild.created_at.strftime("%A, %B %d, %Y %I:%M %p")
    
    # Count channels
    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    categories = len(guild.categories)
    
    # Count emojis
    total_emojis = len(guild.emojis)
    static_emojis = sum(1 for emoji in guild.emojis if not emoji.animated)
    animated_emojis = sum(1 for emoji in guild.emojis if emoji.animated)
    
    # Boost information
    boost_level = guild.premium_tier
    boost_count = guild.premium_subscription_count
    
    # Embed construction
    embed = discord.Embed(
        title=guild.name,
        description=f"ID: {guild.id}",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()  # Use discord's method for UTC time
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name="Owner", value=f"<@{owner.id}>", inline=False)
    embed.add_field(name="Created Date", value=f"{created_at} ({(discord.utils.utcnow() - guild.created_at).days} days ago)", inline=False)
    embed.add_field(name="Invite Tracker Premium", value="❌", inline=False)
    embed.add_field(
        name="Features",
        value=(
            f"{'✅' if 'COMMUNITY' in guild.features else '❌'}: Community Server\n"
            f"{'✅' if 'INVITE_SPLASH' in guild.features else '❌'}: Invite Splash\n"
            f"{'✅' if 'NEWS' in guild.features else '❌'}: News Channels\n"
            f"{'✅' if 'ANIMATED_ICON' in guild.features else '❌'}: Animated Icon\n"
            f"{'✅' if 'BANNER' in guild.features else '❌'}: Banner"
        ),
        inline=False
    )
    embed.add_field(name="Member Count", value=f"{guild.member_count}", inline=True)
    embed.add_field(name="Boosts", value=f"Level {boost_level}\n{boost_count} boosts", inline=True)
    embed.add_field(name="Roles", value=f"{len(guild.roles)} roles", inline=True)
    embed.add_field(
        name="Channels",
        value=(
            f"Textual: {text_channels}\n"
            f"Voice: {voice_channels}\n"
            f"Category: {categories}"
        ),
        inline=True
    )
    embed.add_field(
        name="Emojis",
        value=(
            f"Regular: {static_emojis}/{guild.emoji_limit * 2}\n"
            f"Animated: {animated_emojis}/{guild.emoji_limit * 2}\n"
            f"Total: {total_emojis}/{guild.emoji_limit * 4}"
        ),
        inline=True
    )
    embed.set_footer(text="Server Information")

    # Send the embed
    await ctx.send(embed=embed)


@bot.command(name='uptime')
async def uptime(ctx):
    """Command to check the bot's uptime with detailed time information."""

    # Get the Philippines timezone
    philippines_tz = pytz.timezone('Asia/Manila')

    # Get the current time in the Philippines timezone
    current_time = datetime.datetime.now(philippines_tz)

    # Calculate uptime in seconds
    uptime_seconds = int(time.time() - bot_start_time)

    # Format the uptime as days, hours, minutes, seconds
    uptime_str = str(datetime.timedelta(seconds=uptime_seconds))

    # Format the bot's start time
    start_time = datetime.datetime.fromtimestamp(
        bot_start_time, philippines_tz).strftime('%Y-%m-%d %H:%M:%S')

    # Send the detailed uptime message
    await ctx.send(
        f"**Local Time (PH):** {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"**Current Uptime:** {uptime_str}\n"
        f"**Start Time:** {start_time}"
    )

@bot.command()
async def avatar(ctx, user: discord.User = None):
    user = user or ctx.author  # If no user is specified, use the command author

    # Fetch the member if they are part of the server
    member = ctx.guild.get_member(user.id) if user != ctx.author else None

    # Prepare the embed
    embed = discord.Embed(
        title=f"{user.name}'s Avatar",
        description=f"Here is the avatar of {user.name}",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()  # Add timestamp to the embed
    )

    # Add user ID
    embed.add_field(name="User ID", value=user.id, inline=False)

    # Check if the user is a member of the server or if the user is an owner/admin
    if member:  # If user is a member of the guild
        status = str(member.status).capitalize()  # Status like "Online", "Offline", "Idle"
        activity = member.activity  # Get the user's current activity (e.g., game, listening to music)
        
        # If the user is playing a game or listening to music
        if activity:
            activity_type = f" ({activity.type.name})"
            activity_name = f"{activity.name}{activity_type}" if activity.name else "Unknown Activity"
            embed.add_field(name="Current Activity", value=activity_name, inline=False)
        else:
            embed.add_field(name="Current Activity", value="No activity", inline=False)

        embed.add_field(name="Status", value=status, inline=False)

        # Handle "Do Not Disturb" and "Idle" status
        if status == 'Do Not Disturb':
            embed.add_field(name="Status Message", value="The user is currently busy.", inline=False)
        elif status == 'Idle':
            embed.add_field(name="Status Message", value="The user is away or inactive.", inline=False)

    else:
        # For users who are not in the server, check if they are the owner or have a special role
        if ctx.guild.owner.id == user.id:  # If the user is the server owner
            embed.add_field(name="Status", value="Server Owner (Status is not available for non-members)", inline=False)
        elif any(role.permissions.administrator for role in ctx.guild.roles if role in user.roles):  # Admin check
            embed.add_field(name="Status", value="Admin (Status is not available for non-members)", inline=False)
        else:
            embed.add_field(name="Status", value="Unavailable (User is not a member of the server)", inline=False)

    # Account creation date
    embed.add_field(name="Account Created", value=user.created_at.strftime("%A, %B %d, %Y %I:%M %p"), inline=False)

    # Show user's avatar image
    embed.set_image(url=user.avatar.url)

    # Optional: Display the user's banner if they have one (profile banner)
    if user.banner:
        embed.set_thumbnail(url=user.banner.url)

    # Add footer with a small credit or bot name
    embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url)

    # Send the embed, but only one embed is sent
    await ctx.send(embed=embed)



# Help Command with Interactive Menu and Version Updates
@bot.command(name='helpme')
async def helpme(ctx):
    embed = discord.Embed(
        title="\ud83d\udcac KabayanX Bot Help",
        description=
        "Welcome to the **KabayanX Bot** help section! Below you'll find the available commands, their usage, and links to teams for support and collaboration.",
        color=discord.Color.blue())

    # Version Update Section
    embed.add_field(
        name="\u2139\ufe0f **Version Updates**",
        value=
        ("\ud83d\udd30 **Version 1.1.0** (December 2024)\n"
         "- Added the `?codes` command to display KabayanX code snippets.\n"
         "- Introduced logging functionality with `?logs` command to view the last few log entries.\n"
         "- Added the `?announce` command with a confirmation button for sending announcements to the `Announcer Channel`.\n"
         "\n"
         "\ud83d\udd30 **Version 1.0.0** (November 2024)\n"
         "- Initial release of KabayanX Bot.\n"
         "- Features include `?helpme`, `?announce`, and `?schedule` commands.\n"
         "- Interactive help menu with buttons for detailed command descriptions.\n"
         ),
        inline=False)

    embed.add_field(
        name="1\ufe0f\u20e3 `?announce <message>`",
        value=
        ("\ud83d\udce2 **Description:** Sends an announcement to the `Announcer Channel` with an `@everyone` mention.\n"
         "\ud83d\udca1 **Usage Example:** `?announce This is an important announcement!`\n"
         "\ud83d\udd11 **Permissions:** Admin, Moderator, or user with specific ID.\n"
         "\ud83d\udccd **Channel Restriction:** Command can only be used in the `Command Channel`.\n"
         ),
        inline=False)

    embed.add_field(
        name="2\ufe0f\u20e3 `?schedule <HH:MM> <message>`",
        value=
        ("\ud83d\udd52 **Description:** Schedules an announcement at a specific time (in 24-hour format).\n"
         "\ud83d\udca1 **Usage Example:** `?schedule 15:30 Reminder to attend the meeting!`\n"
         "\ud83d\udd11 **Permissions:** Admin, Moderator, or user with specific ID.\n"
         "\ud83d\udccd **Channel Restriction:** Command can only be used in the `Command Channel`.\n"
         "\u26a0\ufe0f **Note:** The time format should be `HH:MM` (24-hour format). If the time has already passed, it will schedule for the next day.\n"
         ),
        inline=False)

    embed.add_field(
        name="3\ufe0f\u20e3 `?helpme`",
        value=(
            "\ud83d\udcda **Description:** Displays this help message.\n"
            "\ud83d\udca1 **Usage Example:** `?helpme`\n"
            "\ud83d\udd11 **Permissions:** No special permissions required.\n"
        ),
        inline=False)

    embed.add_field(
        name="\ud83c\udf0d **Links**",
        value=
        ("\ud83d\udd17 **Support Server:** [Click Here to Join](https://discord.gg/aqqg7Swn4K)\n"
         "\ud83d\udce7 **Contact Developer:** [Clay Bautista](https://web.facebook.com/itsmeS3th)\n"
         "\ud83c\udf10 **Website:** [KabayanXBot Website](https://a4164c07-e213-41bf-9eff-575df4040b0b-00-23y8n0sy8icgp.sisko.replit.dev/)\n"
         ),
        inline=False)

    embed.set_footer(text="KabayanX Bot | Developer: Clay Bautista",
                     icon_url="https://i.imgur.com/6lDg9hz.png")

    # Create menu buttons for help
    button_announce = Button(label="Send an Announcement",
                             style=discord.ButtonStyle.primary)
    button_schedule = Button(label="Schedule a Message",
                             style=discord.ButtonStyle.primary)
    button_logs = Button(label="View Logs", style=discord.ButtonStyle.primary)

    async def on_announce(interaction):
        await interaction.response.send_message(
            "You can use `?announce <message>` to send an announcement.")

    async def on_schedule(interaction):
        await interaction.response.send_message(
            "You can use `?schedule <HH:MM> <message>` to schedule an announcement."
        )

    # Updated on_logs function to show logs
    async def on_logs(interaction):
        logs = await on_logs()
        await interaction.response.send_message(f"Latest logs:\n{logs}")

    button_announce.callback = on_announce
    button_schedule.callback = on_schedule
    button_logs.callback = on_logs

    help_view = View()
    help_view.add_item(button_announce)
    help_view.add_item(button_schedule)
    help_view.add_item(button_logs)

    await ctx.send(embed=embed, view=help_view)


# Error handling
import logging
from discord.ext import commands

@bot.event
async def on_command_error(ctx, error):
    # Check for the specific "??" input and handle it
    if ctx.message.content == "??":
        await ctx.send("Did you mean a specific command? Try `?helpme` for a list of commands!")
        logging.info(f"User {ctx.author} entered '??', prompting help message.")
        return  # Prevent further error handling

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Please provide all the required arguments.")
        logging.error(f"Missing argument in command {ctx.command}: {str(error)}")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to perform this action.")
        logging.warning(f"Permission denied for {ctx.author} in {ctx.command}")
    elif isinstance(error, commands.CommandNotFound):
        # Prevent duplicate responses for "??"
        if ctx.message.content == "??":
            return
        await ctx.send("Sorry, I didn't understand that command.")
        logging.warning(f"Command not found: {str(error)}")
    else:
        await ctx.send(f"An error occurred: {str(error)}")
        logging.error(f"Unexpected error: {str(error)}")



@bot.command(name='userinfo')
async def user_info(ctx, user: discord.User = None):
    """Get detailed information about a user."""
    
    # If no user is mentioned, get the command author's info
    if user is None:
        user = ctx.author
    
    # Attempt to get the user as a member of the guild (server)
    member = ctx.guild.get_member(user.id)
    
    # Set joined_at depending on whether the user is a member of the server
    if member:
        joined_at = member.joined_at.strftime('%Y-%m-%d %H:%M:%S')
    else:
        joined_at = "Not available"  # If the user is not a member of the server

    # Create the embed for user information
    embed = discord.Embed(title=f"User Info: {user.name}",
                          description=f"Information about {user.mention}",
                          color=discord.Color.blue())

    # Add user-specific fields to the embed
    embed.add_field(name="ID", value=user.id, inline=True)
    embed.add_field(name="Discriminator", value=user.discriminator, inline=True)
    embed.add_field(name="Account Created", value=user.created_at.strftime('%Y-%m-%d %H:%M:%S'), inline=True)
    embed.add_field(name="Joined Server", value=joined_at, inline=True)
    
    # Only attempt to access status if the user is a member of the server
    if member:
        embed.add_field(name="Status", value=str(member.status).capitalize(), inline=True)
    else:
        embed.add_field(name="Status", value="N/A (User not in server)", inline=True)

    embed.add_field(name="Is Bot?", value="Yes" if user.bot else "No", inline=True)

    # Add roles (if the user is a member of the server) excluding @everyone role
    if member:
        roles = [role.name for role in member.roles[1:]]  # Exclude @everyone role
        roles = ", ".join(roles) if roles else "No roles"
        embed.add_field(name="Roles", value=roles, inline=False)

    # Add the user's avatar if available
    avatar_url = user.avatar.url if user.avatar else "https://i.imgur.com/3kmJ75Q.png"  # Default avatar if no avatar is set
    embed.set_thumbnail(url=avatar_url)

    # Send the embed
    await ctx.send(embed=embed)

# Wikipedia API URL
WIKI_API_URL = "https://en.wikipedia.org/w/api.php"

# Function to fetch Wikipedia summary and clean the result
def clean_html(html_content):
    """Remove HTML tags and unnecessary characters from Wikipedia summary."""
    clean_text = re.sub(r'<[^>]+>', '', html_content)  # Remove HTML tags
    clean_text = clean_text.replace("\n", " ")  # Replace newlines with spaces
    clean_text = clean_text.strip()  # Remove leading/trailing spaces
    return clean_text

def get_wikipedia_summary(query):
    """Fetch a summary from Wikipedia using the search query."""
    params = {
        'action': 'query',
        'format': 'json',
        'prop': 'extracts',
        'exintro': True,
        'exchars': 500,  # Limit summary to 500 characters
        'titles': query,
        'redirects': True  # Automatically follow redirects
    }

    try:
        response = requests.get(WIKI_API_URL, params=params)
        response.raise_for_status()  # Raise an exception for invalid responses
        data = response.json()

        # Extract the page information from the response
        pages = data.get("query", {}).get("pages", {})
        for page_id, page_info in pages.items():
            if 'extract' in page_info:
                title = page_info['title']
                raw_extract = page_info['extract']
                clean_extract = clean_html(raw_extract)
                url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                return title, clean_extract, url

        return None, "No information found on Wikipedia.", None
    except requests.exceptions.RequestException as e:
        return None, f"An error occurred while fetching data: {e}", None

# Wiki command to search Wikipedia
@bot.command()
async def wiki(ctx, *, query: str):
    """Fetch a Wikipedia article summary."""
    await ctx.message.delete()  # Optionally, delete the command message to keep things tidy
    title, extract, url = get_wikipedia_summary(query)
    
    if title:
        # Create a rich embed to display the results with improved formatting
        embed = discord.Embed(
            title=title, 
            description=extract,
            color=discord.Color.blue()  # Set a clean color
        )
        
        embed.add_field(
            name="🔍 Read More", 
            value=f"[Click here to read more]({url})", 
            inline=False
        )
        
        embed.set_footer(text="Powered by Wikipedia")
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Wikipedia-logo-v2.svg/1200px-Wikipedia-logo-v2.svg.png")  # Add Wikipedia logo as thumbnail
        await ctx.send(embed=embed)
    else:
        # Send an error message if no article found or an issue occurred
        await ctx.send(extract)

# Error handling for command errors
@bot.event
async def on_command_error(ctx, error):
    """Handle errors gracefully."""
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Please provide a search query.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("Sorry, I couldn't find that command.")
    else:
        await ctx.send(f"An error occurred: {str(error)}")

@bot.command(name='status')
async def bot_status(ctx):
    """Command to check the bot's status and system stats."""
    # Get bot memory and CPU usage
    memory = psutil.virtual_memory().percent
    cpu = psutil.cpu_percent(interval=1)
    uptime = time.time() - bot.start_time

    # Determine if the bot is online or offline
    if bot_online:
        status_message = "✅ The bot is currently **online**."
    else:
        status_message = "❌ The bot is currently **offline**."

    # Create the embed message for the bot's stats
    embed = discord.Embed(title="Bot Status & Stats", color=discord.Color.green())
    embed.add_field(name="Bot Status", value=status_message, inline=False)
    embed.add_field(name="CPU Usage", value=f"{cpu}%", inline=False)
    embed.add_field(name="Memory Usage", value=f"{memory}%", inline=False)
    embed.add_field(name="Uptime", value=f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m", inline=False)

    await ctx.send(embed=embed)

@bot.command()
async def joke(ctx):
    try:
        # Debugging: Show the URL we are trying to access
        print("Sending request to: https://api.chucknorris.io/jokes/random")

        # Make the API request to get a random joke
        response = requests.get("https://api.chucknorris.io/jokes/random")

        # Debugging output: Show raw response content and status code
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Content: {response.text}")

        # Check if the response was successful
        if response.status_code == 200:
            # Parse the JSON response
            joke_data = response.json()

            # Debugging output: Print the parsed JSON data
            print(f"Joke Data: {joke_data}")

            if joke_data:  # Ensure there is a joke in the response
                # Access the joke directly from the dictionary
                joke = joke_data.get('value', 'No joke available.')
                await ctx.send(joke)
            else:
                await ctx.send("Oops! No jokes were returned.")
        else:
            await ctx.send(f"Failed to retrieve a joke. Status Code: {response.status_code}")

    except requests.exceptions.RequestException as e:
        # Catch issues with the HTTP request
        print(f"Request error: {e}")
        await ctx.send(f"An error occurred while making the request: {e}")

    except ValueError as e:
        # Catch issues with JSON decoding
        print(f"JSON decode error: {e}")
        await ctx.send(f"An error occurred while processing the response: {e}")

    except Exception as e:
        # Catch any other errors
        print(f"Unexpected error: {e}")
        await ctx.send(f"An unexpected error occurred: {e}")


@bot.command(name="leaderboard")
async def leaderboard(ctx, top_n: int = 5):
    """Shows the leaderboard of most active users and highlights Admins and Moderators."""

    # Get the sorted list of users by their message count
    sorted_users = sorted(message_counts.items(), key=lambda x: x[1], reverse=True)

    # Ensure that we show at least the top 5 or the number of users in the sorted list
    top_n = min(top_n, len(sorted_users))

    # Prepare the leaderboard data
    leaderboard_data = []
    highlighted_users = set()  # Set to track users we want to highlight (admins, mods, etc.)

    # Get roles from the server
    admin_roles = [role.name.lower() for role in ctx.guild.roles if "admin" in role.name.lower()]
    mod_roles = [role.name.lower() for role in ctx.guild.roles if "mod" in role.name.lower()]

    # Add the top N users first, but ensure admins and mods are always included
    for i, (user_id, count) in enumerate(sorted_users[:top_n]):
        user = await bot.fetch_user(user_id)  # Fetch user using the bot's cached data
        member = ctx.guild.get_member(user_id)  # Get the member object from the server

        if member:
            join_date = member.joined_at.strftime('%Y-%m-%d')  # For members of the server
        else:
            join_date = "N/A"  # If the user isn't a member, show "N/A"

        # Add user to the leaderboard data
        leaderboard_data.append(
            {
                "rank": i + 1,
                "user_id": user_id,
                "username": user.name,
                "discriminator": user.discriminator,
                "messages": count,
                "avatar": user.avatar.url,
                "join_date": join_date,
                "is_admin_or_mod": any(role.name.lower() in admin_roles + mod_roles for role in member.roles) if member else False
            }
        )

        # Mark admins and mods to be highlighted
        if leaderboard_data[i]["is_admin_or_mod"]:
            highlighted_users.add(user_id)

    # Prepare the embed message for better presentation
    embed = discord.Embed(title="🏆 Most Active Users - Leaderboard", color=discord.Color.gold())

    # Loop over the leaderboard data and add entries to the embed
    for entry in leaderboard_data:
        role_highlight = "🔹 **Admin/Mod**" if entry["is_admin_or_mod"] else ""
        embed.add_field(
            name=f"**{entry['rank']}. {entry['username']}#{entry['discriminator']}** {role_highlight}",
            value=f"Messages: {entry['messages']}\nJoined: {entry['join_date']}",
            inline=False
        )

    # If the user who ran the command is in the leaderboard, add their position
    if any(entry["user_id"] == ctx.author.id for entry in leaderboard_data):
        user_position = next(entry for entry in leaderboard_data if entry["user_id"] == ctx.author.id)
        embed.set_footer(text=f"{ctx.author.name}#{ctx.author.discriminator} is ranked #{user_position['rank']}")

    # Display the leaderboard
    await ctx.send(embed=embed)



# Update bot status when it starts or stops
@bot.event
async def on_ready():
    global bot_online
    bot_online = True
    bot.start_time = time.time()
    logging.info(f'{bot.user} has connected to Discord!')


@bot.event
async def on_disconnect():
    global bot_online
    bot_online = False
    logging.info('Bot has disconnected from Discord')
    time.sleep(10)  # Wait before restarting
    restart_bot()
    save_data()


# Run the Flask server in a separate thread
thread = threading.Thread(target=run_flask)
thread.start()

# Start Flask in a separate thread
threading.Thread(target=run_flask, daemon=True).start()

async def scan_channels():
    """Scan all channels for their properties and log details in a clear format."""
    for guild in bot.guilds:
        header = f"\n=== Scanning Channels in Guild: {guild.name} (ID: {guild.id}) ==="
        logging.info(header)
        print(header)  # Send to terminal
        
        for channel in guild.channels:
            if isinstance(channel, discord.TextChannel):
                nsfw_status = "NSFW" if channel.is_nsfw() else "Safe"
                permissions = channel.permissions_for(guild.me)

                channel_info = (
                    f"Channel: {channel.name} (ID: {channel.id})\n"
                    f" - Type: {channel.type}\n"
                    f" - NSFW: {nsfw_status}\n"
                    f" - Can Send Messages: {'Yes' if permissions.send_messages else 'No'}\n"
                )
                logging.debug(channel_info)
                print(channel_info)  # Send to terminal

            elif isinstance(channel, discord.VoiceChannel):
                voice_channel_info = (
                    f"Channel: {channel.name} (ID: {channel.id})\n"
                    f" - Type: {channel.type} (Voice)\n"
                    f" - Bitrate: {channel.bitrate}\n"
                )
                logging.debug(voice_channel_info)
                print(voice_channel_info)  # Send to terminal

            elif isinstance(channel, discord.CategoryChannel):
                category_info = (
                    f"Category: {channel.name} (ID: {channel.id})\n"
                    f" - Contains {len(channel.channels)} Channels\n"
                )
                logging.debug(category_info)
                print(category_info)  # Send to terminal

        footer = f"=== Completed Scanning Guild: {guild.name} ===\n"
        logging.info(footer)
        print(footer)  # Send to terminal


# Trigger channel scanning after the bot is ready
@bot.event
async def on_ready():
    """Triggered when the bot is fully ready."""
    ready_message = f"Bot is online and connected as {bot.user.name} (ID: {bot.user.id})"
    logging.info(ready_message)
    print(ready_message)  # Send to terminal

    # Call scan_channels
    await scan_channels()

# Asynchronous extension loader
async def load_extensions():
    """Load extensions for the bot."""
    initial_extensions = ['status']  # Add the name of your cog file without the `.py` extension
    for extension in initial_extensions:
        try:
            await bot.load_extension(extension)
            message = f"Loaded extension: {extension}"
            logging.info(message)
            print(message)  # Send to terminal
        except Exception as e:
            error_message = f"Failed to load extension {extension}: {e}"
            logging.error(error_message)
            print(error_message)  # Send to terminal

# Background task for debug logging
async def debug_logger():
    """Log system stats every second for debugging."""
    while True:
        try:
            memory_usage = psutil.virtual_memory().percent
            cpu_usage = psutil.cpu_percent(interval=1)  # 1-second average CPU usage
            system_stats = (
                f"System stats - Memory Usage: {memory_usage}% | CPU Usage: {cpu_usage}%"
            )
            logging.debug(system_stats)
            print(system_stats)  # Send to terminal
        except Exception as e:
            error_message = f"Error while logging system stats: {e}"
            logging.error(error_message)
            print(error_message)  # Send to terminal
        await asyncio.sleep(1)  # Run every second

# Main bot runner
async def main():
    """Main asynchronous entry point for the bot."""
    
    # Check if token is available
    if not discord_token:
        raise ValueError("Discord token is missing in .env file.")  # Raise error if token is missing
    
    async with bot:
        start_message = "Starting bot..."
        logging.info(start_message)
        print(start_message)  # Send to terminal

        await load_extensions()  # Load extensions
        bot.loop.create_task(debug_logger())  # Start debug logger task

        try:
            # Start the bot with the token from the .env file
            await bot.start(discord_token)
        except discord.LoginFailure:
            critical_message = "Invalid token provided. Please check your bot token."
            logging.critical(critical_message)
            print(critical_message)  # Send to terminal
        except discord.HTTPException as e:
            http_error_message = f"HTTP error occurred: {e}"
            logging.critical(http_error_message)
            print(http_error_message)  # Send to terminal
        except ValueError as e:
            # Handle missing token
            logging.error(f"Error: {e}")
            print(f"Error: {e}")
        except Exception as e:
            unexpected_error_message = f"Unexpected error: {e}"
            logging.error(unexpected_error_message)
            print(unexpected_error_message)  # Send to terminal
            await restart_bot()  # Restart the bot on failure

# Entry point for running the bot
if __name__ == "__main__":
    try:
        asyncio.run(main())  # Start the bot asynchronously
    except KeyboardInterrupt:
        print("Bot terminated by user.")
        logger.info("Bot terminated by user.")
    except Exception as e:
        print(f"Critical failure: {e}")
        logger.critical(f"Critical failure: {e}")