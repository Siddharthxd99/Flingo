import discord
from discord.ext import commands
import sqlite3
import asyncio
import datetime

COOLDOWN_TIME = 2

class Voice(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.vc_role_data = {}
        self.vc_bans = {}
        self.cooldowns = {}
        self.warning_messages = {}
        self.init_database()
        self.load_data()

    def init_database(self):
        """Initialize SQLite database and create tables if they don't exist"""
        conn = sqlite3.connect('voice_data.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vc_roles (
                guild_id TEXT PRIMARY KEY,
                role_id INTEGER
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vc_bans (
                guild_id TEXT,
                user_id INTEGER,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')
        
        conn.commit()
        conn.close()

    def load_data(self):
        """Load data from SQLite database into memory"""
        conn = sqlite3.connect('voice_data.db')
        cursor = conn.cursor()
        cursor.execute('SELECT guild_id, role_id FROM vc_roles')
        for guild_id, role_id in cursor.fetchall():
            self.vc_role_data[guild_id] = role_id
        cursor.execute('SELECT guild_id, user_id FROM vc_bans')
        for guild_id, user_id in cursor.fetchall():
            if guild_id not in self.vc_bans:
                self.vc_bans[guild_id] = []
            self.vc_bans[guild_id].append(user_id)
        
        conn.close()

    async def save_vc_data(self):
        """Save both VC role and ban data to SQLite database"""
        conn = sqlite3.connect('voice_data.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM vc_roles')
        cursor.execute('DELETE FROM vc_bans')
        for guild_id, role_id in self.vc_role_data.items():
            cursor.execute('INSERT INTO vc_roles (guild_id, role_id) VALUES (?, ?)', (guild_id, role_id))
        for guild_id, user_ids in self.vc_bans.items():
            for user_id in user_ids:
                cursor.execute('INSERT INTO vc_bans (guild_id, user_id) VALUES (?, ?)', (guild_id, user_id))
        
        conn.commit()
        conn.close()

    async def handle_cooldown(self, ctx, command_name):
        user_id = ctx.author.id
        if user_id in self.cooldowns and command_name in self.cooldowns[user_id]:
            if user_id not in self.warning_messages:
                self.warning_messages[user_id] = {}
            if command_name not in self.warning_messages[user_id]:
                remaining_time = self.cooldowns[user_id][command_name]
                msg = await ctx.send(f"You are on cooldown for `{command_name}` command. Please wait {remaining_time} seconds.")
                self.warning_messages[user_id][command_name] = msg
            return True
        return False

    async def clear_cooldown(self, user_id, command_name):
        await asyncio.sleep(COOLDOWN_TIME)
        if user_id in self.cooldowns and command_name in self.cooldowns[user_id]:
            del self.cooldowns[user_id][command_name]
            if not self.cooldowns[user_id]:
                del self.cooldowns[user_id]

            if user_id in self.warning_messages and command_name in self.warning_messages[user_id]:
                try:
                    await self.warning_messages[user_id][command_name].delete()
                except discord.NotFound:
                    pass
                del self.warning_messages[user_id][command_name]
            if not self.warning_messages[user_id]:
                del self.warning_messages[user_id]

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild_id = str(member.guild.id)
        if guild_id in self.vc_bans and member.id in self.vc_bans[guild_id] and before.channel != after.channel:
            if after.channel is not None:
                await member.move_to(None)
                await member.send(f"You have been banned from joining voice channels in {member.guild.name}.")
                return
        if before.channel != after.channel:
            if after.channel:
                await self.add_vc_role(member, guild_id)
            if before.channel:
                if member.voice is None:
                    await self.remove_vc_role(member, guild_id)

    async def add_vc_role(self, member, guild_id):
        if guild_id in self.vc_role_data:
            role_id = self.vc_role_data[guild_id]
            role = member.guild.get_role(role_id)
            if role and role not in member.roles:
                await member.add_roles(role, reason="Vcrole | vc join")

    async def remove_vc_role(self, member, guild_id):
        if guild_id in self.vc_role_data:
            role_id = self.vc_role_data[guild_id]
            role = member.guild.get_role(role_id)
            if role and role in member.roles:
                if member.voice is None:
                    await member.remove_roles(role, reason="Vcrole | vc leave")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def vcrole(self, ctx, action, role: discord.Role = None):

        if await self.handle_cooldown(ctx, 'vcrole'):
            return

        if not ctx.author.guild_permissions.administrator:
            await ctx.send("You do not have the required permissions to use this command.")
            return

        guild_id = str(ctx.guild.id)
        if action == "set":
            if not role:
                await ctx.send("Please specify a role.")
                return
            self.vc_role_data[guild_id] = role.id
            await self.save_vc_data()
            await ctx.send(f"Voice role set to {role.name}.")
            for member in ctx.guild.members:
                if member.voice and member.guild == ctx.guild:
                    await self.add_vc_role(member, guild_id)

        elif action == "show":
            if guild_id in self.vc_role_data:
                role_id = self.vc_role_data[guild_id]
                role = ctx.guild.get_role(role_id)
                if role:
                    await ctx.send(f"Voice role: {role.name}")
                else:
                    await ctx.send("No voice role set for this server.")
            else:
                await ctx.send("No voice role set for this server.")

        elif action == "reset":
            if guild_id in self.vc_role_data:
                del self.vc_role_data[guild_id]
                await self.save_vc_data()
                await ctx.send("Voice role reset successfully.")
                for member in ctx.guild.members:
                    if member.voice and member.guild == ctx.guild:
                        await self.remove_vc_role(member, guild_id)

            else:
                await ctx.send("No voice role set for this server.")
        else:
            await ctx.send("Invalid action. Use `set`, `show`, or `reset`.")

        self.cooldowns[ctx.author.id] = {'vcrole': COOLDOWN_TIME}
        asyncio.create_task(self.clear_cooldown(ctx.author.id, 'vcrole'))

    @vcrole.error
    async def vcrole_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `.vcrole <action> [role]`")
        elif isinstance(error, commands.CheckFailure):
            await ctx.send("You do not have the required permissions to use this command.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def vcban(self, ctx, member: discord.Member):
        if await self.handle_cooldown(ctx, 'vcban'):
            return

        if not ctx.author.guild_permissions.administrator:
            await ctx.reply("You do not have the required permissions to use this command.")
            return

        if member == ctx.guild.me:
            await ctx.reply("Oh no, you can't voice ban me—I'm the one running the show!")
            return

        guild_id = str(ctx.guild.id)
        if guild_id not in self.vc_bans:
            self.vc_bans[guild_id] = []
        if member.voice:
            await member.move_to(None)

        if member.id not in self.vc_bans[guild_id]:
            self.vc_bans[guild_id].append(member.id)

        await ctx.reply(f"{member.display_name} has been banned from joining voice channels in {ctx.guild.name}.")
        await self.save_vc_data()
        self.cooldowns[ctx.author.id] = {'vcban': COOLDOWN_TIME}
        asyncio.create_task(self.clear_cooldown(ctx.author.id, 'vcban'))

    @vcban.error
    async def vcban_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `.vcban <member>`")
        elif isinstance(error, commands.CheckFailure):
            await ctx.send("You do not have the required permissions to use this command.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def vcunban(self, ctx, member: discord.Member):
        if await self.handle_cooldown(ctx, 'vcunban'):
            return

        if not ctx.author.guild_permissions.administrator:
            await ctx.send("You do not have the required permissions to use this command.")
            return

        guild_id = str(ctx.guild.id)
        if guild_id in self.vc_bans and member.id in self.vc_bans[guild_id]:
            self.vc_bans[guild_id].remove(member.id)
            await ctx.send(f"{member.display_name} has been unbanned from joining voice channels in {ctx.guild.name}.")
            await self.save_vc_data()
        else:
            await ctx.send(f"{member.display_name} is not currently banned from joining voice channels in {ctx.guild.name}.")
        self.cooldowns[ctx.author.id] = {'vcunban': COOLDOWN_TIME}
        asyncio.create_task(self.clear_cooldown(ctx.author.id, 'vcunban'))

    @vcunban.error
    async def vcunban_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `.vcunban <member>`")
        elif isinstance(error, commands.CheckFailure):
            await ctx.send("You do not have the required permissions to use this command.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def vckick(self, ctx, member: discord.Member):
        if await self.handle_cooldown(ctx, 'vckick'):
            return

        if not ctx.author.guild_permissions.administrator:
            await ctx.send("You do not have the required permissions to use this command.")
            return

        if ctx.author.voice:
            if member.voice:
                await member.move_to(None)
                await ctx.send(f"{member.display_name} has been kicked from the voice channel.")
            else:
                await ctx.send(f"{member.display_name} is not in a voice channel.")
        else:
            await ctx.send("You need to be in a voice channel to use this command.")
        self.cooldowns[ctx.author.id] = {'vckick': COOLDOWN_TIME}
        asyncio.create_task(self.clear_cooldown(ctx.author.id, 'vckick'))

    @vckick.error
    async def vckick_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `.vckick <member>`")
        elif isinstance(error, commands.CheckFailure):
            await ctx.send("You do not have the required permissions to use this command.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def drag(self, ctx, member: discord.Member, channel: discord.VoiceChannel):
        if await self.handle_cooldown(ctx, 'drag'):
            return

        if not ctx.author.guild_permissions.administrator:
            await ctx.send("You do not have the required permissions to use this command.")
            return

        if ctx.author.voice:
            if member.voice:
                await member.move_to(channel)
                await ctx.send(f"{member.display_name} has been dragged to {channel.name}.")
                guild_id = str(ctx.guild.id)
                await self.add_vc_role(member, guild_id)
            else:
                await ctx.send(f"{member.display_name} is not in a voice channel.")
        else:
            await ctx.send("You need to be in a voice channel to use this command.")
        self.cooldowns[ctx.author.id] = {'drag': COOLDOWN_TIME}
        asyncio.create_task(self.clear_cooldown(ctx.author.id, 'drag'))

    @drag.error
    async def drag_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `.drag <member> <channel>`")
        elif isinstance(error, commands.CheckFailure):
            await ctx.send("You do not have the required permissions to use this command.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def moveall(self, ctx, dest_channel: discord.VoiceChannel):
        if await self.handle_cooldown(ctx, 'moveall'):
            return

        if not ctx.author.guild_permissions.administrator:
            await ctx.send("You do not have the required permissions to use this command.")
            return

        if ctx.author.voice:
            voice_channel = ctx.author.voice.channel
            if voice_channel.members:
                for member in voice_channel.members:
                    await member.move_to(dest_channel)
                await ctx.send(f"All members from {voice_channel.name} have been moved to {dest_channel.name}.")
            else:
                await ctx.send("There are no members in your voice channel.")
        else:
            await ctx.send("You need to be in a voice channel to use this command.")
        self.cooldowns[ctx.author.id] = {'moveall': COOLDOWN_TIME}
        asyncio.create_task(self.clear_cooldown(ctx.author.id, 'moveall'))

    @moveall.error
    async def moveall_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `.moveall <channel_id>`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Invalid voice channel. Please mention a valid voice channel.")
        elif isinstance(error, commands.CheckFailure):
            await ctx.send("You do not have the required permissions to use this command.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def vcmute(self, ctx, member: discord.Member):
        if await self.handle_cooldown(ctx, 'vcmute'):
            return

        if not ctx.author.guild_permissions.administrator and "vcmute" not in [role.name.lower() for role in ctx.author.roles]:
            await ctx.send("You do not have the required permissions (`vcmute`) to use this command.")
            return

        if ctx.author.voice:
            if member.voice:
                await member.edit(mute=True)
                await ctx.send(f"{member.display_name} has been muted in the voice channel.")
            else:
                await ctx.send(f"{member.display_name} is not in a voice channel.")
        else:
            await ctx.send("You need to be in a voice channel to use this command.")
        self.cooldowns[ctx.author.id] = {'vcmute': COOLDOWN_TIME}
        asyncio.create_task(self.clear_cooldown(ctx.author.id, 'vcmute'))

    @vcmute.error
    async def vcmute_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `.vcmute <member>`")
        elif isinstance(error, commands.CheckFailure):
            await ctx.send("You do not have the required permissions (`vcmute`) to use this command.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def vcunmute(self, ctx, member: discord.Member):
        if await self.handle_cooldown(ctx, 'vcunmute'):
            return

        if not ctx.author.guild_permissions.administrator and "vcunmute" not in [role.name.lower() for role in ctx.author.roles]:
            await ctx.send("You do not have the required permissions (`vcunmute`) to use this command.")
            return

        if ctx.author.voice:
            if member.voice:
                await member.edit(mute=False)
                await ctx.send(f"{member.display_name} has been unmuted in the voice channel.")
            else:
                await ctx.send(f"{member.display_name} is not in a voice channel.")
        else:
            await ctx.send("You need to be in a voice channel to use this command.")
        self.cooldowns[ctx.author.id] = {'vcunmute': COOLDOWN_TIME}
        asyncio.create_task(self.clear_cooldown(ctx.author.id, 'vcunmute'))

    @vcunmute.error
    async def vcunmute_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `.vcunmute <member>`")
        elif isinstance(error, commands.CheckFailure):
            await ctx.send("You do not have the required permissions (`vcunmute`) to use this command.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def vcmuteall(self, ctx):
        if await self.handle_cooldown(ctx, 'vcmuteall'):
            return

        if not ctx.author.guild_permissions.administrator:
            await ctx.send("You do not have the required permissions to use this command.")
            return

        if ctx.author.voice:
            voice_channel = ctx.author.voice.channel
            if voice_channel.members:
                for member in voice_channel.members:
                    await member.edit(mute=True)
                await ctx.send(f"All members in {voice_channel.name} have been muted.")
            else:
                await ctx.send("There are no members in your voice channel.")
        else:
            await ctx.send("You need to be in a voice channel to use this command.")
        self.cooldowns[ctx.author.id] = {'vcmuteall': COOLDOWN_TIME}
        asyncio.create_task(self.clear_cooldown(ctx.author.id, 'vcmuteall'))

    @vcmuteall.error
    async def vcmuteall_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("You do not have the required permissions to use this command.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def vcunmuteall(self, ctx):
        if await self.handle_cooldown(ctx, 'vcunmuteall'):
            return

        if not ctx.author.guild_permissions.administrator:
            await ctx.send("You do not have the required permissions to use this command.")
            return

        if ctx.author.voice:
            voice_channel = ctx.author.voice.channel
            if voice_channel.members:
                for member in voice_channel.members:
                    await member.edit(mute=False)
                await ctx.send(f"All members in {voice_channel.name} have been unmuted.")
            else:
                await ctx.send("There are no members in your voice channel.")
        else:
            await ctx.send("You need to be in a voice channel to use this command.")
        self.cooldowns[ctx.author.id] = {'vcunmuteall': COOLDOWN_TIME}
        asyncio.create_task(self.clear_cooldown(ctx.author.id, 'vcunmuteall'))

    @vcunmuteall.error
    async def vcunmuteall_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("You do not have the required permissions to use this command.")

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
    @commands.has_permissions(administrator=True)
    async def votemute(self, ctx, user: discord.Member = None):
        if not ctx.author.guild_permissions.mute_members:
            await ctx.send("You don't have permission to mute members in voice channels.")
            return

        if user is None:
            await ctx.send("Correct usage: `.votemute <@user/user_id>`")
            return

        if await self.handle_cooldown(ctx, 'votemute'):
            return

        if not user.voice:
            await ctx.send(f"{user.mention} is not in a voice channel.")
            return
        if not ctx.guild.me.guild_permissions.mute_members:
            await ctx.send("I don't have permission to mute members in voice channels.")
            return

        embed = discord.Embed(
            title="Vote to Mute",
            description=f"Vote to mute {user.mention} in the voice channel.",
            color=0x010505
        )
        embed.set_footer(text='Powered by Flingo', icon_url=self.bot.user.display_avatar.url)
        message = await ctx.send(embed=embed)
        await message.add_reaction("<a:flingo_tick:1385161850668449843>")
        await message.add_reaction("<a:flingo_cross:1385161874437312594>")

        async def get_reactions():
            updated_message = await ctx.channel.fetch_message(message.id)
            yes_votes = next((r for r in updated_message.reactions if str(r.emoji) == "<a:flingo_tick:1385161850668449843>"), None)
            no_votes = next((r for r in updated_message.reactions if str(r.emoji) == "<a:flingo_cross:1385161874437312594>"), None)
            
            yes_count = 0
            no_count = 0
            
            if yes_votes:
                yes_count = max(0, yes_votes.count - (1 if self.bot.user in await yes_votes.users().flatten() else 0))
            if no_votes:
                no_count = max(0, no_votes.count - (1 if self.bot.user in await no_votes.users().flatten() else 0))
                
            return yes_count, no_count

        try:
            await asyncio.sleep(12.0)
            yes_votes, no_votes = await get_reactions()
            voice_members_count = len([m for m in user.voice.channel.members if not m.bot])
            
            if yes_votes > voice_members_count / 2:
                await user.edit(mute=True)
                await ctx.send(f"{user.mention} has been muted as voted by VC members.")
            elif no_votes > voice_members_count / 2:
                await ctx.send(f"No action taken as VC members voted against muting {user.mention}.")
            elif yes_votes > no_votes:
                await user.edit(mute=True)
                await ctx.send(f"{user.mention} has been muted as more VC members voted for it.")
            else:
                await ctx.send(f"No action taken as there wasn't enough support to mute {user.mention}.")
                
            await message.delete()

        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            await ctx.send(f"Error processing vote: {str(e)}")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred: {str(e)}")

        self.set_cooldown(ctx.author.id, 'votemute')

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def voteunmute(self, ctx, user: discord.Member = None):
        if not ctx.author.guild_permissions.mute_members:
            await ctx.send("You don't have permission to unmute members in voice channels.")
            return

        if user is None:
            await ctx.send("Correct usage: `.voteunmute <@user/user_id>`")
            return

        if await self.handle_cooldown(ctx, 'voteunmute'):
            return

        if not user.voice:
            await ctx.send(f"{user.mention} is not in a voice channel.")
            return
        if not ctx.guild.me.guild_permissions.mute_members:
            await ctx.send(f"I don't have permission to unmute members in voice channels.")
            return

        embed = discord.Embed(
            title="Vote to Unmute",
            description=f"Vote to unmute {user.mention} in the voice channel.",
            color=0x010505
        )
        embed.set_footer(text='Powered by Flingo', icon_url=self.bot.user.display_avatar.url)
        message = await ctx.send(embed=embed)
        await message.add_reaction("<a:flingo_tick:1385161850668449843>")
        await message.add_reaction("<a:flingo_cross:1385161874437312594>")

        async def get_reactions():
            updated_message = await ctx.channel.fetch_message(message.id)
            yes_votes = next((r for r in updated_message.reactions if str(r.emoji) == "<a:flingo_tick:1385161850668449843>"), None)
            no_votes = next((r for r in updated_message.reactions if str(r.emoji) == "<a:flingo_cross:1385161874437312594>"), None)
            
            yes_count = 0
            no_count = 0
            
            if yes_votes:
                yes_count = max(0, yes_votes.count - (1 if self.bot.user in await yes_votes.users().flatten() else 0))
            if no_votes:
                no_count = max(0, no_votes.count - (1 if self.bot.user in await no_votes.users().flatten() else 0))
                
            return yes_count, no_count

        try:
            await asyncio.sleep(12.0)
            yes_votes, no_votes = await get_reactions()
            voice_members_count = len([m for m in user.voice.channel.members if not m.bot])
            
            if yes_votes > voice_members_count / 2:
                await user.edit(mute=False)
                await ctx.send(f"{user.mention} has been unmuted as voted by VC members.")
            elif no_votes > voice_members_count / 2:
                await ctx.send(f"No action taken as VC members voted against unmuting {user.mention}.")
            elif yes_votes > no_votes:
                await user.edit(mute=False)
                await ctx.send(f"{user.mention} has been unmuted as more VC members voted for it.")
            else:
                await ctx.send(f"No action taken as there wasn't enough support to unmute {user.mention}.")
                
            await message.delete()

        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            await ctx.send(f"Error processing vote: {str(e)}")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred: {str(e)}")

        self.set_cooldown(ctx.author.id, 'voteunmute')
        
async def setup(bot):
    await bot.add_cog(Voice(bot))