import os
import asyncio
import datetime
import discord
import sqlite3
from discord.ext import commands
from discord import ui
from typing import Optional, Union
from collections import defaultdict, deque
import time


EMBEDCOLOR = 0x2f3136
tick = "✅"
excla = "<:Sageexclamation:1250851224886968470>"
loading = "⏳"
shield = "<:SageShield:1250854009876480000>"
warn = "<:SageWarn:1250854501233451008>"


# ========================= ULTRA-FAST RATE LIMITER =========================
class RateLimiter:
    def __init__(self, max_calls: int = 5, period: float = 5.0):
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()
        self.lock = asyncio.Lock()
    
    async def __aenter__(self):
        async with self.lock:
            now = time.time()
            while self.calls and now - self.calls[0] > self.period:
                self.calls.popleft()
            if len(self.calls) >= self.max_calls:
                sleep_time = self.period - (now - self.calls[0]) + 0.1
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    self.calls.popleft()
            self.calls.append(time.time())
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


ban_limiter = RateLimiter(max_calls=4, period=8.0)
kick_limiter = RateLimiter(max_calls=4, period=8.0)
role_limiter = RateLimiter(max_calls=8, period=5.0)
channel_limiter = RateLimiter(max_calls=8, period=5.0)
message_limiter = RateLimiter(max_calls=15, period=5.0)


# ========================= DATABASE FUNCTIONS =========================
def init_db():
    os.makedirs('database', exist_ok=True)
    conn = sqlite3.connect('database/antinuke.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS guild_settings
                 (guild_id INTEGER PRIMARY KEY, enabled INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS event_settings
                 (guild_id INTEGER, event_name TEXT, enabled INTEGER DEFAULT 1,
                  PRIMARY KEY (guild_id, event_name))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS whitelist
                 (guild_id INTEGER, user_id INTEGER,
                  PRIMARY KEY (guild_id, user_id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS extra_owners
                 (guild_id INTEGER, user_id INTEGER,
                  PRIMARY KEY (guild_id, user_id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS punishment_settings
                 (guild_id INTEGER PRIMARY KEY, punishment_type TEXT DEFAULT 'ban')''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS logging_settings
                 (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")


# ========================= CUSTOM CHECK DECORATOR =========================
def is_antinuke_manager():
    """
    Custom check: Only server owner, bot owner, and extra owners can use antinuke commands
    """
    async def predicate(ctx):
        # Check if user is server owner
        if ctx.author.id == ctx.guild.owner_id:
            return True
        
        # Check if user is bot owner
        if await ctx.bot.is_owner(ctx.author):
            return True
        
        # Check if user is extra owner
        antinuke_cog = ctx.bot.get_cog('Antinuke')
        if antinuke_cog and antinuke_cog.is_extra_owner(ctx.guild.id, ctx.author.id):
            return True
        
        # If none of the above, deny access
        raise commands.CheckFailure("❌ **Access Denied!** Only the server owner, bot owner, or extra owners can manage the antinuke system.")
    
    return commands.check(predicate)


# ========================= ANTINUKE COG =========================
class Antinuke(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.cache = {
            'guild_settings': {},
            'event_settings': defaultdict(dict),
            'whitelist': defaultdict(set),
            'extra_owners': defaultdict(set)
        }
        self.ban_queue = asyncio.Queue()
        self.client.loop.create_task(self.load_cache())
        self.client.loop.create_task(self.process_ban_queue())
    
    async def load_cache(self):
        await self.client.wait_until_ready()
        conn = sqlite3.connect('database/antinuke.db')
        c = conn.cursor()
        
        c.execute("SELECT guild_id, enabled FROM guild_settings")
        for guild_id, enabled in c.fetchall():
            self.cache['guild_settings'][guild_id] = bool(enabled)
        
        c.execute("SELECT guild_id, event_name, enabled FROM event_settings")
        for guild_id, event_name, enabled in c.fetchall():
            self.cache['event_settings'][guild_id][event_name] = bool(enabled)
        
        c.execute("SELECT guild_id, user_id FROM whitelist")
        for guild_id, user_id in c.fetchall():
            self.cache['whitelist'][guild_id].add(user_id)
        
        c.execute("SELECT guild_id, user_id FROM extra_owners")
        for guild_id, user_id in c.fetchall():
            self.cache['extra_owners'][guild_id].add(user_id)
        
        conn.close()
        print("✅ Antinuke cache loaded!")
    
    async def process_ban_queue(self):
        await self.client.wait_until_ready()
        while True:
            try:
                guild, user, reason = await self.ban_queue.get()
                await self._execute_ban(guild, user, reason)
            except Exception as e:
                print(f"❌ Ban queue error: {e}")
            await asyncio.sleep(0.01)
    
    async def _execute_ban(self, guild: discord.Guild, user: Union[discord.Member, discord.User], reason: str):
        async with ban_limiter:
            try:
                await guild.ban(user, reason=reason, delete_message_days=0)
                return True
            except discord.errors.HTTPException as e:
                if e.status == 429:
                    retry_after = getattr(e, 'retry_after', 2)
                    await asyncio.sleep(retry_after)
                    await self._execute_ban(guild, user, reason)
                return False
            except Exception:
                return False
    
    # ========================= CACHE METHODS =========================
    def is_antinuke_enabled(self, guild_id: int) -> bool:
        return self.cache['guild_settings'].get(guild_id, False)
    
    def get_event_status(self, guild_id: int, event_name: str) -> bool:
        return self.cache['event_settings'].get(guild_id, {}).get(event_name, True)
    
    def is_whitelisted(self, guild_id: int, user_id: int) -> bool:
        return user_id in self.cache['whitelist'].get(guild_id, set())
    
    def is_extra_owner(self, guild_id: int, user_id: int) -> bool:
        return user_id in self.cache['extra_owners'].get(guild_id, set())
    
    # ========================= DATABASE UPDATE METHODS =========================
    def update_guild_setting(self, guild_id: int, enabled: bool):
        conn = sqlite3.connect('database/antinuke.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO guild_settings (guild_id, enabled) VALUES (?, ?)",
                  (guild_id, int(enabled)))
        conn.commit()
        conn.close()
        self.cache['guild_settings'][guild_id] = enabled
    
    def update_event_setting(self, guild_id: int, event_name: str, enabled: bool):
        conn = sqlite3.connect('database/antinuke.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO event_settings (guild_id, event_name, enabled) VALUES (?, ?, ?)",
                  (guild_id, event_name, int(enabled)))
        conn.commit()
        conn.close()
        if guild_id not in self.cache['event_settings']:
            self.cache['event_settings'][guild_id] = {}
        self.cache['event_settings'][guild_id][event_name] = enabled
    
    def add_to_whitelist(self, guild_id: int, user_id: int):
        conn = sqlite3.connect('database/antinuke.db')
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO whitelist (guild_id, user_id) VALUES (?, ?)",
                  (guild_id, user_id))
        conn.commit()
        conn.close()
        if guild_id not in self.cache['whitelist']:
            self.cache['whitelist'][guild_id] = set()
        self.cache['whitelist'][guild_id].add(user_id)
    
    def remove_from_whitelist(self, guild_id: int, user_id: int):
        conn = sqlite3.connect('database/antinuke.db')
        c = conn.cursor()
        c.execute("DELETE FROM whitelist WHERE guild_id = ? AND user_id = ?",
                  (guild_id, user_id))
        conn.commit()
        conn.close()
        if guild_id in self.cache['whitelist']:
            self.cache['whitelist'][guild_id].discard(user_id)
    
    def add_extra_owner(self, guild_id: int, user_id: int):
        conn = sqlite3.connect('database/antinuke.db')
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO extra_owners (guild_id, user_id) VALUES (?, ?)",
                  (guild_id, user_id))
        conn.commit()
        conn.close()
        if guild_id not in self.cache['extra_owners']:
            self.cache['extra_owners'][guild_id] = set()
        self.cache['extra_owners'][guild_id].add(user_id)
    
    def remove_extra_owner(self, guild_id: int, user_id: int):
        conn = sqlite3.connect('database/antinuke.db')
        c = conn.cursor()
        c.execute("DELETE FROM extra_owners WHERE guild_id = ? AND user_id = ?",
                  (guild_id, user_id))
        conn.commit()
        conn.close()
        if guild_id in self.cache['extra_owners']:
            self.cache['extra_owners'][guild_id].discard(user_id)
    
    def get_whitelist_users(self, guild_id: int):
        return list(self.cache['whitelist'].get(guild_id, set()))
    
    def get_extra_owners(self, guild_id: int):
        return list(self.cache['extra_owners'].get(guild_id, set()))
    
    def get_extra_owner_count(self, guild_id: int) -> int:
        """Get the count of extra owners for a guild"""
        return len(self.cache['extra_owners'].get(guild_id, set()))
    
    def reset_guild_settings(self, guild_id: int):
        """Reset all antinuke settings for a guild"""
        conn = sqlite3.connect('database/antinuke.db')
        c = conn.cursor()
        
        c.execute("DELETE FROM guild_settings WHERE guild_id = ?", (guild_id,))
        c.execute("DELETE FROM event_settings WHERE guild_id = ?", (guild_id,))
        c.execute("DELETE FROM whitelist WHERE guild_id = ?", (guild_id,))
        c.execute("DELETE FROM extra_owners WHERE guild_id = ?", (guild_id,))
        c.execute("DELETE FROM punishment_settings WHERE guild_id = ?", (guild_id,))
        c.execute("DELETE FROM logging_settings WHERE guild_id = ?", (guild_id,))
        
        conn.commit()
        conn.close()
        
        if guild_id in self.cache['guild_settings']:
            del self.cache['guild_settings'][guild_id]
        if guild_id in self.cache['event_settings']:
            del self.cache['event_settings'][guild_id]
        if guild_id in self.cache['whitelist']:
            del self.cache['whitelist'][guild_id]
        if guild_id in self.cache['extra_owners']:
            del self.cache['extra_owners'][guild_id]
    
    # ========================= PUNISHMENT & LOGGING =========================
    def get_punishment_type(self, guild_id: int) -> str:
        conn = sqlite3.connect('database/antinuke.db')
        c = conn.cursor()
        c.execute("SELECT punishment_type FROM punishment_settings WHERE guild_id = ?", (guild_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else 'ban'
    
    def set_punishment_type(self, guild_id: int, punishment_type: str):
        conn = sqlite3.connect('database/antinuke.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO punishment_settings (guild_id, punishment_type) VALUES (?, ?)",
                  (guild_id, punishment_type))
        conn.commit()
        conn.close()
    
    def get_log_channel(self, guild_id: int) -> int:
        conn = sqlite3.connect('database/antinuke.db')
        c = conn.cursor()
        c.execute("SELECT channel_id FROM logging_settings WHERE guild_id = ?", (guild_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None
    
    def set_log_channel(self, guild_id: int, channel_id: int):
        conn = sqlite3.connect('database/antinuke.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO logging_settings (guild_id, channel_id) VALUES (?, ?)",
                  (guild_id, channel_id))
        conn.commit()
        conn.close()
    
    async def send_log(self, guild: discord.Guild, embed: discord.Embed):
        channel_id = self.get_log_channel(guild.id)
        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel:
                try:
                    await channel.send(embed=embed)
                except:
                    pass
    
    # ========================= ACTION METHODS =========================
    async def instant_ban(self, guild: discord.Guild, user: Union[discord.Member, discord.User], reason: str = None):
        await self.ban_queue.put((guild, user, reason or "Antinuke Protection"))
    
    async def safe_kick(self, guild: discord.Guild, member: discord.Member, reason: str = None):
        async with kick_limiter:
            try:
                await guild.kick(member, reason=reason or "Antinuke Protection")
                return True
            except discord.errors.HTTPException as e:
                if e.status == 429:
                    await asyncio.sleep(getattr(e, 'retry_after', 2))
                    return await self.safe_kick(guild, member, reason)
                return False
            except Exception:
                return False
    
    async def safe_send_message(self, channel, content=None, embed=None, view=None):
        async with message_limiter:
            try:
                return await channel.send(content=content, embed=embed, view=view)
            except discord.errors.HTTPException as e:
                if e.status == 429:
                    await asyncio.sleep(getattr(e, 'retry_after', 1))
                    return await self.safe_send_message(channel, content, embed, view)
                return None
            except Exception:
                return None
    
    # ========================= ERROR HANDLER =========================
    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            embed = discord.Embed(
                title=f"{warn} Access Denied",
                description=str(error),
                color=0xff0000
            )
            embed.add_field(
                name="Who can use these commands?",
                value="• Server Owner\n• Bot Owner\n• Extra Owners (max 2)",
                inline=False
            )
            await self.safe_send_message(ctx, embed=embed)
    
    # ========================= COMMANDS =========================
    @commands.group(name="antinuke", aliases=['an'], invoke_without_command=True)
    @is_antinuke_manager()
    async def antinuke(self, ctx):
        embed = discord.Embed(
            title=f"{shield} Antinuke System",
            description="⚡ Ultra-fast server protection",
            color=EMBEDCOLOR
        )
        embed.add_field(
            name="Commands",
            value=f"`{ctx.prefix}antinuke enable` - Enable with setup\n"
                  f"`{ctx.prefix}antinuke disable` - Disable & reset\n"
                  f"`{ctx.prefix}antinuke config` - Configure events\n"
                  f"`{ctx.prefix}antinuke status` - Check status\n"
                  f"`{ctx.prefix}whitelist` - Manage whitelist\n"
                  f"`{ctx.prefix}extraowner` - Manage extra owners",
            inline=False
        )
        embed.set_footer(text="🔐 Only accessible by server owner, bot owner, and extra owners")
        await self.safe_send_message(ctx, embed=embed)
    
    @antinuke.command(name="enable")
    @is_antinuke_manager()
    async def enable(self, ctx):
        view = SetupView(self, ctx.guild.id)
        embed = discord.Embed(
            title=f"{shield} Antinuke Setup Wizard",
            description="Please configure the antinuke settings below:",
            color=EMBEDCOLOR
        )
        await self.safe_send_message(ctx, embed=embed, view=view)
    
    @antinuke.command(name="disable")
    @is_antinuke_manager()
    async def disable(self, ctx):
        if not self.is_antinuke_enabled(ctx.guild.id):
            embed = discord.Embed(
                title=f"{warn} Antinuke Not Enabled",
                description="⚠️ **Antinuke system is currently disabled!**\n\n"
                           f"To use this command, please enable antinuke first:\n"
                           f"`{ctx.prefix}antinuke enable`",
                color=0xff0000
            )
            await self.safe_send_message(ctx, embed=embed)
            return
        
        view = DisableConfirmView(self, ctx.guild.id)
        embed = discord.Embed(
            title=f"{warn} Confirm Antinuke Disable",
            description="⚠️ **Warning!**\n\n"
                       "This will **completely reset** all antinuke settings including:\n"
                       "• Protection status\n"
                       "• Whitelisted users\n"
                       "• Extra owners\n"
                       "• Punishment settings\n"
                       "• Logging channel\n"
                       "• Event configurations\n\n"
                       "**Are you sure you want to continue?**",
            color=0xff9900
        )
        await self.safe_send_message(ctx, embed=embed, view=view)
    
    @antinuke.command(name="status")
    @is_antinuke_manager()
    async def status(self, ctx):
        if not self.is_antinuke_enabled(ctx.guild.id):
            embed = discord.Embed(
                title=f"{warn} Antinuke Not Enabled",
                description="⚠️ **Antinuke system is currently disabled!**\n\n"
                           f"To use this command, please enable antinuke first:\n"
                           f"`{ctx.prefix}antinuke enable`",
                color=0xff0000
            )
            await self.safe_send_message(ctx, embed=embed)
            return
        
        whitelisted = self.get_whitelist_users(ctx.guild.id)
        extra_owners = self.get_extra_owners(ctx.guild.id)
        punishment = self.get_punishment_type(ctx.guild.id)
        log_channel = self.get_log_channel(ctx.guild.id)
        
        embed = discord.Embed(
            title=f"{shield} Antinuke Status",
            color=0x00ff00
        )
        embed.add_field(name="Protection", value="✅ Enabled", inline=True)
        embed.add_field(name="Punishment", value=f"`{punishment.upper()}`", inline=True)
        embed.add_field(name="Log Channel", value=f"<#{log_channel}>" if log_channel else "Not set", inline=True)
        embed.add_field(name="Whitelisted", value=f"{len(whitelisted)} users", inline=True)
        embed.add_field(name="Extra Owners", value=f"{len(extra_owners)}/2 users", inline=True)
        await self.safe_send_message(ctx, embed=embed)
    
    @antinuke.command(name="config")
    @is_antinuke_manager()
    async def config(self, ctx):
        if not self.is_antinuke_enabled(ctx.guild.id):
            embed = discord.Embed(
                title=f"{warn} Antinuke Not Enabled",
                description="⚠️ **Antinuke system is currently disabled!**\n\n"
                           f"To use this command, please enable antinuke first:\n"
                           f"`{ctx.prefix}antinuke enable`",
                color=0xff0000
            )
            await self.safe_send_message(ctx, embed=embed)
            return
        
        view = ConfigView(self, ctx.guild.id)
        embed = discord.Embed(
            title=f"{shield} Antinuke Configuration",
            description="Configure which events to protect\n\n🟢 **Green** = Enabled\n🔴 **Red** = Disabled",
            color=EMBEDCOLOR
        )
        await self.safe_send_message(ctx, embed=embed, view=view)
    
    # ========================= WHITELIST COMMANDS =========================
    @commands.group(name="whitelist", aliases=['wl'], invoke_without_command=True)
    @is_antinuke_manager()
    async def whitelist(self, ctx):
        if not self.is_antinuke_enabled(ctx.guild.id):
            embed = discord.Embed(
                title=f"{warn} Antinuke Not Enabled",
                description="⚠️ **Antinuke system is currently disabled!**\n\n"
                           f"To use this command, please enable antinuke first:\n"
                           f"`{ctx.prefix}antinuke enable`",
                color=0xff0000
            )
            await self.safe_send_message(ctx, embed=embed)
            return
        
        users = self.get_whitelist_users(ctx.guild.id)
        if not users:
            embed = discord.Embed(title="📋 Whitelist", description="No users whitelisted", color=EMBEDCOLOR)
        else:
            user_list = "\n".join([f"<@{uid}>" for uid in users[:10]])
            if len(users) > 10:
                user_list += f"\n\n...and {len(users) - 10} more"
            embed = discord.Embed(title="📋 Whitelisted Users", description=user_list, color=EMBEDCOLOR)
            embed.set_footer(text=f"Total: {len(users)} users")
        await self.safe_send_message(ctx, embed=embed)
    
    @whitelist.command(name="add")
    @is_antinuke_manager()
    async def whitelist_add(self, ctx, user: discord.User):
        if not self.is_antinuke_enabled(ctx.guild.id):
            embed = discord.Embed(
                title=f"{warn} Antinuke Not Enabled",
                description="⚠️ **Antinuke system is currently disabled!**\n\n"
                           f"To use this command, please enable antinuke first:\n"
                           f"`{ctx.prefix}antinuke enable`",
                color=0xff0000
            )
            await self.safe_send_message(ctx, embed=embed)
            return
        
        self.add_to_whitelist(ctx.guild.id, user.id)
        embed = discord.Embed(
            title=f"{tick} User Whitelisted",
            description=f"{user.mention} has been added to whitelist",
            color=0x00ff00
        )
        await self.safe_send_message(ctx, embed=embed)
    
    @whitelist.command(name="remove")
    @is_antinuke_manager()
    async def whitelist_remove(self, ctx, user: discord.User):
        if not self.is_antinuke_enabled(ctx.guild.id):
            embed = discord.Embed(
                title=f"{warn} Antinuke Not Enabled",
                description="⚠️ **Antinuke system is currently disabled!**\n\n"
                           f"To use this command, please enable antinuke first:\n"
                           f"`{ctx.prefix}antinuke enable`",
                color=0xff0000
            )
            await self.safe_send_message(ctx, embed=embed)
            return
        
        self.remove_from_whitelist(ctx.guild.id, user.id)
        embed = discord.Embed(
            title=f"{tick} User Removed",
            description=f"{user.mention} has been removed from whitelist",
            color=0xff0000
        )
        await self.safe_send_message(ctx, embed=embed)
    
    # ========================= EXTRA OWNER COMMANDS =========================
    @commands.group(name="extraowner", aliases=['eo'], invoke_without_command=True)
    @is_antinuke_manager()
    async def extraowner(self, ctx):
        if not self.is_antinuke_enabled(ctx.guild.id):
            embed = discord.Embed(
                title=f"{warn} Antinuke Not Enabled",
                description="⚠️ **Antinuke system is currently disabled!**\n\n"
                           f"To use this command, please enable antinuke first:\n"
                           f"`{ctx.prefix}antinuke enable`",
                color=0xff0000
            )
            await self.safe_send_message(ctx, embed=embed)
            return
        
        owners = self.get_extra_owners(ctx.guild.id)
        if not owners:
            embed = discord.Embed(
                title="👑 Extra Owners",
                description="No extra owners set\n\n**Limit:** 2 extra owners per server",
                color=EMBEDCOLOR
            )
        else:
            owner_list = "\n".join([f"<@{uid}>" for uid in owners])
            embed = discord.Embed(title="👑 Extra Owners", description=owner_list, color=EMBEDCOLOR)
            embed.set_footer(text=f"Total: {len(owners)}/2 owners")
        await self.safe_send_message(ctx, embed=embed)
    
    @extraowner.command(name="add")
    @is_antinuke_manager()
    async def extraowner_add(self, ctx, user: discord.User):
        if not self.is_antinuke_enabled(ctx.guild.id):
            embed = discord.Embed(
                title=f"{warn} Antinuke Not Enabled",
                description="⚠️ **Antinuke system is currently disabled!**\n\n"
                           f"To use this command, please enable antinuke first:\n"
                           f"`{ctx.prefix}antinuke enable`",
                color=0xff0000
            )
            await self.safe_send_message(ctx, embed=embed)
            return
        
        # Check if limit is reached
        current_count = self.get_extra_owner_count(ctx.guild.id)
        if current_count >= 2:
            embed = discord.Embed(
                title=f"{warn} Extra Owner Limit Reached",
                description="❌ **Cannot add more extra owners!**\n\n"
                           f"This server already has **2/2** extra owners.\n"
                           f"Please remove an existing extra owner first using:\n"
                           f"`{ctx.prefix}extraowner remove <user>`",
                color=0xff0000
            )
            await self.safe_send_message(ctx, embed=embed)
            return
        
        # Check if user is already an extra owner
        if self.is_extra_owner(ctx.guild.id, user.id):
            embed = discord.Embed(
                title=f"{excla} Already Extra Owner",
                description=f"{user.mention} is already an extra owner!",
                color=0xff9900
            )
            await self.safe_send_message(ctx, embed=embed)
            return
        
        self.add_extra_owner(ctx.guild.id, user.id)
        new_count = self.get_extra_owner_count(ctx.guild.id)
        embed = discord.Embed(
            title=f"{tick} Extra Owner Added",
            description=f"{user.mention} is now an extra owner",
            color=0x00ff00
        )
        embed.set_footer(text=f"Extra Owners: {new_count}/2")
        await self.safe_send_message(ctx, embed=embed)
    
    @extraowner.command(name="remove")
    @is_antinuke_manager()
    async def extraowner_remove(self, ctx, user: discord.User):
        if not self.is_antinuke_enabled(ctx.guild.id):
            embed = discord.Embed(
                title=f"{warn} Antinuke Not Enabled",
                description="⚠️ **Antinuke system is currently disabled!**\n\n"
                           f"To use this command, please enable antinuke first:\n"
                           f"`{ctx.prefix}antinuke enable`",
                color=0xff0000
            )
            await self.safe_send_message(ctx, embed=embed)
            return
        
        # Check if user is an extra owner
        if not self.is_extra_owner(ctx.guild.id, user.id):
            embed = discord.Embed(
                title=f"{warn} Not an Extra Owner",
                description=f"{user.mention} is not an extra owner!",
                color=0xff0000
            )
            await self.safe_send_message(ctx, embed=embed)
            return
        
        self.remove_extra_owner(ctx.guild.id, user.id)
        new_count = self.get_extra_owner_count(ctx.guild.id)
        embed = discord.Embed(
            title=f"{tick} Extra Owner Removed",
            description=f"{user.mention} is no longer an extra owner",
            color=0xff0000
        )
        embed.set_footer(text=f"Extra Owners: {new_count}/2")
        await self.safe_send_message(ctx, embed=embed)


# ========================= SETUP VIEW WITH ANIMATION =========================
class SetupView(ui.View):
    def __init__(self, antinuke_cog, guild_id):
        super().__init__(timeout=180)
        self.antinuke = antinuke_cog
        self.guild_id = guild_id
        self.punishment_type = None
        self.log_channel = None
        
        punishment_select = ui.Select(
            placeholder="Select Punishment Type",
            options=[
                discord.SelectOption(label="Ban", value="ban", emoji="🔨", description="Ban unauthorized users"),
                discord.SelectOption(label="Kick", value="kick", emoji="👢", description="Kick unauthorized users")
            ],
            custom_id="punishment_select"
        )
        punishment_select.callback = self.punishment_callback
        self.add_item(punishment_select)
        
        channel_select = ui.ChannelSelect(
            placeholder="Select Logging Channel",
            channel_types=[discord.ChannelType.text],
            custom_id="channel_select"
        )
        channel_select.callback = self.channel_callback
        self.add_item(channel_select)
        
        confirm_button = ui.Button(label="Confirm & Enable", style=discord.ButtonStyle.green, emoji="✅")
        confirm_button.callback = self.confirm_callback
        self.add_item(confirm_button)
    
    async def punishment_callback(self, interaction: discord.Interaction):
        self.punishment_type = interaction.data['values'][0]
        await interaction.response.send_message(
            f"✅ Punishment type set to: **{self.punishment_type.upper()}**",
            ephemeral=True
        )
    
    async def channel_callback(self, interaction: discord.Interaction):
        self.log_channel = int(interaction.data['values'][0])
        channel = interaction.guild.get_channel(self.log_channel)
        await interaction.response.send_message(
            f"✅ Logging channel set to: {channel.mention}",
            ephemeral=True
        )
    
    async def confirm_callback(self, interaction: discord.Interaction):
        if not self.punishment_type:
            await interaction.response.send_message("❌ Please select a punishment type first!", ephemeral=True)
            return
        if not self.log_channel:
            await interaction.response.send_message("❌ Please select a logging channel first!", ephemeral=True)
            return
        
        self.antinuke.update_guild_setting(self.guild_id, True)
        self.antinuke.set_punishment_type(self.guild_id, self.punishment_type)
        self.antinuke.set_log_channel(self.guild_id, self.log_channel)
        
        embed = discord.Embed(
            title="Antinuke System Activation",
            description="⏳ **Initializing protection protocols...**",
            color=0x2f3136
        )
        await interaction.response.edit_message(embed=embed, view=None)
        
        message = await interaction.original_response()
        
        features = [
            ("Anti Ban", 0.25),
            ("Anti Kick", 0.25),
            ("Anti Bot Add", 0.25),
            ("Anti Channel Create", 0.25),
            ("Anti Channel Delete", 0.25),
            ("Anti Channel Update", 0.25),
            ("Anti Everyone/Here Ping", 0.25),
            ("Anti Guild Update", 0.25),
            ("Anti Role Create", 0.25),
            ("Anti Role Delete", 0.25),
            ("Anti Role Update", 0.25),
            ("Anti Member Update", 0.25),
            ("Anti Webhook", 0.25),
            ("Anti Prune", 0.25),
            ("Anti Emoji Create", 0.25),
            ("Anti Emoji Delete", 0.25)
        ]
        
        loaded_features = ["⏳ **Initializing protection protocols...**", ""]
        
        for feature_name, delay in features:
            loaded_features.append(f"**{feature_name}:** Enabled")
            embed.description = "\n".join(loaded_features)
            try:
                await message.edit(embed=embed)
            except:
                pass
            await asyncio.sleep(delay)
        
        loaded_features.append("")
        loaded_features.append("✅ **Antinuke system is now active!**")
        
        embed.description = "\n".join(loaded_features)
        embed.color = 0x00ff00
        embed.set_footer(text="Protection enabled successfully!")
        
        try:
            await message.edit(embed=embed)
        except:
            pass


# ========================= DISABLE CONFIRM VIEW =========================
class DisableConfirmView(ui.View):
    def __init__(self, antinuke_cog, guild_id):
        super().__init__(timeout=60)
        self.antinuke = antinuke_cog
        self.guild_id = guild_id
        
        confirm_button = ui.Button(label="Yes, Disable & Reset", style=discord.ButtonStyle.danger, emoji="⚠️")
        confirm_button.callback = self.confirm_callback
        self.add_item(confirm_button)
        
        cancel_button = ui.Button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)
    
    async def confirm_callback(self, interaction: discord.Interaction):
        whitelist_count = len(self.antinuke.get_whitelist_users(self.guild_id))
        extra_owner_count = len(self.antinuke.get_extra_owners(self.guild_id))
        
        self.antinuke.reset_guild_settings(self.guild_id)
        
        embed = discord.Embed(
            title=f"{tick} Antinuke Disabled & Reset",
            description="✅ **All antinuke settings have been reset!**",
            color=0xff0000
        )
        embed.add_field(
            name="🗑️ Cleared Data",
            value=f"• Protection: Disabled\n"
                  f"• Whitelist: {whitelist_count} users removed\n"
                  f"• Extra Owners: {extra_owner_count} users removed\n"
                  f"• Punishment settings: Reset\n"
                  f"• Logging channel: Unset\n"
                  f"• Event configs: Reset",
            inline=False
        )
        embed.add_field(
            name="ℹ️ To Re-enable",
            value=f"Run `&antinuke enable` to set up protection again",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    async def cancel_callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"{tick} Action Cancelled",
            description="Antinuke remains **enabled** with current settings.",
            color=0x00ff00
        )
        await interaction.response.edit_message(embed=embed, view=None)


class ConfigView(ui.View):
    def __init__(self, antinuke_cog, guild_id):
        super().__init__(timeout=180)
        self.antinuke = antinuke_cog
        self.guild_id = guild_id
        
        events = [
            "anti_ban", "anti_kick", "anti_bot", "anti_channel_create",
            "anti_channel_delete", "anti_channel_update", "anti_role_create",
            "anti_role_delete", "anti_role_update", "anti_webhook",
            "anti_emoji_delete", "anti_guild_update", "anti_prune"
        ]
        
        for event in events:
            button = ui.Button(
                label=event.replace("_", " ").title(),
                style=discord.ButtonStyle.green if self.antinuke.get_event_status(guild_id, event) else discord.ButtonStyle.red,
                custom_id=event
            )
            button.callback = self.toggle_event
            self.add_item(button)
    
    async def toggle_event(self, interaction: discord.Interaction):
        event = interaction.data['custom_id']
        current = self.antinuke.get_event_status(self.guild_id, event)
        self.antinuke.update_event_setting(self.guild_id, event, not current)
        
        for item in self.children:
            if item.custom_id == event:
                item.style = discord.ButtonStyle.green if not current else discord.ButtonStyle.red
        
        await interaction.response.edit_message(view=self)


async def setup(client):
    init_db()
    await client.add_cog(Antinuke(client))
    print("✅ Antinuke cog loaded successfully!")