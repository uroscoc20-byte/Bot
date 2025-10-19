import discord
import re
from database import db

ACCENT = 0x5865F2
PER_PAGE = 15

async def create_leaderboard_embed(page: int = 1, per_page: int = PER_PAGE) -> discord.Embed:
    rows = await db.get_leaderboard()
    sorted_points = sorted(rows, key=lambda x: x[1], reverse=True)
    total_pages = max(1, (len(sorted_points) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page

    lines = []
    top_emojis = ["🥇", "🥈", "🥉"]
    for idx, (user_id, pts) in enumerate(sorted_points[start:end], start=start + 1):
        prefix = f"#{idx} "
        if idx <= 3:
            prefix += f"{top_emojis[idx - 1]} "
        lines.append(f"{prefix}<@{user_id}> — **{pts}**")

    description = "\n".join(lines) if lines else "No entries yet."
    embed = discord.Embed(
        title="🏆 Helper's Leaderboard Season 7",
        description=description,
        color=ACCENT,
    )
    embed.set_footer(text=f"Page {page}/{total_pages}")
    return embed


class LeaderboardView(discord.ui.View):
    def __init__(self):
        # Persistent view so buttons keep working across restarts/timeouts
        super().__init__(timeout=None)

    @staticmethod
    def _parse_page_from_embed(embed: discord.Embed) -> tuple[int, int]:
        footer = (embed.footer.text or "") if embed.footer else ""
        # Expect formats like "Page 1/10"
        m = re.search(r"(\d+)\s*/\s*(\d+)", footer)
        if m:
            try:
                return max(1, int(m.group(1))), max(1, int(m.group(2)))
            except Exception:
                pass
        # Fallback when not parsable
        return 1, 1

    async def _edit_with_page(self, interaction: discord.Interaction, target_page: int):
        rows = await db.get_leaderboard()
        total_pages = max(1, (len(rows) + PER_PAGE - 1) // PER_PAGE)
        page = max(1, min(target_page, total_pages))
        embed = await create_leaderboard_embed(page=page, per_page=PER_PAGE)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji="◀️", custom_id="lb_prev")
    async def prev_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        embed = interaction.message.embeds[0] if interaction.message and interaction.message.embeds else None
        if not embed:
            await interaction.response.defer()
            return
        current_page, _ = self._parse_page_from_embed(embed)
        await self._edit_with_page(interaction, max(1, current_page - 1))

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji="▶️", custom_id="lb_next")
    async def next_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        embed = interaction.message.embeds[0] if interaction.message and interaction.message.embeds else None
        if not embed:
            await interaction.response.defer()
            return
        current_page, total_pages = self._parse_page_from_embed(embed)
        await self._edit_with_page(interaction, min(total_pages, current_page + 1))