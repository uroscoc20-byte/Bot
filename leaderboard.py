import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from database import db

ACCENT = 0x5865F2
TOP_EMOJIS = ["🥇", "🥈", "🥉"]
PER_PAGE = 10
DEFAULT_TITLE = "🏆 Helper's Leaderboard"

# -------------------------------
# Leaderboard Pagination View
# -------------------------------
class LeaderboardView(View):
    def __init__(self, entries, page=0):
        super().__init__(timeout=None)
        self.entries = entries
        self.page = page
        self.max_page = max(0, (len(entries) - 1) // PER_PAGE)

        self.previous.disabled = (self.page == 0)
        self.next.disabled = (self.page == self.max_page)

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, custom_id="leader_prev")
    async def previous(self, interaction: discord.Interaction, button: Button):
        if self.page > 0:
            self.page -= 1
        await interaction.response.edit_message(embed=self.get_page_embed(interaction.guild), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, custom_id="leader_next")
    async def next(self, interaction: discord.Interaction, button: Button):
        if self.page < self.max_page:
            self.page += 1
        await interaction.response.edit_message(embed=self.get_page_embed(interaction.guild), view=self)

    def get_page_embed(self, guild):
        start = self.page * PER_PAGE
        end = start + PER_PAGE
        page_entries = self.entries[start:end]

        # Load leaderboard title from DB
        cfg = db.get_config(guild.id, "leaderboard_title")
        title = cfg if cfg else DEFAULT_TITLE

        embed = discord.Embed(title=title, color=ACCENT)
        if not page_entries:
            embed.description = "No points recorded yet."
            return embed

        desc = ""
        rank = start + 1
        for user_id, points in page_entries:
            member = guild.get_member(int(user_id))
            name = member.display_name if member else f"<@{user_id}>"

            prefix = f"#{rank} "
            if rank <= 3:
                prefix += f"{TOP_EMOJIS[rank-1]} "

            desc += f"{prefix}{name} — **{points} pts**\n"
            rank += 1

        embed.description = desc
        embed.set_footer(text=f"Page {self.page+1}/{self.max_page+1}")
        return embed


# -------------------------------
# Points & Leaderboard Cog
# -------------------------------
class PointsModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # -------------------------------
    # /points command
    # -------------------------------
    @app_commands.command(name="points", description="Check your points or another user's points")
    async def points(self, interaction: discord.Interaction, user: discord.User = None):
        target = user or interaction.user
        pts = await db.get_points(target.id)
        avatar = target.display_avatar.url if target.display_avatar else None
        embed = discord.Embed(
            title=f"🏅 Points for {target.display_name}",
            description=f"**{pts} pts**",
            color=ACCENT
        )
        if avatar:
            embed.set_thumbnail(url=avatar)
        embed.set_footer(text="Use /leaderboard to view rankings")
        await interaction.response.send_message(embed=embed)

    # -------------------------------
    # /leaderboard command
    # -------------------------------
    @app_commands.command(name="leaderboard", description="Show server leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        data = await db.get_leaderboard()
        if not data:
            await interaction.response.send_message("Leaderboard is empty.")
            return
        sorted_data = sorted(data, key=lambda x: int(x[1]), reverse=True)
        view = LeaderboardView(sorted_data)
        embed = view.get_page_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, view=view)

    # -------------------------------
    # /leaderboard_rename (Admin only)
    # -------------------------------
    @app_commands.command(name="leaderboard_rename", description="Rename the leaderboard title")
    @app_commands.checks.has_permissions(administrator=True)
    async def leaderboard_rename(self, interaction: discord.Interaction, new_title: str):
        await db.save_config("leaderboard_title", {"title": new_title})
        await interaction.response.send_message(f"✅ Leaderboard renamed to: **{new_title}**")

    # -------------------------------
    # Admin points commands
    # -------------------------------
    @app_commands.command(name="points_add", description="Add points to a user (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def points_add(self, interaction: discord.Interaction, user: discord.User, amount: int):
        if amount <= 0:
            await interaction.response.send_message("Amount must be positive.")
            return
        current = await db.get_points(user.id)
        await db.set_points(user.id, current + amount)
        await interaction.response.send_message(f"Added {amount} pts to {user.mention}.")

    @app_commands.command(name="points_remove", description="Remove points from a user (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def points_remove(self, interaction: discord.Interaction, user: discord.User, amount: int):
        if amount <= 0:
            await interaction.response.send_message("Amount must be positive.")
            return
        current = await db.get_points(user.id)
        await db.set_points(user.id, max(0, current - amount))
        await interaction.response.send_message(f"Removed {amount} pts from {user.mention}.")

    @app_commands.command(name="points_set", description="Set user's points (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def points_set(self, interaction: discord.Interaction, user: discord.User, amount: int):
        if amount < 0:
            await interaction.response.send_message("Amount cannot be negative.")
            return
        await db.set_points(user.id, amount)
        await interaction.response.send_message(f"Set {user.mention}'s points to {amount}.")

    @app_commands.command(name="points_remove_user", description="Remove a user from leaderboard (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def points_remove_user(self, interaction: discord.Interaction, user: discord.User):
        await db.delete_user_points(user.id)
        await interaction.response.send_message(f"Removed {user.mention} from the leaderboard.")

    @app_commands.command(name="points_reset", description="Reset all points (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def points_reset(self, interaction: discord.Interaction):
        await db.reset_points()
        await interaction.response.send_message("Leaderboard has been reset!")


# -------------------------------
# Setup Cog
# -------------------------------
async def setup(bot):
    await bot.add_cog(PointsModule(bot))
