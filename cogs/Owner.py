import discord
from discord.ext import commands, tasks
import aiosqlite
import aiohttp
from settings.config import *
import flingo
import asyncio
from discord.ui import View, Button
import sqlite3


def extraowner():
    async def predicate(ctx: commands.Context):
        async with aiosqlite.connect("database/prefix.db") as con:
            async with con.execute("SELECT user_id FROM Owner") as cursor:
                ids_ = await cursor.fetchall()
                if ctx.author.id in [i[0] for i in ids_]:
                    return True
                else:
                    return False

    return commands.check(predicate)


class owner(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.color = color

    @commands.Cog.listener()
    async def on_ready(self):
        print("Owner Is Ready")

    @commands.hybrid_group(hidden=True, invoke_without_command=True)
    @commands.is_owner()
    async def owner(self, ctx):
        await ctx.reply("Lund lele")

    @owner.command(name="add")
    @commands.is_owner()
    async def ownerkrdu(self, ctx, user: discord.User):
        async with aiosqlite.connect("database/prefix.db") as con:
            async with con.execute("SELECT user_id FROM Owner") as cursor:
                re = await cursor.fetchall()
                if re != []:
                    ids = [int(i[0]) for i in re]
                    if user.id in ids:
                        embed = discord.Embed(
                            description=f"That user is already in owner list.", color=self.color
                        )
                        await ctx.reply(embed=embed, mention_author=False)
                        return
            await con.execute("INSERT INTO Owner(user_id) VALUES(?)", (user.id,))
            embed = discord.Embed(
                description=f"Successfully added **{user}** in owner list.",
                color=self.color,
            )
            await ctx.reply(embed=embed, mention_author=False)
            await con.commit()

    @owner.command(name="remove")
    @commands.is_owner()
    async def ownerhatadu(self, ctx, user: discord.User):
        async with aiosqlite.connect("database/prefix.db") as con:
            async with con.execute("SELECT user_id FROM Owner") as cursor:
                re = await cursor.fetchall()
                if re == []:
                    embed = discord.Embed(
                        description=f"That user is not in owner list.", color=self.color
                    )
                    await ctx.reply(embed=embed, mention_author=False)
                    return
            ids = [int(i[0]) for i in re]
            if user.id not in ids:
                embed = discord.Embed(
                    description=f"That user is not in owner list.", color=self.color
                )
                await ctx.reply(embed=embed, mention_author=False)
                return
            await con.execute("DELETE FROM Owner WHERE user_id = ?", (user.id,))
            embed = discord.Embed(
                description=f"Successfully removed **{user}** from owner list.",
                color=self.color,
            )
            await ctx.reply(embed=embed, mention_author=False)
            await con.commit()

    @commands.hybrid_group(
        description="Noprefix Commands",
        aliases=["np"],
        invoke_without_command=True,
        hidden=True,
    )
    @commands.check_any(commands.is_owner(), extraowner())
    async def noprefix(self, ctx):
        await ctx.reply("")

    @noprefix.command(name="add", description="Adds a user to noprefix.")
    @commands.check_any(commands.is_owner(), extraowner())
    async def noprefix_add(self, ctx, user: discord.User):
        async with aiosqlite.connect("database/prefix.db") as con:
            async with con.execute("SELECT users FROM Np") as cursor:
                result = await cursor.fetchall()
                if user.id not in [int(i[0]) for i in result]:
                    await con.execute(f"INSERT INTO Np(users) VALUES(?)", (user.id,))
                    embed = discord.Embed(
                        description=f"Successfully added **{user}** to no prefix.",
                        color=self.color,
                    )
                    await ctx.reply(embed=embed, mention_author=False)
                    
                    async with aiohttp.ClientSession() as session:
                        webhook = discord.Webhook.from_url(url=flingo.np_hook, session=session)
                        embed = discord.Embed(
                            title="No Prefix Added",
                            description=f"**Action By:** {ctx.author} ({ctx.author.id})\n**User:** {user} ({user.id})",
                            color=self.color,
                        )
                        await webhook.send(embed=embed)
                else:
                    embed = discord.Embed(
                        description=f"That user is already in no prefix.", color=self.color
                    )
                    await ctx.reply(embed=embed, mention_author=False)
            await con.commit()

    @noprefix.command(name="remove", description="Removes a user from noprefix.")
    @commands.check_any(commands.is_owner(), extraowner())
    async def noprefix_remove(self, ctx, user: discord.User):
        async with aiosqlite.connect("database/prefix.db") as con:
            async with con.execute("SELECT users FROM Np") as cursor:
                result = await cursor.fetchall()
                if user.id in [int(i[0]) for i in result]:
                    await con.execute(f"DELETE FROM Np WHERE users = ?", (user.id,))
                    embed = discord.Embed(
                        description=f"Successfully removed **{user}** from no prefix.",
                        color=self.color,
                    )
                    await ctx.reply(embed=embed, mention_author=False)
                    
                    async with aiohttp.ClientSession() as session:
                        webhook = discord.Webhook.from_url(url=flingo.np_hook, session=session)
                        embed = discord.Embed(
                            title="No Prefix Removed",
                            description=f"**Action By:** {ctx.author} ({ctx.author.id})\n**User:** {user} ({user.id})",
                            color=self.color,
                        )
                        await webhook.send(embed=embed)
                else:
                    embed = discord.Embed(
                        description=f"That user isn't in no prefix.", color=self.color
                    )
                    await ctx.reply(embed=embed, mention_author=False)
            await con.commit()

    @noprefix.command(name="list", description="Shows all users with no prefix access.")
    @commands.check_any(commands.is_owner(), extraowner())
    async def noprefix_list(self, ctx):
        async with aiosqlite.connect("database/prefix.db") as con:
            async with con.execute("SELECT users FROM Np") as cursor:
                result = await cursor.fetchall()
                if not result:
                    embed = discord.Embed(
                        description="No users are currently in the no prefix list.",
                        color=self.color
                    )
                    return await ctx.reply(embed=embed, mention_author=False)

                users = []
                for row in result:
                    user_id = int(row[0])
                    user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                    users.append(f"`-` {user} | `{user_id}`")

                embed = discord.Embed(
                    title="No Prefix Users",
                    description="\n".join(users),
                    color=self.color
                )
                await ctx.reply(embed=embed, mention_author=False)




    @commands.command(aliases=["guildleave"])
    @commands.check_any(commands.is_owner())
    async def gleave(self, ctx, guild_id: int):
            guild = self.client.get_guild(guild_id)
            if guild is None:
                guild = ctx.guild

            await guild.leave()
            await ctx.send(f"Left guild: {guild.name}")


    @commands.command(aliases=["link"])
    @commands.check_any(commands.is_owner())
    async def ginv(self, ctx, guild_id: int):
        guild = self.client.get_guild(guild_id)

        if guild is None:
            await ctx.send("Guild not found.")
            return

        if not ctx.me.guild_permissions.create_instant_invite:
            await ctx.send("I don't have permission to create invites in this guild.")
            return

        for channel in guild.text_channels:
            try:
                invite_link = await channel.create_invite(unique=False)
                await ctx.send(f"**Here is the Invite link:** \n {invite_link}")
                return  
            except Exception as e:
                await ctx.send(f"An error occurred: {e}")
                continue
        await ctx.send("Couldn't create an invite for this server.")

class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.allowed_users = [897798897030795294]
        self.db_path = 'guild_blacklist.db'
        self.init_database()

    def is_owner():
        def predicate(ctx):
            return ctx.author.id in ctx.cog.allowed_users
        return commands.check(predicate)

    def init_database(self):
        """Initialize the SQLite database and create the blacklist table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guild_blacklist (
                guild_id INTEGER PRIMARY KEY
            )
        ''')
        conn.commit()
        conn.close()

    def load_blacklist(self):
        """Load the blacklist from SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT guild_id FROM guild_blacklist')
        blacklist = [row[0] for row in cursor.fetchall()]
        conn.close()
        return blacklist

    def save_blacklist_item(self, guild_id):
        """Add a guild ID to the blacklist in SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO guild_blacklist (guild_id) VALUES (?)', (guild_id,))
        conn.commit()
        conn.close()

    def remove_blacklist_item(self, guild_id):
        """Remove a guild ID from the blacklist in SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM guild_blacklist WHERE guild_id = ?', (guild_id,))
        conn.commit()
        conn.close()

    def is_guild_blacklisted(self, guild_id):
        """Check if a guild ID is in the blacklist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM guild_blacklist WHERE guild_id = ?', (guild_id,))
        result = cursor.fetchone() is not None
        conn.close()
        return result

    @property
    def guild_blacklist(self):
        """Property to get the current blacklist."""
        return self.load_blacklist()

    @commands.command(name='ginvite')
    @is_owner()
    async def generate_invite(self, ctx, guild_id: int):
        guild = self.bot.get_guild(guild_id)
        if guild:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).create_instant_invite:
                    invite = await channel.create_invite(max_age=300)
                    await ctx.send(f"Invite link: {invite.url}")
                    return
            await ctx.send("Could not create an invite link. No suitable channel found.")
        else:
            await ctx.send("The bot is not in a guild with that ID.")

    @commands.command(name='gleave')
    @is_owner()
    async def leave_guild(self, ctx, guild_id: int):
        guild = self.bot.get_guild(guild_id)
        if guild:
            await guild.leave()
            await ctx.send(f"Left the guild: {guild.name} ({guild.id})")
        else:
            await ctx.send("The bot is not in a guild with that ID.")

    @commands.command(name='g-list')
    @is_owner()
    async def list_guilds(self, ctx):
        guilds = sorted(self.bot.guilds, key=lambda g: g.member_count, reverse=True)
        pages = [guilds[i:i + 10] for i in range(0, len(guilds), 10)]
        
        view = GuildListView(pages)
        view.message = await ctx.send(embed=view.create_embed(), view=view)

    @commands.command(name='gbl_add')
    @is_owner()
    async def gbl_add(self, ctx, guild_id: int):
        if not self.is_guild_blacklisted(guild_id):
            self.save_blacklist_item(guild_id)
            await ctx.send(f"Added guild ID {guild_id} to the blacklist.")
            guild = self.bot.get_guild(guild_id)
            if guild:
                await guild.leave()
                await ctx.send(f"Left the blacklisted guild: {guild.name} ({guild.id})")
        else:
            await ctx.send("Guild ID is already in the blacklist.")

    @commands.command(name='gbl_remove')
    @is_owner()
    async def gbl_remove(self, ctx, guild_id: int):
        if self.is_guild_blacklisted(guild_id):
            self.remove_blacklist_item(guild_id)
            await ctx.send(f"Removed guild ID {guild_id} from the blacklist.")
        else:
            await ctx.send("Guild ID is not in the blacklist.")

    @commands.command()
    @is_owner()
    async def globalban(self, ctx, *, user: discord.User = None):
        if user is None:
            return await ctx.send("You need to define the user")

        banned_guilds = []

        for guild in self.bot.guilds:
            member = guild.get_member(user.id)
            if member:
                await guild.ban(user, reason="This user has been banned for violating Discord's terms of service, specifically engaging in nuking servers. Such actions severely disrupt server integrity and compromise user experience. As a result, the user has been permanently banned from our community to uphold our standards of safety and respect.")
                banned_guilds.append(guild.name)

        if banned_guilds:
            banned_guilds_str = "\n".join(banned_guilds)
            await ctx.send(f"Successfully banned {user} from the following servers:\n{banned_guilds_str}")
        else:
            await ctx.send(f"{user} was not found in any of the servers the bot is in.")

    @tasks.loop(minutes=30)
    async def leave_blacklisted_guilds(self):
        blacklisted_ids = self.guild_blacklist
        for guild in self.bot.guilds:
            if guild.id in blacklisted_ids:
                try:
                    await guild.leave()
                    print(f"Left blacklisted guild: {guild.name} ({guild.id})")
                    await asyncio.sleep(2)
                except discord.HTTPException as e:
                    print(f"Failed to leave guild {guild.name} ({guild.id}): {e}")
                    await asyncio.sleep(10)

    @leave_blacklisted_guilds.before_loop
    async def before_leave_blacklisted_guilds(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Automatically leave guild if it's blacklisted."""
        if self.is_guild_blacklisted(guild.id):
            try:
                await guild.leave()
                print(f"Left blacklisted guild on join: {guild.name} ({guild.id})")
            except discord.HTTPException as e:
                print(f"Failed to leave blacklisted guild on join {guild.name} ({guild.id}): {e}")

class GuildListView(View):
    def __init__(self, pages):
        super().__init__()
        self.pages = pages
        self.current_page = 0
        self.message = None

        self.rewind_button = Button(label="Rewind", style=discord.ButtonStyle.primary)
        self.rewind_button.callback = self.rewind
        self.add_item(self.rewind_button)

        self.close_button = Button(label="Close", style=discord.ButtonStyle.danger)
        self.close_button.callback = self.close
        self.add_item(self.close_button)

        self.forward_button = Button(label="Forward", style=discord.ButtonStyle.primary)
        self.forward_button.callback = self.forward
        self.add_item(self.forward_button)

    def create_embed(self):
        total_pages = len(self.pages)
        embed = discord.Embed(
            title=f"Guilds the bot is in ({len(self.pages[self.current_page])} guilds)",
            description=f"Page {self.current_page + 1}/{total_pages}",
            color=discord.Colour(0x010505)
        )
        for guild in self.pages[self.current_page]:
            member_count = guild.member_count
            embed.add_field(
                name=guild.name,
                value=f"ID: {guild.id}\nMembers: {member_count}",
                inline=False
            )
        return embed

    async def rewind(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
        await self.update_embed(interaction)

    async def forward(self, interaction: discord.Interaction):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
        await self.update_embed(interaction)

    async def close(self, interaction: discord.Interaction):
        await interaction.message.delete()

    async def update_embed(self, interaction: discord.Interaction):
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)


async def setup(client):
    await client.add_cog(owner(client))