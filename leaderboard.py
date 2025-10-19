import re
import discord
from database import db

ACCENT = 0x5865F2

# Increase default page size to make the leaderboard "bigger"
LEADERBOARD_PAGE_SIZE = 15

async def create_leaderboard_embed(page: int = 1, per_page: int = LEADERBOARD_PAGE_SIZE) -> discord.Embed:
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
        title="Helper's Leaderboard Season 7",
        description=description,
        color=ACCENT,
    )
    embed.set_footer(text=f"Page {page}/{total_pages}")
    return embed


class LeaderboardView(discord.ui.View):
    def __init__(self):
        # Persistent, stateless view so buttons keep working indefinitely
        super().__init__(timeout=None)

    @staticmethod
    def _parse_page_info(text: str) -> tuple[int, int] | tuple[None, None]:
        if not text:
            return None, None
        try:
            m = re.search(r"Page\s+(\d+)\s*/\s*(\d+)", text)
            if not m:
                return None, None
            return int(m.group(1)), int(m.group(2))
        except Exception:
            return None, None

    def _sync_buttons_with_page(self, page: int, total_pages: int):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "lb_prev":
                    child.disabled = page <= 1
                elif child.custom_id == "lb_next":
                    child.disabled = page >= total_pages

    @discord.ui.button(style=discord.ButtonStyle.primary, emoji="◀️", custom_id="lb_prev")
    async def prev_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        try:
            msg = interaction.message
            embed = msg.embeds[0] if msg and msg.embeds else None
            page, total_pages = self._parse_page_info(embed.footer.text if embed and embed.footer else "")
            if not page or page <= 1:
                await interaction.response.defer()
                return
            new_page = max(1, page - 1)
            new_embed = await create_leaderboard_embed(new_page, LEADERBOARD_PAGE_SIZE)
            self._sync_buttons_with_page(new_page, int(new_embed.footer.text.split("/")[-1]))
            await interaction.response.edit_message(embed=new_embed, view=self)
        except Exception:
            try:
                await interaction.response.defer()
            except Exception:
                pass

    @discord.ui.button(style=discord.ButtonStyle.primary, emoji="▶️", custom_id="lb_next")
    async def next_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        try:
            msg = interaction.message
            embed = msg.embeds[0] if msg and msg.embeds else None
            page, total_pages = self._parse_page_info(embed.footer.text if embed and embed.footer else "")
            if not page or not total_pages or page >= total_pages:
                await interaction.response.defer()
                return
            new_page = min(total_pages, page + 1)
            new_embed = await create_leaderboard_embed(new_page, LEADERBOARD_PAGE_SIZE)
            self._sync_buttons_with_page(new_page, int(new_embed.footer.text.split("/")[-1]))
            await interaction.response.edit_message(embed=new_embed, view=self)
        except Exception:
            try:
                await interaction.response.defer()
            except Exception:
                pass