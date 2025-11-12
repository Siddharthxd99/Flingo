import discord
from discord.ext import commands
import sqlite3
import asyncio

class Ignore(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ignore_channels = self.load_ignore_channels()
        self.ignored_users = {}

    def load_ignore_channels(self):
        try:
            conn = sqlite3.connect("ignore.db")
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS ignore_channels 
                             (channel_id INTEGER PRIMARY KEY)''')
            cursor.execute("SELECT channel_id FROM ignore_channels")
            channels = [row[0] for row in cursor.fetchall()]
            conn.close()
            return channels
        except Exception:
            return []

    def save_ignore_channels(self):
        conn = sqlite3.connect("ignore.db")
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS ignore_channels 
                         (channel_id INTEGER PRIMARY KEY)''')
        cursor.execute("DELETE FROM ignore_channels")
        for channel_id in self.ignore_channels:
            cursor.execute("INSERT INTO ignore_channels (channel_id) VALUES (?)", (channel_id,))
        conn.commit()
        conn.close()

    async def send_and_delete(self, ctx, message, delay=2):
        msg = await ctx.send(message)
        await asyncio.sleep(delay)
        try:
            await msg.delete()
        except discord.NotFound:
            pass

    async def cog_check(self, ctx):
        return ctx.guild and ctx.author.guild_permissions.administrator

    @commands.group(name="ignore", invoke_without_command=True)
    async def ignore(self, ctx):
        await ctx.send("Invalid usage. Use `ignore channel add <channel>` or `ignore channel remove <channel>`")

    @ignore.command(name="channel")
    async def ignore_channel(self, ctx, action, channel: discord.TextChannel):
        if action.lower() == "add":
            if channel.id not in self.ignore_channels:
                self.ignore_channels.append(channel.id)
                self.save_ignore_channels()
                embed = discord.Embed(description=f"#**{channel.name}** has been added to the ignore list.", color=0x010505)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(description=f"#**{channel.name}** is already in the ignore list.", color=0x010505)
                await ctx.send(embed=embed)
        elif action.lower() == "remove":
            if channel.id in self.ignore_channels:
                self.ignore_channels.remove(channel.id)
                self.save_ignore_channels()
                embed = discord.Embed(description=f"#**{channel.name}** has been removed from the ignore list.", color=0x010505)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(description=f"#**{channel.name}** is not in the ignore list.", color=0x010505)
                await ctx.send(embed=embed)
        else:
            await ctx.send("Invalid action. Use `add` or `remove`.")

    @commands.Cog.listener()
    async def on_command(self, ctx):
        if ctx.channel.id in self.ignore_channels:
            user_id = ctx.author.id
            if user_id not in self.ignored_users or not self.ignored_users[user_id]:
                self.ignored_users[user_id] = True
                await self.send_and_delete(ctx, "This channel is in the ignore list. No commands can be used here.", delay=3)
                await asyncio.sleep(10)
                self.ignored_users[user_id] = False

def is_not_ignored_channel(ctx):
    return ctx.channel.id not in ctx.bot.get_cog("Ignore").ignore_channels

async def setup(bot):
    await bot.add_cog(Ignore(bot))
    bot.add_check(is_not_ignored_channel)
    print("Ignore cog successfully loaded.")