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
        
        # Calculate some interesting stats
        avg_per_day = total // 30  # Rough estimate
        
        embed = discord.Embed(
            title="📊 Server Statistics",
            color=config.COLORS["PRIMARY"]
        )
        
        # Main stat
        embed.add_field(
            name="Total Tickets Completed",
            value=f"```{total:,}```",
            inline=False
        )
        
        # Secondary stats
        embed.add_field(
            name="Est. Daily Average",
            value=f"```{avg_per_day:,}```",
            inline=True
        )
        embed.add_field(
            name="Server Status",
            value="```✅ Active```",
            inline=True
        )
        
        embed.set_footer(text="Statistics updated in real-time")
        
        await interaction.response.send_message(embed=embed)