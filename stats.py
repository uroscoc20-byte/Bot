# stats.py
# Statistics and Ticket Counter System

import discord
from discord.ext import commands
from discord import app_commands
import config


async def setup_stats(bot):
    """Setup stats commands"""
    
    @bot.tree.command(name="stats", description="Show server ticket statistics")
    async def stats(interaction: discord.Interaction):
        """Show total tickets completed"""
        total = await bot.db.get_total_tickets()
        
        embed = discord.Embed(
            title="📊 Server Statistics",
            description=f"Total Tickets Completed: **{total:,}**",
            color=config.COLORS["PRIMARY"]
        )
        embed.set_footer(text="Counting since 13,120")
        
        await interaction.response.send_message(embed=embed)