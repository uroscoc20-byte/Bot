import discord
from discord.ext import commands
from discord import app_commands
import sqlite3

class Points(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="add_points", description="Add points to a user")
    @app_commands.describe(user="User to add points to", amount="Amount of points to add")
    async def add_points(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        # Check if user has permission (adjust role names as needed)
        if not any(role.name.lower() in ['admin', 'moderator', 'staff'] for role in interaction.user.roles):
            await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
            return
        
        if amount <= 0:
            await interaction.response.send_message("❌ Amount must be positive!", ephemeral=True)
            return
        
        try:
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            
            # Create table if not exists
            cursor.execute('''CREATE TABLE IF NOT EXISTS points
                            (user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0)''')
            
            # Add points
            cursor.execute('''INSERT OR IGNORE INTO points (user_id, points) VALUES (?, 0)''', (user.id,))
            cursor.execute('''UPDATE points SET points = points + ? WHERE user_id = ?''', (amount, user.id))
            
            # Get new total
            cursor.execute('SELECT points FROM points WHERE user_id = ?', (user.id,))
            new_total = cursor.fetchone()[0]
            
            conn.commit()
            conn.close()
            
            # Public response - everyone can see
            embed = discord.Embed(
                title="✅ Points Added!",
                description=f"**{user.mention}** received **{amount:,}** points!\n"
                           f"**New Total:** {new_total:,} points",
                color=0x00ff00
            )
            embed.set_footer(text=f"Added by {interaction.user.display_name}")
            
            await interaction.response.send_message(embed=embed)  # Public response
            
        except Exception as e:
            print(f"Add points error: {e}")
            await interaction.response.send_message("❌ Error adding points!", ephemeral=True)

    @app_commands.command(name="remove_points", description="Remove points from a user")
    @app_commands.describe(user="User to remove points from", amount="Amount of points to remove")
    async def remove_points(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        # Check if user has permission
        if not any(role.name.lower() in ['admin', 'moderator', 'staff'] for role in interaction.user.roles):
            await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
            return
        
        if amount <= 0:
            await interaction.response.send_message("❌ Amount must be positive!", ephemeral=True)
            return
        
        try:
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            
            # Check current points
            cursor.execute('SELECT points FROM points WHERE user_id = ?', (user.id,))
            result = cursor.fetchone()
            
            if not result:
                await interaction.response.send_message(f"❌ {user.mention} has no points!", ephemeral=True)
                return
            
            current_points = result[0]
            new_total = max(0, current_points - amount)  # Don't go below 0
            
            cursor.execute('UPDATE points SET points = ? WHERE user_id = ?', (new_total, user.id))
            conn.commit()
            conn.close()
            
            # Public response - everyone can see
            embed = discord.Embed(
                title="❌ Points Removed!",
                description=f"**{user.mention}** lost **{amount:,}** points!\n"
                           f"**New Total:** {new_total:,} points",
                color=0xff0000
            )
            embed.set_footer(text=f"Removed by {interaction.user.display_name}")
            
            await interaction.response.send_message(embed=embed)  # Public response
            
        except Exception as e:
            print(f"Remove points error: {e}")
            await interaction.response.send_message("❌ Error removing points!", ephemeral=True)

    @app_commands.command(name="points", description="Check your or someone's points")
    @app_commands.describe(user="User to check points for (optional)")
    async def check_points(self, interaction: discord.Interaction, user: discord.Member = None):
        target_user = user or interaction.user
        
        try:
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            
            cursor.execute('SELECT points FROM points WHERE user_id = ?', (target_user.id,))
            result = cursor.fetchone()
            conn.close()
            
            points = result[0] if result else 0
            
            embed = discord.Embed(
                title="💰 Points Check",
                description=f"**{target_user.mention}** has **{points:,}** points!",
                color=0x00aaff
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            print(f"Check points error: {e}")
            await interaction.response.send_message("❌ Error checking points!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Points(bot))
