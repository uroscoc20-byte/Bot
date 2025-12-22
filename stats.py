# stats.py
# Statistics and Ticket Counter System

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import config


async def setup_stats(bot):
    """Setup stats commands"""
    
    @bot.tree.command(name="stats", description="Show server ticket statistics")
    async def stats(interaction: discord.Interaction):
        """Show total tickets completed"""
        total = await bot.db.get_total_tickets()
        
        # Calculate days since April 9, 2025 to today
        start_date = datetime(2025, 4, 9)
        today = datetime.now()
        days_elapsed = (today - start_date).days
        
        # Calculate average per day
        avg_per_day = round(total / days_elapsed, 1) if days_elapsed > 0 else 0
        
        embed = discord.Embed(
            title="📊 Server Statistics",
            color=config.COLORS["PRIMARY"]
        )
        
        embed.add_field(
            name="Total Tickets Completed",
            value=f"**{total:,}**",
            inline=False
        )
        embed.add_field(
            name="Daily Average",
            value=f"**{avg_per_day:,}**",
            inline=True
        )
        embed.add_field(
            name="Days Tracked",
            value=f"**{days_elapsed}**",
            inline=True
        )
        
        embed.set_footer(text="Tracking since April 9, 2025")
        
        await interaction.response.send_message(embed=embed)