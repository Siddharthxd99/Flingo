import discord
from discord.ext import commands
import sqlite3
import asyncio
import datetime

COOLDOWN_TIME = 2

class Moderation2(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.sniped_messages = {}
        
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Listen for deleted messages and store them for snipe command"""
        if message.author.bot:
            return
        self.sniped_messages[message.channel.id] = {
            'author': message.author,
            'author_id': message.author.id,
            'content': message.content,
            'deleted_at': datetime.datetime.utcnow(),
            'message_id': message.id
        }
    
    @commands.command(name='snipe')
    @commands.cooldown(1, COOLDOWN_TIME, commands.BucketType.channel)
    async def snipe(self, ctx):
        """Show the most recently deleted message in the channel"""
        channel_id = ctx.channel.id
        
        if channel_id not in self.sniped_messages:
            embed = discord.Embed(
                title="<a:flingo_cross:1385161874437312594> No Recently Deleted Messages",
                description="There are no recently deleted messages to snipe in this channel.",
                color=discord.Color.black()
            )
            await ctx.send(embed=embed)
            return
        
        sniped_data = self.sniped_messages[channel_id]
        author = sniped_data['author']
        content = sniped_data['content']
        deleted_at = sniped_data['deleted_at']
        time_diff = datetime.datetime.utcnow() - deleted_at
        
        if time_diff.total_seconds() < 60:
            time_ago = f"{int(time_diff.total_seconds())} seconds ago"
        elif time_diff.total_seconds() < 3600:
            time_ago = f"{int(time_diff.total_seconds() / 60)} minutes ago"
        else:
            time_ago = f"{int(time_diff.total_seconds() / 3600)} hours ago"
        embed = discord.Embed(
            title="🔍 Recently Deleted Messages",
            color=discord.Color.black()()
        )
        embed.add_field(
            name="Author Name:", 
            value=f"{author.display_name}", 
            inline=False
        )
        embed.add_field(
            name="Author ID:", 
            value=f"{author.id}", 
            inline=False
        )
        embed.add_field(
            name="Author Mention:", 
            value=f"{author.mention}", 
            inline=False
        )
        embed.add_field(
            name="Deleted:", 
            value=time_ago, 
            inline=False
        )
        embed.add_field(
            name="Deleted Messages:", 
            value="1", 
            inline=False
        )
        embed.add_field(
            name="Message Content",
            value=f"Content: {content[:1000]}{'...' if len(content) > 1000 else ''}",
            inline=False
        )
        embed.set_thumbnail(url=author.display_avatar.url)
        embed.set_footer(
            text=f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )
        
        await ctx.send(embed=embed)
    
    @snipe.error
    async def snipe_error(self, ctx, error):
        """Handle snipe command errors"""
        if isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="<:GettoClock:1384851204772986890> Command on Cooldown",
                description=f"Please wait {error.retry_after:.1f} seconds before using this command again.",
                color=discord.Color.black()()
            )
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Moderation2(bot))