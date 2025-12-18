# points_logger.py
# Points Logging System - Logs all points changes to a channel

import discord
from discord import app_commands
import config
from datetime import datetime

LOG_CHANNEL_ID = 1451319266941997279


async def get_leaderboard_preview(bot, limit: int = 10) -> str:
    """Get top 10 users from leaderboard"""
    leaderboard = await bot.db.get_leaderboard()
    
    if not leaderboard:
        return "*No leaderboard data*"
    
    lines = []
    for i, entry in enumerate(leaderboard[:limit]):
        rank = i + 1
        user_id = entry["user_id"]
        points = entry["points"]
        lines.append(f"**#{rank}** <@{user_id}> - {points:,} pts")
    
    return "\n".join(lines) if lines else "*No data*"


async def log_points_added(bot, target_user_id: int, admin_id: int, amount: int, new_total: int):
    """Log when points are added"""
    try:
        channel = bot.get_channel(LOG_CHANNEL_ID)
        if not channel:
            return
        
        leaderboard_preview = await get_leaderboard_preview(bot, limit=10)
        
        embed = discord.Embed(
            title="➕ Points Added",
            description=f"**Amount:** +{amount:,} points\n**Target:** <@{target_user_id}>\n**New Total:** {new_total:,} points\n**Admin:** <@{admin_id}>",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="📊 Top 10 Leaderboard", value=leaderboard_preview, inline=False)
        
        await channel.send(embed=embed)
    except Exception as e:
        print(f"❌ Error logging points_add: {e}")


async def log_points_removed(bot, target_user_id: int, admin_id: int, amount: int, new_total: int):
    """Log when points are removed"""
    try:
        channel = bot.get_channel(LOG_CHANNEL_ID)
        if not channel:
            return
        
        leaderboard_preview = await get_leaderboard_preview(bot, limit=10)
        
        embed = discord.Embed(
            title="➖ Points Removed",
            description=f"**Amount:** -{amount:,} points\n**Target:** <@{target_user_id}>\n**New Total:** {new_total:,} points\n**Admin:** <@{admin_id}>",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="📊 Top 10 Leaderboard", value=leaderboard_preview, inline=False)
        
        await channel.send(embed=embed)
    except Exception as e:
        print(f"❌ Error logging points_remove: {e}")


async def log_points_set(bot, target_user_id: int, admin_id: int, new_total: int):
    """Log when points are set to exact value"""
    try:
        channel = bot.get_channel(LOG_CHANNEL_ID)
        if not channel:
            return
        
        leaderboard_preview = await get_leaderboard_preview(bot, limit=10)
        
        embed = discord.Embed(
            title="🎯 Points Set",
            description=f"**New Total:** {new_total:,} points\n**Target:** <@{target_user_id}>\n**Admin:** <@{admin_id}>",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="📊 Top 10 Leaderboard", value=leaderboard_preview, inline=False)
        
        await channel.send(embed=embed)
    except Exception as e:
        print(f"❌ Error logging points_set: {e}")


async def log_points_reset(bot, admin_id: int):
    """Log when all points are reset"""
    try:
        channel = bot.get_channel(LOG_CHANNEL_ID)
        if not channel:
            return
        
        embed = discord.Embed(
            title="⚠️ ALL POINTS RESET",
            description=f"**Admin:** <@{admin_id}>\n**Action:** Reset ALL user points to 0",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="📊 Leaderboard Preview", value="*All reset to 0*", inline=False)
        
        await channel.send(embed=embed)
    except Exception as e:
        print(f"❌ Error logging points_reset: {e}")


async def log_user_deleted(bot, user_id: int, admin_id: int):
    """Log when a user is removed from leaderboard"""
    try:
        channel = bot.get_channel(LOG_CHANNEL_ID)
        if not channel:
            return
        
        leaderboard_preview = await get_leaderboard_preview(bot, limit=10)
        
        embed = discord.Embed(
            title="🗑️ User Removed from Leaderboard",
            description=f"**User:** <@{user_id}>\n**Admin:** <@{admin_id}>",
            color=discord.Color.dark_red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="📊 Top 10 Leaderboard", value=leaderboard_preview, inline=False)
        
        await channel.send(embed=embed)
    except Exception as e:
        print(f"❌ Error logging user_deleted: {e}")


async def log_member_left(bot, member_id: int, member_name: str):
    """Log when a member leaves the server"""
    try:
        channel = bot.get_channel(LOG_CHANNEL_ID)
        if not channel:
            return
        
        leaderboard_preview = await get_leaderboard_preview(bot, limit=10)
        
        embed = discord.Embed(
            title="👋 Member Left - Points Auto-Deleted",
            description=f"**Member:** {member_name} (ID: {member_id})\n**Action:** Auto-removed from leaderboard",
            color=discord.Color.greyple(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="📊 Top 10 Leaderboard", value=leaderboard_preview, inline=False)
        
        await channel.send(embed=embed)
    except Exception as e:
        print(f"❌ Error logging member_left: {e}")