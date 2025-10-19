import re
import discord
from database import db

# Use a brighter gold to make it visually "bigger" and more prominent
ACCENT = 0xFFD700

TITLE_TEXT = "🏆 Helper's Leaderboard Season 7"
PAGE_FOOTER_PATTERN = re.compile(r"Page\s+(\d+)\/(\d+)")


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
        prefix = f"#{idx} "
        if idx <= 3:
            prefix += f"{top_emojis[idx - 1]} "
        # Emphasize entries for a more pronounced look
        lines.append(f"{prefix}**<@{user_id}>** — **{pts} pts**")

    header = "═══════ Top Helpers ═══════"
    description = (f"{header}\n\n" + "\n".join(lines)) if lines else "No entries yet."
    embed = discord.Embed(
        title=TITLE_TEXT,
        description=description,
        color=ACCENT,
    )
    embed.set_footer(text=f"Page {page}/{total_pages}")
    return embed


class LeaderboardView(discord.ui.View):
    def __init__(self, per_page: int = 10):
        # Persistent so leaderboard controls work after restarts
        super().__init__(timeout=None)
        self.per_page = per_page

    def _sync_buttons(self, current_page: int, total_pages: int):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "lb_prev":
                    child.disabled = current_page <= 1
                elif child.custom_id == "lb_next":
                    child.disabled = current_page >= total_pages

    @staticmethod
    def _parse_page_from_embed(embed: discord.Embed) -> tuple[int, int]:
        footer = (embed.footer and embed.footer.text) or ""
        m = PAGE_FOOTER_PATTERN.search(footer)
        if not m:
            return 1, 1
        try:
            return int(m.group(1)), int(m.group(2))
        except Exception:
            return 1, 1

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji="◀️", custom_id="lb_prev")
    async def prev_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        msg = interaction.message
        if not msg or not msg.embeds:
            await interaction.response.defer()
            return
        current_page, _ = self._parse_page_from_embed(msg.embeds[0])
        new_page = max(1, current_page - 1)
        embed = await create_leaderboard_embed(new_page, self.per_page)
        # Recompute total pages to properly disable buttons
        _, total_pages = self._parse_page_from_embed(embed)
        self._sync_buttons(new_page, total_pages)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji="▶️", custom_id="lb_next")
    async def next_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        msg = interaction.message
        if not msg or not msg.embeds:
            await interaction.response.defer()
            return
        current_page, total_pages = self._parse_page_from_embed(msg.embeds[0])
        new_page = min(total_pages, current_page + 1)
        embed = await create_leaderboard_embed(new_page, self.per_page)
        # Recompute total pages to properly disable buttons
        _, total_pages = self._parse_page_from_embed(embed)
        self._sync_buttons(new_page, total_pages)
        await interaction.response.edit_message(embed=embed, view=self)


def register_persistent_views(bot: discord.Client):
    """Register persistent leaderboard controls so they work after restarts."""
    try:
        bot.add_view(LeaderboardView())
    except Exception:
        # Ignore if already added
        pass