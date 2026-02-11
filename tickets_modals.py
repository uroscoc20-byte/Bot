"""Modal dialogs for ticket creation"""

import discord
from typing import Optional, List
import json
import random
import asyncio
import config
from tickets_embeds import create_ticket_embed
from tickets_utils import generate_join_commands


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
        from tickets_buttons_actions import TicketActionView
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
            import traceback
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