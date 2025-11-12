import discord
from discord.ext import commands
import sqlite3
import asyncio
import datetime
import json

COOLDOWN_TIME = 2

class Logging(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.setup_database()

    def setup_database(self):
        """Initialize the database tables for logging configuration"""
        conn = sqlite3.connect('logging.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logging_config (
                guild_id INTEGER,
                feature TEXT,
                enabled BOOLEAN,
                channel_id INTEGER,
                PRIMARY KEY (guild_id, feature)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                log_type TEXT,
                timestamp TEXT,
                user_id INTEGER,
                channel_id INTEGER,
                content TEXT,
                additional_data TEXT
            )
        ''')
        
        conn.commit()
        conn.close()

    def get_logging_config(self, guild_id):
        """Get logging configuration for a guild"""
        conn = sqlite3.connect('logging.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT feature, enabled, channel_id FROM logging_config WHERE guild_id = ?', (guild_id,))
        results = cursor.fetchall()
        
        config = {}
        for feature, enabled, channel_id in results:
            config[feature] = {'enabled': bool(enabled), 'channel_id': channel_id}
        
        conn.close()
        return config

    def update_logging_config(self, guild_id, feature, enabled, channel_id=None):
        """Update logging configuration for a guild"""
        conn = sqlite3.connect('logging.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO logging_config (guild_id, feature, enabled, channel_id)
            VALUES (?, ?, ?, ?)
        ''', (guild_id, feature, enabled, channel_id))
        
        conn.commit()
        conn.close()

    async def create_logging_category(self, guild):
        """Create the Flingo Logs category if it doesn't exist"""
        category_name = "Flingo Logs"
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True,
                    embed_links=True
                )
            }
            for role in guild.roles:
                if role.permissions.administrator:
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True)
            
            try:
                category = await guild.create_category(category_name, overwrites=overwrites)
            except discord.Forbidden:
                raise discord.Forbidden("Bot lacks permissions to create categories")
            except Exception as e:
                raise e
        
        return category

    async def create_logging_channel(self, guild, channel_name, category):
        """Create a logging channel under the Flingo Logs category"""
        channel = discord.utils.get(guild.text_channels, name=channel_name, category=category)
        if not channel:
            try:
                channel = await guild.create_text_channel(
                    channel_name,
                    category=category,
                    topic=f"Automated logging channel for {channel_name.replace('-', ' ').title()}"
                )
            except discord.Forbidden:
                raise discord.Forbidden("Bot lacks permissions to create channels")
            except Exception as e:
                raise e
        return channel

    async def setup_logging_channels(self, guild, features):
        """Setup logging channels for specified features"""
        try:
            category = await self.create_logging_category(guild)
        except Exception as e:
            raise e
        
        channel_mapping = {
            'message_logs': 'message-logs',
            'member_join_leave': 'member-logs', 
            'channel_changes': 'channel-logs',
            'role_changes': 'role-logs',
            'voice_state': 'voice-logs',
            'emoji_changes': 'emoji-logs',
            'member_update': 'member-updates',
            'guild_updates': 'guild-updates',
            'moderation_actions': 'moderation-logs'
        }
        
        created_channels = {}
        
        for feature in features:
            if feature in channel_mapping:
                channel_name = channel_mapping[feature]
                try:
                    channel = await self.create_logging_channel(guild, channel_name, category)
                    created_channels[feature] = channel
                    self.update_logging_config(guild.id, feature, True, channel.id)
                except Exception as e:
                    print(f"Failed to create channel {channel_name}: {e}")
                    continue
        
        return created_channels

    def create_log_embed(self, title, description, color=0x010505):
        """Create a standard log embed"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.datetime.utcnow()
        )
        return embed

    @commands.group(name='logging', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def logging(self, ctx):
        """Main logging command group"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="<:logging:1381504143272968235> Flingo Logging System",
                description="**Logging Commands**\n\nUse the commands below to manage logging settings.",
                color=0x010505,
                timestamp=datetime.datetime.utcnow()
            )
            embed.add_field(
                name="<:Notepad:1384842987330211850> `logging setup`",
                value="Setup logging features.",
                inline=False
            )
            embed.add_field(
                name="<:reset:1384852357002825798> `logging reset`",
                value="Resets all logging config.",
                inline=False
            )
            embed.add_field(
                name="<:system:1384849012993032273> `logging status`",
                value="Show logging status of this guild",
                inline=False
            )
            embed.set_footer(text=f"Flingo - Ultimate Multipurpose Discord bot • Today at {datetime.datetime.now().strftime('%H:%M')}")
            await ctx.send(embed=embed)

    @logging.command(name='setup')
    @commands.has_permissions(administrator=True)
    async def logging_setup(self, ctx):
        """Setup logging features"""
        embed = discord.Embed(
            title="<:logging:1381504143272968235> Flingo Logging System",
            description="Flingo provides you with the best logging system that's easy to use and user-friendly. Select the logging feature from the drop-down menu you want to enable. You can enable **All Logs** to send every log to channels.",
            color=0x010505,
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_footer(text=f"Today at {datetime.datetime.now().strftime('%H:%M')}")
        view = LoggingSetupView(self, ctx.guild.id, ctx.guild)
        await ctx.send(embed=embed, view=view)

    @logging.command(name='reset')
    @commands.has_permissions(administrator=True)
    async def logging_reset(self, ctx):
        """Reset all logging configurations and delete channels"""
        try:
            category = discord.utils.get(ctx.guild.categories, name="Flingo Logs")
            if category:
                for channel in category.channels:
                    try:
                        await channel.delete()
                    except discord.Forbidden:
                        pass
                    except Exception:
                        pass
                try:
                    await category.delete()
                except discord.Forbidden:
                    pass
                except Exception:
                    pass
            conn = sqlite3.connect('logging.db')
            cursor = conn.cursor()
            cursor.execute('DELETE FROM logging_config WHERE guild_id = ?', (ctx.guild.id,))
            conn.commit()
            conn.close()
            
            embed = discord.Embed(
                title="<:reset:1384852357002825798> Logging Reset",
                description="All logging configurations have been erased, and the **Flingo Logs** category along with its channels have been deleted.",
                color=0x010505,
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_footer(text=f"Today at {datetime.datetime.now().strftime('%H:%M')}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Error",
                description=f"An error occurred while resetting logging: {str(e)}",
                color=0x010505
            )
            await ctx.send(embed=error_embed)

    @logging.command(name='status')
    @commands.has_permissions(administrator=True)
    async def logging_status(self, ctx):
        """Show current logging status"""
        config = self.get_logging_config(ctx.guild.id)
        
        embed = discord.Embed(
            title="<:logging:1381504143272968235> Flingo Logging System",
            description=f"**Logging Status**\n\nCurrent logging status for **{ctx.guild.name}**",
            color=0x010505,
            timestamp=datetime.datetime.utcnow()
        )
        features = {
            'message_logs': 'Message Logs',
            'member_join_leave': 'Member Join/Leave',
            'channel_changes': 'Channel Changes',
            'role_changes': 'Role Changes',
            'voice_state': 'Voice State',
            'emoji_changes': 'Emoji Changes',
            'moderation_actions': 'Moderation Actions',
            'member_update': 'Member Update',
            'guild_updates': 'Guild Updates'
        }
        
        enabled_features = []
        disabled_features = []
        
        for feature_key, feature_name in features.items():
            if feature_key in config and config[feature_key]['enabled']:
                channel = self.client.get_channel(config[feature_key]['channel_id'])
                channel_mention = channel.mention if channel else "Channel not found"
                enabled_features.append(f"<a:flingo_tick:1385161850668449843> **{feature_name}** → {channel_mention}")
            else:
                disabled_features.append(f"<a:flingo_cross:1385161874437312594> **{feature_name}**")
        
        if enabled_features:
            embed.add_field(
                name="<a:flingo_tick:1385161850668449843> Enabled Features",
                value="\n".join(enabled_features),
                inline=False
            )
        
        if disabled_features:
            embed.add_field(
                name="<a:flingo_cross:1385161874437312594> Disabled Features", 
                value="\n".join(disabled_features),
                inline=False
            )
        
        if not enabled_features and not disabled_features:
            embed.add_field(
                name="Status",
                value="No logging features configured. Use `logging setup` to get started!",
                inline=False
            )
        
        embed.set_footer(text=f"Today at {datetime.datetime.now().strftime('%H:%M')}")
        await ctx.send(embed=embed)
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Log message edits"""
        if before.author.bot or before.content == after.content:
            return
        
        if not before.guild:
            return
            
        config = self.get_logging_config(before.guild.id)
        if 'message_logs' not in config or not config['message_logs']['enabled']:
            return
        
        channel_id = config['message_logs']['channel_id']
        if channel_id:
            channel = self.client.get_channel(channel_id)
            if channel:
                try:
                    embed = self.create_log_embed(
                        "<:Notepad:1384842987330211850> Message Edited",
                        f"**Author:** {before.author.mention}\n**Channel:** {before.channel.mention}\n**Before:** {before.content[:1000]}{'...' if len(before.content) > 1000 else ''}\n**After:** {after.content[:1000]}{'...' if len(after.content) > 1000 else ''}",
                        0x010505
                    )
                    embed.set_author(
                        name=str(before.author), 
                        icon_url=before.author.display_avatar.url
                    )
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    pass
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Log message deletions"""
        if message.author.bot:
            return
            
        if not message.guild:
            return
        
        config = self.get_logging_config(message.guild.id)
        if 'message_logs' not in config or not config['message_logs']['enabled']:
            return
        
        channel_id = config['message_logs']['channel_id']
        if channel_id:
            channel = self.client.get_channel(channel_id)
            if channel:
                try:
                    embed = self.create_log_embed(
                        "<:lvb_Trash:1384844060618919936> Message Deleted",
                        f"**Author:** {message.author.mention}\n**Channel:** {message.channel.mention}\n**Content:** {message.content[:1000]}{'...' if len(message.content) > 1000 else ''}",
                        0x010505
                    )
                    embed.set_author(
                        name=str(message.author), 
                        icon_url=message.author.display_avatar.url
                    )
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    pass
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Log member joins"""
        config = self.get_logging_config(member.guild.id)
        if 'member_join_leave' not in config or not config['member_join_leave']['enabled']:
            return
        
        channel_id = config['member_join_leave']['channel_id']
        if channel_id:
            channel = self.client.get_channel(channel_id)
            if channel:
                try:
                    embed = self.create_log_embed(
                        "👋 Member Joined",
                        f"**Member:** {member.mention}\n**Account Created:** {discord.utils.format_dt(member.created_at, 'F')}\n**Member Count:** {member.guild.member_count}",
                        0x00ff00
                    )
                    embed.set_author(
                        name=str(member), 
                        icon_url=member.display_avatar.url
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    pass
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Log member leaves"""
        config = self.get_logging_config(member.guild.id)
        if 'member_join_leave' not in config or not config['member_join_leave']['enabled']:
            return
        
        channel_id = config['member_join_leave']['channel_id']
        if channel_id:
            channel = self.client.get_channel(channel_id)
            if channel:
                try:
                    joined_text = discord.utils.format_dt(member.joined_at, 'F') if member.joined_at else 'Unknown'
                    embed = self.create_log_embed(
                        "👋 Member Left",
                        f"**Member:** {member.mention}\n**Joined:** {joined_text}\n**Member Count:** {member.guild.member_count}",
                        0x010505
                    )
                    embed.set_author(
                        name=str(member), 
                        icon_url=member.display_avatar.url
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    pass
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        """Log channel creation"""
        config = self.get_logging_config(channel.guild.id)
        if 'channel_changes' not in config or not config['channel_changes']['enabled']:
            return
        
        channel_id = config['channel_changes']['channel_id']
        if channel_id:
            log_channel = self.client.get_channel(channel_id)
            if log_channel:
                try:
                    embed = self.create_log_embed(
                        "📁 Channel Created",
                        f"**Channel:** {channel.mention}\n**Type:** {str(channel.type).title()}",
                        0x00ff00
                    )
                    await log_channel.send(embed=embed)
                except discord.Forbidden:
                    pass
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        """Log channel deletion"""
        config = self.get_logging_config(channel.guild.id)
        if 'channel_changes' not in config or not config['channel_changes']['enabled']:
            return
        
        channel_id = config['channel_changes']['channel_id']
        if channel_id:
            log_channel = self.client.get_channel(channel_id)
            if log_channel:
                try:
                    embed = self.create_log_embed(
                        "<:lvb_Trash:1384844060618919936> Channel Deleted",
                        f"**Channel:** {channel.name}\n**Type:** {str(channel.type).title()}",
                        0x010505
                    )
                    await log_channel.send(embed=embed)
                except discord.Forbidden:
                    pass
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        """Log role creation"""
        config = self.get_logging_config(role.guild.id)
        if 'role_changes' not in config or not config['role_changes']['enabled']:
            return
        
        channel_id = config['role_changes']['channel_id']
        if channel_id:
            channel = self.client.get_channel(channel_id)
            if channel:
                try:
                    perms_count = sum(1 for perm, value in role.permissions if value)
                    embed = self.create_log_embed(
                        "<:Meko_Role:1384854321740513282> Role Created",
                        f"**Role:** {role.mention}\n**Color:** {str(role.color)}\n**Permissions:** {perms_count} enabled",
                        0x00ff00
                    )
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    pass
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        """Log role deletion"""
        config = self.get_logging_config(role.guild.id)
        if 'role_changes' not in config or not config['role_changes']['enabled']:
            return
        
        channel_id = config['role_changes']['channel_id']
        if channel_id:
            channel = self.client.get_channel(channel_id)
            if channel:
                try:
                    embed = self.create_log_embed(
                        "<:lvb_Trash:1384844060618919936> Role Deleted",
                        f"**Role:** {role.name}\n**Color:** {str(role.color)}",
                        0x010505
                    )
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    pass
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Log voice state changes"""
        config = self.get_logging_config(member.guild.id)
        if 'voice_state' not in config or not config['voice_state']['enabled']:
            return
        
        channel_id = config['voice_state']['channel_id']
        if channel_id:
            channel = self.client.get_channel(channel_id)
            if channel:
                try:
                    if before.channel != after.channel:
                        if before.channel is None:
                            embed = self.create_log_embed(
                                "🔊 Voice Channel Joined",
                                f"**Member:** {member.mention}\n**Channel:** {after.channel.mention}",
                                0x00ff00
                            )
                        elif after.channel is None:
                            embed = self.create_log_embed(
                                "🔇 Voice Channel Left",
                                f"**Member:** {member.mention}\n**Channel:** {before.channel.mention}",
                                0x010505
                            )
                        else:
                            embed = self.create_log_embed(
                                "🔀 Voice Channel Moved",
                                f"**Member:** {member.mention}\n**From:** {before.channel.mention}\n**To:** {after.channel.mention}",
                                0x010505
                            )
                        
                        embed.set_author(
                            name=str(member), 
                            icon_url=member.display_avatar.url
                        )
                        await channel.send(embed=embed)
                except discord.Forbidden:
                    pass
                except Exception:
                    pass

    @logging.error
    async def logging_error(self, ctx, error):
        """Handle logging command errors"""
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Missing Permissions",
                description="You need **Administrator** permissions to use logging commands.",
                color=0x010505
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Error",
                description=f"An error occurred: {str(error)}",
                color=0x010505
            )
            await ctx.send(embed=embed)


class LoggingSetupView(discord.ui.View):
    def __init__(self, logging_cog, guild_id, guild):
        super().__init__(timeout=300)
        self.logging_cog = logging_cog
        self.guild_id = guild_id
        self.guild = guild

    @discord.ui.select(
        placeholder="Select Logging Features",
        options=[
            discord.SelectOption(label="Message Logs", description="Log all message edits and deletions.", value="message_logs"),
            discord.SelectOption(label="Member Join/Leave", description="Log when members join or leave.", value="member_join_leave"),
            discord.SelectOption(label="Channel Changes", description="Log all channel creations, deletions, and edits.", value="channel_changes"),
            discord.SelectOption(label="Role Changes", description="Log all role creations, deletions, and edits.", value="role_changes"),
            discord.SelectOption(label="Voice State", description="Log voice channel events.", value="voice_state"),
            discord.SelectOption(label="Emoji Changes", description="Log emoji additions, deletions, and changes.", value="emoji_changes"),
            discord.SelectOption(label="Member Update", description="Log when member roles, nickname etc. are updated.", value="member_update"),
            discord.SelectOption(label="Guild Updates", description="Logs of guild updates.", value="guild_updates"),
            discord.SelectOption(label="All Logs", description="Log everything.", value="all_logs"),
        ],
        max_values=9
    )
    async def select_logging_feature(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer()
        
        selected_features = select.values
        
        try:
            if "all_logs" in selected_features:
                features = ['message_logs', 'member_join_leave', 'channel_changes', 'role_changes', 
                           'voice_state', 'emoji_changes', 'member_update', 'guild_updates']
                created_channels = await self.logging_cog.setup_logging_channels(self.guild, features)
                
                embed = discord.Embed(
                    title="<a:flingo_tick:1385161850668449843> All Logging Enabled",
                    description=f"All logging features have been enabled! Created {len(created_channels)} logging channels in the **Flingo Logs** category.",
                    color=0x00ff00,
                    timestamp=datetime.datetime.utcnow()
                )
                if created_channels:
                    channel_list = "\n".join([f"• {channel.mention}" for channel in created_channels.values()])
                    embed.add_field(name="Created Channels", value=channel_list, inline=False)
                
            else:
                created_channels = await self.logging_cog.setup_logging_channels(self.guild, selected_features)
                
                if created_channels:
                    feature_names = [feature.replace('_', ' ').title() for feature in selected_features]
                    embed = discord.Embed(
                        title="<a:flingo_tick:1385161850668449843> Logging Enabled",
                        description=f"**{', '.join(feature_names)}** logging has been enabled!",
                        color=0x00ff00,
                        timestamp=datetime.datetime.utcnow()
                    )
                    channel_list = "\n".join([f"• {channel.mention}" for channel in created_channels.values()])
                    embed.add_field(name="Created Channels", value=channel_list, inline=False)
                else:
                    embed = discord.Embed(
                        title="<:ByteStrik_Warning:1384843852577247254> Warning",
                        description="No channels were created. They may already exist or there was a permission issue.",
                        color=0x010505,
                        timestamp=datetime.datetime.utcnow()
                    )
            
            await interaction.followup.send(embed=embed)
            
        except discord.Forbidden:
            error_embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Permission Error",
                description="I don't have permission to create channels and categories. Please ensure I have the **Manage Channels** permission.",
                color=0x010505
            )
            await interaction.followup.send(embed=error_embed)
        except Exception as e:
            error_embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Error",
                description=f"Failed to setup logging channels.\n\nError: {str(e)}",
                color=0x010505
            )
            await interaction.followup.send(embed=error_embed)

    async def on_timeout(self):
        """Called when the view times out"""
        for item in self.children:
            item.disabled = True


async def setup(bot):
    await bot.add_cog(Logging(bot))