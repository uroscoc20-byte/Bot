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
import time
import config

# === GLOBAL LOCK DICTIONARY FOR RACE CONDITION PREVENTION ===
ticket_locks = {}

# === COOLDOWN TRACKING ===
join_cooldowns = {}  # {user_id: timestamp}
leave_cooldowns = {}  # {user_id: timestamp}
COOLDOWN_SECONDS = 120  # 2 minutes

def get_ticket_lock(channel_id: int):
    """Get or create a lock for a specific ticket channel"""
    if channel_id not in ticket_locks:
        ticket_locks[channel_id] = asyncio.Lock()
    return ticket_locks[channel_id]

def check_cooldown(user_id: int, cooldown_dict: dict) -> Optional[int]:
    """Check if user is on cooldown. Returns remaining seconds or None if no cooldown"""
    if user_id in cooldown_dict:
        elapsed = time.time() - cooldown_dict[user_id]
        if elapsed < COOLDOWN_SECONDS:
            return int(COOLDOWN_SECONDS - elapsed)
    return None

def set_cooldown(user_id: int, cooldown_dict: dict):
    """Set cooldown for user"""
    cooldown_dict[user_id] = time.time()


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
        
        bot = interaction.client
        all_tickets = await bot.db.get_all_tickets()
        
        # === NEW: CHECK IF USER ALREADY HAS AN ACTIVE TICKET AS REQUESTOR ===
        for ticket in all_tickets:
            if interaction.user.id == ticket["requestor_id"]:
                # Verify channel exists
                channel = interaction.guild.get_channel(ticket["channel_id"])
                if channel:
                    await interaction.response.send_message(
                        f"❌ You already have an active ticket: {channel.mention}\n"
                        "Please close or cancel that ticket before creating a new one.",
                        ephemeral=True
                    )
                    return
        
        # Check if user is a helper in any active ticket - PREVENT CREATING TICKET
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
        
        # Create options with CORRECT display names (remove Ultra from non-ultra bosses)
        options = []
        for boss in boss_list:
            display_name = format_boss_name_for_select(boss)
            options.append(discord.SelectOption(label=display_name, value=boss, emoji="⚔️"))
        
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
        
        # === DOUBLE-CHECK: User doesn't have an active ticket ===
        bot = interaction.client
        all_tickets = await bot.db.get_all_tickets()
        
        for ticket in all_tickets:
            if interaction.user.id == ticket["requestor_id"]:
                channel = interaction.guild.get_channel(ticket["channel_id"])
                if channel:
                    await interaction.followup.send(
                        f"❌ You already have an active ticket: {channel.mention}\n"
                        "Please close or cancel that ticket before creating a new one.",
                        ephemeral=True
                    )
                    return
        
        guild = interaction.guild
        category_id = config.CHANNEL_IDS.get("TICKETS_CATEGORY")
        
        if not category_id:
            await interaction.followup.send("❌ Ticket category not configured!", ephemeral=True)
            return
        
        category = guild.get_channel(category_id)
        if not category:
            await interaction.followup.send("❌ Ticket category not found!", ephemeral=True)
            return
        
        # Generate random number for ticket (1000-99999)
        random_number = random.randint(1000, 99999)
        
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
       
        # PIN THE TICKET MESSAGE (with system message cleanup)
        try:
            await ticket_msg.pin(reason="Ticket embed auto-pinned for easy access")
            print(f"✅ Pinned ticket message in {channel.name}")
            
            # Wait a moment for the system message to appear
            await asyncio.sleep(1)
            
            # Delete the "X pinned a message" system notification
            async for msg in channel.history(limit=10):
                if msg.type == discord.MessageType.pins_add:
                    try:
                        await msg.delete()
                        print(f"✅ Deleted pin notification in {channel.name}")
                    except Exception as e:
                        print(f"⚠️ Could not delete pin notification: {e}")
                    break
        except discord.Forbidden:
            print(f"❌ Bot lacks permission to pin messages in {channel.name}")
        except discord.HTTPException as e:
            print(f"❌ HTTP error while pinning: {e}")
        except Exception as e:
            print(f"❌ Unexpected error while pinning: {e}")
            traceback.print_exc()
        
        # Save ticket to database
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
    """Action buttons for ticket (Join, Leave, Close, Cancel, Show Room Info)"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Show Room Info", style=discord.ButtonStyle.primary, emoji="🔢", custom_id="show_room_info_persistent", row=0)
    async def show_room_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show room info - REQUESTOR/STAFF/ADMIN/OFFICER/JOINED HELPERS"""
        bot = interaction.client
        ticket = await bot.db.get_ticket(interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message("❌ No active ticket found.", ephemeral=True)
            return
        
        # Check permissions - ONLY staff/admin/officer or requestor or helpers who JOINED
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF"), config.ROLE_IDS.get("OFFICER")] if rid)
        is_requestor = interaction.user.id == ticket["requestor_id"]
        is_helper_in_ticket = interaction.user.id in ticket["helpers"]
        
        if not (is_staff or is_requestor or is_helper_in_ticket):
            await interaction.response.send_message("❌ Only the requestor, helpers who joined this ticket, staff, officers, or admins can view room info.", ephemeral=True)
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
                f"⚠️ **DO NOT share this room number with anyone outside this ticket!**",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"🎮 **Room Number: `{ticket['random_number']}`**\n\n"
                f"⚠️ **DO NOT share this room number with anyone outside this ticket!**",
                ephemeral=True
            )
    
    @discord.ui.button(label="Leave Ticket", style=discord.ButtonStyle.secondary, emoji="🚪", custom_id="leave_ticket_persistent", row=0)
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Helper leaves ticket - WITH 120 SECOND COOLDOWN"""
        # Check cooldown
        remaining = check_cooldown(interaction.user.id, leave_cooldowns)
        if remaining:
            await interaction.response.send_message(
                f"⏳ You're on cooldown! Please wait **{remaining} seconds** before leaving another ticket.",
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
        
        # Check if user is a helper
        if interaction.user.id not in ticket["helpers"]:
            await interaction.response.send_message("❌ You are not a helper in this ticket!", ephemeral=True)
            return
        
        # Remove helper
        ticket["helpers"].remove(interaction.user.id)
        await bot.db.save_ticket(ticket)
        
        # Set cooldown
        set_cooldown(interaction.user.id, leave_cooldowns)
        
        # Remove channel permissions
        try:
            await interaction.channel.set_permissions(interaction.user, overwrite=None)
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
        
        await interaction.response.send_message(f"✅ You've left the ticket!", ephemeral=True)
        await interaction.channel.send(f"🚪 {interaction.user.mention} left the ticket.")
    
    @discord.ui.button(label="Join Ticket", style=discord.ButtonStyle.success, emoji="✅", custom_id="ticket_join_persistent", row=1)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Helper joins ticket - ONE TICKET AT A TIME - WITH RACE CONDITION PROTECTION AND 120 SECOND COOLDOWN"""
        # Check cooldown FIRST
        remaining = check_cooldown(interaction.user.id, join_cooldowns)
        if remaining:
            await interaction.response.send_message(
                f"⏳ You're on cooldown! Please wait **{remaining} seconds** before joining another ticket.",
                ephemeral=True
            )
            return
        
        # === ACQUIRE LOCK TO PREVENT RACE CONDITIONS ===
        lock = get_ticket_lock(interaction.channel_id)
        
        async with lock:  # Only one person can execute this block at a time
            try:
                bot = interaction.client
                
                # === FRESH DATABASE READ (CRITICAL FOR RACE CONDITION FIX) ===
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
                
                # Check if user is already a helper (FRESH CHECK)
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
                
                # Check if ticket is full (FRESH CHECK WITH LATEST DATA)
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
                
                # === SET COOLDOWN AFTER ALL CHECKS PASS ===
                set_cooldown(interaction.user.id, join_cooldowns)
                
                # Add helper
                ticket["helpers"].append(interaction.user.id)
                await bot.db.save_ticket(ticket)
                
                # Grant channel permissions
                await interaction.channel.set_permissions(
                    interaction.user,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )
                
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
                
                # Generate join commands
                join_commands = generate_join_commands(
                    ticket["category"],
                    selected_bosses,
                    ticket["random_number"],
                    selected_server
                )
                
                # Show room number to helper
                if join_commands:
                    await interaction.response.send_message(
                        f"✅ You've joined the ticket!\n\n"
                        f"🎮 **Room Number: `{ticket['random_number']}`**\n\n"
                        f"**Join Commands:**\n{join_commands}\n\n"
                        f"⚠️ **DO NOT share this room number with anyone outside this ticket!**",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"✅ You've joined the ticket!\n\n"
                        f"🎮 **Room Number: `{ticket['random_number']}`**\n\n"
                        f"⚠️ **DO NOT share this room number with anyone outside this ticket!**",
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
        
        # ADMIN/STAFF/OFFICER roles get full access + manage channels
        if admin_role:
            new_overwrites[admin_role] = discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                read_message_history=True,
                manage_channels=True,
                manage_permissions=True
            )
        if staff_role:
            new_overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                read_message_history=True,
                manage_channels=True,
                manage_permissions=True
            )
        if officer_role:
            new_overwrites[officer_role] = discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                read_message_history=True
            )
        
        # Block requestor UNLESS they are staff/officer/admin
        requestor = guild.get_member(ticket["requestor_id"])
        if requestor:
            is_requestor_staff = (admin_role and admin_role in requestor.roles) or \
                                 (staff_role and staff_role in requestor.roles) or \
                                 (officer_role and officer_role in requestor.roles)
            
            if not is_requestor_staff:
                # Regular requestor - block access
                new_overwrites[requestor] = discord.PermissionOverwrite(
                    view_channel=False,
                    send_messages=False,
                    read_message_history=False
                )
            # If requestor IS staff/officer/admin, they keep access via role permissions
        
        # Remove all helpers
        for helper_id in ticket["helpers"]:
            helper = guild.get_member(helper_id)
            if helper:
                is_helper_staff = (admin_role and admin_role in helper.roles) or \
                                  (staff_role and staff_role in helper.roles) or \
                                  (officer_role and officer_role in helper.roles)
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
        
        # === STEP 2: CREATE FINAL EMBED ===
        helpers_text = ", ".join([f"<@{h}>" for h in ticket["helpers"]]) if ticket["helpers"] else "None"
        
        # Get points per helper
        points_per = config.POINT_VALUES.get(ticket["category"], 0)
        total_points = points_per * len(ticket["helpers"]) if ticket["helpers"] else 0
        
        final_embed = discord.Embed(
            title=f"✅ {ticket['category']} (Completed)",
            description="**Ticket Completed! Points awarded to all helpers.**",
            color=config.COLORS["SUCCESS"],
            timestamp=discord.utils.utcnow()
        )
        final_embed.add_field(name="Requestor", value=f"<@{ticket['requestor_id']}>", inline=False)
        final_embed.add_field(name="Helpers", value=helpers_text, inline=False)
        final_embed.add_field(name="Points per Helper", value=f"**{points_per}**", inline=True)
        final_embed.add_field(name="Total Points Awarded", value=f"**{total_points}**", inline=True)
        final_embed.set_footer(text=f"Closed by {interaction.user}")
        
        await interaction.channel.send(embed=final_embed)
        
        # === STEP 3: AWARD POINTS ===
        volunteer_role = guild.get_role(config.ROLE_IDS.get("VOLUNTEER"))

        for helper_id in ticket["helpers"]:
            try:
                # Check for volunteer role
                helper_member = guild.get_member(helper_id)
                if helper_member and volunteer_role and volunteer_role in helper_member.roles:
                     print(f"ℹ️ {helper_member.name} is a Volunteer - Skipping points.")
                     continue

                new_points = await bot.db.add_points(helper_id, points_per)
                print(f"✅ Awarded {points_per} points to {helper_id} (Total: {new_points})")
            except Exception as e:
                print(f"⚠️ Failed to award points to {helper_id}: {e}")
        
        # === STEP 4: DATABASE OPERATIONS ===
        try:
            # Mark as closed
            ticket["is_closed"] = True
            await bot.db.save_ticket(ticket)
            
            # === NEW: INCREMENT TOTAL TICKETS COUNTER ===
            try:
                await bot.db.increment_total_tickets()
                print(f"✅ Incremented total tickets counter")
            except Exception as e:
                print(f"⚠️ Failed to increment total tickets: {e}")
            
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
                    "points_per_helper": points_per,
                    "total_points_awarded": total_points,
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
        
        # === SEND DELETE BUTTON ===
        delete_embed = discord.Embed(
            title="🗑️ Delete Channel?",
            description=(
                "This ticket has been closed.\n\n"
                "Click the button below to delete this channel.\n"
                "Only staff can delete the channel."
            ),
            color=config.COLORS["SUCCESS"]
        )
        
        delete_view = DeleteChannelView()
        await interaction.followup.send(embed=delete_embed, view=delete_view, ephemeral=False)
    
    @discord.ui.button(label="Cancel Ticket", style=discord.ButtonStyle.secondary, emoji="❌", custom_id="ticket_cancel_persistent", row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel ticket - STAFF/ADMIN/OFFICER/REQUESTOR"""
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
        
        # === STEP 1: REMOVE PERMISSIONS IMMEDIATELY ===
        new_overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        
        # ADMIN/STAFF/OFFICER roles get full access + manage channels
        if admin_role:
            new_overwrites[admin_role] = discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                read_message_history=True,
                manage_channels=True,
                manage_permissions=True
            )
        if staff_role:
            new_overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                read_message_history=True,
                manage_channels=True,
                manage_permissions=True
            )
        if officer_role:
            new_overwrites[officer_role] = discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                read_message_history=True
            )
        
        # Block requestor UNLESS they are staff/officer/admin
        requestor = guild.get_member(ticket["requestor_id"])
        if requestor:
            is_requestor_staff = (admin_role and admin_role in requestor.roles) or \
                                 (staff_role and staff_role in requestor.roles) or \
                                 (officer_role and officer_role in requestor.roles)
            
            if not is_requestor_staff:
                # Regular requestor - block access
                new_overwrites[requestor] = discord.PermissionOverwrite(
                    view_channel=False,
                    send_messages=False,
                    read_message_history=False
                )
            # If requestor IS staff/officer/admin, they keep access via role permissions
        
        # Remove all helpers
        for helper_id in ticket["helpers"]:
            helper = guild.get_member(helper_id)
            if helper:
                is_helper_staff = (admin_role and admin_role in helper.roles) or \
                                  (staff_role and staff_role in helper.roles) or \
                                  (officer_role and officer_role in helper.roles)
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
        
        # === DATABASE OPERATIONS ===
        try:
            # Mark as closed (cancelled)
            ticket["is_closed"] = True
            await bot.db.save_ticket(ticket)
            
            # Generate transcript (cancelled)
            try:
                await generate_transcript(interaction.channel, bot, ticket, is_cancelled=True)
            except Exception as e:
                print(f"⚠️ Transcript generation failed: {e}")
            
            # Save history
            try:
                await bot.db.save_ticket_history({
                    "channel_id": ticket["channel_id"],
                    "category": ticket["category"],
                    "requestor_id": ticket["requestor_id"],
                    "helpers": json.dumps(ticket["helpers"]),
                    "points_per_helper": 0,
                    "total_points_awarded": 0,
                    "closed_by": interaction.user.id,
                    "cancelled": True
                })
            except Exception as e:
                print(f"⚠️ History save failed: {e}")
            
            # Delete from active
            try:
                await bot.db.delete_ticket(ticket["channel_id"])
            except Exception as e:
                print(f"⚠️ Ticket deletion failed: {e}")
                
        except Exception as e:
            print(f"⚠️ Database error during cancel: {e}")
            traceback.print_exc()


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


def format_boss_name_for_select(boss: str) -> str:
    """Format boss names correctly for SELECT DROPDOWN (remove Ultra from non-ultra bosses)"""
    boss_select_names = {
        "Ultra Lich": "Lich Lord",
        "Ultra Beast": "Beast",
        "Ultra Deimos": "Deimos",
        "Ultra Flibbi": "Void Flibbi",
        "Ultra Bane": "Void Nightbane",
        "Ultra Xyfrag": "Void Xyfrag",
        "Ultra Kathool": "Kathool",
        "Ultra Astral": "Astral Shrine",
        "Ultra Champion Drakath": "Champion Drakath"
    }
    
    return boss_select_names.get(boss, boss)


def format_boss_name_for_embed(boss: str) -> str:
    """Format boss names for TICKET EMBED (merged names like voidflibbi, ultradage)"""
    boss_embed_names = {
        "Ultra Lich": "lichlord",
        "Ultra Beast": "beast",
        "Ultra Deimos": "deimos",
        "Ultra Flibbi": "voidflibbi",
        "Ultra Bane": "voidnightbane",
        "Ultra Xyfrag": "voidxyfrag",
        "Ultra Kathool": "kathool",
        "Ultra Astral": "astralshrine",
        "Ultra Champion Drakath": "championdrakath",
        "Ultra Dage": "ultradage",
        "Ultra Tyndarius": "ultratyndarius",
        "Ultra Engineer": "ultraengineer",
        "Ultra Warden": "ultrawarden",
        "Ultra Ezrajal": "ultraezrajal",
        "Ultra Nulgath": "ultranulgath",
        "Ultra Drago": "ultradrago",
        "Ultra Darkon": "ultradarkon"
    }
    
    return boss_embed_names.get(boss, boss.lower().replace(" ", ""))


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
        description=(
            f"{config.CATEGORY_METADATA.get(category, {}).get('description', 'Ticket')}\n\n"
            f"🔢 **Click 'Show Room Info' button below to see the room number and join commands!**"
        ),
        color=config.COLORS["PRIMARY"],
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(name="👤 Requestor", value=f"<@{requestor_id}>", inline=True)
    embed.add_field(name="🎮 In-game Name", value=in_game_name, inline=True)
    embed.add_field(name="🌍 Server", value=selected_server, inline=True)
    
    if selected_bosses:
        # Format boss names as MERGED (voidflibbi, ultradage)
        formatted_bosses = [format_boss_name_for_embed(boss) for boss in selected_bosses]
        embed.add_field(
            name="📋 Selected Bosses",
            value=", ".join(formatted_bosses),  # Comma-separated merged names
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
        # Order: Lich, Beast, Deimos, Flibbi, Bane, Xyfrag, Kathool, Astral
        boss_order = ["Ultra Lich", "Ultra Beast", "Ultra Deimos", "Ultra Flibbi", "Ultra Bane", 
                      "Ultra Xyfrag", "Ultra Kathool", "Ultra Astral"]
        for boss in boss_order:
            if boss in selected_bosses:
                # Special cases
                if boss == "Ultra Lich":
                    commands.append(f"`/join frozenlair-{room_number}`")
                elif boss == "Ultra Beast":
                    commands.append(f"`/join sevencircleswar-{room_number}`")
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
        try:
            bot = interaction.client
            ticket = await bot.db.get_ticket(interaction.channel_id)
            
            if not ticket:
                await interaction.response.send_message("❌ This command must be used in a ticket channel.", ephemeral=True)
                return
            
            member = interaction.user
            is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF"), config.ROLE_IDS.get("OFFICER")] if rid)
            
            # Only staff/officer/admin can kick
            if not is_staff:
                await interaction.response.send_message("❌ Only admins, staff, or officers can use this command.", ephemeral=True)
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
        
        except Exception as e:
            print(f"❌ Error in kick_from_ticket: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
            except:
                await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)
    
    @bot.tree.command(name="proof", description="Show proof submission guide")
    async def proof(interaction: discord.Interaction):
        """Show proof submission guide"""
        proof_data = config.HARDCODED_COMMANDS.get("proof", {})
        text = proof_data.get("text", "No proof guide configured.")
        image = proof_data.get("image")
        
        text = (
            "# 📸 Submit Your Proof\n"
            "After requesting a ticket and completing the objective, make sure to provide proof!\n"
            "**❌ No Proof = No Points**\n\n"
            "1️⃣ Take a screenshot of the **Helpers' names and the quests they completed.**\n"
            "2️⃣ Send the screenshot **directly inside the ticket.**\n\n"
            "✅ If everything is submitted correctly, it should look something like this:"
        )
        
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
