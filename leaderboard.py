import discord
from discord.ext import commands
import sqlite3
import math

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="leaderboard", description="Show the points leaderboard")
    async def leaderboard(self, ctx: discord.ApplicationContext, page: discord.Option(int, "Page number to view", required=False, default=1)):
        try:
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            
            # Get total count for pagination
            cursor.execute("SELECT COUNT(*) FROM points WHERE points > 0")
            total_users = cursor.fetchone()[0]
            
            if total_users == 0:
                embed = discord.Embed(
                    title="🏆 HELPER'S LEADERBOARD 🏆",
                    description="No users with points yet!",
                    color=0x2F3136
                )
                await ctx.respond(embed=embed)
                return
            
            # Calculate pagination
            per_page = 10
            total_pages = math.ceil(total_users / per_page)
            
            if page < 1 or page > total_pages:
                page = 1
            
            offset = (page - 1) * per_page
            
            # Get leaderboard data
            cursor.execute("""
                SELECT user_id, points 
                FROM points 
                WHERE points > 0 
                ORDER BY points DESC 
                LIMIT ? OFFSET ?
            """, (per_page, offset))
            
            results = cursor.fetchall()
            conn.close()
            
            # Create embed
            embed = discord.Embed(
                title="🏆 HELPER'S LEADERBOARD SEASON 7 🏆",
                color=0x2F3136
            )
            
            description = ""
            for i, (user_id, points) in enumerate(results):
                rank = offset + i + 1
                user = self.bot.get_user(user_id)
                username = user.display_name if user else f"Unknown User"
                
                # Add medal emojis for top 3 (only for global top 3, not page top 3)
                global_rank = offset + i + 1
                if global_rank == 1:
                    medal = "🥇 "
                elif global_rank == 2:
                    medal = "🥈 "
                elif global_rank == 3:
                    medal = "🥉 "
                else:
                    medal = ""
                
                # Add verification checkmark if user has certain roles
                checkmark = ""
                if user:
                    member = ctx.guild.get_member(user.id)
                    if member and any(role.name.lower() in ['verified', 'helper', 'staff', 'moderator', 'admin'] for role in member.roles):
                        checkmark = " ✓"
                
                # Format exactly like the image
                description += f"#{rank} {medal}@{username}{checkmark}\n"
                description += f"└ {points:,} points\n\n"
            
            embed.description = description
            embed.set_footer(text=f"📄 Page {page}/{total_pages}")
            
            # Add navigation buttons if multiple pages
            if total_pages > 1:
                view = LeaderboardView(page, total_pages)
                await ctx.respond(embed=embed, view=view)
            else:
                await ctx.respond(embed=embed)
                
        except Exception as e:
            print(f"Leaderboard error: {e}")
            await ctx.respond("❌ Error loading leaderboard!", ephemeral=True)

class LeaderboardView(discord.ui.View):
    def __init__(self, current_page, total_pages):
        super().__init__(timeout=None)  # Make buttons persistent
        self.current_page = current_page
        self.total_pages = total_pages
        
        # Disable buttons if needed
        if current_page <= 1:
            self.previous_button.disabled = True
        if current_page >= total_pages:
            self.next_button.disabled = True

    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.current_page > 1:
            new_page = self.current_page - 1
            await self.update_leaderboard(interaction, new_page)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.current_page < self.total_pages:
            new_page = self.current_page + 1
            await self.update_leaderboard(interaction, new_page)

    async def update_leaderboard(self, interaction, page):
        try:
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            
            per_page = 10
            offset = (page - 1) * per_page
            
            cursor.execute("""
                SELECT user_id, points 
                FROM points 
                WHERE points > 0 
                ORDER BY points DESC 
                LIMIT ? OFFSET ?
            """, (per_page, offset))
            
            results = cursor.fetchall()
            conn.close()
            
            embed = discord.Embed(
                title="🏆 HELPER'S LEADERBOARD SEASON 7 🏆",
                color=0x2F3136
            )
            
            description = ""
            for i, (user_id, points) in enumerate(results):
                rank = offset + i + 1
                user = interaction.client.get_user(user_id)
                username = user.display_name if user else f"Unknown User"
                
                # Add medal emojis for global top 3
                global_rank = offset + i + 1
                if global_rank == 1:
                    medal = "🥇 "
                elif global_rank == 2:
                    medal = "🥈 "
                elif global_rank == 3:
                    medal = "🥉 "
                else:
                    medal = ""
                
                # Add verification checkmark if user has certain roles
                checkmark = ""
                if user:
                    member = interaction.guild.get_member(user.id)
                    if member and any(role.name.lower() in ['verified', 'helper', 'staff', 'moderator', 'admin'] for role in member.roles):
                        checkmark = " ✓"
                
                # Format exactly like the image
                description += f"#{rank} {medal}@{username}{checkmark}\n"
                description += f"└ {points:,} points\n\n"
            
            embed.description = description
            embed.set_footer(text=f"📄 Page {page}/{self.total_pages}")
            
            # Update view
            self.current_page = page
            self.previous_button.disabled = (page <= 1)
            self.next_button.disabled = (page >= self.total_pages)
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            print(f"Leaderboard update error: {e}")
            await interaction.response.send_message("❌ Error updating leaderboard!", ephemeral=True)

def setup(bot):
    bot.add_cog(Leaderboard(bot))