import traceback
from typing import Optional
from discord.ext import commands
import discord
import aiohttp
import datetime
import flingo
from settings.config import color
import discord
from discord.ext import commands
import datetime
import asyncio

tick = "<a:SageCheck:1250852491768369172>"
excla = "<:Sageexclamation:1250851224886968470>"

class Errors(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                description=(f"{excla} | You're missing a required argument: `{error.param.name}`."),
                color=0x2f3136
            )
            await ctx.reply(embed=embed, delete_after=10)

        elif isinstance(error, commands.NotOwner):
            embed = discord.Embed(
                description=f"{excla} | You Can't Use it. This Command Can Only be used by the Owner and Admin of the bot.",
                color=0x2f3136
            )
            await ctx.send(embed=embed, delete_after=5)

        elif isinstance(error, commands.NoPrivateMessage):
            embed = discord.Embed(
                description=f"{excla} | You Cannot Use My Commands in DMs.",
                color=0x2f3136
            )
            await ctx.reply(embed=embed, delete_after=5)

        elif isinstance(error, commands.MissingPermissions):
            missing_perms = ', '.join(error.missing_permissions)
            embed = discord.Embed(
                description=f"{excla} | You need the following permissions to run this command: `{missing_perms}`",
                color=0x2f3136
            )
            await ctx.reply(embed=embed, delete_after=5)

        elif isinstance(error, commands.BotMissingPermissions):
            missing_perms = ', '.join(error.missing_permissions)
            embed = discord.Embed(
                description=f"{excla} | Bot Needs the following Permissions to run this Command: `{missing_perms}`",
                color=0x2f3136
            )
            await ctx.reply(embed=embed, delete_after=5)


async def setup(bot):
    await bot.add_cog(Errors(bot))
    print("Ignore cog successfully loaded.")