"""Slash commands for ticket system"""

import discord
from discord.ext import commands
import json
import traceback
import config


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
                "**GrimChallenge Express