import discord
import typing
from discord.ext import commands
from settings.config import color
from discord.ui import Button, View
from typing import Optional, Union
import datetime
import requests
from flingo import token
import random
from quickchart import QuickChart
import time

async def generate_chart(ws_latency, msg_latency):
    qc = QuickChart()

    def gen(wsl, msg):
        rnd_wsl = random.uniform(-0.05, 0.05)
        rnd_msg = random.uniform(-0.02, 0.02)
        wsl = int(wsl + wsl * rnd_wsl)
        msg = int(msg + msg * rnd_msg)
        return [wsl, msg]

    data = []
    for _ in range(17):
        data.append(gen(ws_latency, msg_latency))
    data.append([ws_latency, msg_latency])

    qc.config = {
        "type": "line",
        "data": {
            "labels": ["_" for _ in range(18)],
            "datasets": [
                {
                    "label": "WebSocket Latency",
                    "yAxisID": "ws",
                    "data": [item[0] for item in data],
                    "fill": "start",
                    "borderColor": "#ff5500",
                    "borderWidth": 2,
                    "backgroundColor": "rgba(255, 85, 0, 0.5)",
                    "pointRadius": 5,
                    "pointBackgroundColor": "#ff5500",
                },
                {
                    "label": "Message Latency",
                    "yAxisID": "msg",
                    "data": [item[1] for item in data],
                    "fill": "start",
                    "borderColor": "#00d8ff",
                    "borderWidth": 2,
                    "backgroundColor": "rgba(0, 216, 255, 0.5)",
                    "pointRadius": 5,
                    "pointBackgroundColor": "#00d8ff",
                },
            ],
        },
        "options": {
            "scales": {
                "yAxes": [
                    {
                        "id": "msg",
                        "type": "linear",
                        "position": "right",
                        "ticks": {
                            "suggestedMin": 0,
                            "suggestedMax": min(max(msg_latency + 50, 100), 100),
                            "stepSize": 50,
                        },
                    },
                    {
                        "id": "ws",
                        "type": "linear",
                        "position": "left",
                        "ticks": {
                            "suggestedMin": 0,
                            "suggestedMax": min(max(ws_latency + 50, 100), 100),
                            "stepSize": 50,
                        },
                    },
                ]
            },
            "title": {"display": True, "text": "Latency Comparison", "fontSize": 16},
            "legend": {"display": True, "position": "top"},
            "elements": {"line": {"tension": 0.4}},
        },
    }

    qc.width = 600
    qc.height = 300
    qc.background_color = "transparent"

    uri = qc.get_url()
    return uri

class ServerInfoView(discord.ui.View):
    def __init__(self, guild, requested_by):
        super().__init__(timeout=300)
        self.guild = guild
        self.requested_by = requested_by
        self.current_page = "general"

    @discord.ui.button(label="General Info", style=discord.ButtonStyle.success, emoji="<:system:1384849012993032273>")
    async def general_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.requested_by:
            await interaction.response.send_message("You can't interact with this!", ephemeral=True)
            return
        
        self.current_page = "general"
        embed = await self.create_general_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Additional Info", style=discord.ButtonStyle.primary, emoji="<:Notepad:1384842987330211850>")
    async def additional_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.requested_by:
            await interaction.response.send_message("You can't interact with this!", ephemeral=True)
            return
        
        self.current_page = "additional"
        embed = await self.create_additional_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Extra Info", style=discord.ButtonStyle.secondary, emoji="<:logging:1381504143272968235>")
    async def extra_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.requested_by:
            await interaction.response.send_message("You can't interact with this!", ephemeral=True)
            return
        
        self.current_page = "extra"
        embed = await self.create_extra_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def create_general_embed(self):
        guild = self.guild
        features = []
        feature_map = {
            'ANIMATED_BANNER': 'Animated Banner',
            'ANIMATED_ICON': 'Animated Icon',
            'AUTO_MODERATION': 'Auto Moderation',
            'BANNER': 'Banner',
            'COMMUNITY': 'Community',
            'DISCOVERABLE': 'Discoverable',
            'FEATURABLE': 'Featurable',
            'INVITES_DISABLED': 'Invites Disabled',
            'INVITE_SPLASH': 'Invite Splash',
            'MEMBER_VERIFICATION_GATE_ENABLED': 'Member Verification Gate',
            'MONETIZATION_ENABLED': 'Monetization Enabled',
            'MORE_STICKERS': 'More Stickers',
            'NEWS': 'News',
            'PARTNERED': 'Partnered',
            'PREVIEW_ENABLED': 'Preview Enabled',
            'PRIVATE_THREADS': 'Private Threads',
            'ROLE_ICONS': 'Role Icons',
            'SEVEN_DAY_THREAD_ARCHIVE': 'Seven Day Thread Archive',
            'THREE_DAY_THREAD_ARCHIVE': 'Three Day Thread Archive',
            'TICKETED_EVENTS_ENABLED': 'Ticketed Events',
            'VANITY_URL': 'Vanity URL',
            'VERIFIED': 'Verified',
            'VIP_REGIONS': 'VIP Regions',
            'WELCOME_SCREEN_ENABLED': 'Welcome Screen'
        }
        
        for feature in guild.features:
            if feature in feature_map:
                features.append(feature_map[feature])
        
        embed = discord.Embed(color=0x010505)
        embed.set_author(name=f"General Information - {guild.name}", icon_url=guild.icon.url if guild.icon else None)

        guild_info_lines = [
            f"<@{guild.owner_id}>",
            f"Owner ID: `{guild.owner_id}`",
            f"Created At: <t:{int(guild.created_at.timestamp())}:R>",
            f"Region: `{getattr(guild, 'preferred_locale', 'Unknown')}`",
            f"Member Count: `{guild.member_count}`",
            f"Upload Limit: `{guild.filesize_limit // (1024*1024)} MB`"
        ]
        
        embed.add_field(
            name="<:Notepad:1384842987330211850> Guild Owner",
            value="\n".join(guild_info_lines),
            inline=False
        )
        
        if hasattr(guild, 'vanity_url_code') and guild.vanity_url_code:
            embed.add_field(
                name="<:MekoLink:1384853638786187335> Vanity URL",
                value=f"Vanity Code: `{guild.vanity_url_code}`",
                inline=False
            )
        if hasattr(guild, 'description') and guild.description:
            embed.add_field(
                name="<:Notepad:1384842987330211850> Guild Description",
                value=guild.description,
                inline=False
            )
        if features:
            features_text = "\n".join([f"• {feature}" for feature in features[:15]])
            if len(features) > 15:
                features_text += f"\nAnd {len(features) - 15} More..."
            
            embed.add_field(
                name="<a:star_flingo:1385161895299911691> Guild Features",
                value=features_text,
                inline=False
            )
        system_info = []
        system_info.append(f"Verification Level: `{guild.verification_level.name}`")
        system_info.append(f"Explicit Content Filter: `{guild.explicit_content_filter.name}`")
        system_info.append(f"MFA Level: `{guild.mfa_level.name}`")
        
        if hasattr(guild, 'afk_channel') and guild.afk_channel:
            system_info.append(f"AFK Channel: {guild.afk_channel.mention}")
            system_info.append(f"AFK Timeout: `{guild.afk_timeout // 60} minutes`")
        else:
            system_info.append("AFK Channel: `None`")
        
        if hasattr(guild, 'system_channel') and guild.system_channel:
            system_info.append(f"System Channel: {guild.system_channel.mention}")
        
        system_info.append(f"Default Notification: `{guild.default_notifications.name}`")
        system_info.append(f"NSFW Level: `{guild.nsfw_level.name}`")

        if hasattr(guild, 'discovery_splash') and guild.discovery_splash:
            system_info.append(f"Discovery Splash: [View Splash]({guild.discovery_splash.url})")
        else:
            system_info.append("Discovery Splash: `None`")
        if hasattr(guild, 'scheduled_events'):
            system_info.append(f"Scheduled Events: `{len(guild.scheduled_events)}`")
        else:
            system_info.append("Scheduled Events: `0`")
        
        embed.add_field(
            name="<:system:1384849012993032273> System Information",
            value="\n".join(system_info),
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {self.requested_by.display_name}", icon_url=self.requested_by.display_avatar.url)
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        return embed

    async def create_additional_embed(self):
        guild = self.guild
        
        embed = discord.Embed(color=0x010505)
        embed.set_author(name=f"Additional Information - {guild.name}", icon_url=guild.icon.url if guild.icon else None)

        embed.add_field(
            name="<:MekoSearch:1384854124675338252> Advanced Information",
            value=f"Member Count: `{guild.member_count}`\nCreation Date: `{guild.created_at.strftime('%Y-%m-%d %H:%M:%S')}`",
            inline=False
        )

        role_count = len(guild.roles)
        integrated_roles = sum(1 for role in guild.roles if role.managed)
        bot_roles = sum(1 for role in guild.roles if role.tags and hasattr(role.tags, 'bot_id') and role.tags.bot_id)
        highest_role = max(guild.roles, key=lambda r: r.position) if guild.roles else None

        bottom_roles = sorted([role for role in guild.roles if role != guild.default_role], key=lambda r: r.position)[:5]
        bottom_roles_text = " > ".join([role.mention for role in bottom_roles]) if bottom_roles else "None"
        
        role_info = []
        role_info.append(f"Role Count: `{role_count}`")
        role_info.append(f"Integrated Roles: `{integrated_roles}`")
        role_info.append(f"Bot Roles: `{bot_roles}`")
        if highest_role:
            role_info.append(f"Highest Role: {highest_role.mention}")
        role_info.append(f"Bottom Five: {bottom_roles_text}")
        
        embed.add_field(
            name="<:Meko_Role:1384854321740513282> Role Information",
            value="\n".join(role_info),
            inline=False
        )
        roles_list = []
        sorted_roles = sorted([role for role in guild.roles if role != guild.default_role], 
                            key=lambda r: r.position, reverse=True)
        
        for i, role in enumerate(sorted_roles[:20], 1):
            roles_list.append(f"{i}. {role.mention}")
        
        if roles_list:
            roles_text = "\n".join(roles_list[:15])
            if len(sorted_roles) > 15:
                roles_text += f"\n... and {len(sorted_roles) - 15} more roles"
            
            embed.add_field(
                name="<:Notepad:1384842987330211850> List of Roles",
                value=roles_text,
                inline=False
            )
        
        embed.set_footer(text=f"Requested by {self.requested_by.display_name}", icon_url=self.requested_by.display_avatar.url)
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        return embed

    async def create_extra_embed(self):
        guild = self.guild
        
        embed = discord.Embed(color=0x010505)
        embed.set_author(name=f"Extra Information - {guild.name}", icon_url=guild.icon.url if guild.icon else None)

        text_channels = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
        voice_channels = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
        stage_channels = len([c for c in guild.channels if isinstance(c, discord.StageChannel)])
        threads = len(guild.threads) if hasattr(guild, 'threads') else 0
        categories = len(guild.categories)
        
        channel_info = []
        channel_info.append(f"Text Channels: `{text_channels}`")
        channel_info.append(f"Voice Channels: `{voice_channels}`")
        channel_info.append(f"Stage: `{stage_channels}`")
        channel_info.append(f"Threads: `{threads}`")
        channel_info.append(f"Categories: `{categories}`")
        
        embed.add_field(
            name="<:File:1381565175320023155> Channel Information",
            value="\n".join(channel_info),
            inline=False
        )

        total_emojis = len(guild.emojis)
        animated_emojis = len([e for e in guild.emojis if e.animated])
        static_emojis = len([e for e in guild.emojis if not e.animated])
        total_stickers = len(guild.stickers) if hasattr(guild, 'stickers') else 0
        
        emoji_info = []
        emoji_info.append(f"Total Stickers: `{total_stickers}`")
        emoji_info.append(f"Animated Emoji: `{animated_emojis}`")
        emoji_info.append(f"Static Emoji: `{static_emojis}`")
        emoji_info.append(f"Total Emojis: `{total_emojis}`")
        
        embed.add_field(
            name="<:lvb_Emoji:1384936804741812275> Emoji Information",
            value="\n".join(emoji_info),
            inline=False
        )

        boost_level = guild.premium_tier
        total_boosts = guild.premium_subscription_count or 0

        booster_role = None
        for role in guild.roles:
            if hasattr(role, 'tags') and role.tags and hasattr(role.tags, 'premium_subscriber') and role.tags.premium_subscriber:
                booster_role = role
                break
        
        boost_info = []
        boost_info.append(f"Boost Level: `{boost_level}`")
        boost_info.append(f"Total Boosts: `{total_boosts}`")
        if booster_role:
            boost_info.append(f"Booster Role: {booster_role.mention}")
        else:
            boost_info.append("Booster Role: `None`")
        boost_info.append("Boost Progress Bar: `Yes`" if total_boosts > 0 else "Boost Progress Bar: `No`")
        
        embed.add_field(
            name="<:dnx_boosters:1384937277800710164> Boost Details",
            value="\n".join(boost_info),
            inline=False
        )

        embed.add_field(
            name="<:Notepad:1384842987330211850> Note",
            value="Recent booster tracking would require\nseparate event handling implementation\nto store boost history data.",
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {self.requested_by.display_name}", icon_url=self.requested_by.display_avatar.url)
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        return embed

class Utility(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.sniped = {}
        self.start_time = time.time()

    @commands.hybrid_command(aliases=['av'], description="Shows user's avatar")
    async def avatar(self, ctx, user: discord.User = None):
        if user is None:
            user = ctx.author
        if user.avatar is not None:
            embed = discord.Embed(color=color)
            embed.set_footer(text=f"Requested By {ctx.author}", icon_url=ctx.author.display_avatar.url)
            embed.set_image(url=user.avatar.url)
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            embed.set_author(name=user, icon_url=user.avatar.url)
            button = discord.ui.Button(label="Download", url=user.avatar.url)
            view = discord.ui.View().add_item(button)
            await ctx.send(embed=embed, view=view)
        else:
            await ctx.send(f"This user doesn't have any avatar.")

    @commands.hybrid_command(aliases=['mc', 'members'], description="Shows member count in the server.")
    async def membercount(self, ctx):
        embed = discord.Embed(title="Member Count", description=f"{ctx.guild.member_count} Members", color=color)
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.set_footer(text=f"{ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(aliases=['si', 'server', 'guildinfo'], description="Shows detailed server information with interactive tabs")
    async def serverinfo(self, ctx):
        """
        Display comprehensive server information.
        
        Shows detailed information about the current server including:
        - General server details (owner, creation date, member count, etc.)
        - Channel and role statistics
        - Server features and boost information
        - Interactive navigation between different information tabs
        
        Usage:
        - `/serverinfo`: Shows server information with interactive buttons
        """
        if not ctx.guild:
            await ctx.send("This command can only be used in a server!")
            return
        
        view = ServerInfoView(ctx.guild, ctx.author)
        embed = await view.create_general_embed()
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_group(invoke_without_command=True, description="Banner command for user and server.")
    async def banner(self, ctx):
        await ctx.send_help(ctx.command)

    @banner.command(description="Shows banner of a user.")
    async def user(self, ctx, user: discord.Member = None):
        if user is None:
            user = ctx.author
        try:
            user_info = await self.client.fetch_user(user.id)
            if user_info.banner is None:
                await ctx.send(f"This user doesn't have any banner.")
                return
            embed = discord.Embed(color=color)
            embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            embed.set_image(url=user_info.banner.url)
            button = discord.ui.Button(label="Download", url=user_info.banner.url)
            view = discord.ui.View(timeout=None).add_item(button)
            await ctx.send(embed=embed, view=view)
        except discord.HTTPException:
            await ctx.send("Could not fetch user information.")

    @banner.command(description="Shows banner of the server")
    async def server(self, ctx):
        if ctx.guild.banner is None:
            await ctx.send(f"This server doesn't have any banner.")
            return
        embed = discord.Embed(color=color)
        embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.set_image(url=ctx.guild.banner.url)
        button = discord.ui.Button(label="Download", url=ctx.guild.banner.url)
        view = discord.ui.View(timeout=None).add_item(button)
        await ctx.send(embed=embed, view=view) 

async def setup(client):
    await client.add_cog(Utility(client))