# cogs/tickets.py
# Ticket System with Boss Selection and Transcript Generation

import discord
from discord.ext import commands
from discord import app_commands
import random
from typing import Optional, List
import json
import io
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
            emoji="🎫",
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
            # Direct to modal (no boss selection needed)
            modal = TicketModal(self.category, selected_bosses=None)
            await interaction.response.send_modal(modal)


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
        """Handle boss selection and open modal"""
        selected_bosses = self.values
        
        # Show modal with selected bosses
        modal = TicketModal(self.category, selected_bosses=selected_bosses)
        await interaction.response.send_modal(modal)


class TicketModal(discord.ui.Modal):
    """Modal for ticket creation"""
    def __init__(self, category: str, selected_bosses: Optional[List[str]] = None):
        super().__init__(title=f"{category} Ticket")
        self.category = category
        self.selected_bosses = selected_bosses or []
        
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
        
        # Generate random number for ticket
        random_number = random.randint(1000, 9999)
        
        # Get channel prefix
        prefix = config.CATEGORY_METADATA.get(self.category, {}).get("prefix", "ticket")
        channel_name = f"{prefix}-{random_number}"
        
        # Create ticket channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        
        # Add staff/admin permissions
        admin_role = guild.get_role(config.ROLE_IDS.get("ADMIN"))
        staff_role = guild.get_role(config.ROLE_IDS.get("STAFF"))
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        
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
            selected_bosses=self.selected_bosses
        )
        
        # Create ticket action buttons
        view = TicketActionView()
        
        # Send ticket message
        ticket_msg = await channel.send(
            content=f"{interaction.user.mention} ticket created!",
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
            "selected_bosses": json.dumps(self.selected_bosses)
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
        
        # Check if user is requestor
        if interaction.user.id == ticket["requestor_id"]:
            await interaction.response.send_message("❌ You cannot join your own ticket.", ephemeral=True)
            return
        
        # Check if already helping
        if interaction.user.id in ticket["helpers"]:
            await interaction.response.send_message("❌ You are already helping this ticket.", ephemeral=True)
            return
        
        # Check slot limit
        slots = config.HELPER_SLOTS.get(ticket["category"], 3)
        if len(ticket["helpers"]) >= slots:
            await interaction.response.send_message("❌ This ticket already has the maximum number of helpers.", ephemeral=True)
            return
        
        # Add helper
        ticket["helpers"].append(interaction.user.id)
        await bot.db.save_ticket(ticket)
        
        # Get selected bosses
        selected_bosses = json.loads(ticket.get("selected_bosses", "[]"))
        
        # Update embed
        embed = create_ticket_embed(
            category=ticket["category"],
            requestor_id=ticket["requestor_id"],
            in_game_name=ticket.get("in_game_name", "N/A"),
            concerns=ticket.get("concerns", "None"),
            helpers=ticket["helpers"],
            random_number=ticket["random_number"],
            selected_bosses=selected_bosses
        )
        
        # Give helper view permission
        await interaction.channel.set_permissions(
            interaction.user,
            view_channel=True,
            send_messages=True
        )
        
        # Update message
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message(f"✅ {interaction.user.mention} joined as helper!", ephemeral=False)
    
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close and reward ticket"""
        bot = interaction.client
        ticket = await bot.db.get_ticket(interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message("❌ No active ticket found.", ephemeral=True)
            return
        
        # Check permissions (staff/admin or helper)
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF")] if rid)
        is_helper = member.id in ticket["helpers"]
        
        if not (is_staff or is_helper):
            await interaction.response.send_message("❌ Only staff or helpers can close this ticket.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        # Award points to helpers
        points_per_helper = ticket["points"]
        total_awarded = 0
        
        for helper_id in ticket["helpers"]:
            await bot.db.add_points(helper_id, points_per_helper)
            total_awarded += points_per_helper
        
        # Create closed embed
        helpers_text = ", ".join([f"<@{h}>" for h in ticket["helpers"]]) if ticket["helpers"] else "None"
        
        closed_embed = discord.Embed(
            title=f"🎫 {ticket['category']} (Closed)",
            color=config.COLORS["PRIMARY"],
            timestamp=discord.utils.utcnow()
        )
        closed_embed.add_field(name="Requestor", value=f"<@{ticket['requestor_id']}>", inline=False)
        closed_embed.add_field(name="Helpers", value=helpers_text, inline=False)
        closed_embed.add_field(name="Points per Helper", value=f"**{points_per_helper}**", inline=True)
        closed_embed.add_field(name="Total Points Awarded", value=f"**{total_awarded}**", inline=True)
        closed_embed.add_field(name="Closed By", value=interaction.user.mention, inline=False)
        closed_embed.set_footer(text="Ticket closed")
        
        # Send closed message
        await interaction.channel.send(embed=closed_embed)
        
        # Generate and send transcript
        await generate_transcript(interaction.channel, ticket, interaction.user)
        
        # Remove ticket from database
        await bot.db.delete_ticket(interaction.channel_id)
        
        # Archive ticket to history
        await bot.db.archive_ticket({
            "channel_id": interaction.channel_id,
            "category": ticket["category"],
            "requestor_id": ticket["requestor_id"],
            "helpers": ticket["helpers"],
            "points_per_helper": points_per_helper,
            "total_points_awarded": total_awarded,
            "closed_by": interaction.user.id
        })
        
        # Send delete message
        delete_view = DeleteChannelView()
        await interaction.followup.send(
            "✅ Ticket closed and points awarded! Transcript saved. Channel will be deleted in 10 seconds or click the button below.",
            view=delete_view
        )
        
        # Auto-delete after 10 seconds
        import asyncio
        await asyncio.sleep(10)
        try:
            await interaction.channel.delete(reason="Ticket closed")
        except:
            pass


class DeleteChannelView(discord.ui.View):
    """Delete button for closed tickets"""
    def __init__(self):
        super().__init__(timeout=60)
    
    @discord.ui.button(label="Delete Channel", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Deleting channel...", ephemeral=True)
        await interaction.channel.delete(reason="Ticket deleted by user")


def create_ticket_embed(category: str, requestor_id: int, in_game_name: str, concerns: str, helpers: list, random_number: int, selected_bosses: List[str] = None) -> discord.Embed:
    """Create ticket embed with selected bosses"""
    slots = config.HELPER_SLOTS.get(category, 3)
    helpers_text = ", ".join([f"<@{h}>" for h in helpers]) if helpers else "None"
    
    embed = discord.Embed(
        title=f"🎫 {category} Ticket",
        description=(
            f"**Requester:** <@{requestor_id}>\n"
            f"**In-game name:** {in_game_name}\n"
            f"**Concerns:** {concerns}\n\n"
            f"**Helpers ({len(helpers)}/{slots}):** {helpers_text}"
        ),
        color=config.COLORS["PRIMARY"],
        timestamp=discord.utils.utcnow()
    )
    
    # Add boss-specific join commands based on selected bosses
    if selected_bosses and len(selected_bosses) > 0:
        if category == "Daily 4-Man Express":
            for boss in selected_bosses:
                embed.add_field(name=boss, value=f"`/join {boss}-{random_number}`", inline=False)
        
        elif category == "Daily 7-Man Express":
            for boss in selected_bosses:
                commands = config.BOSS_7MAN_COMMANDS.get(boss, [boss])
                cmd_text = "\n".join([f"`/join {cmd}-{random_number}`" for cmd in commands])
                embed.add_field(name=boss, value=cmd_text, inline=False)
        
        elif category == "Weekly Ultra Express":
            for boss in selected_bosses:
                embed.add_field(name=boss, value=f"`/join {boss}-{random_number}`", inline=False)
    else:
        # For other categories, show single join command
        prefix = config.CATEGORY_METADATA.get(category, {}).get("prefix", "ticket")
        embed.add_field(name="Join Command", value=f"`/join {prefix}-{random_number}`", inline=False)
    
    return embed


async def generate_transcript(channel: discord.TextChannel, ticket: dict, closed_by: discord.Member):
    """Generate and send transcript to transcript channel"""
    try:
        # Get transcript channel
        transcript_channel_id = config.CHANNEL_IDS.get("TRANSCRIPT")
        if not transcript_channel_id:
            print("⚠️ Transcript channel not configured")
            return
        
        transcript_channel = channel.guild.get_channel(transcript_channel_id)
        if not transcript_channel:
            print("⚠️ Transcript channel not found")
            return
        
        # Fetch all messages from ticket channel
        messages = []
        async for message in channel.history(limit=None, oldest_first=True):
            messages.append(message)
        
        # Create transcript text
        transcript_lines = [
            f"═══════════════════════════════════════════",
            f"TICKET TRANSCRIPT",
            f"═══════════════════════════════════════════",
            f"",
            f"Ticket: {channel.name}",
            f"Category: {ticket['category']}",
            f"Requestor: {channel.guild.get_member(ticket['requestor_id'])}",
            f"In-Game Name: {ticket.get('in_game_name', 'N/A')}",
            f"Helpers: {', '.join([str(channel.guild.get_member(h)) for h in ticket['helpers']]) if ticket['helpers'] else 'None'}",
            f"Closed By: {closed_by}",
            f"Total Messages: {len(messages)}",
            f"",
            f"═══════════════════════════════════════════",
            f"MESSAGES",
            f"═══════════════════════════════════════════",
            f""
        ]
        
        # Add all messages
        for msg in messages:
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            author = f"{msg.author.name}#{msg.author.discriminator}" if msg.author.discriminator != "0" else msg.author.name
            
            # Message header
            transcript_lines.append(f"[{timestamp}] {author}:")
            
            # Message content
            if msg.content:
                transcript_lines.append(f"  {msg.content}")
            
            # Attachments
            if msg.attachments:
                for attachment in msg.attachments:
                    transcript_lines.append(f"  📎 Attachment: {attachment.url}")
            
            # Embeds
            if msg.embeds:
                for embed in msg.embeds:
                    if embed.title:
                        transcript_lines.append(f"  📋 Embed: {embed.title}")
                    if embed.description:
                        # Limit description preview to 100 chars
                        desc_preview = embed.description[:100] + "..." if len(embed.description) > 100 else embed.description
                        transcript_lines.append(f"     {desc_preview}")
            
            transcript_lines.append("")  # Empty line between messages
        
        # Add footer
        transcript_lines.append(f"═══════════════════════════════════════════")
        transcript_lines.append(f"END OF TRANSCRIPT")
        transcript_lines.append(f"═══════════════════════════════════════════")
        
        # Convert to string
        transcript_text = "\n".join(transcript_lines)
        
        # Create file
        transcript_file = discord.File(
            io.BytesIO(transcript_text.encode('utf-8')),
            filename=f"transcript-{channel.name}.txt"
        )
        
        # Create summary embed
        helpers_text = ", ".join([f"<@{h}>" for h in ticket["helpers"]]) if ticket["helpers"] else "None"
        
        summary_embed = discord.Embed(
            title=f"📜 Ticket Transcript - {channel.name}",
            color=config.COLORS["PRIMARY"],
            timestamp=discord.utils.utcnow()
        )
        summary_embed.add_field(name="Category", value=ticket["category"], inline=True)
        summary_embed.add_field(name="Requestor", value=f"<@{ticket['requestor_id']}>", inline=True)
        summary_embed.add_field(name="In-Game Name", value=ticket.get('in_game_name', 'N/A'), inline=True)
        summary_embed.add_field(name="Helpers", value=helpers_text, inline=False)
        summary_embed.add_field(name="Closed By", value=closed_by.mention, inline=True)
        summary_embed.add_field(name="Total Messages", value=str(len(messages)), inline=True)
        summary_embed.set_footer(text=f"Ticket ID: {channel.id}")
        
        # Send to transcript channel
        await transcript_channel.send(
            embed=summary_embed,
            file=transcript_file
        )
        
        print(f"✅ Transcript saved for {channel.name}")
        
    except Exception as e:
        print(f"❌ Failed to generate transcript: {e}")


class Tickets(commands.Cog):
    """Ticket system commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="panel", description="Post the ticket panel (Admin/Staff only)")
    async def panel(self, interaction: discord.Interaction):
        """Post ticket panel"""
        # Check permissions
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF")] if rid)
        
        if not is_staff:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return
        
        # Create panel embed
        category_list = "\n".join([
            f"**{cat.replace(' Express', '')}**\n- {config.CATEGORY_METADATA.get(cat, {}).get('description', 'No description')}"
            for cat in config.CATEGORIES
        ])
        
        embed = discord.Embed(
            title="🎮 IN-GAME ASSISTANCE 🎮",
            description=(
                "**CHOOSE YOUR TICKET TYPE** 🚂💨\n"
                "*Pick the ticket type that fits your request* 📜\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{category_list}\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "**How it works** 📢\n"
                "✅ Select a \"ticket type\"\n"
                "📝 Fill out the form\n"
                "💁 Helpers join\n"
                "🎉 Get help in your private ticket"
            ),
            color=config.COLORS["PRIMARY"]
        )
        
        view = TicketView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Ticket panel posted!", ephemeral=True)
    
    @app_commands.command(name="proof", description="Show proof submission guidelines")
    async def proof(self, interaction: discord.Interaction):
        """Show proof guidelines"""
        cmd_data = config.HARDCODED_COMMANDS["proof"]
        await interaction.response.send_message(cmd_data["text"], ephemeral=False)
    
    @app_commands.command(name="hrules", description="Show helper rules")
    async def hrules(self, interaction: discord.Interaction):
        """Show helper rules"""
        cmd_data = config.HARDCODED_COMMANDS["hrules"]
        await interaction.response.send_message(cmd_data["text"], ephemeral=False)
    
    @app_commands.command(name="rrules", description="Show runner rules")
    async def rrules(self, interaction: discord.Interaction):
        """Show runner rules"""
        cmd_data = config.HARDCODED_COMMANDS["rrules"]
        await interaction.response.send_message(cmd_data["text"], ephemeral=False)


async def setup(bot):
    await bot.add_cog(Tickets(bot))
    # Register persistent views
    bot.add_view(TicketView())
    bot.add_view(TicketActionView())