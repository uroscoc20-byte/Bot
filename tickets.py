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
            style=discord.ButtonStyle.secondary,  # Black/Gray buttons
            custom_id=f"open_ticket::{category}",
            emoji=config.CUSTOM_EMOJI,  # <:URE:1429522388395233331>
            row=row
        )
        self.category = category
    
    async def callback(self, interaction: discord.Interaction):
        """Handle ticket button click"""
        # Check if user has RESTRICTED role - BLOCK THEM
        restricted_role = interaction.guild.get_role(config.ROLE_IDS.get("RESTRICTED"))
        if restricted_role and restricted_role in interaction.user.roles:
            await interaction.response.send_message(
                "❌ You are restricted from opening tickets.",
                ephemeral=True
            )
            return
        
        # Check if user is a helper in any active ticket - PREVENT CREATING TICKET
        bot = interaction.client
        all_tickets = await bot.db.get_all_tickets()
        for ticket in all_tickets:
            if interaction.user.id in ticket["helpers"]:
                # Verify channel exists
                channel = interaction.guild.get_channel(ticket["channel_id"])
                if channel:
                    await interaction.response.send_message(
                        f"❌ You cannot create a ticket while you're a helper in another ticket: {channel.mention}\n"
                        "Please complete or leave that ticket first.",
                        ephemeral=True
                    )
                    return
        
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
        
        # Add staff/admin/officer permissions
        admin_role = guild.get_role(config.ROLE_IDS.get("ADMIN"))
        staff_role = guild.get_role(config.ROLE_IDS.get("STAFF"))
        officer_role = guild.get_role(config.ROLE_IDS.get("OFFICER"))
        helper_role = guild.get_role(config.ROLE_IDS.get("HELPER"))
        
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        if officer_role:
            overwrites[officer_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
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
        
        # Send confirmation in panel channel (ephemeral)
        await interaction.followup.send(
            f"✅ Ticket created: {channel.mention}\n\n"
            f"💡 **Click the 'Show Room Info' button in your ticket to see the room number!**",
            ephemeral=True
        )


class TicketActionView(discord.ui.View):
    """Action buttons for ticket (Join, Close, Cancel, Show Room Info, Kick)"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Show Room Info", style=discord.ButtonStyle.primary, emoji="🔢", custom_id="show_room_info_persistent", row=0)
    async def show_room_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show room info - REQUESTOR/STAFF/ADMIN/OFFICER ONLY (ephemeral)"""
        # Check if user has RESTRICTED role - BLOCK THEM
        restricted_role = interaction.guild.get_role(config.ROLE_IDS.get("RESTRICTED"))
        if restricted_role and restricted_role in interaction.user.roles:
            await interaction.response.send_message(
                "❌ You are restricted from using ticket buttons.",
                ephemeral=True
            )
            return
        
        bot = interaction.client
        ticket = await bot.db.get_ticket(interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message("❌ No active ticket found.", ephemeral=True)
            return
        
        # Check permissions (staff/admin/officer or requestor)
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF"), config.ROLE_IDS.get("OFFICER")] if rid)
        is_requestor = interaction.user.id == ticket["requestor_id"]
        
        if not (is_staff or is_requestor):
            await interaction.response.send_message("❌ Only the requestor, staff, officers, or admins can view room info.", ephemeral=True)
            return
        
        # Parse selected bosses
        try:
            selected_bosses_raw = ticket.get("selected_bosses", "[]")
            if isinstance(selected_bosses_raw, str):
                selected_bosses = json.loads(selected_bosses_raw)
            else:
                selected_bosses = selected_bosses_raw or []
        except:
            selected_bosses = []
        
        selected_server = ticket.get("selected_server", "Unknown")
        
        # Generate join commands
        join_commands = generate_join_commands(
            ticket["category"],
            selected_bosses,
            ticket["random_number"],
            selected_server
        )
        
        # Send ephemeral message with room info + WARNING TO NOT SHARE
        if join_commands:
            await interaction.response.send_message(
                f"🎮 **Room Number: `{ticket['random_number']}`**\n\n"
                f"**Join Commands:**\n{join_commands}\n\n"
                f"⚠️ **DO NOT share this room number with anyone!**",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"🎮 **Room Number: `{ticket['random_number']}`**\n\n"
                f"⚠️ **DO NOT share this room number with anyone!**",
                ephemeral=True
            )
    
    @discord.ui.button(label="Kick Helper", style=discord.ButtonStyle.secondary, emoji="👢", custom_id="kick_helper_persistent", row=0)
    async def kick_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Kick a helper from ticket - STAFF/ADMIN/OFFICER ONLY"""
        # Check if user has RESTRICTED role - BLOCK THEM
        restricted_role = interaction.guild.get_role(config.ROLE_IDS.get("RESTRICTED"))
        if restricted_role and restricted_role in interaction.user.roles:
            await interaction.response.send_message(
                "❌ You are restricted from using ticket buttons.",
                ephemeral=True
            )
            return
        
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF"), config.ROLE_IDS.get("OFFICER")] if rid)
        
        if not is_staff:
            await interaction.response.send_message("❌ Only staff, officers, or admins can kick helpers.", ephemeral=True)
            return
        
        bot = interaction.client
        ticket = await bot.db.get_ticket(interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message("❌ No active ticket found.", ephemeral=True)
            return
        
        if not ticket["helpers"]:
            await interaction.response.send_message("❌ No helpers to kick from this ticket.", ephemeral=True)
            return
        
        # Show modal to select which helper to kick
        modal = KickHelperModal(ticket)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Join Ticket", style=discord.ButtonStyle.success, emoji="✅", custom_id="ticket_join_persistent", row=1)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Helper joins ticket - ONE TICKET AT A TIME"""
        try:
            # Check if user has RESTRICTED role - BLOCK THEM
            restricted_role = interaction.guild.get_role(config.ROLE_IDS.get("RESTRICTED"))
            if restricted_role and restricted_role in interaction.user.roles:
                await interaction.response.send_message(
                    "❌ You are restricted from using ticket buttons.",
                    ephemeral=True
                )
                return
            
            bot = interaction.client
            ticket = await bot.db.get_ticket(interaction.channel_id)
            
            if not ticket:
                await interaction.response.send_message("❌ No active ticket found.", ephemeral=True)
                return
            
            if ticket.get("is_closed", False):
                await interaction.response.send_message("❌ This ticket is already closed.", ephemeral=True)
                return
            
            # Check if user is requestor
            if interaction.user.id == ticket["requestor_id"]:
                await interaction.response.send_message("❌ You cannot join your own ticket!", ephemeral=True)
                return
            
            # Check if user is already a helper
            if interaction.user.id in ticket["helpers"]:
                await interaction.response.send_message("❌ You've already joined this ticket!", ephemeral=True)
                return
            
            # Check if user is REQUESTOR of another active ticket - PREVENT JOINING
            all_tickets = await bot.db.get_all_tickets()
            for other_ticket in all_tickets:
                if other_ticket["channel_id"] == interaction.channel_id:
                    continue
                if interaction.user.id == other_ticket["requestor_id"]:
                    # Verify channel exists
                    other_channel = interaction.guild.get_channel(other_ticket["channel_id"])
                    if other_channel:
                        await interaction.response.send_message(
                            f"❌ You cannot join tickets while you have an active ticket as requestor: {other_channel.mention}\n"
                            "Please close or cancel your ticket first.",
                            ephemeral=True
                        )
                        return
            
            # Check if user is in another active ticket (with verification that ticket channel exists)
            for other_ticket in all_tickets:
                if other_ticket["channel_id"] == interaction.channel_id:
                    continue
                if interaction.user.id in other_ticket["helpers"]:
                    # Verify the channel actually exists
                    other_channel = interaction.guild.get_channel(other_ticket["channel_id"])
                    if other_channel:
                        # Channel exists, user is actually in another ticket
                        await interaction.response.send_message(
                            f"❌ You're already in another ticket: {other_channel.mention}\n"
                            "You must leave that ticket before joining a new one.\n\n"
                            "*If you believe this is an error, ask an admin to run `/free_helper @you`*",
                            ephemeral=True
                        )
                        return
                    else:
                        # Channel doesn't exist - remove user from phantom ticket
                        print(f"⚠️ Removing {interaction.user.id} from phantom ticket {other_ticket['channel_id']}")
                        other_ticket["helpers"].remove(interaction.user.id)
                        await bot.db.save_ticket(other_ticket)
            
            # Check if ticket is full
            max_helpers = config.HELPER_SLOTS.get(ticket["category"], 3)
            if len(ticket["helpers"]) >= max_helpers:
                await interaction.response.send_message(
                    f"❌ This ticket is full! ({len(ticket['helpers'])}/{max_helpers} helpers)",
                    ephemeral=True
                )
                return
            
            # Check if user has helper role
            helper_role = interaction.guild.get_role(config.ROLE_IDS.get("HELPER"))
            if helper_role and helper_role not in interaction.user.roles:
                await interaction.response.send_message("❌ You need the Helper role to join tickets!", ephemeral=True)
                return
            
            # Add helper
            ticket["helpers"].append(interaction.user.id)
            await bot.db.save_ticket(ticket)
            
            # Give channel permissions
            try:
                await interaction.channel.set_permissions(interaction.user, view_channel=True, send_messages=True)
            except Exception as e:
                print(f"Failed to set permissions: {e}")
            
            # Update embed
            try:
                selected_bosses_raw = ticket.get("selected_bosses", "[]")
                if isinstance(selected_bosses_raw, str):
                    selected_bosses = json.loads(selected_bosses_raw)
                else:
                    selected_bosses = selected_bosses_raw or []
            except:
                selected_bosses = []
            
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
            except Exception as e:
                print(f"Failed to update embed: {e}")
            
            # Generate join commands based on selected bosses IN ORDER
            join_commands = generate_join_commands(
                ticket["category"],
                selected_bosses,
                ticket["random_number"],
                selected_server
            )
            
            if join_commands:
                await interaction.response.send_message(
                    f"✅ You've joined the ticket!\n\n**🎮 Room Number: `{ticket['random_number']}`**\n\n**Join Commands:**\n{join_commands}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"✅ You've joined the ticket!\n\n**🎮 Room Number: `{ticket['random_number']}`**",
                    ephemeral=True
                )
            
            # Notify channel
            await interaction.channel.send(f"✅ {interaction.user.mention} joined the ticket!")
        
        except Exception as e:
            print(f"❌ Join button error: {e}")
            import traceback
            traceback.print_exc()
            try:
                await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
            except:
                await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket_close_persistent", row=1)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close ticket with rewards - STAFF/ADMIN/OFFICER/REQUESTOR"""
        # Check if user has RESTRICTED role - BLOCK THEM
        restricted_role = interaction.guild.get_role(config.ROLE_IDS.get("RESTRICTED"))
        if restricted_role and restricted_role in interaction.user.roles:
            await interaction.response.send_message(
                "❌ You are restricted from using ticket buttons.",
                ephemeral=True
            )
            return
        
        bot = interaction.client
        ticket = await bot.db.get_ticket(interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message("❌ No active ticket found.", ephemeral=True)
            return
        
        if ticket.get("is_closed", False):
            await interaction.response.send_message("❌ This ticket is already closed.", ephemeral=True)
            return
        
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF"), config.ROLE_IDS.get("OFFICER")] if rid)
        is_requestor = interaction.user.id == ticket["requestor_id"]
        
        if not (is_staff or is_requestor):
            await interaction.response.send_message("❌ Only staff, officers, admins, or the requestor can close tickets.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        guild = interaction.guild
        admin_role = guild.get_role(config.ROLE_IDS.get("ADMIN"))
        staff_role = guild.get_role(config.ROLE_IDS.get("STAFF"))
        officer_role = guild.get_role(config.ROLE_IDS.get("OFFICER"))
        helper_role = guild.get_role(config.ROLE_IDS.get("HELPER"))
        
        # === STEP 1: REMOVE PERMISSIONS IMMEDIATELY ===
        new_overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        
        if admin_role:
            new_overwrites[admin_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        if staff_role:
            new_overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        if officer_role:
            new_overwrites[officer_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        
        # Block requestor
        requestor = guild.get_member(ticket["requestor_id"])
        if requestor:
            new_overwrites[requestor] = discord.PermissionOverwrite(
                view_channel=False,
                send_messages=False,
                read_message_history=False
            )
        
        # Block helpers (except staff/admin/officer)
        for helper_id in ticket["helpers"]:
            helper = guild.get_member(helper_id)
            if helper:
                is_helper_staff = (admin_role and admin_role in helper.roles) or (staff_role and staff_role in helper.roles) or (officer_role and officer_role in helper.roles)
                if not is_helper_staff:
                    new_overwrites[helper] = discord.PermissionOverwrite(
                        view_channel=False,
                        send_messages=False,
                        read_message_history=False
                    )
        
        # Block Helper ROLE
        if helper_role:
            new_overwrites[helper_role] = discord.PermissionOverwrite(
                view_channel=False,
                send_messages=False,
                read_message_history=False
            )
        
        await interaction.channel.edit(overwrites=new_overwrites)
        
        # === STEP 2: SEND CLOSED EMBED ===
        helpers_text = ", ".join([f"<@{h}>" for h in ticket["helpers"]]) if ticket["helpers"] else "None"
        points_per_helper = ticket.get("points", 0)
        total_awarded = points_per_helper * len(ticket["helpers"])
        
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
        
        # === STEP 3: SEND DELETE BUTTON ===
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
        await interaction.followup.send(embed=delete_embed, view=delete_view, ephemeral=False)
        
        # === STEP 4: DATABASE OPERATIONS ===
        try:
            # Mark as closed
            ticket["is_closed"] = True
            await bot.db.save_ticket(ticket)
            
            # Award points
            for helper_id in ticket["helpers"]:
                try:
                    await bot.db.add_points(helper_id, points_per_helper)
                except Exception as e:
                    print(f"⚠️ Failed to award points to {helper_id}: {e}")
            
            # Generate transcript
            try:
                await generate_transcript(interaction.channel, bot, ticket)
            except Exception as e:
                print(f"⚠️ Transcript generation failed: {e}")
            
            # Save history
            try:
                await bot.db.save_ticket_history({
                    "channel_id": ticket["channel_id"],
                    "category": ticket["category"],
                    "requestor_id": ticket["requestor_id"],
                    "helpers": json.dumps(ticket["helpers"]),
                    "points_per_helper": points_per_helper,
                    "total_points_awarded": total_awarded,
                    "closed_by": interaction.user.id
                })
            except Exception as e:
                print(f"⚠️ History save failed: {e}")
            
            # Delete from active
            try:
                await bot.db.delete_ticket(ticket["channel_id"])
            except Exception as e:
                print(f"⚠️ Ticket deletion failed: {e}")
                
        except Exception as e:
            print(f"⚠️ Database error during close: {e}")
            traceback.print_exc()
    
    @discord.ui.button(label="Cancel Ticket", style=discord.ButtonStyle.secondary, emoji="❌", custom_id="ticket_cancel_persistent", row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel ticket WITHOUT rewards - Requestor/Staff/Admin/Officer"""
        # Check if user has RESTRICTED role - BLOCK THEM
        restricted_role = interaction.guild.get_role(config.ROLE_IDS.get("RESTRICTED"))
        if restricted_role and restricted_role in interaction.user.roles:
            await interaction.response.send_message(
                "❌ You are restricted from using ticket buttons.",
                ephemeral=True
            )
            return
        
        bot = interaction.client
        ticket = await bot.db.get_ticket(interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message("❌ No active ticket found.", ephemeral=True)
            return
        
        if ticket.get("is_closed", False):
            await interaction.response.send_message("❌ This ticket is already closed.", ephemeral=True)
            return
        
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF"), config.ROLE_IDS.get("OFFICER")] if rid)
        is_requestor = interaction.user.id == ticket["requestor_id"]
        
        if not (is_staff or is_requestor):
            await interaction.response.send_message("❌ Only staff, officers, admins, or the requestor can cancel tickets.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        guild = interaction.guild
        admin_role = guild.get_role(config.ROLE_IDS.get("ADMIN"))
        staff_role = guild.get_role(config.ROLE_IDS.get("STAFF"))
        officer_role = guild.get_role(config.ROLE_IDS.get("OFFICER"))
        helper_role = guild.get_role(config.ROLE_IDS.get("HELPER"))
        
        # === REMOVE PERMISSIONS ===
        new_overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        
        if admin_role:
            new_overwrites[admin_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        if staff_role:
            new_overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        if officer_role:
            new_overwrites[officer_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        
        # Block requestor
        requestor = guild.get_member(ticket["requestor_id"])
        if requestor:
            new_overwrites[requestor] = discord.PermissionOverwrite(
                view_channel=False,
                send_messages=False,
                read_message_history=False
            )
        
        # Block helpers
        for helper_id in ticket["helpers"]:
            helper = guild.get_member(helper_id)
            if helper:
                is_helper_staff = (admin_role and admin_role in helper.roles) or (staff_role and staff_role in helper.roles) or (officer_role and officer_role in helper.roles)
                if not is_helper_staff:
                    new_overwrites[helper] = discord.PermissionOverwrite(
                        view_channel=False,
                        send_messages=False,
                        read_message_history=False
                    )
        
        # Block Helper ROLE
        if helper_role:
            new_overwrites[helper_role] = discord.PermissionOverwrite(
                view_channel=False,
                send_messages=False,
                read_message_history=False
            )
        
        await interaction.channel.edit(overwrites=new_overwrites)
        
        # === SEND CANCELLED EMBED ===
        helpers_text = ", ".join([f"<@{h}>" for h in ticket["helpers"]]) if ticket["helpers"] else "None"
        
        cancelled_embed = discord.Embed(
            title=f"❌ {ticket['category']} (Cancelled)",
            description="**This ticket was cancelled. No points were awarded.**",
            color=config.COLORS["DANGER"],
            timestamp=discord.utils.utcnow()
        )
        cancelled_embed.add_field(name="Requestor", value=f"<@{ticket['requestor_id']}>", inline=False)
        cancelled_embed.add_field(name="Helpers", value=helpers_text, inline=False)
        cancelled_embed.add_field(name="Points Awarded", value="**0** (Cancelled)", inline=True)
        cancelled_embed.set_footer(text=f"Cancelled by {interaction.user}")
        
        await interaction.channel.send(embed=cancelled_embed)
        
        # === SEND DELETE BUTTON ===
        delete_embed = discord.Embed(
            title="🗑️ Delete Channel?",
            description=(
                "This ticket has been cancelled.\n\n"
                "Click the button below to delete this channel.\n"
                "Only staff can delete the channel."
            ),
            color=config.COLORS["DANGER"]
        )
        
        delete_view = DeleteChannelView()
        await interaction.followup.send(embed=delete_embed, view=delete_view, ephemeral=False)
        
        # === DATABASE CLEANUP ===
        try:
            ticket["is_closed"] = True
            await bot.db.save_ticket(ticket)
            
            # Generate transcript
            try:
                await generate_transcript(interaction.channel, bot, ticket, is_cancelled=True)
            except Exception as e:
                print(f"⚠️ Transcript generation failed: {e}")
            
            # Delete from active
            try:
                await bot.db.delete_ticket(ticket["channel_id"])
            except Exception as e:
                print(f"⚠️ Ticket deletion failed: {e}")
                
        except Exception as e:
            print(f"⚠️ Database error during cancel: {e}")
            traceback.print_exc()


class KickHelperModal(discord.ui.Modal):
    """Modal to kick a helper from ticket"""
    def __init__(self, ticket: dict):
        super().__init__(title="Kick Helper")
        self.ticket = ticket
        
        self.helper_mention = discord.ui.TextInput(
            label="Helper to kick (mention or ID)",
            placeholder="@username or user ID",
            required=True,
            max_length=100,
            style=discord.TextStyle.short
        )
        self.add_item(self.helper_mention)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Kick the specified helper"""
        bot = interaction.client
        
        # Parse user mention or ID
        helper_input = self.helper_mention.value.strip()
        helper_id = None
        
        # Try to extract ID from mention
        if helper_input.startswith("<@") and helper_input.endswith(">"):
            helper_id = int(helper_input.replace("<@", "").replace("!", "").replace(">", ""))
        else:
            try:
                helper_id = int(helper_input)
            except:
                await interaction.response.send_message("❌ Invalid user mention or ID.", ephemeral=True)
                return
        
        # Check if helper is in ticket
        if helper_id not in self.ticket["helpers"]:
            await interaction.response.send_message("❌ This user is not a helper in this ticket.", ephemeral=True)
            return
        
        # Remove helper
        self.ticket["helpers"].remove(helper_id)
        await bot.db.save_ticket(self.ticket)
        
        # Remove channel permissions
        guild = interaction.guild
        helper = guild.get_member(helper_id)
        if helper:
            try:
                await interaction.channel.set_permissions(helper, overwrite=None)
            except Exception as e:
                print(f"Failed to remove permissions: {e}")
        
        # Update embed
        try:
            selected_bosses_raw = self.ticket.get("selected_bosses", "[]")
            if isinstance(selected_bosses_raw, str):
                selected_bosses = json.loads(selected_bosses_raw)
            else:
                selected_bosses = selected_bosses_raw or []
        except:
            selected_bosses = []
        
        selected_server = self.ticket.get("selected_server", "Unknown")
        
        embed = create_ticket_embed(
            category=self.ticket["category"],
            requestor_id=self.ticket["requestor_id"],
            in_game_name=self.ticket.get("in_game_name", "N/A"),
            concerns=self.ticket.get("concerns", "None"),
            helpers=self.ticket["helpers"],
            random_number=self.ticket["random_number"],
            selected_bosses=selected_bosses,
            selected_server=selected_server
        )
        
        # Update ticket message
        try:
            msg = await interaction.channel.fetch_message(self.ticket["embed_message_id"])
            await msg.edit(embed=embed)
        except Exception as e:
            print(f"Failed to update embed: {e}")
        
        await interaction.response.send_message(f"✅ Kicked <@{helper_id}> from the ticket.", ephemeral=False)
        await interaction.channel.send(f"👢 <@{helper_id}> was kicked from the ticket by {interaction.user.mention}.")


class DeleteChannelView(discord.ui.View):
    """View with delete channel button"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Delete Channel", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="delete_channel_persistent")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete the channel - STAFF/ADMIN/OFFICER ONLY"""
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF"), config.ROLE_IDS.get("OFFICER")] if rid)
        
        if not is_staff:
            await interaction.response.send_message("❌ Only staff, officers, or admins can delete the channel.", ephemeral=True)
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


def format_boss_name_for_display(boss: str) -> str:
    """Remove 'Ultra' prefix from non-ultra bosses for display in embed"""
    # Bosses that should NOT have "Ultra" in display
    non_ultra_bosses = {
        "Ultra Lich": "Lich",
        "Ultra Beast": "Beast", 
        "Ultra Deimos": "Deimos",
        "Ultra Flibbi": "Flibbi",
        "Ultra Bane": "Bane",
        "Ultra Xyfrag": "Xyfrag",
        "Ultra Kathool": "Kathool",
        "Ultra Astral": "Astral",
        "Ultra Azalith": "Azalith",
        "Ultra Champion Drakath": "Champion Drakath"
    }
    
    return non_ultra_bosses.get(boss, boss)


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
        # Format boss names to remove "Ultra" where it shouldn't be
        formatted_bosses = [format_boss_name_for_display(boss) for boss in selected_bosses]
        embed.add_field(
            name="📋 Selected Bosses",
            value="\n".join([f"⚔️ {boss}" for boss in formatted_bosses]),
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
    """Generate /join commands based on selected bosses IN CORRECT ORDER"""
    commands = []
    
    # Define correct order for each category
    if category == "Daily 4-Man Express":
        # Order: Dage, Tyndarius, Engineer, Warden, Ezrajal
        boss_order = ["Ultra Dage", "Ultra Tyndarius", "Ultra Engineer", "Ultra Warden", "Ultra Ezrajal"]
        for boss in boss_order:
            if boss in selected_bosses:
                # Ultra + word together
                commands.append(f"`/join ultra{boss.replace('Ultra ', '').lower()}-{room_number}`")
    
    elif category == "Daily 7-Man Express":
        # Order: Lich, Beast, Deimos, Flibbi, Bane, Xyfrag, Kathool, Astral, Azalith
        boss_order = ["Ultra Lich", "Ultra Beast", "Ultra Deimos", "Ultra Flibbi", "Ultra Bane", 
                      "Ultra Xyfrag", "Ultra Kathool", "Ultra Astral", "Ultra Azalith"]
        for boss in boss_order:
            if boss in selected_bosses:
                # Special cases
                if boss == "Ultra Lich":
                    commands.append(f"`/join frozenlair-{room_number}`")
                elif boss == "Ultra Beast":
                    commands.append(f"`/join beast-{room_number}`")
                elif boss == "Ultra Deimos":
                    commands.append(f"`/join deimos-{room_number}`")
                elif boss == "Ultra Flibbi":
                    commands.append(f"`/join voidflibbi-{room_number}`")
                elif boss == "Ultra Bane":
                    commands.append(f"`/join voidnightbane-{room_number}`")
                elif boss == "Ultra Xyfrag":
                    commands.append(f"`/join voidxyfrag-{room_number}`")
                elif boss == "Ultra Kathool":
                    commands.append(f"`/join kathooldepths-{room_number}`")
                elif boss == "Ultra Astral":
                    commands.append(f"`/join astralshrine-{room_number}`")
                elif boss == "Ultra Azalith":
                    commands.append(f"`/join apexazalith-{room_number}`")
    
    elif category == "Weekly Ultra Express":
        # Order: Dage > Nulgath > Drago > Darkon > CDrakath
        boss_order = ["Ultra Dage", "Ultra Nulgath", "Ultra Drago", "Ultra Darkon", "Ultra Champion Drakath"]
        for boss in boss_order:
            if boss in selected_bosses:
                if boss == "Ultra Champion Drakath":
                    commands.append(f"`/join championdrakath-{room_number}`")
                else:
                    # Ultra + word together
                    commands.append(f"`/join ultra{boss.replace('Ultra ', '').lower()}-{room_number}`")
    
    elif category == "UltraSpeaker Express":
        commands.append(f"`/join ultraspeaker-{room_number}`")
    
    elif category == "Ultra Gramiel Express":
        commands.append(f"`/join ultragramiel-{room_number}`")
    
    elif category == "GrimChallenge Express":
        commands.append(f"`/join grimchallenge-{room_number}`")
    
    elif category == "Daily Temple Express":
        commands.append(f"`/join templeshrine-{room_number}`")
    
    return "\n".join(commands) if commands else ""


async def generate_transcript(channel: discord.TextChannel, bot, ticket: dict, is_cancelled: bool = False):
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
    
    status = "CANCELLED" if is_cancelled else "CLOSED"
    
    transcript_lines = [
        f"=== TRANSCRIPT FOR {channel.name.upper()} ===",
        f"Status: {status}",
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
    
    title_status = "Cancelled" if is_cancelled else "Closed"
    
    embed = discord.Embed(
        title=f"📄 Transcript: {channel.name} ({title_status})",
        description=f"**Category:** {ticket['category']}\n**Room Number:** {ticket['random_number']}\n**Status:** {title_status}",
        color=config.COLORS["DANGER"] if is_cancelled else config.COLORS["PRIMARY"],
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
    
    @bot.tree.command(name="free_helper", description="Remove a helper from all phantom tickets (Admin only)")
    async def free_helper(interaction: discord.Interaction, user: discord.Member):
        """Free a helper stuck in phantom tickets"""
        member = interaction.user
        is_admin = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF")] if rid)
        
        if not is_admin:
            await interaction.response.send_message("❌ Only admins can use this command.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        freed_count = 0
        all_tickets = await bot.db.get_all_tickets()
        
        for ticket in all_tickets:
            if user.id in ticket["helpers"]:
                # Check if channel exists
                channel = interaction.guild.get_channel(ticket["channel_id"])
                if not channel:
                    # Phantom ticket - remove user
                    ticket["helpers"].remove(user.id)
                    await bot.db.save_ticket(ticket)
                    freed_count += 1
                    print(f"✅ Freed {user.name} from phantom ticket {ticket['channel_id']}")
        
        if freed_count > 0:
            await interaction.followup.send(
                f"✅ Freed {user.mention} from **{freed_count}** phantom ticket(s)!\n"
                f"They can now join new tickets.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"ℹ️ {user.mention} is not stuck in any phantom tickets.",
                ephemeral=True
            )
    
    @bot.tree.command(name="kick_from_ticket", description="Kick a helper from a ticket (Admin/Staff/Officer only)")
    async def kick_from_ticket(interaction: discord.Interaction, user: discord.Member):
        """Kick a user from current ticket - Admin/Staff/Officer only"""
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF"), config.ROLE_IDS.get("OFFICER")] if rid)
        
        if not is_staff:
            await interaction.response.send_message("❌ Only admins, staff, or officers can use this command.", ephemeral=True)
            return
        
        bot = interaction.client
        ticket = await bot.db.get_ticket(interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message("❌ This command must be used in a ticket channel.", ephemeral=True)
            return
        
        if user.id not in ticket["helpers"]:
            await interaction.response.send_message(f"❌ {user.mention} is not a helper in this ticket.", ephemeral=True)
            return
        
        # Remove helper
        ticket["helpers"].remove(user.id)
        await bot.db.save_ticket(ticket)
        
        # Remove permissions
        try:
            await interaction.channel.set_permissions(user, overwrite=None)
        except Exception as e:
            print(f"Failed to remove permissions: {e}")
        
        # Update embed
        try:
            selected_bosses_raw = ticket.get("selected_bosses", "[]")
            if isinstance(selected_bosses_raw, str):
                selected_bosses = json.loads(selected_bosses_raw)
            else:
                selected_bosses = selected_bosses_raw or []
        except:
            selected_bosses = []
        
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
        
        # Update ticket message
        try:
            msg = await interaction.channel.fetch_message(ticket["embed_message_id"])
            await msg.edit(embed=embed)
        except Exception as e:
            print(f"Failed to update embed: {e}")
        
        await interaction.response.send_message(f"✅ Kicked {user.mention} from the ticket.", ephemeral=False)
        await interaction.channel.send(f"👢 {user.mention} was kicked from the ticket by {interaction.user.mention}.")
    
    @bot.tree.command(name="give_points", description="Give points to a user (Admin/Staff only)")
    async def give_points(interaction: discord.Interaction, user: discord.Member, points: int):
        """Give points to a user"""
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF")] if rid)
        
        if not is_staff:
            await interaction.response.send_message("❌ Only admins or staff can give points.", ephemeral=True)
            return
        
        if points <= 0:
            await interaction.response.send_message("❌ Points must be positive.", ephemeral=True)
            return
        
        await bot.db.add_points(user.id, points)
        await interaction.response.send_message(
            f"✅ Gave **{points}** points to {user.mention}!",
            ephemeral=False
        )
    
    @bot.tree.command(name="remove_points", description="Remove points from a user (Admin/Staff only)")
    async def remove_points(interaction: discord.Interaction, user: discord.Member, points: int):
        """Remove points from a user"""
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF")] if rid)
        
        if not is_staff:
            await interaction.response.send_message("❌ Only admins or staff can remove points.", ephemeral=True)
            return
        
        if points <= 0:
            await interaction.response.send_message("❌ Points must be positive.", ephemeral=True)
            return
        
        await bot.db.add_points(user.id, -points)
        await interaction.response.send_message(
            f"✅ Removed **{points}** points from {user.mention}!",
            ephemeral=False
        )
    
    @bot.tree.command(name="proof", description="Show proof submission guidelines")
    async def proof(interaction: discord.Interaction):
        """Show proof guidelines with example image"""
        proof_data = config.HARDCODED_COMMANDS.get("proof", {})
        text = proof_data.get("text", "No proof guidelines configured.")
        image = proof_data.get("image")
        
        embed = discord.Embed(
            title="📸 Proof Submission Guide",
            description=text,
            color=config.COLORS["PRIMARY"]
        )
        
        if image:
            embed.set_image(url=image)
        
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="hrules", description="Show helper rules")
    async def hrules(interaction: discord.Interaction):
        """Show helper rules"""
        rules_data = config.HARDCODED_COMMANDS.get("hrules", {})
        text = rules_data.get("text", "No helper rules configured.")
        
        embed = discord.Embed(
            title="📋 Helper Rules",
            description=text,
            color=config.COLORS["WARNING"]
        )
        
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="rrules", description="Show requestor rules")
    async def rrules(interaction: discord.Interaction):
        """Show requestor rules"""
        rules_data = config.HARDCODED_COMMANDS.get("rrules", {})
        text = rules_data.get("text", "No requestor rules configured.")
        
        embed = discord.Embed(
            title="📋 Requestor Rules",
            description=text,
            color=config.COLORS["WARNING"]
        )
        
        await interaction.response.send_message(embed=embed)