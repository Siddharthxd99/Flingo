import logging
import discord
from discord.ext import commands
import asyncio
import re
from discord_webhook import DiscordWebhook

class RateLimitHandler(logging.Handler):
    def __init__(self, webhook_url, bot):
        super().__init__()
        self.webhook_url = webhook_url
        self.bot = bot
        self.recent_actions = {}
        
    def send_message(self, message):
        try:
            webhook = DiscordWebhook(url=self.webhook_url, content=message)
            response = webhook.execute()
            if response.status_code != 200:
                print(f"Failed to send webhook. Status code: {response.status_code}")
        except Exception as e:
            print(f"Failed to send message to Discord webhook: {e}")

    def get_server_info(self, channel_id):
        try:
            channel = self.bot.get_channel(int(channel_id))
            if channel:
                return channel.guild.name, channel.guild.id, channel.name
        except:
            pass
        return None, None, None

    def analyze_bot_actions(self, message, endpoint):
        """
        Analyzes the specific bot action that caused the rate limit
        """
        action = "Unknown Action"
        details = ""

        if '/messages' in endpoint:
            if 'DELETE' in message:
                action = "Bot Command Cleanup"
                details = "Bot is deleting command messages or responses too quickly"
            elif 'POST' in message:
                action = "Command Execution"
                details = "Commands are being triggered too rapidly in this channel"
            elif 'PATCH' in message:
                action = "Response Edit"
                details = "Bot is editing its responses too quickly"

        elif '/channels' in endpoint:
            if 'POST' in message:
                action = "Channel Creation"
                details = "Bot is creating new channels too rapidly"
            elif 'DELETE' in message:
                action = "Channel Deletion"
                details = "Bot is deleting channels too quickly"
            elif 'PATCH' in message:
                action = "Channel Modification"
                details = "Bot is modifying channel settings too frequently"

        elif '/members' in endpoint:
            if 'roles' in endpoint.lower():
                action = "Role Management"
                details = "Bot is modifying member roles too quickly"
            elif 'PATCH' in message:
                action = "Member Modification"
                details = "Bot is updating member properties too rapidly"

        elif 'bulk' in endpoint.lower():
            action = "Bulk Operation"
            details = "Bot is performing bulk message operations too quickly"

        elif '/reactions' in endpoint:
            action = "Reaction Management"
            details = "Bot is adding/removing reactions too quickly"

        return action, details

    def emit(self, record):
        try:
            message = record.getMessage()
            
            url_match = re.search(r'https://discord\.com/api/v\d+/([^\s]+)', message)
            endpoint = url_match.group(1) if url_match else "unknown"
            channel_id_match = re.search(r'/channels/(\d+)', message)
            channel_id = channel_id_match.group(1) if channel_id_match else None
            
            rate_limit_match = re.search(r'rate[ -]?limit.*?(\d+\.\d+) seconds', message, re.IGNORECASE)
            
            if rate_limit_match:
                retry_after = rate_limit_match.group(1)
                
                server_name, server_id, channel_name = self.get_server_info(channel_id) if channel_id else (None, None, None)
                
                is_global = 'global' in message.lower() and 'true' in message.lower()
                
                action, details = self.analyze_bot_actions(message, endpoint)
                
                warning_message = (
                    "```py\n"
                    f"<:ByteStrik_Warning:1384843852577247254> Rate Limit Hit!\n\n"
                    f"Bot Action: {action}\n"
                    f"Details: {details}\n"
                    f"Rate Limit Type: {'Global' if is_global else 'Per-Server'}\n"
                    "\n"
                    f"Server: {server_name if server_name else 'Unknown'}\n"
                    f"Server ID: {server_id if server_id else 'Unknown'}\n"
                    f"Channel: {channel_name if channel_name else 'Unknown'}\n"
                    f"Channel ID: {channel_id if channel_id else 'Unknown'}\n"
                    "\n"
                    f"Retry After: {retry_after} seconds\n"
                    f"Endpoint: {endpoint}\n"
                    "```"
                )
                
                self.send_message(warning_message)
                
        except Exception as e:
            print(f"Error in rate limit handler: {str(e)}")
            import traceback
            print(traceback.format_exc())

class RateLimitCog(commands.Cog):
    def __init__(self, bot, webhook_url):
        self.bot = bot
        self.webhook_url = webhook_url
        
        self.logger = logging.getLogger('discord.http')
        self.logger.setLevel(logging.WARNING)
        self.logger.handlers = []
        handler = RateLimitHandler(webhook_url, bot)
        handler.setLevel(logging.WARNING)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    @commands.Cog.listener()
    async def on_ready(self):
        print("Rate limit monitoring is active with bot action detection")

async def setup(bot):
    webhook_url = ""
    await bot.add_cog(RateLimitCog(bot, webhook_url))