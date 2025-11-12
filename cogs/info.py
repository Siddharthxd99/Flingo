import discord
from discord.ext import commands
import datetime
import asyncio
import psutil
import platform

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.COOLDOWN_TIME = 2
        self.cooldowns = {}
        self.warning_messages = {}
        if not hasattr(self.bot, 'start_time') or self.bot.start_time is None:
            self.bot.start_time = datetime.datetime.utcnow()

    async def handle_cooldown(self, ctx, command_name):
        user_id = ctx.author.id
        current_time = datetime.datetime.utcnow()
        
        if user_id not in self.cooldowns:
            self.cooldowns[user_id] = {}
            
        if command_name in self.cooldowns[user_id]:
            cooldown_end_time = self.cooldowns[user_id][command_name]
            remaining_time = (cooldown_end_time - current_time).total_seconds()
            
            if remaining_time > 0:
                if user_id not in self.warning_messages:
                    self.warning_messages[user_id] = {}
                    
                if command_name not in self.warning_messages[user_id]:
                    warning_msg = await ctx.send(f"You are on cooldown for `{command_name}` command. Please wait {int(remaining_time)} seconds.")
                    self.warning_messages[user_id][command_name] = warning_msg
                return True
        return False

    def set_cooldown(self, user_id, command_name):
        current_time = datetime.datetime.utcnow()
        cooldown_end_time = current_time + datetime.timedelta(seconds=self.COOLDOWN_TIME)
        
        if user_id not in self.cooldowns:
            self.cooldowns[user_id] = {}
            
        self.cooldowns[user_id][command_name] = cooldown_end_time
        asyncio.create_task(self.clear_cooldown(user_id, command_name))

    async def clear_cooldown(self, user_id, command_name):
        await asyncio.sleep(self.COOLDOWN_TIME)
        
        if user_id in self.cooldowns and command_name in self.cooldowns[user_id]:
            del self.cooldowns[user_id][command_name]
            if not self.cooldowns[user_id]:
                del self.cooldowns[user_id]
                
        if user_id in self.warning_messages and command_name in self.warning_messages[user_id]:
            try:
                await self.warning_messages[user_id][command_name].delete()
            except (discord.errors.NotFound, discord.errors.Forbidden):
                pass
            
            del self.warning_messages[user_id][command_name]
            if not self.warning_messages[user_id]:
                del self.warning_messages[user_id]

    @commands.command()
    async def ping(self, ctx):
        if await self.handle_cooldown(ctx, 'ping'):
            return

        latency_ms = round(self.bot.latency * 1000)
        
        embed = discord.Embed(
            title="**!Pong**",
            description=f"<:Cute_Cute_Cute:1381515657153347605> Currently experiencing a latency of **{latency_ms}ms**",
            color=discord.Color(0x010505))
        embed.set_footer(text='Powered by Flingo', icon_url=self.bot.user.display_avatar.url)
        await ctx.send(embed=embed)
        self.set_cooldown(ctx.author.id, 'ping')
    
    @commands.command()
    async def uptime(self, ctx):
        if await self.handle_cooldown(ctx, 'uptime'):
            return

        if not hasattr(self.bot, 'start_time') or self.bot.start_time is None:
            embed = discord.Embed(
                title="Uptime",
                description="Bot hasn't started yet.",
                color=discord.Color(0x010505))
            embed.set_footer(text='Powered by Flingo', icon_url=self.bot.user.display_avatar.url)
            await ctx.send(embed=embed)
            return

        delta_uptime = datetime.datetime.utcnow() - self.bot.start_time
        days = delta_uptime.days
        hours, remainder = divmod(int(delta_uptime.seconds), 3600)
        minutes, seconds = divmod(remainder, 60)

        uptime_str = f"{days} days, {hours} hours, {minutes} minutes, {seconds} seconds"

        embed = discord.Embed(
            title="Uptime",
            description=uptime_str,
            color=discord.Color(0x010505))
        embed.set_footer(text='Powered by Flingo', icon_url=self.bot.user.display_avatar.url)
        await ctx.send(embed=embed)
        self.set_cooldown(ctx.author.id, 'uptime')

    @commands.command()
    async def stats(self, ctx):
        if await self.handle_cooldown(ctx, 'stats'):
            return
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)
        if hasattr(self.bot, 'start_time') and self.bot.start_time:
            delta_uptime = datetime.datetime.utcnow() - self.bot.start_time
            uptime_str = f"{delta_uptime.days} days ago"
        else:
            uptime_str = "Unknown"
        total_guilds = len(self.bot.guilds)
        total_users = len(set(self.bot.get_all_members()))
        total_channels = len(list(self.bot.get_all_channels()))
        commands_executed = getattr(self.bot, 'commands_executed', 0)

        embed = discord.Embed(color=0x010505)
        embed.set_author(name=f"{self.bot.user.name}'s Information", icon_url=self.bot.user.display_avatar.url)
        embed.add_field(name="**General Informations**", value=f"**Bot's Mention:** {self.bot.user.mention}\n**Bot's Tag:** {self.bot.user.name}#{self.bot.user.discriminator}\n**Cluster:** 0\n**Shard:** 0\n**Bot's Version:** 6.9.0\n**Total Servers:** {total_guilds}\n**Total Users:** {total_users:,} ({len([m for m in self.bot.get_all_members() if m.status != discord.Status.offline]):,} Cached)\n**Total Channels:** {total_channels}\n**Last Rebooted:** {uptime_str}\n**Commands Executed:** {commands_executed}", inline=False)
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f'Requested By {ctx.author.name}', icon_url=ctx.author.display_avatar.url)
        view = StatsView()
        
        await ctx.send(embed=embed, view=view)
        self.set_cooldown(ctx.author.id, 'stats')

class StatsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label='Dev', style=discord.ButtonStyle.secondary)
    async def dev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(color=0x010505)
        embed.set_author(name=f"{interaction.client.user.name}'s Information", icon_url=interaction.client.user.display_avatar.url)
        embed.add_field(name="**Developers**", value="siddharth_xd.", inline=False)
        embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
        embed.set_footer(text=f'Requested by {interaction.user.name}', icon_url=interaction.user.display_avatar.url)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='General Info', style=discord.ButtonStyle.secondary)
    async def general_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        total_guilds = len(interaction.client.guilds)
        total_users = len(set(interaction.client.get_all_members()))
        total_channels = len(list(interaction.client.get_all_channels()))
        if hasattr(interaction.client, 'start_time') and interaction.client.start_time:
            delta_uptime = datetime.datetime.utcnow() - interaction.client.start_time
            uptime_str = f"{delta_uptime.days} days ago"
        else:
            uptime_str = "Unknown"
        
        commands_executed = getattr(interaction.client, 'commands_executed', 0)

        embed = discord.Embed(color=0x010505)
        embed.set_author(name=f"{interaction.client.user.name}'s Information", icon_url=interaction.client.user.display_avatar.url)
        embed.add_field(name="**General Informations**", value=f"**Bot's Mention:** {interaction.client.user.mention}\n**Bot's Tag:** {interaction.client.user.name}#{interaction.client.user.discriminator}\n**Cluster:** 0\n**Shard:** 0\n**Bot's Version:** 6.9.0\n**Total Servers:** {total_guilds}\n**Total Users:** {total_users:,} ({len([m for m in interaction.client.get_all_members() if m.status != discord.Status.offline]):,} Cached)\n**Total Channels:** {total_channels}\n**Last Rebooted:** {uptime_str}\n**Commands Executed:** {commands_executed}", inline=False)
        embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
        embed.set_footer(text=f'Requested by {interaction.user.name}', icon_url=interaction.user.display_avatar.url)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='System Info', style=discord.ButtonStyle.secondary)
    async def system_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        memory = psutil.virtual_memory()
        cpu_info = platform.processor()
        system_info = platform.system()
        architecture = platform.architecture()[0]
        latency_ms = round(interaction.client.latency * 1000)
        
        embed = discord.Embed(color=0x010505)
        embed.set_author(name=f"{interaction.client.user.name} Informations", icon_url=interaction.client.user.display_avatar.url)
        embed.add_field(name="**System Informations**", value=f"**System Latency:** {latency_ms}ms\n**Platform:** {system_info}\n**Architecture:** {architecture}\n**Memory Usage:** {memory.used // (1024**3):.1f}GB/{memory.total // (1024**3):.1f} GB\n**Model:** {cpu_info}\n**Speed:** 3100 MHz\n**User:** {interaction.user.name}\n**Sys:** {int(psutil.cpu_percent())}ms\n**Idle:** {int(100 - psutil.cpu_percent())}ms\n**IRQ:** 0 ms\n**Database Latency:** 6.39ms", inline=False)
        embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
        embed.set_footer(text=f'Requested By {interaction.user.name}', icon_url=interaction.user.display_avatar.url)
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


async def setup(bot):
    await bot.add_cog(Info(bot))