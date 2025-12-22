# dumb_things.py
# Dumb/Fun Commands - Random rolls, jokes, silly stuff

import discord
from discord.ext import commands
from discord import app_commands
import random
import config


async def setup_dumb_things(bot):
    """Setup fun and dumb commands"""
    
    @bot.tree.command(name="roll", description="Roll a dice with up to 1000 sides")
    @app_commands.describe(sides="Number of sides on the dice (1-1000)")
    async def roll(interaction: discord.Interaction, sides: app_commands.Range[int, 1, 1000]):
        """Roll a dice with specified number of sides"""
        result = random.randint(1, sides)
        
        # Fun emojis based on result
        if result == sides:
            emoji = "🎯"  # Perfect roll
            text = "**CRITICAL HIT!**"
        elif result == 1:
            emoji = "💀"  # Worst roll
            text = "**CRITICAL FAIL!**"
        elif result > sides * 0.75:
            emoji = "🔥"  # Great roll
            text = "**Great roll!**"
        else:
            emoji = "🎲"  # Normal roll
            text = "**Roll result:**"
        
        embed = discord.Embed(
            title=f"{emoji} Dice Roll {emoji}",
            description=(
                f"{text}\n\n"
                f"**Result:** `{result}` / `{sides}`"
            ),
            color=config.COLORS["PRIMARY"]
        )
        embed.set_footer(text=f"Rolled by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)