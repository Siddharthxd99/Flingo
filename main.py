from discord.ext import commands
from discord.ext import tasks
import discord
import os
import json
import pymongo
import aiosqlite
import flingo
from tools import context
from settings.config import *

cache_flags = discord.MemberCacheFlags(voice=True, joined=False)

class Flingo(commands.AutoShardedBot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(
            command_prefix=self.get_prefix,  
            case_insensitive=True,
            intents=intents,
            max_messages=100,
            help_command=None,
            allowed_mentions=discord.AllowedMentions.none(),
            member_cache_flags=cache_flags,
            chunk_guilds_at_startup=False
        )
        self.db_ready = False
        self.config = None

    async def setup_hook(self):
        self.config = await aiosqlite.connect('database/prefix.db')

        await self.config.execute("CREATE TABLE IF NOT EXISTS config (guild INTEGER PRIMARY KEY, prefix TEXT)")
        await self.config.execute("CREATE TABLE IF NOT EXISTS Np (users INTEGER)")  
        await self.config.execute("CREATE TABLE IF NOT EXISTS Owner (user_id INTEGER PRIMARY KEY)") 
        await self.config.commit()
        try:
            async with aiosqlite.connect('np_data.db') as setup_db:
                await setup_db.execute("""
                    CREATE TABLE IF NOT EXISTS setup_data (
                        guild_id INTEGER PRIMARY KEY,
                        data TEXT
                    )
                """)
                await setup_db.commit()
                print("Setup data database initialized")
        except Exception as e:
            print(f"Error initializing setup data database: {e}")
        
        self.db_ready = True

        try:
            await self.load_extension('jishaku')
            print('[Loaded] jishaku')
        except Exception as e:
            print(f'Failed to load jishaku: {e}')
            
        self.owner_ids = [897798897030795294]

        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f'[Loaded] `{filename}`')
                except Exception as e:
                    print(f'Failed to load {filename}: {e}')

        try:
            await self.tree.sync()
            print('Command tree synced')
        except Exception as e:
            print(f'Failed to sync command tree: {e}')

    async def get_prefix(self, message):
        if not self.db_ready or not self.config:
            return "."
            
        try:
            async with self.config.execute("SELECT prefix FROM config WHERE guild = ?", (message.guild.id,)) as cursor:
                guild_row = await cursor.fetchone()

            async with self.config.execute("SELECT users FROM Np") as cursor:
                NP = await cursor.fetchall()

            prefix = guild_row[0] if guild_row else "&"  

            if message.author.id in [int(i[0]) for i in NP]: 
                return sorted(commands.when_mentioned_or('', prefix)(self, message), reverse=True)
            else:
                return commands.when_mentioned_or(prefix)(self, message)
        except Exception as e:
            print(f"Error getting prefix: {e}")
            return "&"

    async def close(self):
        """Clean up resources when bot shuts down"""
        if self.config:
            await self.config.close()
        await super().close()

client = Flingo()
client.cluster = pymongo.MongoClient(flingo.mongo_db_url)
client.db = client.cluster["Flingo"]

@client.event
async def on_ready():
    print(f'Logged in as {client.user} (ID: {client.user.id})')
    await client.change_presence(status=discord.Status.idle, activity=discord.Activity(type=discord.ActivityType.listening, name='&help'))
    
    cache_sweeper.start()

@tasks.loop(minutes=60)
async def cache_sweeper():
    """Clear various caches every hour to save memory"""
    try:
        client._connection._private_channels.clear()
        client._connection._users.clear() 
        client._connection._messages.clear()
        print("Cleared Cache")
    except Exception as e:
        print(f"Error clearing cache: {e}")

@client.event
async def on_command_completion(ctx: commands.Context) -> None:
    """Log command usage to webhook"""
    try:
        full_command_name = ctx.command.qualified_name
        split = full_command_name.split("\n")
        executed_command = str(split[0])
        siddharth = discord.SyncWebhook.from_url(flingo.commandlog_URL)  

        if not ctx.message.content.startswith("&"):
            pcmd = f"`.{ctx.message.content}`"
        else:
            pcmd = f"`{ctx.message.content}`"
            
        embed = discord.Embed(color=0x010505)
        embed.set_author(
            name=f"Executed {executed_command} Command By: {ctx.author}",
            icon_url=ctx.author.display_avatar.url
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.add_field(
            name="Command Name:", value=f"{executed_command}", inline=False
        )
        embed.add_field(
            name="Command Content:", value="{}".format(pcmd), inline=False
        )
        embed.add_field(
            name="Command Executed By:",
            value=f"{ctx.author} | ID: [{ctx.author.id}](https://discord.com/users/{ctx.author.id})",
            inline=False,
        )
        
        if ctx.guild is not None:
            embed.add_field(
                name="Command Executed In:",
                value=f"{ctx.guild.name} | ID: [{ctx.guild.id}](https://discord.com/guilds/{ctx.guild.id})",
                inline=False,
            )
            embed.add_field(
                name="Command Executed In Channel:",
                value=f"{ctx.channel.name} | ID: [{ctx.channel.id}](https://discord.com/channels/{ctx.guild.id}/{ctx.channel.id})",
                inline=False,
            )
        else:
            embed.add_field(
                name="Command Executed In:", value="Direct Message", inline=False
            )
            
        embed.set_footer(
            text=f"Thank you for choosing {client.user.name}",
            icon_url=client.user.display_avatar.url,
        )
        siddharth.send(embed=embed)
        
    except Exception as e:
        print(f"Error in command completion logging: {e}")

async def initialize_setup_database():
    """Initialize the setup data database and create tables"""
    try:
        async with aiosqlite.connect('np_data.db') as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS setup_data (
                    guild_id INTEGER PRIMARY KEY,
                    data TEXT DEFAULT '{}'
                )
            """)
            await db.commit()
            print("Setup database initialized successfully")
            return True
    except Exception as e:
        print(f"Error initializing setup database: {e}")
        return False

async def get_setup_data():
    """Retrieve setup data from database"""
    try:
        await initialize_setup_database()
        
        async with aiosqlite.connect('np_data.db') as db:
            cursor = await db.execute('SELECT guild_id, data FROM setup_data')
            rows = await cursor.fetchall()
            setup_data = {}
            
            if not rows:
                print("No setup data found in database")
                return {}
                
            for guild_id, data_json in rows:
                try:
                    if data_json:
                        setup_data[guild_id] = json.loads(data_json)
                    else:
                        setup_data[guild_id] = {}
                except json.JSONDecodeError as e:
                    print(f"Error parsing JSON for guild {guild_id}: {e}")
                    setup_data[guild_id] = {}
            return setup_data
    except Exception as e:
        print(f"Error getting setup data: {e}")
        return {}

@client.event
async def on_error(event, *args, **kwargs):
    print(f"Error in event {event}: {args}, {kwargs}")

import logging
logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    try:
        client.run(flingo.token)
    except KeyboardInterrupt:
        print("Bot interrupted by user")
    except Exception as e:
        print(f"Error running bot: {e}")
    finally:
        os._exit(0)