import discord
from discord.ext import commands
from discord.ui import View, Modal, TextInput, Button
import json
import os
from typing import Optional


class WelcomeSetup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_file = "welcome_config.json"
        self.config = self.load_config()

    def load_config(self):
        """Load welcome configuration from JSON file"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return {}

    def save_config(self):
        """Save welcome configuration to JSON file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    def replace_variables(self, text: str, member: discord.Member) -> str:
        """Replace all variables in text"""
        replacements = {
            '{user}': member.mention,
            '{username}': member.name,
            '{user.tag}': str(member),
            '{user.id}': str(member.id),
            '{server}': member.guild.name,
            '{server.id}': str(member.guild.id),
            '{membercount}': str(member.guild.member_count),
            '{server.membercount}': str(member.guild.member_count),
            '{position}': str(len([m for m in member.guild.members if not m.bot])),
        }
        
        for key, value in replacements.items():
            text = text.replace(key, value)
        
        return text

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Send welcome message when a member joins"""
        if member.bot:
            return
        
        guild_id = str(member.guild.id)
        
        if guild_id not in self.config:
            return
        
        config = self.config[guild_id]
        if not config.get('enabled', False):
            return
        
        channel_id = config.get('channel_id')
        if not channel_id:
            return
        
        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            return
        
        try:
            # Auto-role assignment
            auto_roles = config.get('auto_roles', [])
            for role_id in auto_roles:
                role = member.guild.get_role(int(role_id))
                if role:
                    await member.add_roles(role, reason="Welcome Auto-Role")
            
            # Create embed
            embed_config = config.get('embed', {})
            
            # Get message content (mention outside embed)
            message_content = config.get('message_content', '{user}')
            if message_content:
                message_content = self.replace_variables(message_content, member)
            
            if embed_config.get('enabled', True):
                # Build the embed
                title = self.replace_variables(embed_config.get('title', 'Welcome to {server}!'), member)
                description = self.replace_variables(embed_config.get('description', 'Welcome {user} to the server!'), member)
                color = int(embed_config.get('color', '0xE74C3C').replace('0x', ''), 16)
                
                embed = discord.Embed(
                    title=title,
                    description=description,
                    color=color
                )
                
                # Author
                if embed_config.get('show_author', True):
                    embed.set_author(
                        name=member.name,
                        icon_url=member.display_avatar.url
                    )
                
                # Thumbnail
                thumbnail_type = embed_config.get('thumbnail', 'user_avatar')
                if thumbnail_type == 'user_avatar':
                    embed.set_thumbnail(url=member.display_avatar.url)
                elif thumbnail_type == 'server_icon' and member.guild.icon:
                    embed.set_thumbnail(url=member.guild.icon.url)
                elif thumbnail_type == 'custom' and embed_config.get('thumbnail_url'):
                    embed.set_thumbnail(url=embed_config['thumbnail_url'])
                
                # Image
                if embed_config.get('image_url'):
                    embed.set_image(url=embed_config['image_url'])
                
                # Fields
                fields = embed_config.get('fields', [])
                for field in fields:
                    name = self.replace_variables(field['name'], member)
                    value = self.replace_variables(field['value'], member)
                    inline = field.get('inline', False)
                    embed.add_field(name=name, value=value, inline=inline)
                
                # Footer
                if embed_config.get('show_footer', True):
                    footer_text = self.replace_variables(
                        embed_config.get('footer_text', 'Member #{membercount}'),
                        member
                    )
                    if embed_config.get('footer_icon') == 'server_icon' and member.guild.icon:
                        embed.set_footer(text=footer_text, icon_url=member.guild.icon.url)
                    else:
                        embed.set_footer(text=footer_text)
                
                # Timestamp
                if embed_config.get('show_timestamp', True):
                    embed.timestamp = discord.utils.utcnow()
                
                # Send message with mention outside embed
                await channel.send(content=message_content, embed=embed)
            else:
                # Send plain message
                await channel.send(message_content)
            
            # Send DM if enabled
            if config.get('send_dm', False):
                dm_message = self.replace_variables(
                    config.get('dm_message', 'Welcome to {server}!'),
                    member
                )
                try:
                    await member.send(dm_message)
                except:
                    pass
        
        except Exception as e:
            print(f"Error sending welcome message: {e}")

    @commands.group(name='welcome', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def welcome(self, ctx):
        """Welcome system commands"""
        embed = discord.Embed(
            title="📋 Welcome System Commands",
            description="Use the following commands to configure the welcome system",
            color=0xE74C3C
        )
        embed.add_field(
            name="Setup",
            value="`welcome setup` - Interactive setup wizard\n"
                  "`welcome channel <#channel>` - Set welcome channel\n"
                  "`welcome toggle` - Enable/disable welcome\n"
                  "`welcome content <text>` - Set message outside embed",
            inline=False
        )
        embed.add_field(
            name="Embed Customization",
            value="`welcome embed` - Customize embed settings\n"
                  "`welcome title <text>` - Set embed title\n"
                  "`welcome description <text>` - Set embed description\n"
                  "`welcome color <hex>` - Set embed color\n"
                  "`welcome thumbnail <option>` - Set thumbnail\n"
                  "`welcome image <url>` - Set embed image\n"
                  "`welcome footer <text>` - Set footer text",
            inline=False
        )
        embed.add_field(
            name="Advanced",
            value="`welcome field add <name> | <value>` - Add embed field\n"
                  "`welcome field remove <index>` - Remove embed field\n"
                  "`welcome autorole <@role>` - Add auto-role\n"
                  "`welcome dm <message>` - Set DM message\n"
                  "`welcome test` - Test welcome message\n"
                  "`welcome variables` - Show available variables",
            inline=False
        )
        await ctx.send(embed=embed)

    @welcome.command(name='setup')
    async def welcome_setup(self, ctx):
        """Interactive welcome setup wizard"""
        view = WelcomeSetupView(self, ctx)
        embed = discord.Embed(
            title="🎉 Welcome System Setup",
            description="Let's configure your welcome system!\n\nSelect an option below to get started.",
            color=0xE74C3C
        )
        await ctx.send(embed=embed, view=view)

    @welcome.command(name='channel')
    async def set_channel(self, ctx, channel: discord.TextChannel):
        """Set the welcome channel"""
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.config:
            self.config[guild_id] = {'enabled': False}
        
        self.config[guild_id]['channel_id'] = channel.id
        self.save_config()
        
        embed = discord.Embed(
            title="✅ Welcome Channel Set",
            description=f"Welcome messages will be sent to {channel.mention}",
            color=0x2ECC71
        )
        await ctx.send(embed=embed)

    @welcome.command(name='content')
    async def set_content(self, ctx, *, content: str):
        """Set the message content outside embed (supports variables)"""
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.config:
            self.config[guild_id] = {}
        
        self.config[guild_id]['message_content'] = content
        self.save_config()
        
        embed = discord.Embed(
            title="✅ Message Content Updated",
            description=f"New content: **{content}**\n\nThis will appear outside the embed.",
            color=0x2ECC71
        )
        await ctx.send(embed=embed)

    @welcome.command(name='toggle')
    async def toggle_welcome(self, ctx):
        """Enable or disable the welcome system"""
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.config:
            self.config[guild_id] = {'enabled': True}
        else:
            self.config[guild_id]['enabled'] = not self.config[guild_id].get('enabled', False)
        
        self.save_config()
        status = "enabled" if self.config[guild_id]['enabled'] else "disabled"
        
        embed = discord.Embed(
            title=f"✅ Welcome System {status.title()}",
            description=f"The welcome system is now **{status}**",
            color=0x2ECC71 if self.config[guild_id]['enabled'] else 0xE74C3C
        )
        await ctx.send(embed=embed)

    @welcome.command(name='title')
    async def set_title(self, ctx, *, title: str):
        """Set the embed title"""
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.config:
            self.config[guild_id] = {}
        if 'embed' not in self.config[guild_id]:
            self.config[guild_id]['embed'] = {}
        
        self.config[guild_id]['embed']['title'] = title
        self.save_config()
        
        embed = discord.Embed(
            title="✅ Title Updated",
            description=f"New title: **{title}**",
            color=0x2ECC71
        )
        await ctx.send(embed=embed)

    @welcome.command(name='description')
    async def set_description(self, ctx, *, description: str):
        """Set the embed description"""
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.config:
            self.config[guild_id] = {}
        if 'embed' not in self.config[guild_id]:
            self.config[guild_id]['embed'] = {}
        
        self.config[guild_id]['embed']['description'] = description
        self.save_config()
        
        embed = discord.Embed(
            title="✅ Description Updated",
            description=f"New description: **{description}**",
            color=0x2ECC71
        )
        await ctx.send(embed=embed)

    @welcome.command(name='color')
    async def set_color(self, ctx, color: str):
        """Set the embed color (hex code)"""
        guild_id = str(ctx.guild.id)
        
        if not color.startswith('#') and not color.startswith('0x'):
            color = f"0x{color}"
        
        if guild_id not in self.config:
            self.config[guild_id] = {}
        if 'embed' not in self.config[guild_id]:
            self.config[guild_id]['embed'] = {}
        
        self.config[guild_id]['embed']['color'] = color
        self.save_config()
        
        embed = discord.Embed(
            title="✅ Color Updated",
            description=f"New color: **{color}**",
            color=int(color.replace('#', '').replace('0x', ''), 16)
        )
        await ctx.send(embed=embed)

    @welcome.command(name='thumbnail')
    async def set_thumbnail(self, ctx, option: str):
        """Set thumbnail (user_avatar, server_icon, custom, none)"""
        guild_id = str(ctx.guild.id)
        
        valid_options = ['user_avatar', 'server_icon', 'custom', 'none']
        if option.lower() not in valid_options:
            await ctx.send(f"❌ Invalid option! Choose from: {', '.join(valid_options)}")
            return
        
        if guild_id not in self.config:
            self.config[guild_id] = {}
        if 'embed' not in self.config[guild_id]:
            self.config[guild_id]['embed'] = {}
        
        self.config[guild_id]['embed']['thumbnail'] = option.lower()
        self.save_config()
        
        embed = discord.Embed(
            title="✅ Thumbnail Updated",
            description=f"Thumbnail set to: **{option}**",
            color=0x2ECC71
        )
        await ctx.send(embed=embed)

    @welcome.command(name='image')
    async def set_image(self, ctx, url: str = None):
        """Set the embed image URL"""
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.config:
            self.config[guild_id] = {}
        if 'embed' not in self.config[guild_id]:
            self.config[guild_id]['embed'] = {}
        
        self.config[guild_id]['embed']['image_url'] = url
        self.save_config()
        
        if url:
            embed = discord.Embed(
                title="✅ Image Updated",
                description="Image has been set successfully",
                color=0x2ECC71
            )
            embed.set_image(url=url)
        else:
            embed = discord.Embed(
                title="✅ Image Removed",
                description="Image has been removed",
                color=0x2ECC71
            )
        
        await ctx.send(embed=embed)

    @welcome.command(name='footer')
    async def set_footer(self, ctx, *, footer: str):
        """Set the embed footer text"""
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.config:
            self.config[guild_id] = {}
        if 'embed' not in self.config[guild_id]:
            self.config[guild_id]['embed'] = {}
        
        self.config[guild_id]['embed']['footer_text'] = footer
        self.save_config()
        
        embed = discord.Embed(
            title="✅ Footer Updated",
            description=f"New footer: **{footer}**",
            color=0x2ECC71
        )
        await ctx.send(embed=embed)

    @welcome.group(name='field', invoke_without_command=True)
    async def field_group(self, ctx):
        """Manage embed fields"""
        await ctx.send("Use `welcome field add` or `welcome field remove`")

    @field_group.command(name='add')
    async def add_field(self, ctx, *, content: str):
        """Add an embed field (format: name | value | inline)"""
        parts = content.split('|')
        
        if len(parts) < 2:
            await ctx.send("❌ Format: `welcome field add <name> | <value> | [inline]`")
            return
        
        name = parts[0].strip()
        value = parts[1].strip()
        inline = parts[2].strip().lower() in ['true', 'yes', '1'] if len(parts) > 2 else False
        
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.config:
            self.config[guild_id] = {}
        if 'embed' not in self.config[guild_id]:
            self.config[guild_id]['embed'] = {}
        if 'fields' not in self.config[guild_id]['embed']:
            self.config[guild_id]['embed']['fields'] = []
        
        self.config[guild_id]['embed']['fields'].append({
            'name': name,
            'value': value,
            'inline': inline
        })
        self.save_config()
        
        embed = discord.Embed(
            title="✅ Field Added",
            description=f"**{name}**\n{value}",
            color=0x2ECC71
        )
        await ctx.send(embed=embed)

    @field_group.command(name='remove')
    async def remove_field(self, ctx, index: int):
        """Remove an embed field by index"""
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.config or 'embed' not in self.config[guild_id]:
            await ctx.send("❌ No fields configured!")
            return
        
        fields = self.config[guild_id]['embed'].get('fields', [])
        
        if index < 1 or index > len(fields):
            await ctx.send(f"❌ Invalid index! Use 1-{len(fields)}")
            return
        
        removed = fields.pop(index - 1)
        self.config[guild_id]['embed']['fields'] = fields
        self.save_config()
        
        embed = discord.Embed(
            title="✅ Field Removed",
            description=f"Removed field: **{removed['name']}**",
            color=0x2ECC71
        )
        await ctx.send(embed=embed)

    @welcome.command(name='autorole')
    async def set_autorole(self, ctx, role: discord.Role):
        """Add an auto-role for new members"""
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.config:
            self.config[guild_id] = {}
        if 'auto_roles' not in self.config[guild_id]:
            self.config[guild_id]['auto_roles'] = []
        
        if role.id in self.config[guild_id]['auto_roles']:
            self.config[guild_id]['auto_roles'].remove(role.id)
            status = "removed"
            color = 0xE74C3C
        else:
            self.config[guild_id]['auto_roles'].append(role.id)
            status = "added"
            color = 0x2ECC71
        
        self.save_config()
        
        embed = discord.Embed(
            title=f"✅ Auto-Role {status.title()}",
            description=f"Role {role.mention} has been {status}",
            color=color
        )
        await ctx.send(embed=embed)

    @welcome.command(name='dm')
    async def set_dm(self, ctx, *, message: str = None):
        """Set or disable DM message for new members"""
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.config:
            self.config[guild_id] = {}
        
        if message:
            self.config[guild_id]['send_dm'] = True
            self.config[guild_id]['dm_message'] = message
            self.save_config()
            
            embed = discord.Embed(
                title="✅ DM Message Set",
                description=f"New members will receive: **{message}**",
                color=0x2ECC71
            )
        else:
            self.config[guild_id]['send_dm'] = False
            self.save_config()
            
            embed = discord.Embed(
                title="✅ DM Disabled",
                description="DM messages have been disabled",
                color=0xE74C3C
            )
        
        await ctx.send(embed=embed)

    @welcome.command(name='test')
    async def test_welcome(self, ctx):
        """Test the welcome message with your account"""
        await self.on_member_join(ctx.author)
        await ctx.send("✅ Test message sent!", ephemeral=True)

    @welcome.command(name='variables')
    async def show_variables(self, ctx):
        """Show available variables"""
        embed = discord.Embed(
            title="📝 Available Variables",
            description="Use these variables in your messages, titles, descriptions, and fields:",
            color=0x3498DB
        )
        embed.add_field(
            name="User Variables",
            value="`{user}` - Mention the user\n"
                  "`{username}` - Username only\n"
                  "`{user.tag}` - Username with discriminator\n"
                  "`{user.id}` - User ID",
            inline=False
        )
        embed.add_field(
            name="Server Variables",
            value="`{server}` - Server name\n"
                  "`{server.id}` - Server ID\n"
                  "`{membercount}` - Total member count\n"
                  "`{position}` - Member join position",
            inline=False
        )
        await ctx.send(embed=embed)

    @welcome.command(name='embed')
    async def embed_setup(self, ctx):
        """Advanced embed customization wizard"""
        view = EmbedCustomizeView(self, ctx)
        embed = discord.Embed(
            title="🎨 Embed Customization",
            description="Click the buttons below to customize your welcome embed",
            color=0xE74C3C
        )
        await ctx.send(embed=embed, view=view)


class WelcomeSetupView(View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=120)
        self.cog = cog
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Only the command user can use this!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Set Channel", style=discord.ButtonStyle.green, emoji="📢")
    async def set_channel_btn(self, interaction: discord.Interaction, button: Button):
        view = ChannelSelectView(self.cog, self.ctx)
        embed = discord.Embed(
            title="Select Welcome Channel",
            description="Choose a channel from the dropdown",
            color=0xE74C3C
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Customize Message", style=discord.ButtonStyle.blurple, emoji="✏️")
    async def customize_msg_btn(self, interaction: discord.Interaction, button: Button):
        modal = WelcomeMessageModal(self.cog, self.ctx)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Add Auto-Role", style=discord.ButtonStyle.gray, emoji="🎭")
    async def autorole_btn(self, interaction: discord.Interaction, button: Button):
        view = RoleSelectView(self.cog, self.ctx)
        embed = discord.Embed(
            title="Select Auto-Role",
            description="Choose roles to assign automatically to new members",
            color=0xE74C3C
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Test Welcome", style=discord.ButtonStyle.blurple, emoji="🧪")
    async def test_btn(self, interaction: discord.Interaction, button: Button):
        await self.cog.on_member_join(interaction.user)
        await interaction.response.send_message("✅ Test message sent!", ephemeral=True)

    @discord.ui.button(label="Toggle Enable", style=discord.ButtonStyle.red, emoji="🔔")
    async def toggle_btn(self, interaction: discord.Interaction, button: Button):
        guild_id = str(self.ctx.guild.id)
        
        if guild_id not in self.cog.config:
            self.cog.config[guild_id] = {'enabled': True}
        else:
            self.cog.config[guild_id]['enabled'] = not self.cog.config[guild_id].get('enabled', False)
        
        self.cog.save_config()
        status = "enabled" if self.cog.config[guild_id]['enabled'] else "disabled"
        
        await interaction.response.send_message(f"✅ Welcome system **{status}**!", ephemeral=True)


class ChannelSelectView(View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=60)
        self.cog = cog
        self.ctx = ctx
        self.page = 0
        self.channels = ctx.guild.text_channels
        self.create_select()

    def create_select(self):
        start = self.page * 25
        end = start + 25
        page_channels = self.channels[start:end]

        self.clear_items()

        if page_channels:
            options = [
                discord.SelectOption(
                    label=channel.name[:100],
                    value=str(channel.id),
                    emoji="📢"
                )
                for channel in page_channels
            ]

            select = discord.ui.Select(placeholder="Select a channel", options=options)
            select.callback = self.select_callback
            self.add_item(select)

        if len(self.channels) > 25:
            if self.page > 0:
                prev_btn = Button(label="← Previous", style=discord.ButtonStyle.gray)
                prev_btn.callback = self.prev_page
                self.add_item(prev_btn)

            if end < len(self.channels):
                next_btn = Button(label="Next →", style=discord.ButtonStyle.gray)
                next_btn.callback = self.next_page
                self.add_item(next_btn)

    async def prev_page(self, interaction: discord.Interaction):
        self.page -= 1
        self.create_select()
        await interaction.response.edit_message(view=self)

    async def next_page(self, interaction: discord.Interaction):
        self.page += 1
        self.create_select()
        await interaction.response.edit_message(view=self)

    async def select_callback(self, interaction: discord.Interaction):
        channel_id = int(interaction.data['values'][0])
        guild_id = str(self.ctx.guild.id)
        
        if guild_id not in self.cog.config:
            self.cog.config[guild_id] = {}
        
        self.cog.config[guild_id]['channel_id'] = channel_id
        self.cog.save_config()
        
        channel = self.ctx.guild.get_channel(channel_id)
        await interaction.response.send_message(
            f"✅ Welcome channel set to {channel.mention}!",
            ephemeral=True
        )


class RoleSelectView(View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=60)
        self.cog = cog
        self.ctx = ctx
        self.create_select()

    def create_select(self):
        roles = [r for r in self.ctx.guild.roles if not r.is_default() and not r.managed][:25]
        
        if not roles:
            return

        options = [
            discord.SelectOption(
                label=role.name[:100],
                value=str(role.id),
                emoji="🎭"
            )
            for role in roles
        ]

        select = discord.ui.Select(placeholder="Select roles", options=options, max_values=len(options))
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        guild_id = str(self.ctx.guild.id)
        
        if guild_id not in self.cog.config:
            self.cog.config[guild_id] = {}
        
        role_ids = [int(rid) for rid in interaction.data['values']]
        self.cog.config[guild_id]['auto_roles'] = role_ids
        self.cog.save_config()
        
        roles = [self.ctx.guild.get_role(rid).mention for rid in role_ids]
        await interaction.response.send_message(
            f"✅ Auto-roles set: {', '.join(roles)}!",
            ephemeral=True
        )


class WelcomeMessageModal(Modal):
    def __init__(self, cog, ctx):
        super().__init__(title="Customize Welcome Message", timeout=300)
        self.cog = cog
        self.ctx = ctx
        
        guild_id = str(ctx.guild.id)
        config = cog.config.get(guild_id, {})
        embed_config = config.get('embed', {})
        
        self.content_input = TextInput(
            label="Message Content (outside embed)",
            placeholder="{user} welcome to the server!",
            default=config.get('message_content', ''),
            style=discord.TextStyle.short,
            required=False
        )
        self.add_item(self.content_input)
        
        self.title_input = TextInput(
            label="Embed Title",
            placeholder="Welcome to {server}!",
            default=embed_config.get('title', ''),
            style=discord.TextStyle.short,
            required=False
        )
        self.add_item(self.title_input)
        
        self.description_input = TextInput(
            label="Embed Description",
            placeholder="Welcome {username}! You are member #{membercount}",
            default=embed_config.get('description', ''),
            style=discord.TextStyle.long,
            required=False
        )
        self.add_item(self.description_input)
        
        self.color_input = TextInput(
            label="Embed Color (hex)",
            placeholder="#E74C3C or 0xE74C3C",
            default=embed_config.get('color', ''),
            style=discord.TextStyle.short,
            required=False
        )
        self.add_item(self.color_input)

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = str(self.ctx.guild.id)
        
        if guild_id not in self.cog.config:
            self.cog.config[guild_id] = {}
        if 'embed' not in self.cog.config[guild_id]:
            self.cog.config[guild_id]['embed'] = {}
        
        if self.content_input.value:
            self.cog.config[guild_id]['message_content'] = self.content_input.value
        
        if self.title_input.value:
            self.cog.config[guild_id]['embed']['title'] = self.title_input.value
        
        if self.description_input.value:
            self.cog.config[guild_id]['embed']['description'] = self.description_input.value
        
        if self.color_input.value:
            color = self.color_input.value
            if not color.startswith('#') and not color.startswith('0x'):
                color = f"0x{color}"
            self.cog.config[guild_id]['embed']['color'] = color
        
        self.cog.config[guild_id]['embed']['enabled'] = True
        self.cog.save_config()
        
        embed = discord.Embed(
            title="✅ Welcome Message Updated",
            description="Your welcome message and embed have been customized successfully!",
            color=0x2ECC71
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class EmbedCustomizeView(View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=120)
        self.cog = cog
        self.ctx = ctx

    @discord.ui.button(label="Edit Text", style=discord.ButtonStyle.blurple, emoji="📝")
    async def edit_text_btn(self, interaction: discord.Interaction, button: Button):
        modal = WelcomeMessageModal(self.cog, self.ctx)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Set Image", style=discord.ButtonStyle.gray, emoji="🖼️")
    async def set_image_btn(self, interaction: discord.Interaction, button: Button):
        modal = ImageModal(self.cog, self.ctx)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Add Field", style=discord.ButtonStyle.green, emoji="➕")
    async def add_field_btn(self, interaction: discord.Interaction, button: Button):
        modal = FieldModal(self.cog, self.ctx)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Preview", style=discord.ButtonStyle.blurple, emoji="👁️")
    async def preview_btn(self, interaction: discord.Interaction, button: Button):
        await self.cog.on_member_join(interaction.user)
        await interaction.response.send_message("✅ Preview sent!", ephemeral=True)


class ImageModal(Modal):
    def __init__(self, cog, ctx):
        super().__init__(title="Set Embed Image", timeout=120)
        self.cog = cog
        self.ctx = ctx
        
        self.image_input = TextInput(
            label="Image URL",
            placeholder="https://example.com/image.png",
            style=discord.TextStyle.short,
            required=False
        )
        self.add_item(self.image_input)
        
        self.thumbnail_input = TextInput(
            label="Thumbnail URL (optional)",
            placeholder="https://example.com/thumbnail.png",
            style=discord.TextStyle.short,
            required=False
        )
        self.add_item(self.thumbnail_input)

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = str(self.ctx.guild.id)
        
        if guild_id not in self.cog.config:
            self.cog.config[guild_id] = {}
        if 'embed' not in self.cog.config[guild_id]:
            self.cog.config[guild_id]['embed'] = {}
        
        if self.image_input.value:
            self.cog.config[guild_id]['embed']['image_url'] = self.image_input.value
        
        if self.thumbnail_input.value:
            self.cog.config[guild_id]['embed']['thumbnail'] = 'custom'
            self.cog.config[guild_id]['embed']['thumbnail_url'] = self.thumbnail_input.value
        
        self.cog.save_config()
        
        await interaction.response.send_message("✅ Images updated!", ephemeral=True)


class FieldModal(Modal):
    def __init__(self, cog, ctx):
        super().__init__(title="Add Embed Field", timeout=120)
        self.cog = cog
        self.ctx = ctx
        
        self.name_input = TextInput(
            label="Field Name",
            placeholder="Rules",
            style=discord.TextStyle.short,
            required=True
        )
        self.add_item(self.name_input)
        
        self.value_input = TextInput(
            label="Field Value",
            placeholder="Please read our rules in #rules",
            style=discord.TextStyle.long,
            required=True
        )
        self.add_item(self.value_input)

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = str(self.ctx.guild.id)
        
        if guild_id not in self.cog.config:
            self.cog.config[guild_id] = {}
        if 'embed' not in self.cog.config[guild_id]:
            self.cog.config[guild_id]['embed'] = {}
        if 'fields' not in self.cog.config[guild_id]['embed']:
            self.cog.config[guild_id]['embed']['fields'] = []
        
        self.cog.config[guild_id]['embed']['fields'].append({
            'name': self.name_input.value,
            'value': self.value_input.value,
            'inline': False
        })
        self.cog.save_config()
        
        await interaction.response.send_message("✅ Field added!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(WelcomeSetup(bot))