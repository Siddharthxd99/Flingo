import discord
from discord.ext import commands
from typing import List, Union
import asyncio

class AntinukeEvents(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.antinuke = None
        self.processing = set()
        self.last_audit_check = {}
    
    async def cog_load(self):
        await asyncio.sleep(0.5)
        self.antinuke = self.client.get_cog('Antinuke')
        if self.antinuke:
            print("⚡ AntinukeEvents loaded successfully!")
            self.client.loop.create_task(self.check_unbans())
    
    async def is_protected(self, guild: discord.Guild, user: Union[discord.Member, discord.User], event_name: str) -> bool:
        if not self.antinuke or user.id == self.client.user.id:
            return False
        if not self.antinuke.is_antinuke_enabled(guild.id):
            return False
        if not self.antinuke.get_event_status(guild.id, event_name):
            return False
        if isinstance(user, discord.User):
            try:
                user = await guild.fetch_member(user.id)
            except:
                pass
        if self.antinuke.is_extra_owner(guild.id, user.id):
            return False
        if self.antinuke.is_whitelisted(guild.id, user.id):
            return False
        return True
    
    async def take_action_against_high_role(self, guild: discord.Guild, executor: Union[discord.Member, discord.User], action_type: str, target=None):
        action_key = f"{guild.id}-{executor.id}-{action_type}"
        if action_key in self.processing:
            return
        self.processing.add(action_key)
        
        try:
            is_owner = executor.id == guild.owner_id
            bot_member = guild.get_member(self.client.user.id)
            if bot_member and isinstance(executor, discord.Member):
                has_higher_role = executor.top_role >= bot_member.top_role
            else:
                has_higher_role = False
            
            punishment_type = self.antinuke.get_punishment_type(guild.id)
            action_taken = None
            
            if is_owner or has_higher_role:
                action_taken = "Warning Sent (Role Hierarchy)"
                try:
                    embed = discord.Embed(
                        title="🛡️ Antinuke Protection",
                        description=f"⚠️ **Action Reversed**\n\nYour action `{action_type}` was reversed because you are not whitelisted.\n\nContact server admins to get whitelisted.",
                        color=0xff9900
                    )
                    await executor.send(embed=embed)
                except:
                    pass
            else:
                if isinstance(executor, discord.Member):
                    if executor.top_role >= bot_member.top_role:
                        action_taken = "Warning Sent (Role Hierarchy)"
                        try:
                            embed = discord.Embed(
                                title="🛡️ Antinuke Protection",
                                description=f"⚠️ **Action Reversed**\n\nYour action `{action_type}` was reversed.\n{punishment_type.title()} was not possible due to role hierarchy.",
                                color=0xff0000
                            )
                            await executor.send(embed=embed)
                        except:
                            pass
                    else:
                        if punishment_type == 'ban':
                            if hasattr(self.antinuke, 'instant_ban'):
                                await self.antinuke.instant_ban(guild, executor, f"Unauthorized {action_type}")
                                action_taken = "Banned"
                        elif punishment_type == 'kick':
                            try:
                                await guild.kick(executor, reason=f"Antinuke: Unauthorized {action_type}")
                                action_taken = "Kicked"
                            except:
                                action_taken = "Kick Failed"
                else:
                    if punishment_type == 'ban':
                        if hasattr(self.antinuke, 'instant_ban'):
                            await self.antinuke.instant_ban(guild, executor, f"Unauthorized {action_type}")
                            action_taken = "Banned"
            
            # Send log
            log_embed = discord.Embed(
                title="🛡️ Antinuke Action Logged",
                color=0xff0000,
                timestamp=discord.utils.utcnow()
            )
            log_embed.add_field(name="Executor", value=f"{executor.mention} (`{executor.id}`)", inline=False)
            log_embed.add_field(name="Action Type", value=f"`{action_type}`", inline=True)
            log_embed.add_field(name="Punishment", value=f"`{action_taken}`", inline=True)
            if target:
                target_str = target.mention if hasattr(target, 'mention') else str(target)
                log_embed.add_field(name="Target", value=target_str, inline=False)
            log_embed.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
            
            await self.antinuke.send_log(guild, log_embed)
            
        finally:
            await asyncio.sleep(3)
            self.processing.discard(action_key)
    
    # ========================= UNBAN CHECKER =========================
    async def check_unbans(self):
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            try:
                for guild in self.client.guilds:
                    if not self.antinuke or not self.antinuke.is_antinuke_enabled(guild.id):
                        continue
                    if not self.antinuke.get_event_status(guild.id, "anti_ban"):
                        continue
                    
                    try:
                        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.unban):
                            entry_id = f"{guild.id}-{entry.id}"
                            if entry_id in self.last_audit_check:
                                break
                            
                            self.last_audit_check[entry_id] = True
                            executor = entry.user
                            target = entry.target
                            
                            if executor.id == self.client.user.id:
                                continue
                            
                            if await self.is_protected(guild, executor, "anti_ban"):
                                try:
                                    await guild.ban(target, reason="Antinuke: Reversing unauthorized unban")
                                except:
                                    pass
                                await self.take_action_against_high_role(guild, executor, "unban", target)
                            break
                    except:
                        pass
            except:
                pass
            
            await asyncio.sleep(2)
    
    # ========================= ANTI ROLE ASSIGNMENT =========================
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles == after.roles:
            return
        try:
            added_roles = [role for role in after.roles if role not in before.roles]
            removed_roles = [role for role in before.roles if role not in after.roles]
            if not added_roles and not removed_roles:
                return
            
            await asyncio.sleep(0.15)
            action_type = discord.AuditLogAction.member_role_update
            
            async for entry in after.guild.audit_logs(limit=3, action=action_type):
                if entry.target.id != after.id:
                    continue
                executor = entry.user
                if executor.id == self.client.user.id:
                    return
                
                if await self.is_protected(after.guild, executor, "anti_role_update"):
                    try:
                        for role in added_roles:
                            if role != after.guild.default_role:
                                try:
                                    await after.remove_roles(role, reason="Antinuke: Unauthorized")
                                except:
                                    pass
                        for role in removed_roles:
                            if role != after.guild.default_role:
                                try:
                                    await after.add_roles(role, reason="Antinuke: Reversing")
                                except:
                                    pass
                    except:
                        pass
                    await self.take_action_against_high_role(after.guild, executor, f"role assignment", after)
                break
        except:
            pass
    
    # ========================= ANTI BAN =========================
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: Union[discord.User, discord.Member]):
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id:
                    executor = entry.user
                    if executor.id == self.client.user.id:
                        return
                    if await self.is_protected(guild, executor, "anti_ban"):
                        try:
                            await guild.unban(user, reason="Antinuke: Reversing")
                        except:
                            pass
                        await self.take_action_against_high_role(guild, executor, "ban", user)
                    break
        except:
            pass
    
    # ========================= ANTI KICK =========================
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        try:
            async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
                if entry.target.id == member.id:
                    executor = entry.user
                    if executor.id == self.client.user.id:
                        return
                    if await self.is_protected(member.guild, executor, "anti_kick"):
                        await self.take_action_against_high_role(member.guild, executor, "kick", member)
                    break
        except:
            pass
    
    # ========================= ANTI BOT ADD =========================
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.bot:
            return
        try:
            async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
                if entry.target.id == member.id:
                    executor = entry.user
                    if executor.id == self.client.user.id:
                        return
                    if await self.is_protected(member.guild, executor, "anti_bot"):
                        try:
                            await member.kick(reason="Antinuke: Unauthorized bot")
                        except:
                            pass
                        await self.take_action_against_high_role(member.guild, executor, "bot addition", member)
                    break
        except:
            pass
    
    # ========================= ANTI CHANNEL CREATE =========================
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
                if entry.target.id == channel.id:
                    executor = entry.user
                    if executor.id == self.client.user.id:
                        return
                    if await self.is_protected(channel.guild, executor, "anti_channel_create"):
                        try:
                            await channel.delete(reason="Antinuke: Unauthorized")
                        except:
                            pass
                        await self.take_action_against_high_role(channel.guild, executor, "channel creation", channel)
                    break
        except:
            pass
    
    # ========================= ANTI CHANNEL DELETE =========================
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
                if entry.target.id == channel.id:
                    executor = entry.user
                    if executor.id == self.client.user.id:
                        return
                    if await self.is_protected(channel.guild, executor, "anti_channel_delete"):
                        await self.take_action_against_high_role(channel.guild, executor, "channel deletion", channel)
                    break
        except:
            pass
    
    # ========================= ANTI CHANNEL UPDATE =========================
    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        try:
            async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_update):
                if entry.target.id == after.id:
                    executor = entry.user
                    if executor.id == self.client.user.id:
                        return
                    if await self.is_protected(after.guild, executor, "anti_channel_update"):
                        await self.take_action_against_high_role(after.guild, executor, "channel update", after)
                    break
        except:
            pass
    
    # ========================= ANTI ROLE CREATE =========================
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        try:
            async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
                if entry.target.id == role.id:
                    executor = entry.user
                    if executor.id == self.client.user.id:
                        return
                    if await self.is_protected(role.guild, executor, "anti_role_create"):
                        try:
                            await role.delete(reason="Antinuke: Unauthorized")
                        except:
                            pass
                        await self.take_action_against_high_role(role.guild, executor, "role creation", role)
                    break
        except:
            pass
    
    # ========================= ANTI ROLE DELETE =========================
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        try:
            async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
                if entry.target.id == role.id:
                    executor = entry.user
                    if executor.id == self.client.user.id:
                        return
                    if await self.is_protected(role.guild, executor, "anti_role_delete"):
                        await self.take_action_against_high_role(role.guild, executor, "role deletion", role)
                    break
        except:
            pass
    
    # ========================= ANTI ROLE UPDATE =========================
    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        try:
            async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_update):
                if entry.target.id == after.id:
                    executor = entry.user
                    if executor.id == self.client.user.id:
                        return
                    if await self.is_protected(after.guild, executor, "anti_role_update"):
                        try:
                            if before.name != after.name:
                                await after.edit(name=before.name, reason="Antinuke: Reverting")
                            if before.permissions != after.permissions:
                                await after.edit(permissions=before.permissions, reason="Antinuke: Reverting")
                        except:
                            pass
                        await self.take_action_against_high_role(after.guild, executor, "role update", after)
                    break
        except:
            pass
    
    # ========================= ANTI WEBHOOK =========================
    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.TextChannel):
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.webhook_create):
                executor = entry.user
                if executor.id == self.client.user.id:
                    return
                if await self.is_protected(channel.guild, executor, "anti_webhook"):
                    try:
                        webhook = entry.target
                        await webhook.delete(reason="Antinuke: Unauthorized")
                    except:
                        pass
                    await self.take_action_against_high_role(channel.guild, executor, "webhook creation", None)
                break
        except:
            pass
    
    # ========================= ANTI EMOJI DELETE =========================
    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before: List[discord.Emoji], after: List[discord.Emoji]):
        if len(before) <= len(after):
            return
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.emoji_delete):
                executor = entry.user
                if executor.id == self.client.user.id:
                    return
                if await self.is_protected(guild, executor, "anti_emoji_delete"):
                    await self.take_action_against_high_role(guild, executor, "emoji deletion", None)
                break
        except:
            pass
    
    # ========================= ANTI GUILD UPDATE =========================
    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        try:
            async for entry in after.audit_logs(limit=1, action=discord.AuditLogAction.guild_update):
                executor = entry.user
                if executor.id == self.client.user.id:
                    return
                if await self.is_protected(after, executor, "anti_guild_update"):
                    await self.take_action_against_high_role(after, executor, "server update", None)
                break
        except:
            pass
    
    # ========================= ANTI PRUNE =========================
    @commands.Cog.listener()
    async def on_member_prune(self, guild: discord.Guild, pruned: int):
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.member_prune):
                executor = entry.user
                if executor.id == self.client.user.id:
                    return
                if await self.is_protected(guild, executor, "anti_prune"):
                    await self.take_action_against_high_role(guild, executor, "member prune", None)
                break
        except:
            pass

async def setup(client):
    await client.add_cog(AntinukeEvents(client))