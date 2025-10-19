import discord
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
        title="🏆 Helper's Leaderboard Season 7",
        description=description,
        color=ACCENT,
    )
    embed.set_footer(text=f"📄 Page {page}/{total_pages} • 🔄 Auto-refreshes every 15 minutes")
    return embed


class LeaderboardView(discord.ui.View):
    def __init__(self, current_page: int, total_pages: int, per_page: int):
        super().__init__(timeout=120)
        self.current_page = current_page
        self.total_pages = max(1, total_pages)
        self.per_page = per_page
        self._sync_buttons()

    def _sync_buttons(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "lb_prev":
                    child.disabled = self.current_page <= 1
                elif child.custom_id == "lb_next":
                    child.disabled = self.current_page >= self.total_pages

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji="◀️", custom_id="lb_prev")
    async def prev_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.current_page <= 1:
            await interaction.response.defer()
            return
        self.current_page -= 1
        embed = await create_leaderboard_embed(self.current_page, self.per_page)
        self._sync_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji="▶️", custom_id="lb_next")
    async def next_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.current_page >= self.total_pages:
            await interaction.response.defer()
            return
        self.current_page += 1
        embed = await create_leaderboard_embed(self.current_page, self.per_page)
        self._sync_buttons()
        await interaction.response.edit_message(embed=embed, view=self)