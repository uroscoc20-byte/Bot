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
import traceback
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
            style=discord.ButtonStyle.secondary,
            custom_id=f"open_ticket::{category}",
            emoji=config.CUSTOM_EMOJI,
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
            # Direct to server selection menu
            view = ServerSelectView(self.category, selected_bosses=[])
            
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
        super().__init__(timeout=300)
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
    def __init__(self, category: str, selected_bosses: List[str]):
        super().__init__(timeout=300)
        self.category = category
        self.selected_bosses = selected_bosses
        self.add_item(ServerSelectMenu(category, selected_bosses))


class ServerSelectMenu(discord.ui.Select):
    """Dropdown menu for server selection"""
    def __init__(self, category: str, selected_bosses: List[str]):
        self.category = category
        self.selected_bosses = selected_bosses
        
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
        modal = TicketModal(
            category=self.category,
            selected_bosses=self.selected_bosses,
            selected_server=selected_server
        )
        await interaction.response.send_modal(modal)


class TicketModal(discord.ui.Modal):
    """Modal for ticket creation - only in-game name and concerns"""
    def __init__(self, category: str, selected_bosses: List[str], selected_server: str):
        super().__init__(title=f"{category}")
        self.category = category
        self.selected_bosses = selected_bosses
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
        await create_ticket_channel(
            interaction=interaction,
            category=self.category,
            selected_bosses=self.selected_bosses,
            selected_server=self.selected_server,
            in_game_name=self.in_game_name.value,
            concerns=self.concerns.value or "None"
        )


async def create_ticket_channel(
    interaction: discord.Interaction,
    category: str,
    selected_bosses: List[str],
    selected_server: str,
    in_game_name: str,
    concerns: str
):
    """Create ticket channel with all information"""
    await interaction.response.defer(ephemeral=True)
    
    guild = interaction.guild
    category_id = config.CHANNEL_IDS.get("TICKETS_CATEGORY")
    
    if not category_id:
        await interaction.followup.send("❌ Ticket category not configured!", ephemeral=True)
        return
    
    category_channel = guild.get_channel(category_id)
    if not category_channel:
        await interaction.followup.send("❌ Ticket category not found!", ephemeral=True)
        return
    
    # Generate random number for ticket (10000-99999)
    random_number = random.randint(10000, 99999)
    
    # Get channel prefix
    prefix = config.CATEGORY_METADATA.get(category, {}).get("prefix", "ticket")
    
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
        channel = await category_channel.create_text_channel(
            name=channel_name,
            overwrites=overwrites
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to create ticket: {e}", ephemeral=True)
        return
    
    # Create ticket embed
    embed = create_ticket_embed(
        category=category,
        requestor_id=interaction.user.id,
        in_game_name=in_game_name,
        concerns=concerns,
        helpers=[],
        random_number=random_number,
        selected_bosses=selected_bosses,
        selected_server=selected_server
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
        "category": category,
        "requestor_id": interaction.user.id,
        "helpers": [],
        "points": config.POINT_VALUES.get(category, 0),
        "random_number": random_number,
        "proof_submitted": False,
        "embed_message_id": ticket_msg.id,
        "in_game_name": in_game_name,
        "concerns": concerns,
        "selected_bosses": json.dumps(selected_bosses),
        "selected_server": selected_server,
        "is_closed": False
    })
    
    # Generate join commands for requestor
    requestor_commands = generate_join_commands(
        category, 
        selected_bosses, 
        random_number, 
        selected_server
    )
    
    # Send room info ONLY to requestor (ephemeral)
    if requestor_commands:
        await interaction.followup.send(
            f"✅ Ticket created: {channel.mention}\n\n**🎮 Your Room Number: `{random_number}`**\n\n**Join Commands:**\n{requestor_commands}",
            ephemeral=True
        )
    else:
        await interaction.followup.send(
            f"✅ Ticket created: {channel.mention}\n\n**🎮 Your Room Number: `{random_number}`**",
            ephemeral=True
        )

class TicketActionView(discord.ui.View):
    """Action buttons for ticket (Join, Close, Cancel)"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Join Ticket", style=discord.ButtonStyle.success, emoji="✅", custom_id="join_ticket")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Helper joins ticket - ONE TICKET AT A TIME"""
        bot = interaction.client
        ticket = await bot.db.get_ticket(interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message("❌ No active ticket found.", ephemeral=True)
            return
        
        if ticket.get("is_closed", False):
            await interaction.response.send_message("❌ This ticket is already closed.", ephemeral=True)
            return
        
        # Check if user is the requestor
        if interaction.user.id == ticket["requestor_id"]:
            await interaction.response.send_message("❌ You cannot join your own ticket.", ephemeral=True)
            return
        
        # Check if user is already a helper
        if interaction.user.id in ticket["helpers"]:
            await interaction.response.send_message("❌ You are already a helper in this ticket.", ephemeral=True)
            return
        
        # Check helper slots
        max_slots = config.HELPER_SLOTS.get(ticket["category"], 3)
        if len(ticket["helpers"]) >= max_slots:
            await interaction.response.send_message(
                f"❌ This ticket is full ({max_slots}/{max_slots} helpers).",
                ephemeral=True
            )
            return
        
        # Check if helper is already in another ticket (ONE TICKET AT A TIME)
        all_tickets = await bot.db.get_all_active_tickets()
        for other_ticket in all_tickets:
            if other_ticket["channel_id"] != interaction.channel_id:
                if interaction.user.id in other_ticket["helpers"]:
                    other_channel = interaction.guild.get_channel(other_ticket["channel_id"])
                    await interaction.response.send_message(
                        f"❌ You are already helping in another ticket: {other_channel.mention if other_channel else 'Unknown Channel'}\n"
                        "You can only help in ONE ticket at a time.",
                        ephemeral=True
                    )
                    return
        
        # Add helper
        ticket["helpers"].append(interaction.user.id)
        await bot.db.save_ticket(ticket)
        
        # Update channel permissions
        await interaction.channel.set_permissions(
            interaction.user,
            view_channel=True,
            send_messages=True
        )
        
        # Update ticket embed
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
        
        # Update the ticket message
        try:
            msg = await interaction.channel.fetch_message(ticket["embed_message_id"])
            await msg.edit(embed=embed)
        except:
            pass
        
        # Send join commands to helper
        helper_commands = generate_join_commands(
            ticket["category"],
            selected_bosses,
            ticket["random_number"],
            selected_server
        )
        
        await interaction.response.send_message(
            f"✅ {interaction.user.mention} joined the ticket!\n\n"
            f"**🎮 Room Number: `{ticket['random_number']}`**\n\n"
            f"**Join Commands:**\n{helper_commands if helper_commands else 'No commands available'}",
            ephemeral=False
        )
    
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close ticket and award points"""
        bot = interaction.client
        ticket = await bot.db.get_ticket(interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message("❌ No active ticket found.", ephemeral=True)
            return
        
        if ticket.get("is_closed", False):
            await interaction.response.send_message("❌ This ticket is already closed.", ephemeral=True)
            return
        
        # Check permissions (staff/admin or requestor)
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF")] if rid)
        is_requestor = interaction.user.id == ticket["requestor_id"]
        
        if not (is_staff or is_requestor):
            await interaction.response.send_message(
                "❌ Only staff or the ticket creator can close tickets.",
                ephemeral=True
            )
            return
        
        # Check if proof was submitted
        if not ticket.get("proof_submitted", False):
            await interaction.response.send_message(
                "❌ Please submit proof before closing the ticket.\n"
                "Upload a screenshot showing completed quests and helper names, then click **Submit Proof**.",
                ephemeral=True
            )
            return
        
        # Award points to helpers
        points_per_helper = ticket["points"]
        total_awarded = 0
        
        for helper_id in ticket["helpers"]:
            await bot.db.add_points(helper_id, points_per_helper)
            total_awarded += points_per_helper
        
        # Mark ticket as closed
        ticket["is_closed"] = True
        await bot.db.save_ticket(ticket)
        
        # Save to history
        await bot.db.save_ticket_history({
            "channel_id": ticket["channel_id"],
            "category": ticket["category"],
            "requestor_id": ticket["requestor_id"],
            "helpers": json.dumps(ticket["helpers"]),
            "points_per_helper": points_per_helper,
            "total_points_awarded": total_awarded,
            "closed_by": interaction.user.id
        })
        
        # Create transcript
        transcript = await generate_transcript(interaction.channel)
        
        # Send transcript to transcript channel
        transcript_channel_id = config.CHANNEL_IDS.get("TRANSCRIPT")
        if transcript_channel_id:
            transcript_channel = interaction.guild.get_channel(transcript_channel_id)
            if transcript_channel:
                # Create summary embed
                summary_embed = discord.Embed(
                    title=f"📋 Ticket Closed - {ticket['category']}",
                    color=config.COLORS["SUCCESS"],
                    timestamp=discord.utils.utcnow()
                )
                summary_embed.add_field(name="Requestor", value=f"<@{ticket['requestor_id']}>", inline=True)
                summary_embed.add_field(name="Helpers", value=f"{len(ticket['helpers'])}", inline=True)
                summary_embed.add_field(name="Points Awarded", value=f"{total_awarded:,}", inline=True)
                
                helpers_list = "\n".join([f"<@{hid}>" for hid in ticket["helpers"]]) if ticket["helpers"] else "None"
                summary_embed.add_field(name="Helper List", value=helpers_list, inline=False)
                
                summary_embed.set_footer(text=f"Closed by {interaction.user}")
                
                # Send transcript file
                file = discord.File(io.BytesIO(transcript.encode()), filename=f"ticket-{ticket['channel_id']}.txt")
                await transcript_channel.send(embed=summary_embed, file=file)
        
        # Notify in ticket channel
        close_embed = discord.Embed(
            title="✅ Ticket Closed",
            description=f"**Points Awarded:** {total_awarded:,} total ({points_per_helper:,} per helper)\n"
                       f"**Helpers:** {len(ticket['helpers'])}\n\n"
                       "This channel will be deleted in 10 seconds...",
            color=config.COLORS["SUCCESS"]
        )
        close_embed.set_footer(text=f"Closed by {interaction.user}")
        
        await interaction.response.send_message(embed=close_embed)
        
        # Delete channel after 10 seconds
        await asyncio.sleep(10)
        try:
            await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
        except:
            pass
    
    @discord.ui.button(label="Submit Proof", style=discord.ButtonStyle.primary, emoji="📸", custom_id="submit_proof")
    async def proof_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mark proof as submitted"""
        bot = interaction.client
        ticket = await bot.db.get_ticket(interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message("❌ No active ticket found.", ephemeral=True)
            return
        
        if ticket.get("is_closed", False):
            await interaction.response.send_message("❌ This ticket is already closed.", ephemeral=True)
            return
        
        # Only requestor can submit proof
        if interaction.user.id != ticket["requestor_id"]:
            await interaction.response.send_message(
                "❌ Only the ticket creator can submit proof.",
                ephemeral=True
            )
            return
        
        # Mark proof as submitted
        ticket["proof_submitted"] = True
        await bot.db.save_ticket(ticket)
        
        await interaction.response.send_message(
            "✅ Proof submitted! You can now close the ticket.",
            ephemeral=False
        )
    
    @discord.ui.button(label="Cancel Ticket", style=discord.ButtonStyle.secondary, emoji="❌", custom_id="cancel_ticket")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel ticket without awarding points"""
        bot = interaction.client
        ticket = await bot.db.get_ticket(interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message("❌ No active ticket found.", ephemeral=True)
            return
        
        # Check permissions (staff/admin or requestor)
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF")] if rid)
        is_requestor = interaction.user.id == ticket["requestor_id"]
        
        if not (is_staff or is_requestor):
            await interaction.response.send_message(
                "❌ Only staff or the ticket creator can cancel tickets.",
                ephemeral=True
            )
            return
        
        # Mark as closed without points
        ticket["is_closed"] = True
        await bot.db.save_ticket(ticket)
        
        cancel_embed = discord.Embed(
            title="❌ Ticket Cancelled",
            description="This ticket was cancelled. No points were awarded.\n\n"
                       "This channel will be deleted in 5 seconds...",
            color=config.COLORS["WARNING"]
        )
        cancel_embed.set_footer(text=f"Cancelled by {interaction.user}")
        
        await interaction.response.send_message(embed=cancel_embed)
        
        # Delete channel after 5 seconds
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket cancelled by {interaction.user}")
        except:
            pass


class DeleteChannelView(discord.ui.View):
    """Simple delete channel button"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Delete Channel", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="delete_channel")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete the channel"""
        await interaction.response.send_message("Deleting channel...", ephemeral=True)
        await asyncio.sleep(2)
        try:
            await interaction.channel.delete(reason=f"Deleted by {interaction.user}")
        except:
            pass


def create_ticket_embed(
    category: str,
    requestor_id: int,
    in_game_name: str,
    concerns: str,
    helpers: List[int],
    random_number: int,
    selected_bosses: List[str],
    selected_server: str
) -> discord.Embed:
    """Create ticket embed"""
    embed = discord.Embed(
        title=f"🎫 {category}",
        color=config.COLORS["PRIMARY"],
        timestamp=discord.utils.utcnow()
    )
    
    # Requestor info
    embed.add_field(name="📝 Requestor", value=f"<@{requestor_id}>", inline=True)
    embed.add_field(name="🎮 In-Game Name", value=in_game_name, inline=True)
    embed.add_field(name="🌍 Server", value=selected_server, inline=True)
    
    # Boss selection (if applicable)
    if selected_bosses:
        bosses_text = "\n".join([f"• {boss}" for boss in selected_bosses])
        embed.add_field(name="⚔️ Selected Bosses", value=bosses_text, inline=False)
    
    # Helpers
    max_slots = config.HELPER_SLOTS.get(category, 3)
    helpers_text = "\n".join([f"<@{hid}>" for hid in helpers]) if helpers else "*No helpers yet*"
    embed.add_field(
        name=f"✅ Helpers ({len(helpers)}/{max_slots})",
        value=helpers_text,
        inline=False
    )
    
    # Concerns
    if concerns and concerns != "None":
        embed.add_field(name="💬 Concerns", value=concerns, inline=False)
    
    # Points
    points = config.POINT_VALUES.get(category, 0)
    embed.add_field(name="💰 Points", value=f"{points:,} per helper", inline=True)
    
    embed.set_footer(text=f"Room: {random_number}")
    
    return embed


def generate_join_commands(category: str, selected_bosses: List[str], room_number: int, server: str) -> str:
    """Generate join commands for helpers"""
    commands = []
    
    if category == "Daily 4-Man Express":
        for boss in selected_bosses:
            commands.append(f"`/join {boss}-{room_number}`")
    
    elif category == "Daily 7-Man Express":
        for boss in selected_bosses:
            # Check if boss has multiple commands
            boss_commands = config.BOSS_7MAN_COMMANDS.get(boss, [boss])
            for cmd in boss_commands:
                commands.append(f"`/join {cmd}-{room_number}`")
    
    elif category == "Weekly Ultra Express":
        for boss in selected_bosses:
            commands.append(f"`/join {boss}-{room_number}`")
    
    elif category == "UltraSpeaker Express":
        commands.append(f"`/join UltraSpeaker-{room_number}`")
    
    elif category == "Ultra Gramiel Express":
        commands.append(f"`/join UltraGramiel-{room_number}`")
    
    elif category == "GrimChallenge Express":
        commands.append(f"`/join Mechabinky-{room_number}`")
        commands.append(f"`/join Raxborg-{room_number}`")
    
    elif category == "Daily Temple Express":
        commands.append(f"`/join TempleShrine-{room_number}`")
    
    return "\n".join(commands) if commands else ""


async def generate_transcript(channel: discord.TextChannel) -> str:
    """Generate text transcript of ticket channel"""
    transcript = f"Ticket Transcript - {channel.name}\n"
    transcript += f"Generated: {discord.utils.utcnow()}\n"
    transcript += "=" * 50 + "\n\n"
    
    try:
        messages = []
        async for message in channel.history(limit=500, oldest_first=True):
            messages.append(message)
        
        for msg in messages:
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            transcript += f"[{timestamp}] {msg.author.name}: {msg.content}\n"
            
            # Add attachments
            if msg.attachments:
                for attachment in msg.attachments:
                    transcript += f"  📎 Attachment: {attachment.url}\n"
            
            transcript += "\n"
    
    except Exception as e:
        transcript += f"Error generating transcript: {e}\n"
    
    return transcript


async def setup_tickets(bot):
    """Setup ticket commands"""
    
    @bot.tree.command(name="panel", description="Post the ticket panel (Admin/Staff only)")
    async def panel(interaction: discord.Interaction):
        """Post ticket panel"""
        # Check permissions
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF")] if rid)
        
        if not is_staff:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return
        
        # Create panel embed
        embed = discord.Embed(
            title="🎫 Helper Ticket Panel",
            description=(
                "Click a button below to request help with bosses!\n\n"
                "**Rules:**\n"
                "• Use `/rrules` to view requestor rules\n"
                "• Use `/hrules` to view helper rules\n"
                "• Use `/proof` to see proof requirements\n\n"
                "**Point Values:**\n"
            ),
            color=config.COLORS["PRIMARY"]
        )
        
        # Add point values
        for cat in config.CATEGORIES:
            points = config.POINT_VALUES.get(cat, 0)
            embed.description += f"• **{cat.replace(' Express', '')}**: {points} pts\n"
        
        view = TicketView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Ticket panel posted!", ephemeral=True)
    
    @bot.tree.command(name="rrules", description="Show requestor rules")
    async def rrules(interaction: discord.Interaction):
        """Show requestor rules"""
        text = config.HARDCODED_COMMANDS["rrules"]["text"]
        embed = discord.Embed(
            description=text,
            color=config.COLORS["PRIMARY"]
        )
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="hrules", description="Show helper rules")
    async def hrules(interaction: discord.Interaction):
        """Show helper rules"""
        text = config.HARDCODED_COMMANDS["hrules"]["text"]
        embed = discord.Embed(
            description=text,
            color=config.COLORS["PRIMARY"]
        )
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="proof", description="Show proof requirements")
    async def proof(interaction: discord.Interaction):
        """Show proof requirements"""
        text = config.HARDCODED_COMMANDS["proof"]["text"]
        image = config.HARDCODED_COMMANDS["proof"].get("image")
        
        embed = discord.Embed(
            description=text,
            color=config.COLORS["PRIMARY"]
        )
        
        if image:
            embed.set_image(url=image)
        
        await interaction.response.send_message(embed=embed)