import discord
from discord.ext import commands
from typing import Optional, Union
import datetime
import flingo

class ConfirmButton(discord.ui.View):
    def __init__(self, timeout=60):
        super().__init__(timeout=timeout)
        self.value = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.response.defer()


class AFKButton(discord.ui.View):
    def __init__(self, user_id, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id

    @discord.ui.button(label="Global AFK", style=discord.ButtonStyle.primary)
    async def global_afk(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This button is not for you!", ephemeral=True)
            return
        cog = interaction.client.get_cog('Moderation')
        if cog:
            cog.afk_users[interaction.user.id] = {
                'reason': cog.afk_users.get(interaction.user.id, {}).get('reason', 'No Reason Provided'),
                'time': datetime.datetime.now(),
                'global': True
            }
        
        embed = discord.Embed(
            description=f"<a:flingo_tick:1385161850668449843> Your afk has been Set Globally with Reason {cog.afk_users[interaction.user.id]['reason']}",
            color=0x010505
        )
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Server AFK", style=discord.ButtonStyle.success)
    async def server_afk(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This button is not for you!", ephemeral=True)
            return
        cog = interaction.client.get_cog('Moderation')
        if cog:
            cog.afk_users[interaction.user.id] = {
                'reason': cog.afk_users.get(interaction.user.id, {}).get('reason', 'No Reason Provided'),
                'time': datetime.datetime.now(),
                'global': False,
                'guild_id': interaction.guild.id
            }
        
        embed = discord.Embed(
            description=f"<a:flingo_tick:1385161850668449843> Your afk has been Set in this Server with Reason {cog.afk_users[interaction.user.id]['reason']}",
            color=0x010505
        )
        await interaction.response.edit_message(embed=embed, view=None)


class RemoveRoleButton(discord.ui.View):
    def __init__(self, target_user, role, timeout=300):
        super().__init__(timeout=timeout)
        self.target_user = target_user
        self.role = role

    @discord.ui.button(label="Remove Role", style=discord.ButtonStyle.danger)
    async def remove_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.target_user.remove_roles(self.role)
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> Role Removed Successfully!",
                description=f"Removed {self.role.mention} from {self.target_user.mention}",
                color=0x010505
            )
            embed.set_thumbnail(url=self.target_user.display_avatar.url)
            await interaction.response.edit_message(embed=embed, view=None)
        except discord.Forbidden:
            await interaction.response.send_message("<a:flingo_cross:1385161874437312594> I don't have permission to remove this role.", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("<:ByteStrik_Warning:1384843852577247254> Failed to remove role due to a Discord error.", ephemeral=True)


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.afk_users = {}
        self.color = 0x010505
        self.token = flingo.token

    async def cog_check(self, ctx):
        return ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.manage_guild

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="Permission Error",
                description="You don't have the required permissions to use this command.",
                color=discord.Color.black()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.CheckFailure):
            embed = discord.Embed(
                title="Permission Error",
                description="You don't have the required permissions to use this command.",
                color=discord.Color.black()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="Cooldown Error",
                description=f"You're on cooldown! Try again in {error.retry_after:.2f} seconds.",
                color=discord.Color.black()
            )
            await ctx.send(embed=embed)

    async def confirm_action(self, ctx, action: str, target: str) -> bool:
        view = ConfirmButton()
        embed = discord.Embed(
            title="Confirmation",
            description=f"Are you sure you want to {action} {target}?",
            color=discord.Color.black()
        )
        msg = await ctx.send(embed=embed, view=view)
        await view.wait()
        await msg.delete()
        return view.value

    @commands.hybrid_command(
        name="role",
        description="Assign or remove a role from a user."
    )
    @commands.has_permissions(manage_roles=True)
    async def role(self, ctx, member: discord.Member, role: discord.Role):
        """Assign or remove a role from a member."""
        if role in member.roles:
            try:
                await member.remove_roles(role)
                embed = discord.Embed(
                    title="<a:flingo_cross:1385161874437312594> Role Removed Successfully!",
                    description=f"Removed {role.mention} from {member.mention}",
                    color=self.color
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                await ctx.send(embed=embed)
            except discord.Forbidden:
                await ctx.send("<a:flingo_cross:1385161874437312594> I don't have permission to remove this role.")
            except discord.HTTPException:
                await ctx.send("<:ByteStrik_Warning:1384843852577247254> Failed to remove role due to a Discord error.")
        else:
            try:
                await member.add_roles(role)
                embed = discord.Embed(
                    title="<a:flingo_cross:1385161874437312594> Updated Role For " + member.display_name + ".",
                    color=self.color
                )
                embed.add_field(
                    name="Target User:",
                    value=member.display_name,
                    inline=False
                )
                embed.add_field(
                    name="Action:",
                    value="Assigned",
                    inline=False
                )
                embed.add_field(
                    name="Role:",
                    value=f"{role.mention} | {role.id}",
                    inline=False
                )
                embed.add_field(
                    name="",
                    value=f"<a:flingo_tick:1385161850668449843> Role Updated By {ctx.author.display_name}.",
                    inline=False
                )
                embed.set_thumbnail(url=member.display_avatar.url)

                view = RemoveRoleButton(member, role)
                await ctx.send(embed=embed, view=view)
                
            except discord.Forbidden:
                await ctx.send("<a:flingo_cross:1385161874437312594> I don't have permission to assign this role.")
            except discord.HTTPException:
                await ctx.send("<:ByteStrik_Warning:1384843852577247254> Failed to assign role due to a Discord error.")

    @role.error
    async def role_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("<a:flingo_cross:1385161874437312594> You lack the `Manage Roles` permission.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("<a:flingo_cross:1385161874437312594> Invalid member or role. Please check your inputs.")
        else:
            await ctx.send(f"<:ByteStrik_Warning:1384843852577247254> Unexpected error: {error}")

    @commands.hybrid_command(
        name="afk",
        description="Set yourself as AFK with an optional reason."
    )
    async def afk(self, ctx, *, reason: Optional[str] = "No Reason Provided"):
        """Set yourself as AFK with a reason."""
        self.afk_users[ctx.author.id] = {
            'reason': reason,
            'time': datetime.datetime.now(),
            'global': False,
            'guild_id': ctx.guild.id
        }
        embed = discord.Embed(
            title="Flingo Afk System!",
            description=f"Back in a bit?\nHey {ctx.author.mention}\nChoose your AFK Status Type:",
            color=self.color
        )
        embed.add_field(
            name="",
            value=f"<a:flingo_tick:1385161850668449843> Requested By {ctx.author.mention}.",
            inline=False
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        
        view = AFKButton(ctx.author.id)
        await ctx.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.author.id in self.afk_users:
            afk_data = self.afk_users[message.author.id]
            if afk_data.get('global', False) or afk_data.get('guild_id') == message.guild.id:
                afk_duration = datetime.datetime.now() - afk_data['time']
                hours, remainder = divmod(int(afk_duration.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                
                if hours > 0:
                    duration_str = f"{hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    duration_str = f"{minutes}m {seconds}s"
                else:
                    duration_str = f"{seconds}s"
                
                embed = discord.Embed(
                    description=f"<a:flingo_tick:1385161850668449843> Welcome back {message.author.mention}! You were AFK for {duration_str}",
                    color=self.color
                )
                await message.channel.send(embed=embed, delete_after=10)
                del self.afk_users[message.author.id]
        for mention in message.mentions:
            if mention.id in self.afk_users:
                afk_data = self.afk_users[mention.id]
                if afk_data.get('global', False) or afk_data.get('guild_id') == message.guild.id:
                    afk_duration = datetime.datetime.now() - afk_data['time']
                    hours, remainder = divmod(int(afk_duration.total_seconds()), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    
                    if hours > 0:
                        duration_str = f"{hours}h {minutes}m {seconds}s"
                    elif minutes > 0:
                        duration_str = f"{minutes}m {seconds}s"
                    else:
                        duration_str = f"{seconds}s"
                    
                    embed = discord.Embed(
                        description=f"💤 {mention.display_name} is currently AFK: {afk_data['reason']} - {duration_str} ago",
                        color=self.color
                    )
                    await message.channel.send(embed=embed, delete_after=15)

    @commands.hybrid_command(
        name="purge",
        aliases=["pu"],
        description="Purges messages in the channel."
    )
    @commands.has_permissions(manage_messages=True)
    async def purge_messages(self, ctx, amount: Optional[int] = None, member: Optional[Union[discord.Member, discord.User]] = None):
        """Purges a specified number of messages, optionally from a specific user."""
        if amount is None and member is None:
            return await ctx.send("❗ Please specify the number of messages or a specific user.")

        if amount is not None:
            if amount < 1 or amount > 100:
                return await ctx.send("❗ Please specify an amount between 1 and 100.")

        def check(m):
            return m.author == member if member else True

        try:
            deleted = await ctx.channel.purge(limit=amount + 1 if amount else None, check=check)
            count = len(deleted) - (1 if amount else 0)
            desc = f"<a:flingo_tick:1385161850668449843> Successfully purged {count} message(s)."
            if member:
                desc += f" (User: {member})"

            embed = discord.Embed(description=desc, color=self.color)
            await ctx.send(embed=embed, delete_after=5)

        except discord.HTTPException as e:
            await ctx.send(f"<:ByteStrik_Warning:1384843852577247254> An error occurred while purging messages: {e}")

    @commands.hybrid_command(
        name="purge_bots",
        aliases=["pb", "purgebots"],
        description="Purges messages sent by bots."
    )
    @commands.has_permissions(manage_messages=True)
    async def purge_bots(self, ctx, amount: Optional[int] = None):
        """Purges messages from bots in the channel."""
        if amount is None:
            return await ctx.send("❗ Please specify the number of bot messages to purge.")
        if amount < 1 or amount > 100:
            return await ctx.send("❗ Please specify an amount between 1 and 100.")

        def check(m):
            return m.author.bot

        try:
            deleted = await ctx.channel.purge(limit=amount + 1, check=check)
            embed = discord.Embed(
                description=f"<a:flingo_tick:1385161850668449843> Successfully purged {len(deleted) - 1} bot message(s).",
                color=self.color
            )
            await ctx.send(embed=embed, delete_after=5)
        except discord.HTTPException as e:
            await ctx.send(f"<:ByteStrik_Warning:1384843852577247254> An error occurred while purging bot messages: {e}")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def ban(self, ctx, member: discord.Member, *, reason="No reason provided"):
        if await self.confirm_action(ctx, "ban", member.mention):
            try:
                await member.ban(reason=reason)
                embed = discord.Embed(
                    title="Member Banned",
                    description=f"{member.mention} has been banned\nReason: {reason}",
                    color=discord.Color.black()
                )
                await ctx.send(embed=embed)
            except discord.DiscordException:
                await ctx.send("Failed to ban member.")
                
    @commands.command()
    @commands.has_permissions(manage_nicknames=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def nickname(self, ctx, member: discord.Member, *, new_nick: Optional[str] = None):
        """Change or reset a member's nickname."""
        action = f"change the nickname of {member.mention} to `{new_nick}`" if new_nick else f"reset the nickname of {member.mention}"

        if await self.confirm_action(ctx, "set nickname", member.mention):
            try:
                await member.edit(nick=new_nick)
                embed = discord.Embed(
                    title="Nickname Changed",
                    description=f"Successfully changed nickname of {member.mention} to `{new_nick}`." if new_nick else f"Successfully reset nickname of {member.mention}.",
                    color=discord.Color.black()()
                )
                await ctx.send(embed=embed)
            except discord.Forbidden:
                await ctx.send("<a:flingo_cross:1385161874437312594> I don't have permission to change that user's nickname.")
            except discord.HTTPException:
                await ctx.send("<:ByteStrik_Warning:1384843852577247254> Failed to change nickname due to a Discord error.")

    @nickname.error
    async def nickname_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("<a:flingo_cross:1385161874437312594> You lack the `Manage Nicknames` permission.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("<a:flingo_cross:1385161874437312594> Invalid member. Please mention a valid user.")
        else:
            await ctx.send(f"<:ByteStrik_Warning:1384843852577247254> Unexpected error: {error}")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def unban(self, ctx, *, member):
        try:
            banned_users = [entry async for entry in ctx.guild.bans()]
            member_name, member_discriminator = member.split('#')

            for ban_entry in banned_users:
                user = ban_entry.user
                if (user.name, user.discriminator) == (member_name, member_discriminator):
                    if await self.confirm_action(ctx, "unban", f"{user.name}#{user.discriminator}"):
                        await ctx.guild.unban(user)
                        embed = discord.Embed(
                            title="Member Unbanned",
                            description=f"{user.mention} has been unbanned",
                            color=discord.Color.black()
                        )
                        await ctx.send(embed=embed)
                        return
        except discord.DiscordException:
            await ctx.send("Failed to unban member.")

    @commands.command()
    @commands.has_permissions(kick_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def kick(self, ctx, member: discord.Member, *, reason="No reason provided"):
        if await self.confirm_action(ctx, "kick", member.mention):
            try:
                await member.kick(reason=reason)
                embed = discord.Embed(
                    title="Member Kicked",
                    description=f"{member.mention} has been kicked\nReason: {reason}",
                    color=discord.Color.black()()
                )
                await ctx.send(embed=embed)
            except discord.DiscordException:
                await ctx.send("Failed to kick member.")

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def mute(self, ctx, member: discord.Member, duration: Optional[str] = "1h", *, reason="No reason provided"):
        if await self.confirm_action(ctx, "timeout", member.mention):
            try:
                time_units = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
                amount = int(duration[:-1])
                unit = duration[-1].lower()

                if unit not in time_units:
                    await ctx.send("Invalid duration format. Use s for seconds, m for minutes, h for hours, or d for days (e.g., 30m, 1h, 7d).")
                    return

                delta = datetime.timedelta(**{time_units[unit]: amount})

                await member.timeout(delta, reason=reason)
                embed = discord.Embed(
                    title="Member Timed Out",
                    description=f"{member.mention} has been timed out for {duration}\nReason: {reason}",
                    color=discord.Color.black()()
                )
                await ctx.send(embed=embed)
            except ValueError:
                await ctx.send("Invalid duration format. Use a number followed by s/m/h/d (e.g., 30m, 1h, 7d).")
            except discord.DiscordException:
                await ctx.send("Failed to timeout member.")

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def unmute(self, ctx, member: discord.Member):
        if await self.confirm_action(ctx, "remove timeout from", member.mention):
            try:
                await member.timeout(None)
                embed = discord.Embed(
                    title="Timeout Removed",
                    description=f"Timeout has been removed from {member.mention}",
                    color=discord.Color.black()
                )
                await ctx.send(embed=embed)
            except discord.DiscordException:
                await ctx.send("Failed to remove timeout from member.")

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def purge_simple(self, ctx, amount: int):
        if await self.confirm_action(ctx, "purge", f"{amount} messages"):
            try:
                await ctx.channel.purge(limit=amount + 1)
                embed = discord.Embed(
                    title="Messages Purged",
                    description=f"{amount} messages have been purged",
                    color=discord.Color.black()
                )
                await ctx.send(embed=embed, delete_after=5)
            except discord.DiscordException:
                await ctx.send("Failed to purge messages.")

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def lock(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        if await self.confirm_action(ctx, "lock", channel.mention):
            try:
                await channel.set_permissions(ctx.guild.default_role, send_messages=False)
                embed = discord.Embed(
                    title="Channel Locked",
                    description=f"{channel.mention} has been locked",
                    color=discord.Color.black()
                )
                await ctx.send(embed=embed)
            except discord.DiscordException:
                await ctx.send("Failed to lock channel.")

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def unlock(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        if await self.confirm_action(ctx, "unlock", channel.mention):
            try:
                await channel.set_permissions(ctx.guild.default_role, send_messages=True)
                embed = discord.Embed(
                    title="Channel Unlocked",
                    description=f"{channel.mention} has been unlocked",
                    color=discord.Color.black()
                )
                await ctx.send(embed=embed)
            except discord.DiscordException:
                await ctx.send("Failed to unlock channel.")

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def hide(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        if await self.confirm_action(ctx, "hide", channel.mention):
            try:
                await channel.set_permissions(ctx.guild.default_role, view_channel=False)
                embed = discord.Embed(
                    title="Channel Hidden",
                    description=f"{channel.mention} has been hidden",
                    color=discord.Color.black()
                )
                await ctx.send(embed=embed)
            except discord.DiscordException:
                await ctx.send("Failed to hide channel.")

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def unhide(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        if await self.confirm_action(ctx, "unhide", channel.mention):
            try:
                await channel.set_permissions(ctx.guild.default_role, view_channel=True)
                embed = discord.Embed(
                    title="Channel Unhidden",
                    description=f"{channel.mention} has been unhidden",
                    color=discord.Color.black()
                )
                await ctx.send(embed=embed)
            except discord.DiscordException:
                await ctx.send("Failed to unhide channel.")
    @purge_messages.error
    async def purge_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("<a:flingo_cross:1385161874437312594> You lack the `Manage Messages` permission.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("<a:flingo_cross:1385161874437312594> Invalid argument. Please check your inputs.")
        else:
            await ctx.send(f"<:ByteStrik_Warning:1384843852577247254> Unexpected error: {error}")

    @purge_bots.error
    async def purge_bots_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("<a:flingo_cross:1385161874437312594> You lack the `Manage Messages` permission.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("<a:flingo_cross:1385161874437312594> Invalid argument. Please check your inputs.")
        else:
            await ctx.send(f"<:ByteStrik_Warning:1384843852577247254> Unexpected error: {error}")


async def setup(bot):
    await bot.add_cog(Moderation(bot))