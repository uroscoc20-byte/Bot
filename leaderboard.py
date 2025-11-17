import discord
from discord.ext import commands
from discord import app_commands
from database import db


class LeaderboardView(discord.ui.View):
    def __init__(self, entries, page_size, user, title):
        super().__init__(timeout=60)
        self.entries = entries
        self.page_size = page_size
        self.user = user
        self.page = 0
        self.title = title

        self.update_buttons()

    def update_buttons(self):
        self.first_page.disabled = self.page == 0
        self.prev_page.disabled = self.page == 0
        max_page = max(0, (len(self.entries) - 1) // self.page_size)
        self.next_page.disabled = self.page >= max_page
        self.last_page.disabled = self.page >= max_page

    def get_page_embed(self):
        start = self.page * self.page_size
        end = start + self.page_size
        page_entries = self.entries[start:end]

        embed = discord.Embed(
            title=self.title,
            colour=discord.Colour.gold()
        )

        if not page_entries:
            embed.description = "No entries found."
            return embed

        description = ""
        for index, (user_id, points) in enumerate(page_entries, start=start + 1):
            description += f"**#{index}** <@{user_id}> — **{points} pts**\n"

        embed.description = description
        embed.set_footer(text=f"Page {self.page + 1}")
        return embed

    async def update(self, interaction: discord.Interaction):
        self.update_buttons()
        await interaction.response.edit_message(
            embed=self.get_page_embed(),
            view=self
        )

    @discord.ui.button(label="⏪ First", style=discord.ButtonStyle.blurple)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = 0
        await self.update(interaction)

    @discord.ui.button(label="⬅ Previous", style=discord.ButtonStyle.primary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
        await self.update(interaction)

    @discord.ui.button(label="Next ➡", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        max_page = (len(self.entries) - 1) // self.page_size
        if self.page < max_page:
            self.page += 1
        await self.update(interaction)

    @discord.ui.button(label="⏩ Last", style=discord.ButtonStyle.blurple)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = (len(self.entries) - 1) // self.page_size
        await self.update(interaction)


class LeaderboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Defaults stored in memory (you can persist these in db if you want)
        self.lb_title = "Leaderboard"
        self.page_size = 10

    # ---------------------------
    # /leaderboard command
    # ---------------------------
    @app_commands.command(name="leaderboard", description="Show the leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        entries = db.get_leaderboard()  # MUST return list of (user_id, points)

        if not entries:
            await interaction.response.send_message("Leaderboard is empty.", ephemeral=True)
            return

        view = LeaderboardView(entries, self.page_size, interaction.user, self.lb_title)
        embed = view.get_page_embed()

        await interaction.response.send_message(embed=embed, view=view)

    # ---------------------------
    # /leaderboard_rename
    # ---------------------------
    @app_commands.command(name="leaderboard_rename", description="Rename the leaderboard title")
    @app_commands.checks.has_permissions(administrator=True)
    async def leaderboard_rename(self, interaction: discord.Interaction, new_title: str):
        self.lb_title = new_title
        await interaction.response.send_message(f"Leaderboard title set to **{new_title}**.")

    # ---------------------------
    # /leaderboard_set_page_size
    # ---------------------------
    @app_commands.command(name="leaderboard_set_page_size", description="Set how many people show per leaderboard page")
    @app_commands.checks.has_permissions(administrator=True)
    async def leaderboard_set_page_size(self, interaction: discord.Interaction, amount: int):
        if amount < 3 or amount > 25:
            await interaction.response.send_message("Page size must be between 3 and 25.", ephemeral=True)
            return

        self.page_size = amount
        await interaction.response.send_message(f"Leaderboard now shows **{amount} entries per page**.")


async def setup(bot):
    await bot.add_cog(LeaderboardCog(bot))
