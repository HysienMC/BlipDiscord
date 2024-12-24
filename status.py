import discord
from discord.ext import commands, tasks
import logging
import time
import datetime
import psutil  # For system stats like memory, CPU, and disk
import json
import os
import random  # For demo purposes, adding some random elements

# Set up logging for error tracking
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = 1320924547272278118  # Default channel for status updates
        self.status_message = None  # Store the status message
        self.status_message_id = None  # Store message ID for persistence
        self.error_count = 0  # Track the number of errors encountered
        self.current_alert = "No alerts"  # Default alert status
        self.state_file = "status_state.json"  # File for persistent state
        self.start_time = self.load_start_time()  # Load persistent uptime
        self.load_channel_state()  # Load channel and message info
        self.update_status.start()  # Start background task

    def load_start_time(self):
        """Load or initialize the bot's start time from a persistent file."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as file:
                    data = json.load(file)
                    return data.get("start_time", time.time())
            except Exception as e:
                logger.error(f"Failed to load start time: {e}")
        return time.time()

    def save_state(self):
        """Save the bot's state to a file."""
        state = {
            "start_time": self.start_time,
            "channel_id": self.channel_id,
            "status_message_id": self.status_message_id,
        }
        try:
            with open(self.state_file, "w") as file:
                json.dump(state, file)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def load_channel_state(self):
        """Load the channel ID and message ID for updates."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as file:
                    data = json.load(file)
                    self.channel_id = data.get("channel_id", self.channel_id)
                    self.status_message_id = data.get("status_message_id", None)
            except Exception as e:
                logger.error(f"Failed to load channel state: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the bot is ready."""
        logger.info(f"{self.bot.user} is now online.")
        await self.initialize_status_message()

    async def initialize_status_message(self):
        """Ensure the status message is present and reuse it if possible."""
        try:
            channel = self.bot.get_channel(self.channel_id)
            if not channel:
                logger.warning(f"Channel with ID {self.channel_id} not found.")
                return

            if self.status_message_id:
                try:
                    # Try to fetch the existing message
                    self.status_message = await channel.fetch_message(self.status_message_id)
                    logger.info("Reusing existing status message.")
                except discord.NotFound:
                    # If not found, send a new message
                    logger.warning("Previous status message not found. Creating a new one.")
                    self.status_message = await channel.send(embed=self.create_status_embed())
                    self.status_message_id = self.status_message.id
                    self.save_state()
            else:
                # Send a new message if no message ID exists
                self.status_message = await channel.send(embed=self.create_status_embed())
                self.status_message_id = self.status_message.id
                self.save_state()

        except Exception as e:
            logger.error(f"Error initializing status message: {e}")
            self.error_count += 1

    def create_status_embed(self):
        """Create the embed for the status message."""
        uptime = str(datetime.timedelta(seconds=int(time.time() - self.start_time)))
        memory_usage = self.get_memory_usage()
        cpu_usage = self.get_cpu_usage()
        disk_usage = self.get_disk_usage()
        latency = f"{round(self.bot.latency * 1000)} ms"

        # For demo, we'll simulate disk and network activity
        network_speed = f"⬆️ {random.randint(1, 10)} MB / ⬇️ {random.randint(1, 10)} MB"
        cpu_temperature = random.randint(30, 75)  # Simulated CPU temperature for demo

        embed = discord.Embed(
            title=":white_check_mark: **Bot Status**",
            description="**Operational**\nAll services are online and running smoothly!",
            color=discord.Color.green(),
        )
        embed.add_field(name="Uptime", value=uptime, inline=True)
        embed.add_field(name="Memory Usage", value=memory_usage, inline=True)
        embed.add_field(name="CPU Usage", value=cpu_usage, inline=True)
        embed.add_field(name="Disk Usage", value=disk_usage, inline=True)
        embed.add_field(name="Latency", value=latency, inline=True)
        embed.add_field(name="Network Speed", value=network_speed, inline=True)
        embed.add_field(name="CPU Temperature", value=f"{cpu_temperature}°C", inline=True)
        embed.add_field(name="Errors Encountered", value=self.error_count, inline=True)
        embed.add_field(name="Alert Status", value=self.current_alert, inline=True)
        embed.set_footer(text="Powered by Blip Bot")
        embed.timestamp = discord.utils.utcnow()
        return embed

    def get_memory_usage(self):
        """Get the current memory usage."""
        memory = psutil.virtual_memory()
        return f"{round(memory.used / (1024 ** 2), 2)} MB"

    def get_cpu_usage(self):
        """Get the current CPU usage."""
        return f"{psutil.cpu_percent()}%"

    def get_disk_usage(self):
        """Get the current disk usage."""
        disk = psutil.disk_usage('/')
        return f"{disk.percent}%"

    @tasks.loop(seconds=1)
    async def update_status(self):
        """Update the status message every second."""
        if self.status_message:
            try:
                embed = self.create_status_embed()
                await self.status_message.edit(embed=embed)
            except discord.NotFound:
                logger.warning("Status message not found. Reinitializing...")
                self.status_message = None
                await self.initialize_status_message()
            except discord.Forbidden:
                logger.error("Missing permissions to edit the status message.")
                self.update_status.stop()
            except Exception as e:
                logger.error(f"Error updating status message: {e}")
                self.error_count += 1

    @commands.command(name="setalert")
    async def set_alert(self, ctx, *, alert_message: str):
        """Set a custom alert message."""
        self.current_alert = alert_message
        await ctx.send(f"Alert set to: {alert_message}")
        logger.info(f"Alert set to: {alert_message}")

    @commands.command(name="clearalert")
    async def clear_alert(self, ctx):
        """Clear the current alert."""
        self.current_alert = "No alerts"
        await ctx.send("Alerts cleared.")
        logger.info("Alerts cleared.")

    @commands.command(name="setchannel")
    async def set_status_channel(self, ctx, channel: discord.TextChannel):
        """Set the channel for status updates."""
        self.channel_id = channel.id
        self.status_message = None  # Reset the status message
        self.save_state()
        await ctx.send(f"Status updates will now be sent to {channel.mention}.")
        logger.info(f"Status channel set to {channel.id}.")

# Async setup function for loading the cog
async def setup(bot):
    await bot.add_cog(Status(bot))
