"""Panel and selection buttons for opening tickets"""

import discord
from typing import Optional, List
import config
from tickets_modals import TicketModal


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
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Check if user has RESTRICTED role
            restricted_role = interaction.guild.get_role(config.ROLE_IDS.get("RESTRICTED"))
            if restricted_role and restricted_role in interaction.user.roles:
                await interaction.followup.send(
                    "❌ You are restricted from opening tickets.",
                    ephemeral=True
                )
                return
            
            bot = interaction.client
            all_tickets = await bot.db.get_all_tickets()
            
            # Check if user already has an active ticket
            for ticket in all_tickets:
                if interaction.user.id == ticket["requestor_id"]:
                    channel = interaction.guild.get_channel(ticket["channel_id"])
                    if channel:
                        await interaction.followup.send(
                            f"❌ You already have an active ticket: {channel.mention}\n"
                            "Please close that ticket first.",
                            ephemeral=True
                        )
                        return
            
            # Open the ticket modal
            modal = TicketModal(category=self.category, selected_bosses=None, selected_server=None)
            await interaction.followup.send("📝 Opening ticket form...", ephemeral=True)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            print(f"❌ Button callback error: {e}")
            traceback.print_exc()
            try:
                await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
            except:
                pass
