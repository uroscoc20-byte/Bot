"""Slash commands for ticket system"""

import discord
from discord.ext import commands
import json
import traceback
import config
from tickets_buttons_panel import TicketView


async def setup_tickets(bot):
    """Setup ticket commands"""
    
    @bot.tree.command(name="panel", description="Post the ticket panel (Staff only)")
    async def panel(interaction: discord.Interaction):
        """Post ticket panel"""
        try:
            await interaction.response.defer()
            
            member = interaction.user
            is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF")] if rid)
            
            if not is_staff:
                await interaction.followup.send("❌ You don't have permission to use this command.", ephemeral=True)
                return
            
            ticket_panel_channel_id = config.CHANNEL_IDS.get("TICKET_PANEL")
            
            embed = discord.Embed(
                title="���� IN-GAME ASSISTANCE 🎮",
                description=(
                    "## CHOOSE YOUR TICKET TYPE\n"
                    "Pick the ticket type that fits your request\n\n"
                    "**Available Ticket Types:**\n"
                    "• **UltraSpeaker Express** - The First Speaker\n"
                    "• **Ultra Gramiel Express** - Ultra Gramiel\n"
                    "• **Daily 4-Man Express** - Daily 4-Man Ultra Bosses\n"
                    "• **Daily 7-Man Express** - Daily 7-Man Ultra Bosses\n"
                    "• **Weekly Ultra Express** - Weekly Ultra Bosses\n"
                    "• **GrimChallenge Express** - Grim Challenge\n\n"
                    "Click the buttons below to open a ticket!"
                ),
                color=config.COLORS.get("PRIMARY", 0x00ff00)
            )
            
            embed.set_footer(text="Ticket System | Click a button to get started")
            
            # Send with TicketView buttons
            view = TicketView()
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            print(f"❌ Panel command error: {e}")
            traceback.print_exc()
            try:
                await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
            except:
                pass
