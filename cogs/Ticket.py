import discord
from discord.ext import commands
from discord.ui import View, Select, Button
import asyncio
import aiosqlite
import datetime


class TicketDatabase:
    def __init__(self, db_path="tickets.db"):
        self.db_path = db_path
    
    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Guild configs table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS guild_configs (
                    guild_id INTEGER PRIMARY KEY,
                    panel_channel INTEGER,
                    panel_message_id INTEGER,
                    ticket_category INTEGER,
                    support_role INTEGER,
                    transcript_channel INTEGER
                )
            """)
            
            # Check if transcript_channel column exists, if not add it
            try:
                await db.execute("SELECT transcript_channel FROM guild_configs LIMIT 1")
            except:
                # Column doesn't exist, add it
                await db.execute("ALTER TABLE guild_configs ADD COLUMN transcript_channel INTEGER")
            
            # Tickets table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    channel_id INTEGER,
                    owner_id INTEGER,
                    owner_name TEXT,
                    created_at TEXT,
                    closed_at TEXT,
                    closed_by INTEGER,
                    status TEXT DEFAULT 'open'
                )
            """)
            
            # Ticket messages table (for transcript)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ticket_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER,
                    author_id INTEGER,
                    author_name TEXT,
                    content TEXT,
                    timestamp TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
                )
            """)
            
            await db.commit()
    
    async def get_guild_config(self, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT panel_channel, panel_message_id, ticket_category, support_role, transcript_channel FROM guild_configs WHERE guild_id = ?",
                (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'panel_channel': row[0],
                        'panel_message_id': row[1],
                        'ticket_category': row[2],
                        'support_role': row[3],
                        'transcript_channel': row[4]
                    }
                return {}
    
    async def get_all_guild_configs(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT guild_id, panel_channel, panel_message_id, ticket_category, support_role, transcript_channel FROM guild_configs"
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        'guild_id': row[0],
                        'panel_channel': row[1],
                        'panel_message_id': row[2],
                        'ticket_category': row[3],
                        'support_role': row[4],
                        'transcript_channel': row[5]
                    }
                    for row in rows
                ]
    
    async def update_guild_config(self, guild_id, **kwargs):
        async with aiosqlite.connect(self.db_path) as db:
            config = await self.get_guild_config(guild_id)
            config.update(kwargs)
            
            await db.execute("""
                INSERT OR REPLACE INTO guild_configs 
                (guild_id, panel_channel, panel_message_id, ticket_category, support_role, transcript_channel)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                guild_id,
                config.get('panel_channel'),
                config.get('panel_message_id'),
                config.get('ticket_category'),
                config.get('support_role'),
                config.get('transcript_channel')
            ))
            await db.commit()
    
    async def clear_guild_config(self, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM guild_configs WHERE guild_id = ?", (guild_id,))
            await db.commit()
    
    async def create_ticket(self, guild_id, channel_id, owner_id, owner_name):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO tickets (guild_id, channel_id, owner_id, owner_name, created_at, status)
                VALUES (?, ?, ?, ?, ?, 'open')
            """, (guild_id, channel_id, owner_id, owner_name, datetime.datetime.utcnow().isoformat()))
            await db.commit()
            return cursor.lastrowid
    
    async def close_ticket(self, channel_id, closed_by):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE tickets 
                SET closed_at = ?, closed_by = ?, status = 'closed'
                WHERE channel_id = ? AND status = 'open'
            """, (datetime.datetime.utcnow().isoformat(), closed_by, channel_id))
            await db.commit()
    
    async def get_ticket_by_channel(self, channel_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT ticket_id, owner_id, owner_name FROM tickets WHERE channel_id = ? AND status = 'open'",
                (channel_id,)
            ) as cursor:
                return await cursor.fetchone()
    
    async def get_all_open_tickets(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT ticket_id, guild_id, channel_id, owner_id, owner_name FROM tickets WHERE status = 'open'"
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        'ticket_id': row[0],
                        'guild_id': row[1],
                        'channel_id': row[2],
                        'owner_id': row[3],
                        'owner_name': row[4]
                    }
                    for row in rows
                ]
    
    async def has_open_ticket(self, guild_id, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT channel_id FROM tickets WHERE guild_id = ? AND owner_id = ? AND status = 'open'",
                (guild_id, user_id)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
    
    async def get_ticket_transcript(self, ticket_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT author_name, content, timestamp FROM ticket_messages WHERE ticket_id = ? ORDER BY timestamp ASC",
                (ticket_id,)
            ) as cursor:
                return await cursor.fetchall()
    
    async def log_message(self, ticket_id, author_id, author_name, content):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO ticket_messages (ticket_id, author_id, author_name, content, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (ticket_id, author_id, author_name, content, datetime.datetime.utcnow().isoformat()))
            await db.commit()
    
    async def get_ticket_stats(self, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM tickets WHERE guild_id = ? AND status = 'open'",
                (guild_id,)
            ) as cursor:
                open_count = (await cursor.fetchone())[0]
            
            async with db.execute(
                "SELECT COUNT(*) FROM tickets WHERE guild_id = ? AND status = 'closed'",
                (guild_id,)
            ) as cursor:
                closed_count = (await cursor.fetchone())[0]
            
            return {'open': open_count, 'closed': closed_count, 'total': open_count + closed_count}


class ChannelSelect(Select):
    def __init__(self, cog, ctx):
        options = [discord.SelectOption(label=ch.name, value=str(ch.id)) for ch in ctx.guild.text_channels]
        super().__init__(placeholder="Select panel channel...", options=options)
        self.cog = cog
        self.ctx = ctx
    
    async def callback(self, interaction: discord.Interaction):
        await self.cog.db.update_guild_config(self.ctx.guild.id, panel_channel=int(self.values[0]))
        await interaction.response.send_message("Panel channel selected.", ephemeral=True)


class CategorySelect(Select):
    def __init__(self, cog, ctx):
        options = [discord.SelectOption(label=cat.name, value=str(cat.id)) for cat in ctx.guild.categories]
        super().__init__(placeholder="Select ticket category...", options=options)
        self.cog = cog
        self.ctx = ctx
    
    async def callback(self, interaction: discord.Interaction):
        await self.cog.db.update_guild_config(self.ctx.guild.id, ticket_category=int(self.values[0]))
        await interaction.response.send_message("Ticket category selected.", ephemeral=True)


class SupporterRoleSelect(Select):
    def __init__(self, cog, ctx):
        options = [
            discord.SelectOption(label=role.name, value=str(role.id))
            for role in ctx.guild.roles if not role.is_default() and not role.is_bot_managed()
        ]
        super().__init__(placeholder="Select supporter role...", options=options)
        self.cog = cog
        self.ctx = ctx
    
    async def callback(self, interaction: discord.Interaction):
        await self.cog.db.update_guild_config(self.ctx.guild.id, support_role=int(self.values[0]))
        await interaction.response.send_message("Supporter role selected.", ephemeral=True)


class TranscriptChannelSelect(Select):
    def __init__(self, cog, ctx):
        options = [discord.SelectOption(label=ch.name, value=str(ch.id)) for ch in ctx.guild.text_channels]
        super().__init__(placeholder="Select transcript channel...", options=options)
        self.cog = cog
        self.ctx = ctx
    
    async def callback(self, interaction: discord.Interaction):
        await self.cog.db.update_guild_config(self.ctx.guild.id, transcript_channel=int(self.values[0]))
        await interaction.response.send_message("Transcript channel selected.", ephemeral=True)


class TicketSetupView(View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=120)
        self.cog = cog
        self.ctx = ctx
        self.add_item(ChannelSelect(cog, ctx))
        self.add_item(CategorySelect(cog, ctx))
        self.add_item(SupporterRoleSelect(cog, ctx))
        self.add_item(TranscriptChannelSelect(cog, ctx))


    @discord.ui.button(label="Finish Setup", style=discord.ButtonStyle.green, custom_id="ticketsetup_finish")
    async def finish_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = await self.cog.db.get_guild_config(self.ctx.guild.id)
        
        if config.get('panel_message_id'):
            await interaction.response.send_message("A ticket panel is already set up in this server.", ephemeral=True)
            return


        await interaction.response.defer(ephemeral=True)
        
        # Check all required fields
        panel_channel_id = config.get('panel_channel')
        ticket_category_id = config.get('ticket_category')
        support_role_id = config.get('support_role')
        transcript_channel_id = config.get('transcript_channel')
        
        missing_fields = []
        if not panel_channel_id:
            missing_fields.append("Panel Channel")
        if not ticket_category_id:
            missing_fields.append("Ticket Category")
        if not support_role_id:
            missing_fields.append("Supporter Role")
        if not transcript_channel_id:
            missing_fields.append("Transcript Channel")
        
        if missing_fields:
            await interaction.followup.send(
                f"❌ Please select all required fields:\n• {', '.join(missing_fields)}",
                ephemeral=True
            )
            return
        
        panel_channel = self.ctx.guild.get_channel(panel_channel_id)
        embed = discord.Embed(
            title="Get Support!",
            description="To create a ticket use the Create ticket button\n\nrem - Ticketing without clutter",
            color=discord.Color.blue()
        )
        view = TicketPanelView(self.cog)
        message = await panel_channel.send(embed=embed, view=view)
        
        await self.cog.db.update_guild_config(self.ctx.guild.id, panel_message_id=message.id)
        await interaction.followup.send("✅ Ticket panel sent successfully!", ephemeral=True)


class TicketPanelView(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog


    @discord.ui.button(label="Create ticket", style=discord.ButtonStyle.primary, custom_id="ticket_create_persistent")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        
        # Check if user already has an open ticket
        existing_channel_id = await self.cog.db.has_open_ticket(guild.id, interaction.user.id)
        if existing_channel_id:
            existing_channel = guild.get_channel(existing_channel_id)
            if existing_channel:
                await interaction.followup.send(
                    f"You already have an open ticket: {existing_channel.mention}\nPlease close it before creating a new one.",
                    ephemeral=True
                )
                return
        
        config = await self.cog.db.get_guild_config(guild.id)
        
        category_id = config.get('ticket_category')
        category = guild.get_channel(category_id) if category_id else None
        support_role_id = config.get('support_role')
        support_role = guild.get_role(support_role_id) if support_role_id else None


        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)


        ticket_channel = await guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )
        
        # Save ticket to database
        ticket_id = await self.cog.db.create_ticket(
            guild.id, 
            ticket_channel.id, 
            interaction.user.id, 
            str(interaction.user)
        )
        
        embed = discord.Embed(
            title="Support will be with you shortly.",
            description="To close this press the close button.",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Ticket ID: {ticket_id}")
        view = TicketActionView(self.cog, ticket_channel.id, interaction.user.id, ticket_id, guild.id)
        
        content = f"Welcome {interaction.user.mention}"
        allowed_mentions = discord.AllowedMentions(users=[interaction.user], roles=[])
        
        if support_role:
            content += f"\n{support_role.mention}, you have a new ticket to handle!"
            allowed_mentions = discord.AllowedMentions(users=[interaction.user], roles=[support_role])


        await ticket_channel.send(
            content=content, 
            embed=embed, 
            view=view,
            allowed_mentions=allowed_mentions
        )
        await interaction.followup.send(f"Ticket created: {ticket_channel.mention}", ephemeral=True)


class TicketActionView(View):
    def __init__(self, cog, channel_id, owner_id, ticket_id, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel_id = channel_id
        self.owner_id = owner_id
        self.ticket_id = ticket_id
        self.guild_id = guild_id


    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="ticket_close_persistent", row=0)
    async def close_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check for moderator permissions
        if not (interaction.user.guild_permissions.administrator or 
                interaction.user.guild_permissions.manage_messages or 
                interaction.guild.owner_id == interaction.user.id):
            await interaction.response.send_message("Only moderators can close tickets.", ephemeral=True)
            return
        
        # Show close options
        view = TicketCloseOptionsView(self.cog, self.channel_id, self.owner_id, self.ticket_id, self.guild_id)
        await interaction.response.send_message(
            "**Choose an action:**",
            view=view,
            ephemeral=True
        )


class TicketCloseView(View):
    def __init__(self, cog, channel_id, owner_id, ticket_id, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel_id = channel_id
        self.owner_id = owner_id
        self.ticket_id = ticket_id
        self.guild_id = guild_id


    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="ticket_close_persistent")
    async def close_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check for moderator permissions
        if not (interaction.user.guild_permissions.administrator or 
                interaction.user.guild_permissions.manage_messages or 
                interaction.guild.owner_id == interaction.user.id):
            await interaction.response.send_message("Only moderators can close tickets.", ephemeral=True)
            return
        
        # Show close options
        view = TicketCloseOptionsView(self.cog, self.channel_id, self.owner_id, self.ticket_id, self.guild_id)
        await interaction.response.send_message(
            "**Choose an action:**",
            view=view,
            ephemeral=True
        )


class TicketCloseOptionsView(View):
    def __init__(self, cog, channel_id, owner_id, ticket_id, guild_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.channel_id = channel_id
        self.owner_id = owner_id
        self.ticket_id = ticket_id
        self.guild_id = guild_id


    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger)
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        # Get owner and channel
        owner = interaction.guild.get_member(self.owner_id)
        channel = interaction.guild.get_channel(self.channel_id)
        
        if not channel:
            await interaction.followup.send("Channel not found.", ephemeral=True)
            return
        
        # Close ticket in database
        await self.cog.db.close_ticket(self.channel_id, interaction.user.id)
        
        # Send proper mention
        if owner:
            await channel.send(
                f"{owner.mention}, your ticket will be deleted in 2 minutes.",
                allowed_mentions=discord.AllowedMentions(users=True)
            )
        else:
            await channel.send(
                f"<@{self.owner_id}>, your ticket will be deleted in 2 minutes."
            )
        
        await asyncio.sleep(120)
        try:
            await channel.delete()
        except:
            pass


    @discord.ui.button(label="Send Transcript", style=discord.ButtonStyle.secondary)
    async def send_transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        # Get config
        config = await self.cog.db.get_guild_config(self.guild_id)
        transcript_channel_id = config.get('transcript_channel')
        
        if not transcript_channel_id:
            await interaction.followup.send("Transcript channel is not configured.", ephemeral=True)
            return
        
        transcript_channel = interaction.guild.get_channel(transcript_channel_id)
        if not transcript_channel:
            await interaction.followup.send("Transcript channel not found.", ephemeral=True)
            return
        
        # Get ticket info
        ticket_data = await self.cog.db.get_ticket_by_channel(self.channel_id)
        if not ticket_data:
            await interaction.followup.send("Ticket data not found.", ephemeral=True)
            return
        
        # Get transcript messages
        messages = await self.cog.db.get_ticket_transcript(self.ticket_id)
        
        # Build transcript text
        owner = interaction.guild.get_member(self.owner_id)
        owner_name = str(owner) if owner else f"User ID: {self.owner_id}"
        
        transcript_text = f"**Ticket Transcript**\n"
        transcript_text += f"**Ticket ID:** {self.ticket_id}\n"
        transcript_text += f"**Owner:** {owner_name}\n"
        transcript_text += f"**Channel:** <#{self.channel_id}>\n"
        transcript_text += f"**Sent by:** {interaction.user.mention}\n"
        transcript_text += f"**Total Messages:** {len(messages)}\n"
        transcript_text += f"\n{'='*50}\n\n"
        
        for msg in messages:
            author_name, content, timestamp = msg
            # Format timestamp
            dt = datetime.datetime.fromisoformat(timestamp)
            formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            transcript_text += f"[{formatted_time}] {author_name}: {content}\n"
        
        # Send as file if too long, otherwise as embed
        if len(transcript_text) > 4000:
            import io
            file = discord.File(io.BytesIO(transcript_text.encode()), filename=f"transcript_{self.ticket_id}.txt")
            embed = discord.Embed(
                title=f"Ticket Transcript #{self.ticket_id}",
                description=f"**Owner:** {owner_name}\n**Sent by:** {interaction.user.mention}",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.utcnow()
            )
            await transcript_channel.send(embed=embed, file=file)
        else:
            embed = discord.Embed(
                title=f"Ticket Transcript #{self.ticket_id}",
                description=transcript_text,
                color=discord.Color.blue(),
                timestamp=datetime.datetime.utcnow()
            )
            await transcript_channel.send(embed=embed)
        
        await interaction.followup.send(f"Transcript sent to {transcript_channel.mention}", ephemeral=True)


class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = TicketDatabase()
        self.views_registered = False


    async def cog_load(self):
        """Called when cog is loaded - setup database and register persistent views"""
        await self.db.init_db()
        await self.register_persistent_views()


    async def register_persistent_views(self):
        """Register all persistent views on bot startup"""
        if self.views_registered:
            return
        
        # Register ticket panel view
        panel_view = TicketPanelView(self)
        self.bot.add_view(panel_view)
        
        # Register close views for all open tickets
        open_tickets = await self.db.get_all_open_tickets()
        for ticket in open_tickets:
            action_view = TicketActionView(self, ticket['channel_id'], ticket['owner_id'], ticket['ticket_id'], ticket['guild_id'])
            self.bot.add_view(action_view)
            close_view = TicketCloseView(self, ticket['channel_id'], ticket['owner_id'], ticket['ticket_id'], ticket['guild_id'])
            self.bot.add_view(close_view)
        
        self.views_registered = True
        print(f"✅ Registered persistent views: 1 panel view + {len(open_tickets)} ticket action views")
        
        # Update existing ticket messages with new view if button is missing
        for ticket in open_tickets:
            try:
                channel = self.bot.get_channel(ticket['channel_id'])
                if channel:
                    # Try to find the ticket embed message and update its view
                    async for message in channel.history(limit=10):
                        if message.author == self.bot.user and message.embeds:
                            embed = message.embeds[0]
                            if embed.footer and "Ticket ID:" in str(embed.footer.text):
                                action_view = TicketActionView(
                                    self, 
                                    ticket['channel_id'], 
                                    ticket['owner_id'], 
                                    ticket['ticket_id'], 
                                    ticket['guild_id']
                                )
                                await message.edit(view=action_view)
                                break
            except Exception as e:
                print(f"Could not update ticket {ticket['ticket_id']}: {e}")


    @commands.Cog.listener()
    async def on_ready(self):
        """Ensure views are registered when bot is ready"""
        await self.register_persistent_views()


    @commands.Cog.listener()
    async def on_message(self, message):
        # Log messages in ticket channels
        if message.author.bot:
            return
        
        ticket_data = await self.db.get_ticket_by_channel(message.channel.id)
        if ticket_data:
            ticket_id = ticket_data[0]
            await self.db.log_message(
                ticket_id,
                message.author.id,
                str(message.author),
                message.content
            )


    @commands.group()
    async def ticketsetup(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Usage: `ticketsetup enable|disable|config|stats`")


    @ticketsetup.command()
    async def enable(self, ctx):
        config = await self.db.get_guild_config(ctx.guild.id)
        if config.get('panel_message_id'):
            await ctx.send("Ticket panel is already set up in this server. Disable it first to create a new one.")
            return
        await ctx.send("Configure ticket system (select options)...", view=TicketSetupView(self, ctx))


    @ticketsetup.command()
    async def disable(self, ctx):
        config = await self.db.get_guild_config(ctx.guild.id)
        panel_channel = config.get("panel_channel")
        panel_message_id = config.get("panel_message_id")
        
        if panel_channel and panel_message_id:
            channel = self.bot.get_channel(panel_channel)
            try:
                message = await channel.fetch_message(panel_message_id)
                await message.delete()
            except Exception:
                pass
        
        await self.db.clear_guild_config(ctx.guild.id)
        await ctx.send("Ticket setup disabled and reset.")


    @ticketsetup.command()
    async def config(self, ctx):
        config = await self.db.get_guild_config(ctx.guild.id)
        
        embed = discord.Embed(title="Ticket System Configuration", color=discord.Color.blue())
        
        panel_ch = ctx.guild.get_channel(config.get('panel_channel')) if config.get('panel_channel') else None
        ticket_cat = ctx.guild.get_channel(config.get('ticket_category')) if config.get('ticket_category') else None
        support_role = ctx.guild.get_role(config.get('support_role')) if config.get('support_role') else None
        transcript_ch = ctx.guild.get_channel(config.get('transcript_channel')) if config.get('transcript_channel') else None
        
        embed.add_field(name="Panel Channel", value=panel_ch.mention if panel_ch else "Not set", inline=False)
        embed.add_field(name="Ticket Category", value=ticket_cat.name if ticket_cat else "Not set", inline=False)
        embed.add_field(name="Support Role", value=support_role.mention if support_role else "Not set", inline=False)
        embed.add_field(name="Transcript Channel", value=transcript_ch.mention if transcript_ch else "Not set", inline=False)
        embed.add_field(name="Panel Message ID", value=config.get('panel_message_id', 'Not set'), inline=False)
        
        await ctx.send(embed=embed)
    
    @ticketsetup.command()
    async def stats(self, ctx):
        stats = await self.db.get_ticket_stats(ctx.guild.id)
        
        embed = discord.Embed(title="Ticket Statistics", color=discord.Color.gold())
        embed.add_field(name="🟢 Open Tickets", value=stats['open'], inline=True)
        embed.add_field(name="🔴 Closed Tickets", value=stats['closed'], inline=True)
        embed.add_field(name="📊 Total Tickets", value=stats['total'], inline=True)
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Ticket(bot))