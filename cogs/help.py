import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import time
from typing import Dict, Optional, Tuple

COOLDOWN_TIME = 2

class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Security", 
                emoji="🛡️",
                description="Anti-nuke protection and server security",
                value="security"
            ),
            discord.SelectOption(
                label="Automod",
                emoji="🤖",
                description="Automatic moderation system",
                value="automod"
            ),
            discord.SelectOption(
                label="Moderation",
                emoji="⚔️",
                description="Server moderation and management",
                value="moderation"
            ),
            discord.SelectOption(
                label="Voice",
                emoji="🎤",
                description="Voice channel management",
                value="voice"
            ),
            discord.SelectOption(
                label="Utility",
                emoji="🔧",
                description="Utility and information commands",
                value="utility"
            ),
        ]
        super().__init__(placeholder="Select a module to view commands", options=options)

    async def callback(self, interaction: discord.Interaction):
        embed = self.get_embed_for_selection(self.values[0], interaction)
        try:
            await interaction.response.edit_message(embed=embed)
        except discord.NotFound:
            pass
        except discord.errors.InteractionResponded:
            await interaction.followup.edit_message(interaction.message.id, embed=embed)

    def get_embed_for_selection(self, selection: str, interaction: discord.Interaction) -> discord.Embed:
        """Generate embed based on selection"""
        embed_data = {
            "security": self._get_security_embed,
            "automod": self._get_automod_embed,
            "moderation": self._get_moderation_embed,
            "voice": self._get_voice_embed,
            "utility": self._get_utility_embed,
        }
        
        embed_func = embed_data.get(selection)
        return embed_func(interaction) if embed_func else self._get_main_embed(interaction)

    def _get_security_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = discord.Embed(
            title="🛡️ Security Commands",
            description="Anti-nuke protection, verification and server security",
            color=0x2B2D31
        )
        
        # Anti-nuke Protection section
        antinuke_commands = (
            "**antinuke** - Main antinuke command group\n"
            "**extraowner** - Manage extra owners\n"
            "**whitelist** - Manage whitelist users"
        )
        embed.add_field(name="🛡️ Anti-nuke Protection", value=antinuke_commands, inline=False)
        
        # Verification System section
        verification_commands = (
            "**verification** - Setup verification system"
        )
        embed.add_field(name="✅ Verification System", value=verification_commands, inline=False)
        
        # Footer
        embed.set_footer(text="Made by siddharth_xd.", icon_url=interaction.user.display_avatar.url)
        
        if interaction.client.user:
            embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
        
        return embed

    def _get_automod_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = discord.Embed(
            title="🤖 AutoMod Commands",
            description="Automatic moderation and content filtering",
            color=0x2B2D31
        )
        
        # AutoMod Settings section
        automod_commands = (
            "**antilink** - Manage anti-link settings\n"
            "**antispam** - Manage anti-spam settings\n"
            "**automod** - Main automod dashboard showing all settings and features\n"
            "**automodbypasschannel** - Manage automod bypass channels\n"
            "**automodbypassuser** - Manage automod bypass users"
        )
        embed.add_field(name="🤖 AutoMod Settings", value=automod_commands, inline=False)
        
        # Footer
        embed.set_footer(text="Made by siddharth_xd.", icon_url=interaction.user.display_avatar.url)
        
        if interaction.client.user:
            embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
        
        return embed

    def _get_moderation_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = discord.Embed(
            title="⚔️ Moderation Commands",
            description="Server moderation, logging and ignore settings",
            color=0x2B2D31
        )
        
        # Moderation Tools section
        mod_commands = (
            "**afk** - Set yourself as AFK with a reason\n"
            "**ban** - Ban a user\n"
            "**hide** - Hide a specific channel\n"
            "**kick** - Kick a specific user\n"
            "**lock** - Lock a specific channel\n"
            "**mute** - Mute a specific user\n"
            "**nickname** - Change or reset a member's nickname\n"
            "**purge** - Purge a specified number of messages, optionally from...\n"
            "**purge_bots** - Purges messages from bots in the channel\n"
            "**role** - Assign or remove a role from a member\n"
            "**snipe** - Show the most recently deleted message in the channel\n"
            "**unban** - Unban a user\n"
            "**unhide** - Unhide a specific channel\n"
            "**unlock** - Unlock a specific channel\n"
            "**unmute** - Unmute a specific user"
        )
        embed.add_field(name="⚔️ Moderation Tools", value=mod_commands, inline=False)
        
        # Ignore Settings section
        ignore_commands = (
            "**ignore** - Main ignore command"
        )
        embed.add_field(name="🚫 Ignore Settings", value=ignore_commands, inline=False)
        
        # Activity Logging section
        logging_commands = (
            "**logging** - Main logging command group"
        )
        embed.add_field(name="📝 Activity Logging", value=logging_commands, inline=False)
        
        # Footer
        embed.set_footer(text="Made by siddharth_xd.", icon_url=interaction.user.display_avatar.url)
        
        if interaction.client.user:
            embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
        
        return embed

    def _get_voice_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = discord.Embed(
            title="🎤 Voice Commands",
            description="Voice channel management and moderation",
            color=0x2B2D31
        )
        
        # Voice Management section
        voice_commands = (
            "**drag** - Drag users to another voice channel\n"
            "**moveall** - Move all users from one voice channel to another\n"
            "**vcban** - Ban user from voice channels\n"
            "**vckick** - Kick user from voice channel\n"
            "**vcmute** - Mute user in voice channel\n"
            "**vcmuteall** - Mute all users in voice channel\n"
            "**vcrole** - Manage voice channel roles\n"
            "**vcunban** - Unban user from voice channels\n"
            "**vcunmute** - Unmute user in voice channel\n"
            "**vcunmuteall** - Unmute all users in voice channel\n"
            "**votemute** - Vote to mute a user\n"
            "**voteunmute** - Vote to unmute a user"
        )
        embed.add_field(name="🎤 Voice Management", value=voice_commands, inline=False)
        
        # Footer
        embed.set_footer(text="Made by siddharth_xd.", icon_url=interaction.user.display_avatar.url)
        
        if interaction.client.user:
            embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
        
        return embed

    def _get_utility_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = discord.Embed(
            title="🔧 Utility Commands",
            description="General utility and information commands",
            color=0x2B2D31
        )
        
        # Utility & Info Tools section
        utility_commands = (
            "**avatar** - Display user avatar\n"
            "**banner** - Display user banner\n"
            "**membercount** - Show server member count\n"
            "**ping** - Check bot latency\n"
            "**serverinfo** - Display comprehensive server information\n"
            "**stats** - Display bot statistics\n"
            "**uptime** - Show bot uptime"
        )
        embed.add_field(name="🔧 Utility & Info Tools", value=utility_commands, inline=False)
        
        # Footer
        embed.set_footer(text="Made by siddharth_xd.", icon_url=interaction.user.display_avatar.url)
        
        if interaction.client.user:
            embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
        
        return embed

    def _get_main_embed(self, interaction: discord.Interaction) -> discord.Embed:
        """Main help menu embed"""
        embed = discord.Embed(
            title="Flingo Help Menu",
            description="Hello ! I'm Flingo, Your Bot For Server Security With Powerful Antinuke Features.\n\n"
                       "**Prefix For This Server &**\n**Total Commands 322**",
            color=0x2B2D31
        )
        
        modules = (
            "🛡️ **Security**\n"
            "🤖 **Automod**\n"
            "⚔️ **Moderation**\n"
            "🎤 **Voice**\n"
            "🔧 **Utility**"
        )
        
        embed.add_field(name="📁 Main Modules", value=modules, inline=False)
        embed.add_field(name="**Links**", value="[Invite](https://discord.com/invite/Flingo) | [Support](https://discord.gg/support)", inline=False)
        
        if interaction.client.user:
            embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
        
        return embed


class HelpView(discord.ui.View):
    def __init__(self, bot_id: str = None, *, timeout=180):
        super().__init__(timeout=timeout)
        self.help_select = HelpSelect()
        self.add_item(self.help_select)
        self.message = None
        
        # Add invite button if bot_id is provided
        if bot_id:
            invite_url = f"https://discord.com/api/oauth2/authorize?client_id={bot_id}&permissions=8&scope=bot%20applications.commands"
            invite_button = discord.ui.Button(
                label="Invite Me",
                style=discord.ButtonStyle.link,
                emoji="📨",
                url=invite_url,
                row=1
            )
            self.add_item(invite_button)

    @discord.ui.button(label="Main Menu", style=discord.ButtonStyle.primary, emoji="📁", row=1)
    async def main_menu_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to main help menu"""
        embed = self.help_select._get_main_embed(interaction)
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="❌", row=1)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete the help menu"""
        try:
            await interaction.response.defer()
            await interaction.delete_original_response()
        except (discord.NotFound, discord.Forbidden):
            pass

    async def on_timeout(self):
        try:
            for item in self.children:
                item.disabled = True
            if self.message:
                await self.message.edit(view=self)
        except (discord.NotFound, discord.Forbidden):
            pass


class CooldownManager:
    """Manages command cooldowns more efficiently"""
    
    def __init__(self):
        self.cooldowns: Dict[int, Dict[str, float]] = {}
        self.warning_messages: Dict[int, Dict[str, discord.Message]] = {}

    def is_on_cooldown(self, user_id: int, command_name: str) -> Optional[int]:
        """Check if user is on cooldown, return remaining time if so"""
        if user_id not in self.cooldowns or command_name not in self.cooldowns[user_id]:
            return None
        
        end_time = self.cooldowns[user_id][command_name]
        remaining = int(end_time - time.time())
        
        if remaining <= 0:
            del self.cooldowns[user_id][command_name]
            if not self.cooldowns[user_id]:
                del self.cooldowns[user_id]
            return None
        
        return remaining

    def set_cooldown(self, user_id: int, command_name: str, duration: int):
        """Set cooldown for user and command"""
        if user_id not in self.cooldowns:
            self.cooldowns[user_id] = {}
        self.cooldowns[user_id][command_name] = time.time() + duration

    async def set_warning_message(self, user_id: int, command_name: str, message: discord.Message):
        """Store warning message for cleanup"""
        if user_id not in self.warning_messages:
            self.warning_messages[user_id] = {}
        self.warning_messages[user_id][command_name] = message

        asyncio.create_task(self._cleanup_warning(user_id, command_name, COOLDOWN_TIME))

    async def _cleanup_warning(self, user_id: int, command_name: str, delay: int):
        """Clean up warning message after delay"""
        await asyncio.sleep(delay)
        try:
            if (user_id in self.warning_messages and 
                command_name in self.warning_messages[user_id]):
                message = self.warning_messages[user_id][command_name]
                await message.delete()
                del self.warning_messages[user_id][command_name]
                if not self.warning_messages[user_id]:
                    del self.warning_messages[user_id]
        except (KeyError, discord.NotFound, discord.Forbidden):
            pass


class Help(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.cooldown_manager = CooldownManager()

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"✅ Help module loaded - {self.__class__.__name__}")

    async def create_help_embed_and_view(self, user: discord.User) -> Tuple[discord.Embed, HelpView]:
        """Create the main help embed and view"""
        bot_id = str(self.client.user.id) if self.client.user else None
        view = HelpView(bot_id=bot_id)
        
        embed = discord.Embed(
            title="Flingo Help Menu",
            description="Hello ! I'm Flingo, Your Bot For Server Security With Powerful Antinuke Features.\n\n"
                       "**Prefix For This Server &**\n**Total Commands 322**",
            color=0x2B2D31
        )
        
        modules = (
            "🛡️ **Security**\n"
            "🤖 **Automod**\n"
            "⚔️ **Moderation**\n"
            "🎤 **Voice**\n"
            "🔧 **Utility**"
        )
        
        embed.add_field(name="📁 Main Modules", value=modules, inline=False)
        embed.add_field(name="**Links**", value="[Invite](https://discord.com/invite/Flingo) | [Support](https://discord.gg/support)", inline=False)
        
        if self.client.user:
            embed.set_thumbnail(url=self.client.user.display_avatar.url)
        
        return embed, view

    @commands.command(name="help", aliases=["h", "commands"])
    async def help_command(self, ctx):
        """Display the help menu"""
        remaining = self.cooldown_manager.is_on_cooldown(ctx.author.id, 'help')
        if remaining:
            embed = discord.Embed(
                title="⏰ Cooldown Active",
                description=f"Please wait **{remaining}** seconds before using this command again.",
                color=0x2B2D31
            )
            msg = await ctx.reply(embed=embed, delete_after=remaining)
            await self.cooldown_manager.set_warning_message(ctx.author.id, 'help', msg)
            return

        embed, view = await self.create_help_embed_and_view(ctx.author)
        message = await ctx.reply(embed=embed, view=view)
        view.message = message

        self.cooldown_manager.set_cooldown(ctx.author.id, 'help', COOLDOWN_TIME)

    @app_commands.command(name="help", description="Display the help menu with bot commands and information")
    async def help_slash(self, interaction: discord.Interaction):
        """Slash command version of help"""
        remaining = self.cooldown_manager.is_on_cooldown(interaction.user.id, 'help')
        if remaining:
            embed = discord.Embed(
                title="⏰ Cooldown Active",
                description=f"Please wait **{remaining}** seconds before using this command again.",
                color=0x2B2D31
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed, view = await self.create_help_embed_and_view(interaction.user)
        await interaction.response.send_message(embed=embed, view=view)

        try:
            message = await interaction.original_response()
            view.message = message
        except discord.NotFound:
            pass

        self.cooldown_manager.set_cooldown(interaction.user.id, 'help', COOLDOWN_TIME)

async def setup(bot):
    await bot.add_cog(Help(bot))