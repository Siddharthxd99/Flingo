import discord
from discord.ext import commands
from discord.ui import Button, View
from settings.config import color

class Ready(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.client.user or message.author.bot:
            return

        if self.client.user.mentioned_in(message):
            mentions = [mention for mention in message.mentions if mention == self.client.user]
            if mentions and message.content.strip() == mentions[0].mention:
                if message.guild:
                    async with self.client.config.execute("SELECT prefix FROM config WHERE guild = ?", (message.guild.id,)) as cursor:
                        guild_row = await cursor.fetchone()
                        guild_prefix = guild_row[0] if guild_row and guild_row[0] else '&'  
                else:
                    guild_prefix = '&'  

                embed = discord.Embed(
                    description=f"Hey {message.author.mention}, my prefix in this server is `{guild_prefix}`\n\nWhat would you like to do today?\nUse `{guild_prefix}help` to start your journey.",
                    color=color
                )

                view = View()

                await message.channel.send(embed=embed, view=view)

async def setup(client):
    await client.add_cog(Ready(client))
