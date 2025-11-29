# tickets.py
# Ticket System with Boss Selection and Transcript Generation

import discord
from discord.ext import commands
from discord import app_commands
import random
from typing import Optional, List
import json
import io
import asyncio
import config


class TicketView(discord.ui.View):
    """Persistent view for ticket panel buttons"""
    def __init__(self):
        super().__init__(timeout=None)
        
        # Add buttons for each category
        for i, category in enumerate(config.CATEGORIES):
            row = i // 4  # 4 buttons per row
            self.add_item(TicketButton(category, row=row))


class TicketButton(discord.ui.Button):
    """Button for each ticket category"""
    def __init__(self, category: str, row: int):
        label = category.replace(" Express", "")
        
        super().__init__(
            label=label,
            style=discord.ButtonStyle.secondary,  # Black/Gray buttons
            custom_id=f"open_ticket::{category}",
            emoji=config.CUSTOM_EMOJI,  # <:URE:1429522388395233331>
            row=row
        )
        self.category = category
    
    async def callback(self, interaction: discord.Interaction):
        """Handle ticket button click"""
        # Check if category needs boss selection
        if self.category in ["Daily 4-Man Express", "Daily 7-Man Express", "Weekly Ultra Express"]:
            # Show boss selection menu
            view = BossSelectView(self.category)
            
            embed = discord.Embed(
                title=f"🎯 Select Bosses - {self.category}",
                description="Choose which bosses you need help with:",
                color=config.COLORS["PRIMARY"]
            )
            
            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True
            )
        else:
            # Direct to server selection modal
            view = ServerSelectView(self.category, selected_bosses=None)
            
            embed = discord.Embed(
                title=f"🌍 Select Server - {self.category}",
                description="Choose which server you're playing on:",
                color=config.COLORS["PRIMARY"]
            )
            
            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True
            )


class BossSelectView(discord.ui.View):
    """View with boss selection dropdown"""
    def __init__(self, category: str):
        super().__init__(timeout=300)  # 5 minute timeout for selection
        self.category = category
        self.add_item(BossSelectMenu(category))


class BossSelectMenu(discord.ui.Select):
    """Dropdown menu for boss selection"""
    def __init__(self, category: str):
        self.category = category
        
        # Get boss list based on category
        if category == "Daily 4-Man Express":
            boss_list = config.DAILY_4MAN_BOSSES
        elif category == "Daily 7-Man Express":
            boss_list = config.DAILY_7MAN_BOSSES
        elif category == "Weekly Ultra Express":
            boss_list = config.WEEKLY_ULTRA_BOSSES
        else:
            boss_list = []
        
        # Create options
        options = [
            discord.SelectOption(label=boss, value=boss, emoji="⚔️")
            for boss in boss_list
        ]
        
        super().__init__(
            placeholder=f"Select bosses (1-{len(boss_list)})",
            min_values=1,
            max_values=len(boss_list),
            options=options,
            custom_id=f"boss_select_{category}"
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle boss selection and show server selection"""
        selected_bosses = self.values
        
        # Show server selection
        view = ServerSelectView(self.category, selected_bosses=selected_bosses)
        
        embed = discord.Embed(
            title=f"🌍 Select Server - {self.category}",
            description="Choose which server you're playing on:",
            color=config.COLORS["PRIMARY"]
        )
        
        await interaction.response.edit_message(embed=embed, view=view)


class ServerSelectView(discord.ui.View):
    """View with server selection dropdown"""
    def __init__(self, category: str, selected_bosses: Optional[List[str]] = None):
        super().__init__(timeout=300)
        self.category = category
        self.selected_bosses = selected_bosses or []
        self.add_item(ServerSelectMenu(category, selected_bosses))


class ServerSelectMenu(discord.ui.Select):
    """Dropdown menu for server selection"""
    def __init__(self, category: str, selected_bosses: Optional[List[str]] = None):
        self.category = category
        self.selected_bosses = selected_bosses or []
        
        # Server options
        servers = ["Swordhaven", "Safiria", "Gravelyn", "Galanoth", "Alteon", "Yorumi"]
        
        options = [
            discord.SelectOption(label=server, value=server, emoji="🌐")
            for server in servers
        ]
        
        super().__init__(
            placeholder="Select your server",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"server_select_{category}"
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle server selection and open modal"""
        selected_server = self.values[0]
        
        # Show modal with selected bosses and server
        modal = TicketModal(self.category, selected_bosses=self.selected_bosses, selected_server=selected_server)
        await interaction.response.send_modal(modal)


class TicketModal(discord.ui.Modal):
    """Modal for ticket creation"""
    def __init__(self, category: str, selected_bosses: Optional[List[str]] = None, selected_server: str = None):
        super().__init__(title=f"{category} Ticket")
        self.category = category
        self.selected_bosses = selected_bosses or []
        self.selected_server = selected_server
        
        # In-game name input
        self.in_game_name = discord.ui.TextInput(
            label="In-game name?",
            placeholder="Enter your in-game name",
            required=True,
            max_length=100,
            style=discord.TextStyle.short
        )
        self.add_item(self.in_game_name)
        
        # Concerns input
        self.concerns = discord.ui.TextInput(
            label="Any concerns?",
            placeholder="Optional: Any special requests or concerns",
            required=False,
            max_length=1000,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.concerns)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Create ticket channel when modal submitted"""
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        category_id = config.CHANNEL_IDS.get("TICKETS_CATEGORY")
        
        if not category_id:
            await interaction.followup.send("❌ Ticket category not configured!", ephemeral=True)
            return
        
        category = guild.get_channel(category_id)
        if not category:
            await interaction.followup.send("❌ Ticket category not found!", ephemeral=True)
            return
        
        # Generate random number for ticket (10000-99999)
        random_number = random.randint(10000, 99999)
        
        # Get channel prefix
        prefix = config.CATEGORY_METADATA.get(self.category, {}).get("prefix", "ticket")
        
        # Create channel name: prefix-username
        username = interaction.user.name.lower().replace(" ", "")[:20]
        channel_name = f"{prefix}-{username}"
        
        # Create ticket channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        
        # Add staff/admin permissions
        admin_role = guild.get_role(config.ROLE_IDS.get("ADMIN"))
        staff_role = guild.get_role(config.ROLE_IDS.get("STAFF"))
        helper_role = guild.get_role(config.ROLE_IDS.get("HELPER"))
        
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        if helper_role:
            overwrites[helper_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        
        try:
            channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to create ticket: {e}", ephemeral=True)
            return
        
        # Create ticket embed
        embed = create_ticket_embed(
            category=self.category,
            requestor_id=interaction.user.id,
            in_game_name=self.in_game_name.value,
            concerns=self.concerns.value or "None",
            helpers=[],
            random_number=random_number,
            selected_bosses=self.selected_bosses,
            selected_server=self.selected_server
        )
        
        # Create ticket action buttons
        view = TicketActionView()
        
        # Send ticket message with REQUESTOR + HELPER ROLE PING
        ping_content = f"{interaction.user.mention}"
        if helper_role:
            ping_content += f" <@&{helper_role.id}>"
        ping_content += " ticket created!"
        
        ticket_msg = await channel.send(
            content=ping_content,
            embed=embed,
            view=view
        )
        
        # Save ticket to database
        bot = interaction.client
        await bot.db.save_ticket({
            "channel_id": channel.id,
            "category": self.category,
            "requestor_id": interaction.user.id,
            "helpers": [],
            "points": config.POINT_VALUES.get(self.category, 0),
            "random_number": random_number,
            "proof_submitted": False,
            "embed_message_id": ticket_msg.id,
            "in_game_name": self.in_game_name.value,
            "concerns": self.concerns.value or "None",
            "selected_bosses": json.dumps(self.selected_bosses),
            "selected_server": self.selected_server,
            "is_closed": False
        })
        
        await interaction.followup.send(
            f"✅ Ticket created: {channel.mention}",
            ephemeral=True
        )


class TicketActionView(discord.ui.View):
    """Action buttons for ticket (Join, Close)"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Join Ticket", style=discord.ButtonStyle.success, emoji="✅", custom_id="join_ticket")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Helper joins ticket"""
        bot = interaction.client
        ticket = await bot.db.get_ticket(interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message("❌ No active ticket found.", ephemeral=True)
            return
        
        if ticket.get("is_closed", False):
            await interaction.response.send_message("❌ This ticket is already closed.", ephemeral=True)
            return
        
        if interaction.user.id == ticket["requestor_id"]:
            await interaction.response.send_message("❌ You cannot join your own ticket.", ephemeral=True)
            return
        
        if interaction.user.id in ticket["helpers"]:
            await interaction.response.send_message("❌ You are already helping this ticket.", ephemeral=True)
            return
        
        slots = config.HELPER_SLOTS.get(ticket["category"], 3)
        if len(ticket["helpers"]) >= slots:
            await interaction.response.send_message("❌ This ticket already has the maximum number of helpers.", ephemeral=True)
            return
        
        ticket["helpers"].append(interaction.user.id)
        await bot.db.save_ticket(ticket)
        
        selected_bosses = json.loads(ticket.get("selected_bosses", "[]"))
        selected_server = ticket.get("selected_server", "Unknown")
        
        embed = create_ticket_embed(
            category=ticket["category"],
            requestor_id=ticket["requestor_id"],
            in_game_name=ticket.get("in_game_name", "N/A"),
            concerns=ticket.get("concerns", "None"),
            helpers=ticket["helpers"],
            random_number=ticket["random_number"],
            selected_bosses=selected_bosses,
            selected_server=selected_server
        )
        
        await interaction.message.edit(embed=embed)
        
        join_commands = generate_join_commands(ticket["category"], selected_bosses, ticket["random_number"], selected_server)
        
        if join_commands:
            await interaction.response.send_message(
                f"✅ You joined as helper!\n\n**🎮 Join Commands:**\n{join_commands}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"✅ You joined as helper!",
                ephemeral=True
            )
        
        await interaction.channel.send(f"✅ {interaction.user.mention} joined as helper!")
    
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close and reward ticket - STAFF/ADMIN ONLY - ULTIMATE DEBUG VERSION"""
        bot = interaction.client
        ticket = await bot.db.get_ticket(interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message("❌ No active ticket found.", ephemeral=True)
            return
        
        if ticket.get("is_closed", False):
            await interaction.response.send_message("❌ This ticket is already closed.", ephemeral=True)
            return
        
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF")] if rid)
        
        if not is_staff:
            await interaction.response.send_message("❌ Only staff or admins can close tickets.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        ticket["is_closed"] = True
        await bot.db.save_ticket(ticket)
        
        points_per_helper = ticket["points"]
        total_awarded = 0
        
        for helper_id in ticket["helpers"]:
            await bot.db.add_points(helper_id, points_per_helper)
            total_awarded += points_per_helper
        
        helpers_text = ", ".join([f"<@{h}>" for h in ticket["helpers"]]) if ticket["helpers"] else "None"
        
        closed_embed = discord.Embed(
            title=f"🔒 {ticket['category']} (Closed)",
            color=config.COLORS["SUCCESS"],
            timestamp=discord.utils.utcnow()
        )
        closed_embed.add_field(name="Requestor", value=f"<@{ticket['requestor_id']}>", inline=False)
        closed_embed.add_field(name="Helpers", value=helpers_text, inline=False)
        closed_embed.add_field(name="Points per Helper", value=f"**{points_per_helper}**", inline=True)
        closed_embed.add_field(name="Total Points Awarded", value=f"**{total_awarded}**", inline=True)
        closed_embed.set_footer(text=f"Closed by {interaction.user}")
        
        await interaction.channel.send(embed=closed_embed)
        
        await generate_transcript(interaction.channel, bot, ticket)
        
        await bot.db.save_ticket_history({
            "channel_id": ticket["channel_id"],
            "category": ticket["category"],
            "requestor_id": ticket["requestor_id"],
            "helpers": json.dumps(ticket["helpers"]),
            "points_per_helper": points_per_helper,
            "total_points_awarded": total_awarded,
            "closed_by": interaction.user.id
        })
        
        await bot.db.delete_ticket(ticket["channel_id"])
        
        # ===== ULTIMATE DEBUG MODE =====
        guild = interaction.guild
        admin_role = guild.get_role(config.ROLE_IDS.get("ADMIN"))
        staff_role = guild.get_role(config.ROLE_IDS.get("STAFF"))
        helper_role = guild.get_role(config.ROLE_IDS.get("HELPER"))
        
        print("\n" + "="*60)
        print(f"🔒 CLOSING TICKET: {interaction.channel.name}")
        print("="*60)
        
        print(f"\n📋 TICKET INFO:")
        print(f"   Requestor ID: {ticket['requestor_id']}")
        print(f"   Helper IDs: {ticket['helpers']}")
        print(f"   Category: {ticket['category']}")
        
        print(f"\n🎭 ROLE INFO:")
        print(f"   Admin Role: {admin_role.name if admin_role else 'NOT FOUND'} (ID: {config.ROLE_IDS.get('ADMIN')})")
        print(f"   Staff Role: {staff_role.name if staff_role else 'NOT FOUND'} (ID: {config.ROLE_IDS.get('STAFF')})")
        print(f"   Helper Role: {helper_role.name if helper_role else 'NOT FOUND'} (ID: {config.ROLE_IDS.get('HELPER')})")
        
        print(f"\n📊 PERMISSIONS BEFORE CLOSE:")
        for target, overwrite in interaction.channel.overwrites.items():
            if isinstance(target, discord.Role):
                print(f"   Role: {target.name} → {overwrite}")
            elif isinstance(target, discord.Member):
                print(f"   User: {target.name} → {overwrite}")
            else:
                print(f"   Other: {target} → {overwrite}")
        
        # Build new overwrites - ONLY staff can see
        new_overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        
        if admin_role:
            new_overwrites[admin_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
            print(f"\n✅ Adding Admin role to new overwrites")
        
        if staff_role:
            new_overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
            print(f"✅ Adding Staff role to new overwrites")
        
        # EXPLICITLY BLOCK REQUESTOR
        requestor = guild.get_member(ticket["requestor_id"])
        if requestor:
            new_overwrites[requestor] = discord.PermissionOverwrite(
                view_channel=False,
                read_messages=False,
                send_messages=False,
                read_message_history=False
            )
            print(f"❌ BLOCKING Requestor: {requestor.name}")
        else:
            print(f"⚠️ Requestor NOT FOUND (ID: {ticket['requestor_id']})")
        
        # EXPLICITLY BLOCK ALL HELPERS (individual users)
        for helper_id in ticket["helpers"]:
            helper = guild.get_member(helper_id)
            if helper:
                # Check if this helper is staff/admin
                is_helper_staff = False
                if admin_role and admin_role in helper.roles:
                    is_helper_staff = True
                    print(f"⏭️ Skipping {helper.name} (has Admin role)")
                if staff_role and staff_role in helper.roles:
                    is_helper_staff = True
                    print(f"⏭️ Skipping {helper.name} (has Staff role)")
                
                # Only block if not staff/admin
                if not is_helper_staff:
                    new_overwrites[helper] = discord.PermissionOverwrite(
                        view_channel=False,
                        read_messages=False,
                        send_messages=False,
                        read_message_history=False
                    )
                    print(f"❌ BLOCKING Helper: {helper.name}")
            else:
                print(f"⚠️ Helper NOT FOUND (ID: {helper_id})")
        
        # EXPLICITLY BLOCK HELPER ROLE
        if helper_role:
            new_overwrites[helper_role] = discord.PermissionOverwrite(
                view_channel=False,
                read_messages=False,
                send_messages=False,
                read_message_history=False
            )
            print(f"❌ BLOCKING Helper Role: {helper_role.name}")
        else:
            print(f"⚠️ Helper Role NOT FOUND")
        
        print(f"\n🔄 APPLYING NEW OVERWRITES...")
        print(f"   Total overwrites to apply: {len(new_overwrites)}")
        
        # APPLY THE NEW PERMISSIONS
        try:
            await interaction.channel.edit(overwrites=new_overwrites)
            print(f"✅ Channel.edit() completed successfully!")
        except discord.Forbidden as e:
            print(f"❌ FORBIDDEN ERROR: {e}")
            print(f"   Bot lacks permissions to edit channel!")
        except discord.HTTPException as e:
            print(f"❌ HTTP EXCEPTION: {e}")
        except Exception as e:
            print(f"❌ UNKNOWN ERROR: {e}")
        
        # Wait for Discord to process
        await asyncio.sleep(1)
        
        print(f"\n📊 PERMISSIONS AFTER CLOSE:")
        # Refresh channel object
        channel = guild.get_channel(interaction.channel.id)
        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Role):
                print(f"   Role: {target.name} → {overwrite}")
            elif isinstance(target, discord.Member):
                print(f"   User: {target.name} → {overwrite}")
            else:
                print(f"   Other: {target} → {overwrite}")
        
        print("="*60)
        print(f"🔒 TICKET CLOSE COMPLETE")
        print("="*60 + "\n")
        
        delete_embed = discord.Embed(
            title="🗑️ Delete Channel?",
            description=(
                "This ticket has been closed.\n\n"
                "Click the button below to delete this channel.\n"
                "Only staff can delete the channel."
            ),
            color=config.COLORS["DANGER"]
        )
        
        delete_view = DeleteChannelView()
        
        await interaction.followup.send(
            embed=delete_embed,
            view=delete_view,
            ephemeral=False
        )


class DeleteChannelView(discord.ui.View):
    """View with delete channel button"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Delete Channel", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="delete_channel")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete the channel - STAFF/ADMIN ONLY"""
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF")] if rid)
        
        if not is_staff:
            await interaction.response.send_message("❌ Only staff or admins can delete the channel.", ephemeral=True)
            return
        
        await interaction.response.send_message(
            f"🗑️ Channel will be deleted in 5 seconds...",
            ephemeral=False
        )
        
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket closed and deleted by {interaction.user}")
        except:
            pass


def create_ticket_embed(
    category: str,
    requestor_id: int,
    in_game_name: str,
    concerns: str,
    helpers: List[int],
    random_number: int,
    selected_bosses: Optional[List[str]] = None,
    selected_server: str = "Unknown"
) -> discord.Embed:
    """Create ticket information embed"""
    embed = discord.Embed(
        title=f"🎫 {category}",
        description=config.CATEGORY_METADATA.get(category, {}).get("description", "Ticket"),
        color=config.COLORS["PRIMARY"],
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(name="👤 Requestor", value=f"<@{requestor_id}>", inline=True)
    embed.add_field(name="🎮 In-game Name", value=in_game_name, inline=True)
    embed.add_field(name="🌍 Server", value=selected_server, inline=True)
    
    if selected_bosses:
        embed.add_field(
            name="📋 Selected Bosses",
            value="\n".join([f"⚔️ {boss}" for boss in selected_bosses]),
            inline=False
        )
    
    slots = config.HELPER_SLOTS.get(category, 3)
    helpers_text = ", ".join([f"<@{h}>" for h in helpers]) if helpers else "Waiting for helpers..."
    embed.add_field(
        name=f"👥 Helpers ({len(helpers)}/{slots})",
        value=helpers_text,
        inline=False
    )
    
    points = config.POINT_VALUES.get(category, 0)
    embed.add_field(name="💰 Points per Helper", value=f"**{points}**", inline=True)
    
    if concerns != "None":
        embed.add_field(name="📝 Concerns", value=concerns, inline=False)
    
    return embed


def generate_join_commands(category: str, selected_bosses: List[str], room_number: int, server: str) -> str:
    """Generate /join commands based on selected bosses"""
    commands = []
    
    if category == "Daily 4-Man Express":
        for boss in selected_bosses:
            commands.append(f"`/join {boss}-{room_number}`")
    
    elif category == "Daily 7-Man Express":
        for boss in selected_bosses:
            if boss in config.BOSS_7MAN_COMMANDS:
                boss_commands = config.BOSS_7MAN_COMMANDS[boss]
                if len(boss_commands) == 1:
                    commands.append(f"`/join {boss_commands[0]}-{room_number}`")
                else:
                    multi = " **OR** ".join([f"`/join {cmd}-{room_number}`" for cmd in boss_commands])
                    commands.append(f"**{boss}:** {multi}")
            else:
                commands.append(f"`/join {boss}-{room_number}`")
    
    elif category == "Weekly Ultra Express":
        for boss in selected_bosses:
            commands.append(f"`/join {boss}-{room_number}`")
    
    elif category == "UltraSpeaker Express":
        commands.append(f"`/join UltraSpeaker-{room_number}`")
    
    elif category == "Ultra Gramiel Express":
        commands.append(f"`/join UltraGramiel-{room_number}`")
    
    elif category == "GrimChallenge Express":
        commands.append(f"`/join GrimChallenge-{room_number}`")
    
    elif category == "Daily Temple Express":
        commands.append(f"`/join TempleShrine-{room_number}`")
    
    return "\n".join(commands) if commands else ""


async def generate_transcript(channel: discord.TextChannel, bot, ticket: dict):
    """Generate transcript and save to transcript channel"""
    transcript_channel_id = config.CHANNEL_IDS.get("TRANSCRIPT")
    
    if not transcript_channel_id:
        return
    
    transcript_channel = bot.get_channel(transcript_channel_id)
    if not transcript_channel:
        return
    
    messages = []
    async for msg in channel.history(limit=500, oldest_first=True):
        messages.append(msg)
    
    transcript_lines = [
        f"=== TRANSCRIPT FOR {channel.name.upper()} ===",
        f"Category: {ticket['category']}",
        f"Requestor: {ticket['requestor_id']}",
        f"Room Number: {ticket['random_number']}",
        f"Created: {channel.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "=" * 50,
        ""
    ]
    
    for msg in messages:
        timestamp = msg.created_at.strftime('%Y-%m-%d %H:%M:%S')
        author = f"{msg.author.name}#{msg.author.discriminator}" if msg.author.discriminator != "0" else msg.author.name
        content = msg.content or "[Embed/Attachment]"
        
        transcript_lines.append(f"[{timestamp}] {author}: {content}")
        
        if msg.embeds:
            for embed in msg.embeds:
                if embed.title:
                    transcript_lines.append(f"  └─ Embed: {embed.title}")
    
    transcript_text = "\n".join(transcript_lines)
    
    file = discord.File(
        io.BytesIO(transcript_text.encode('utf-8')),
        filename=f"transcript-{channel.name}-{ticket['random_number']}.txt"
    )
    
    embed = discord.Embed(
        title=f"📄 Transcript: {channel.name}",
        description=f"**Category:** {ticket['category']}\n**Room Number:** {ticket['random_number']}",
        color=config.COLORS["PRIMARY"],
        timestamp=discord.utils.utcnow()
    )
    
    await transcript_channel.send(embed=embed, file=file)


async def setup_tickets(bot):
    """Setup ticket commands"""
    
    @bot.tree.command(name="panel", description="Post the ticket panel (Staff only)")
    async def panel(interaction: discord.Interaction):
        """Post ticket panel"""
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF")] if rid)
        
        if not is_staff:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return
        
        ticket_panel_channel_id = config.CHANNEL_IDS.get("TICKET_PANEL")
        
        embed = discord.Embed(
            title="### 🎮 IN-GAME ASSISTANCE 🎮",
            description=(
                "## CHOOSE YOUR TICKET TYPE🚂 💨\n"
                "Pick the ticket type that fits your request📜\n"
                f"* <#{ticket_panel_channel_id}>\n"
                "------------------------------------------------------------\n"
                "**UltraSpeaker Express**\n"
                "- The First Speaker\n\n"
                "**Ultra Gramiel Express**\n"
                "- Ultra Gramiel\n\n"
                "**Daily 4-Man Express**\n"
                "- Daily 4-Man Ultra Bosses\n\n"
                "**Daily 7-Man Express**\n"
                "- Daily 7-Man Ultra Bosses\n\n"
                "**Weekly Ultra Express**\n"
                "- Weekly Ultra Bosses (excluding speaker, grim and gramiel)\n\n"
                "**GrimChallenge Express**\n"
                "- Mechabinky & Raxborg 2.0\n\n"
                "**Daily Temple Express**\n"
                "- Daily TempleShrine\n"
                "-----------------------------------------------------------\n"
                "### How it works📢\n"
                "- ✅ Select a \"ticket type\"\n"
                "- 📝 Fill out the form\n"
                "- 💁 Helpers join\n"
                "- 🎉 Get help in your private ticket"
            ),
            color=config.COLORS["PRIMARY"]
        )
        
        view = TicketView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Ticket panel posted!", ephemeral=True)
    
    @bot.tree.command(name="proof", description="Show proof submission guidelines")
    async def proof(interaction: discord.Interaction):
        """Show proof guidelines"""
        cmd_data = config.HARDCODED_COMMANDS.get("proof", {})
        await interaction.response.send_message(cmd_data.get("text", "No info available."))
    
    @bot.tree.command(name="hrules", description="Show helper rules")
    async def hrules(interaction: discord.Interaction):
        """Show helper rules"""
        cmd_data = config.HARDCODED_COMMANDS.get("hrules", {})
        await interaction.response.send_message(cmd_data.get("text", "No info available."))
    
    @bot.tree.command(name="rrules", description="Show runner rules")
    async def rrules(interaction: discord.Interaction):
        """Show runner rules"""
        cmd_data = config.HARDCODED_COMMANDS.get("rrules", {})
        await interaction.response.send_message(cmd_data.get("text", "No info available."))