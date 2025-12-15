# leaderboard.py
# Leaderboard and Points System - FINAL VERSION

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import config


class LeaderboardView(discord.ui.View):
    """Persistent pagination view for leaderboard"""
    def __init__(self, page: int = 1):
        super().__init__(timeout=None)  # Persistent view
        self.page = page
        self.per_page = config.LEADERBOARD_PER_PAGE
    
    async def update_embed(self, interaction: discord.Interaction):
        """Update leaderboard embed"""
        bot = interaction.client
        embed = await create_leaderboard_embed(bot, self.page, self.per_page)
        
        # Create new view with updated page
        new_view = LeaderboardView(self.page)
        await interaction.response.edit_message(embed=embed, view=new_view)
    
    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary, custom_id="lb_prev_persistent")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page"""
        if self.page > 1:
            self.page -= 1
            await self.update_embed(interaction)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(emoji="🔄", style=discord.ButtonStyle.secondary, custom_id="lb_refresh_persistent")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh current page"""
        await self.update_embed(interaction)
    
    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary, custom_id="lb_next_persistent")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page"""
        bot = interaction.client
        # Check if there are more pages
        leaderboard = await bot.db.get_leaderboard()
        total_pages = max(1, (len(leaderboard) + self.per_page - 1) // self.per_page)
        
        if self.page < total_pages:
            self.page += 1
            await self.update_embed(interaction)
        else:
            await interaction.response.defer()


async def create_leaderboard_embed(bot, page: int = 1, per_page: int = 10) -> discord.Embed:
    """Create leaderboard embed with correct formatting"""
    leaderboard = await bot.db.get_leaderboard()
    
    total_pages = max(1, (len(leaderboard) + per_page - 1) // per_page)
    current_page = max(1, min(page, total_pages))
    
    start = (current_page - 1) * per_page
    end = start + per_page
    page_rows = leaderboard[start:end]
    
    # Create description with rankings
    top_emojis = ["🥇", "🥈", "🥉"]
    lines = []
    
    for i, entry in enumerate(page_rows):
        rank = start + i + 1
        user_id = entry["user_id"]
        points = entry["points"]
        
        if rank <= 3:
            # Top 3 with medal emojis - user on first line, points on second
            lines.append(f"{top_emojis[rank - 1]} <@{user_id}>")
            lines.append(f"**└ {points:,} points**")
        else:
            # Rank 4+ - user on first line, points on second
            lines.append(f"**#{rank}** <@{user_id}>")
            lines.append(f"**└ {points:,} points**")
    
    description = "\n".join(lines) if lines else "*No entries yet.*"
    
    embed = discord.Embed(
        title="🏆 HELPER'S LEADERBOARD SEASON 9",
        description=description,
        color=config.COLORS["PRIMARY"],  # PRIMARY BLURPLE (#5865F2)
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text=f"📄 Page {current_page}/{total_pages}")
    
    return embed


async def setup_leaderboard(bot):
    """Setup leaderboard commands"""
    
    @bot.tree.command(name="leaderboard", description="Show the helper leaderboard")
    async def leaderboard(interaction: discord.Interaction):
        """Display leaderboard with pagination"""
        embed = await create_leaderboard_embed(bot, page=1)
        view = LeaderboardView(page=1)
        await interaction.response.send_message(embed=embed, view=view)
    
    @bot.tree.command(name="points", description="Check your points or another user's points")
    @app_commands.describe(user="User to check points for (optional)")
    async def points(interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Check points for a user"""
        target = user or interaction.user
        points = await bot.db.get_points(target.id)
        
        # Get rank
        leaderboard = await bot.db.get_leaderboard()
        rank = None
        for i, entry in enumerate(leaderboard):
            if entry["user_id"] == target.id:
                rank = i + 1
                break
        
        embed = discord.Embed(
            title="📊 Helper Points",
            color=config.COLORS["PRIMARY"]
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="User", value=target.mention, inline=False)
        embed.add_field(name="Points", value=f"**{points:,}**", inline=True)
        
        if rank:
            embed.add_field(name="Rank", value=f"**#{rank}**", inline=True)
        else:
            embed.add_field(name="Rank", value="*Unranked*", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="info", description="Show all important commands and info")
    async def info(interaction: discord.Interaction):
        """Show bot commands and information"""
        embed = discord.Embed(
            title="✨ Server Commands & Info",
            description="Here are all the available commands and how to use the bot:",
            color=config.COLORS["PRIMARY"]
        )
        
        # Ticket Commands
        ticket_cmds = (
            "`/panel` - Post ticket panel (Staff only)\n"
            "`/proof` - Show proof submission guidelines\n"
            "`/hrules` - Show helper rules\n"
            "`/rrules` - Show runner rules"
        )
        embed.add_field(name="🎫 Ticket Commands", value=ticket_cmds, inline=False)
        
        # Points Commands
        points_cmds = (
            "`/leaderboard` - View helper leaderboard\n"
            "`/points [user]` - Check points for yourself or another user"
        )
        embed.add_field(name="📊 Points Commands", value=points_cmds, inline=False)
        
        # Verification
        verify_cmds = (
            "`/verification_panel` - Post verification panel (Staff only)"
        )
        embed.add_field(name="🛡️ Verification", value=verify_cmds, inline=False)
        
        # Admin Commands
        admin_cmds = (
            "`/points_add` - Add points to a user\n"
            "`/points_remove` - Remove points from a user\n"
            "`/points_set` - Set exact points for a user\n"
            "`/points_reset` - Reset all points\n"
            "`/points_remove_user` - Remove user from leaderboard"
        )
        embed.add_field(name="⚙️ Admin Commands", value=admin_cmds, inline=False)
        
        # Point Values
        point_values = "\n".join([
            f"**{cat.replace(' Express', '')}:** {config.POINT_VALUES.get(cat, 0)} pts"
            for cat in config.CATEGORIES
        ])
        embed.add_field(name="💰 Point Values", value=point_values, inline=False)
        
        embed.set_footer(text="Need help? Contact staff!")
        
        await interaction.response.send_message(embed=embed)