"""Embed creation utilities for tickets"""
import discord
from typing import List, Optional
import config

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
    from tickets_utils import format_boss_name_for_embed
    
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
        formatted_bosses = [format_boss_name_for_embed(boss) for boss in selected_bosses]
        embed.add_field(
            name="📋 Selected Bosses",
            value=", ".join(formatted_bosses),
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