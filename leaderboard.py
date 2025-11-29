import discord
from discord.ext import commands
from database import db

ACCENT = 0x5865F2

async def create_leaderboard_embed(page: int = 1, per_page: int = 10) -> discord.Embed:
    rows = await db.get_leaderboard()
    sorted_points = sorted(rows, key=lambda x: x[1], reverse=True)
    total_pages = max(1, (len(sorted_points) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page

    lines = []
    top_emojis = ["🥇", "🥈", "🥉"]
    for idx, (user_id, pts) in enumerate(sorted_points[start:end], start=start + 1):
        prefix = f"**#{idx}** "
        if idx <= 3:
            prefix += f"{top_emojis[idx - 1]} "
        lines.append(f"{prefix}<@{user_id}>\n└ **{pts:,} points**")

    description = "\n".join(lines) if lines else "No entries yet."
    embed = discord.Embed(
        title="🏆 HELPER'S LEADERBOARD SEASON 8 🏆",
        description=description,
        color=ACCENT,
    )
    embed.set_footer(text=f"📄 Page {page}/{max(1, total_pages)}")
    return embed

class LeaderboardView(discord.ui.View):
    def __init__(self, current_page: int = 1, per_page: int = 10):
        super().__init__(timeout=None)
        self.current_page = current_page
        self.per_page = per_page
        self.total_pages = 1

    async def update_total_pages(self):
        rows = await db.get_leaderboard()
        self.total_pages = max(1, (len(rows) + self.per_page - 1) // self.per_page)

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji="◀️", custom_id="lb_prev")
    async def prev_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.update_total_pages()
        if self.current_page <= 1:
            await interaction.response.defer()
            return
        self.current_page -= 1
        embed = await create_leaderboard_embed(self.current_page, self.per_page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji="🔄", custom_id="lb_refresh")
    async def refresh(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.update_total_pages()
        embed = await create_leaderboard_embed(self.current_page, self.per_page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji="▶️", custom_id="lb_next")
    async def next_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.update_total_pages()
        if self.current_page >= self.total_pages:
            await interaction.response.defer()
            return
        self.current_page += 1
        embed = await create_leaderboard_embed(self.current_page, self.per_page)
        await interaction.response.edit_message(embed=embed, view=self)

class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.slash_command(name="leaderboard", description="Show the helper leaderboard")
    async def leaderboard(self, ctx: discord.ApplicationContext):
        embed = await create_leaderboard_embed(page=1, per_page=10)
        view = LeaderboardView(current_page=1, per_page=10)
        await ctx.respond(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
