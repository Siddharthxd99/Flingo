import discord
from discord.ext import commands
import aiosqlite
import os
import re
import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta

class Automod(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.db_path = "database/automod.db"
        self.user_messages = defaultdict(lambda: deque(maxlen=10))
        self.spam_threshold = 5
        self.spam_time_window = 10

        # Fixed URL pattern - removed unnecessary escaping
        self.url_pattern = re.compile(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            r'|(?:www\.)?(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?',
            re.IGNORECASE
        )

        # Use asyncio.create_task properly
        asyncio.create_task(self.init_db())

    async def init_db(self):
        """Initialize the automod database"""
        try:
            os.makedirs("database", exist_ok=True)
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS automod_settings (
                        guild_id INTEGER PRIMARY KEY,
                        antilink_enabled INTEGER DEFAULT 0,
                        antispam_enabled INTEGER DEFAULT 0
                    )
                ''')

                await db.execute('''
                    CREATE TABLE IF NOT EXISTS bypass_users (
                        guild_id INTEGER,
                        user_id INTEGER,
                        PRIMARY KEY (guild_id, user_id)
                    )
                ''')

                await db.execute('''
                    CREATE TABLE IF NOT EXISTS bypass_channels (
                        guild_id INTEGER,
                        channel_id INTEGER,
                        PRIMARY KEY (guild_id, channel_id)
                    )
                ''')
                
                await db.commit()
        except Exception as e:
            print(f"Database initialization error: {e}")

    async def get_automod_settings(self, guild_id):
        """Get automod settings for a guild"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    'SELECT antilink_enabled, antispam_enabled FROM automod_settings WHERE guild_id = ?',
                    (guild_id,)
                )
                result = await cursor.fetchone()
                if result:
                    return {'antilink': bool(result[0]), 'antispam': bool(result[1])}
                return {'antilink': False, 'antispam': False}
        except Exception as e:
            print(f"Error getting automod settings: {e}")
            return {'antilink': False, 'antispam': False}

    async def is_bypass_user(self, guild_id, user_id):
        """Check if user is in bypass list"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    'SELECT 1 FROM bypass_users WHERE guild_id = ? AND user_id = ?',
                    (guild_id, user_id)
                )
                return await cursor.fetchone() is not None
        except Exception as e:
            print(f"Error checking bypass user: {e}")
            return False

    async def is_bypass_channel(self, guild_id, channel_id):
        """Check if channel is in bypass list"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    'SELECT 1 FROM bypass_channels WHERE guild_id = ? AND channel_id = ?',
                    (guild_id, channel_id)
                )
                return await cursor.fetchone() is not None
        except Exception as e:
            print(f"Error checking bypass channel: {e}")
            return False

    async def can_timeout_user(self, guild, user, bot_member):
        """Check if bot can timeout the user"""
        if user == guild.owner:
            return False
        # Check if user has administrator permissions
        if user.guild_permissions.administrator:
            return False
        # Check role hierarchy
        if user.top_role >= bot_member.top_role:
            return False
        return True

    @commands.Cog.listener()
    async def on_message(self, message):
        """Main automod message listener"""
        # Skip bots and DMs
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        user_id = message.author.id
        channel_id = message.channel.id

        # Check if channel is bypassed
        if await self.is_bypass_channel(guild_id, channel_id):
            return

        # Check if user is bypassed
        if await self.is_bypass_user(guild_id, user_id):
            return

        # Get settings and bot member
        settings = await self.get_automod_settings(guild_id)
        bot_member = message.guild.get_member(self.client.user.id)
        
        if not bot_member:
            return

        # Check for links if antilink is enabled
        if settings['antilink'] and self.url_pattern.search(message.content):
            await self.handle_link_violation(message, bot_member)

        # Check for spam if antispam is enabled
        if settings['antispam']:
            await self.handle_spam_check(message, bot_member)

    async def handle_link_violation(self, message, bot_member):
        """Handle link violation"""
        try:
            # Delete the message first
            await message.delete()
            
            # Check if we can timeout the user
            if await self.can_timeout_user(message.guild, message.author, bot_member):
                timeout_until = discord.utils.utcnow() + timedelta(minutes=5)
                try:
                    await message.author.timeout(timeout_until, reason="Anti-link violation")
                    
                    embed = discord.Embed(
                        title="<:ByteStrik_Warning:1384843852577247254> Link Detected",
                        description=f"{message.author.mention} has been timed out for posting a link.",
                        color=0x010505
                    )
                except discord.Forbidden:
                    embed = discord.Embed(
                        title="<:ByteStrik_Warning:1384843852577247254> Link Detected",
                        description=f"{message.author.mention}, links are not allowed in this server. (Unable to timeout - insufficient permissions)",
                        color=0x010505
                    )
            else:
                embed = discord.Embed(
                    title="<:ByteStrik_Warning:1384843852577247254> Link Detected",
                    description=f"{message.author.mention}, links are not allowed in this server.",
                    color=0x010505
                )
            
            await message.channel.send(embed=embed, delete_after=10)
            
        except discord.NotFound:
            # Message was already deleted
            pass
        except discord.Forbidden:
            # Bot lacks permissions to delete message
            try:
                embed = discord.Embed(
                    title="<:ByteStrik_Warning:1384843852577247254> Link Detected",
                    description=f"{message.author.mention}, links are not allowed in this server. (Unable to delete - insufficient permissions)",
                    color=0x010505
                )
                await message.channel.send(embed=embed, delete_after=10)
            except:
                pass
        except Exception as e:
            print(f"Error handling link violation: {e}")

    async def handle_spam_check(self, message, bot_member):
        """Handle spam detection"""
        user_id = message.author.id
        current_time = datetime.now()
        
        # Add current message time to user's message history
        self.user_messages[user_id].append(current_time)
        
        # Count recent messages within time window
        recent_messages = [
            msg_time for msg_time in self.user_messages[user_id]
            if (current_time - msg_time).total_seconds() <= self.spam_time_window
        ]
        
        # If spam threshold exceeded
        if len(recent_messages) >= self.spam_threshold:
            try:
                # Delete the triggering message
                await message.delete()
                
                # Check if we can timeout the user
                if await self.can_timeout_user(message.guild, message.author, bot_member):
                    timeout_until = discord.utils.utcnow() + timedelta(minutes=10)
                    try:
                        await message.author.timeout(timeout_until, reason="Anti-spam violation")
                        
                        embed = discord.Embed(
                            title="<:ByteStrik_Warning:1384843852577247254> Spam Detected",
                            description=f"{message.author.mention} has been timed out for spamming.",
                            color=0x010505
                        )
                    except discord.Forbidden:
                        embed = discord.Embed(
                            title="<:ByteStrik_Warning:1384843852577247254> Spam Warning",
                            description=f"{message.author.mention}, please slow down your messages. (Unable to timeout - insufficient permissions)",
                            color=0x010505
                        )
                else:
                    embed = discord.Embed(
                        title="<:ByteStrik_Warning:1384843852577247254> Spam Warning",
                        description=f"{message.author.mention}, please slow down your messages.",
                        color=0x010505
                    )
                
                await message.channel.send(embed=embed, delete_after=10)
                # Clear user's message history after spam detection
                self.user_messages[user_id].clear()
                
            except discord.NotFound:
                # Message was already deleted
                pass
            except discord.Forbidden:
                # Bot lacks permissions to delete message
                try:
                    embed = discord.Embed(
                        title="<:ByteStrik_Warning:1384843852577247254> Spam Warning",
                        description=f"{message.author.mention}, please slow down your messages. (Unable to delete - insufficient permissions)",
                        color=0x010505
                    )
                    await message.channel.send(embed=embed, delete_after=10)
                    self.user_messages[user_id].clear()
                except:
                    pass
            except Exception as e:
                print(f"Error handling spam check: {e}")

    @commands.group(name='antilink', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def antilink(self, ctx):
        """Manage anti-link settings"""
        settings = await self.get_automod_settings(ctx.guild.id)
        status = "<a:flingo_tick:1385161850668449843> Enabled" if settings['antilink'] else "<a:flingo_cross:1385161874437312594> Disabled"
        
        embed = discord.Embed(
            title="Anti-Link Status",
            description=f"Current status: {status}",
            color=0x010505 if settings['antilink'] else 0xff0000
        )
        embed.add_field(
            name="Commands",
            value="`antilink enable` - Enable anti-link\n`antilink disable` - Disable anti-link",
            inline=False
        )
        await ctx.send(embed=embed)

    @antilink.command(name='enable')
    @commands.has_permissions(manage_guild=True)
    async def antilink_enable(self, ctx):
        """Enable anti-link protection"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT OR REPLACE INTO automod_settings (guild_id, antilink_enabled, antispam_enabled) 
                    VALUES (?, 1, COALESCE((SELECT antispam_enabled FROM automod_settings WHERE guild_id = ?), 0))
                ''', (ctx.guild.id, ctx.guild.id))
                await db.commit()
            
            embed = discord.Embed(
                title="<a:flingo_tick:1385161850668449843> Anti-Link Enabled",
                description="Links will now be automatically deleted and users will be timed out.",
                color=0x010505
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Error",
                description="Failed to enable anti-link protection. Please try again.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            print(f"Error enabling antilink: {e}")

    @antilink.command(name='disable')
    @commands.has_permissions(manage_guild=True)
    async def antilink_disable(self, ctx):
        """Disable anti-link protection"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT OR REPLACE INTO automod_settings (guild_id, antilink_enabled, antispam_enabled) 
                    VALUES (?, 0, COALESCE((SELECT antispam_enabled FROM automod_settings WHERE guild_id = ?), 0))
                ''', (ctx.guild.id, ctx.guild.id))
                await db.commit()
            
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Anti-Link Disabled",
                description="Links will no longer be automatically deleted.",
                color=0x010505
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Error",
                description="Failed to disable anti-link protection. Please try again.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            print(f"Error disabling antilink: {e}")

    @commands.group(name='antispam', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def antispam(self, ctx):
        """Manage anti-spam settings"""
        settings = await self.get_automod_settings(ctx.guild.id)
        status = "<a:flingo_tick:1385161850668449843> Enabled" if settings['antispam'] else "<a:flingo_cross:1385161874437312594> Disabled"
        
        embed = discord.Embed(
            title="Anti-Spam Status",
            description=f"Current status: {status}",
            color=0x010505 if settings['antispam'] else 0xff0000
        )
        embed.add_field(
            name="Settings",
            value=f"**Threshold:** {self.spam_threshold} messages\n**Time Window:** {self.spam_time_window} seconds",
            inline=False
        )
        embed.add_field(
            name="Commands",
            value="`antispam enable` - Enable anti-spam\n`antispam disable` - Disable anti-spam",
            inline=False
        )
        await ctx.send(embed=embed)

    @antispam.command(name='enable')
    @commands.has_permissions(manage_guild=True)
    async def antispam_enable(self, ctx):
        """Enable anti-spam protection"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT OR REPLACE INTO automod_settings (guild_id, antilink_enabled, antispam_enabled) 
                    VALUES (?, COALESCE((SELECT antilink_enabled FROM automod_settings WHERE guild_id = ?), 0), 1)
                ''', (ctx.guild.id, ctx.guild.id))
                await db.commit()
            
            embed = discord.Embed(
                title="<a:flingo_tick:1385161850668449843> Anti-Spam Enabled",
                description=f"Users sending more than {self.spam_threshold} messages in {self.spam_time_window} seconds will be timed out.",
                color=0x010505
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Error",
                description="Failed to enable anti-spam protection. Please try again.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            print(f"Error enabling antispam: {e}")

    @antispam.command(name='disable')
    @commands.has_permissions(manage_guild=True)
    async def antispam_disable(self, ctx):
        """Disable anti-spam protection"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT OR REPLACE INTO automod_settings (guild_id, antilink_enabled, antispam_enabled) 
                    VALUES (?, COALESCE((SELECT antilink_enabled FROM automod_settings WHERE guild_id = ?), 0), 0)
                ''', (ctx.guild.id, ctx.guild.id))
                await db.commit()
            
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Anti-Spam Disabled",
                description="Spam detection has been disabled.",
                color=0x010505
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Error",
                description="Failed to disable anti-spam protection. Please try again.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            print(f"Error disabling antispam: {e}")

    @commands.group(name='automodbypassuser', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def automodbypassuser(self, ctx):
        """Manage automod bypass users"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    'SELECT user_id FROM bypass_users WHERE guild_id = ?',
                    (ctx.guild.id,)
                )
                users = await cursor.fetchall()
            
            if not users:
                embed = discord.Embed(
                    title="Automod Bypass Users",
                    description="No users are currently bypassed.",
                    color=0x010505
                )
            else:
                user_mentions = []
                for (user_id,) in users:
                    try:
                        user = await self.client.fetch_user(user_id)
                        user_mentions.append(f"• {user.mention} ({user.name})")
                    except discord.NotFound:
                        user_mentions.append(f"• <@{user_id}> (ID: {user_id})")
                    except Exception:
                        user_mentions.append(f"• Unknown User (ID: {user_id})")
                
                embed = discord.Embed(
                    title="Automod Bypass Users",
                    description="\n".join(user_mentions),
                    color=0x010505
                )
            
            embed.add_field(
                name="Commands",
                value="`automodbypassuser add <user>` - Add bypass user\n`automodbypassuser remove <user>` - Remove bypass user",
                inline=False
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Error",
                description="Failed to retrieve bypass users. Please try again.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            print(f"Error getting bypass users: {e}")

    @automodbypassuser.command(name='add')
    @commands.has_permissions(manage_guild=True)
    async def bypass_user_add(self, ctx, user: discord.Member):
        """Add a user to automod bypass list"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                try:
                    await db.execute(
                        'INSERT INTO bypass_users (guild_id, user_id) VALUES (?, ?)',
                        (ctx.guild.id, user.id)
                    )
                    await db.commit()
                    
                    embed = discord.Embed(
                        title="<a:flingo_tick:1385161850668449843> User Added to Bypass",
                        description=f"{user.mention} has been added to the automod bypass list.",
                        color=0x010505
                    )
                except aiosqlite.IntegrityError:
                    embed = discord.Embed(
                        title="<:ByteStrik_Warning:1384843852577247254> User Already Bypassed",
                        description=f"{user.mention} is already in the automod bypass list.",
                        color=0x010505
                    )
            
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Error",
                description="Failed to add user to bypass list. Please try again.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            print(f"Error adding bypass user: {e}")

    @automodbypassuser.command(name='remove')
    @commands.has_permissions(manage_guild=True)
    async def bypass_user_remove(self, ctx, user: discord.Member):
        """Remove a user from automod bypass list"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    'DELETE FROM bypass_users WHERE guild_id = ? AND user_id = ?',
                    (ctx.guild.id, user.id)
                )
                await db.commit()
                
                if cursor.rowcount > 0:
                    embed = discord.Embed(
                        title="<a:flingo_tick:1385161850668449843> User Removed from Bypass",
                        description=f"{user.mention} has been removed from the automod bypass list.",
                        color=0x010505
                    )
                else:
                    embed = discord.Embed(
                        title="<:ByteStrik_Warning:1384843852577247254> User Not in Bypass List",
                        description=f"{user.mention} was not in the automod bypass list.",
                        color=0x010505
                    )
            
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Error",
                description="Failed to remove user from bypass list. Please try again.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            print(f"Error removing bypass user: {e}")

    @commands.group(name='automodbypasschannel', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def automodbypasschannel(self, ctx):
        """Manage automod bypass channels"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    'SELECT channel_id FROM bypass_channels WHERE guild_id = ?',
                    (ctx.guild.id,)
                )
                channels = await cursor.fetchall()
            
            if not channels:
                embed = discord.Embed(
                    title="Automod Bypass Channels",
                    description="No channels are currently bypassed.",
                    color=0x010505
                )
            else:
                channel_mentions = []
                for (channel_id,) in channels:
                    channel = self.client.get_channel(channel_id)
                    if channel:
                        channel_mentions.append(f"• {channel.mention}")
                    else:
                        channel_mentions.append(f"• <#{channel_id}> (ID: {channel_id})")
                
                embed = discord.Embed(
                    title="Automod Bypass Channels",
                    description="\n".join(channel_mentions),
                    color=0x010505
                )
            
            embed.add_field(
                name="Commands",
                value="`automodbypasschannel add <channel>` - Add bypass channel\n`automodbypasschannel remove <channel>` - Remove bypass channel",
                inline=False
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Error",
                description="Failed to retrieve bypass channels. Please try again.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            print(f"Error getting bypass channels: {e}")

    @automodbypasschannel.command(name='add')
    @commands.has_permissions(manage_guild=True)
    async def bypass_channel_add(self, ctx, channel: discord.TextChannel = None):
        """Add a channel to automod bypass list"""
        if channel is None:
            channel = ctx.channel
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                try:
                    await db.execute(
                        'INSERT INTO bypass_channels (guild_id, channel_id) VALUES (?, ?)',
                        (ctx.guild.id, channel.id)
                    )
                    await db.commit()
                    
                    embed = discord.Embed(
                        title="<a:flingo_tick:1385161850668449843> Channel Added to Bypass",
                        description=f"{channel.mention} has been added to the automod bypass list.",
                        color=0x010505
                    )
                except aiosqlite.IntegrityError:
                    embed = discord.Embed(
                        title="<:ByteStrik_Warning:1384843852577247254> Channel Already Bypassed",
                        description=f"{channel.mention} is already in the automod bypass list.",
                        color=0x010505
                    )
            
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Error",
                description="Failed to add channel to bypass list. Please try again.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            print(f"Error adding bypass channel: {e}")

    @automodbypasschannel.command(name='remove')
    @commands.has_permissions(manage_guild=True)
    async def bypass_channel_remove(self, ctx, channel: discord.TextChannel = None):
        """Remove a channel from automod bypass list"""
        if channel is None:
            channel = ctx.channel
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    'DELETE FROM bypass_channels WHERE guild_id = ? AND channel_id = ?',
                    (ctx.guild.id, channel.id)
                )
                await db.commit()
                
                if cursor.rowcount > 0:
                    embed = discord.Embed(
                        title="<a:flingo_tick:1385161850668449843> Channel Removed from Bypass",
                        description=f"{channel.mention} has been removed from the automod bypass list.",
                        color=0x010505
                    )
                else:
                    embed = discord.Embed(
                        title="<:ByteStrik_Warning:1384843852577247254> Channel Not in Bypass List",
                        description=f"{channel.mention} was not in the automod bypass list.",
                        color=0x010505
                    )
            
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Error",
                description="Failed to remove channel from bypass list. Please try again.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            print(f"Error removing bypass channel: {e}")

    @commands.command(name='automod')
    @commands.has_permissions(manage_guild=True)
    async def automod_dashboard(self, ctx):
        """Main automod dashboard showing all settings and features"""
        try:
            settings = await self.get_automod_settings(ctx.guild.id)

            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    'SELECT COUNT(*) FROM bypass_users WHERE guild_id = ?',
                    (ctx.guild.id,)
                )
                bypass_users_count = (await cursor.fetchone())[0]

                cursor = await db.execute(
                    'SELECT COUNT(*) FROM bypass_channels WHERE guild_id = ?',
                    (ctx.guild.id,)
                )
                bypass_channels_count = (await cursor.fetchone())[0]

            embed = discord.Embed(
                title="<:Antinuke:1381499536949907488> Automod Dashboard",
                description=f"Automod settings for **{ctx.guild.name}**",
                color=0x010505
            )

            antilink_status = "<a:flingo_tick:1385161850668449843> Enabled" if settings['antilink'] else "<a:flingo_cross:1385161874437312594> Disabled"
            antilink_color = "<a:flingo_tick:1385161850668449843>" if settings['antilink'] else "<a:flingo_cross:1385161874437312594>"

            antispam_status = "<a:flingo_tick:1385161850668449843> Enabled" if settings['antispam'] else "<a:flingo_cross:1385161874437312594> Disabled"
            antispam_color = "<a:flingo_tick:1385161850668449843>" if settings['antispam'] else "<a:flingo_cross:1385161874437312594>"

            embed.add_field(
                name=f"{antilink_color} Anti-Link Protection",
                value=f"**Status:** {antilink_status}\n**Command:** `antilink enable/disable`",
                inline=True
            )
            
            embed.add_field(
                name=f"{antispam_color} Anti-Spam Protection",
                value=f"**Status:** {antispam_status}\n**Threshold:** {self.spam_threshold} msgs/{self.spam_time_window}s\n**Command:** `antispam enable/disable`",
                inline=True
            )
            
            manage_messages_perm = ctx.guild.me.guild_permissions.manage_messages
            moderate_members_perm = ctx.guild.me.guild_permissions.moderate_members
            
            embed.add_field(
                name="<:system:1384849012993032273> System Status",
                value=f"**Bot Status:** Online\n**Database:** Connected\n**Permissions:** {'<a:flingo_tick:1385161850668449843>' if manage_messages_perm else '<a:flingo_cross:1385161874437312594>'} Messages | {'<a:flingo_tick:1385161850668449843>' if moderate_members_perm else '<a:flingo_cross:1385161874437312594>'} Timeout",
                inline=True
            )
            
            embed.add_field(
                name="<:MekoUser:1384849184108314629> Bypass Users",
                value=f"**Count:** {bypass_users_count} users\n**Command:** `automodbypassuser`",
                inline=True
            )
            
            embed.add_field(
                name="<:Notepad:1384842987330211850> Bypass Channels",
                value=f"**Count:** {bypass_channels_count} channels\n**Command:** `automodbypasschannel`",
                inline=True
            )
            
            embed.add_field(
                name="<:system:1384849012993032273> Quick Actions",
                value="• `antilink enable/disable`\n• `antispam enable/disable`\n• `automodbypassuser add/remove`\n• `automodbypasschannel add/remove`",
                inline=True
            )

            embed.set_footer(
                text="💡 Tip: Use individual commands for detailed management | Requires Manage Server permission"
            )

            if ctx.guild.icon:
                embed.set_thumbnail(url=ctx.guild.icon.url)
            
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Error",
                description="Failed to load automod dashboard. Please try again.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            print(f"Error loading automod dashboard: {e}")

    # Error handlers for all command groups
    @antilink.error
    async def antilink_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Missing Permissions",
                description="You need `Manage Server` permissions to use this command.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MemberNotFound):
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Member Not Found",
                description="The specified member could not be found.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Error",
                description="An error occurred while processing the command.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            print(f"Antilink command error: {error}")

    @antispam.error
    async def antispam_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Missing Permissions",
                description="You need `Manage Server` permissions to use this command.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Error",
                description="An error occurred while processing the command.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            print(f"Antispam command error: {error}")

    @automodbypassuser.error
    async def automodbypassuser_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Missing Permissions",
                description="You need `Manage Server` permissions to use this command.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MemberNotFound):
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Member Not Found",
                description="The specified member could not be found.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Missing Argument",
                description="Please specify a member to add/remove from the bypass list.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Error",
                description="An error occurred while processing the command.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            print(f"Automod bypass user command error: {error}")

    @automodbypasschannel.error
    async def automodbypasschannel_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Missing Permissions",
                description="You need `Manage Server` permissions to use this command.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.ChannelNotFound):
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Channel Not Found",
                description="The specified channel could not be found.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Error",
                description="An error occurred while processing the command.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            print(f"Automod bypass channel command error: {error}")

    @automod_dashboard.error
    async def automod_dashboard_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Missing Permissions",
                description="You need `Manage Server` permissions to use this command.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Error",
                description="An error occurred while loading the dashboard.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            print(f"Automod dashboard error: {error}")

async def setup(client):
    await client.add_cog(Automod(client))