import discord
from database import db

ACCENT = 0x5865F2

async def create_leaderboard_embed(page: int = 1, per_page: int = 20) -> discord.Embed:
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
    def __init__(self, current_page: int, total_pages: int, per_page: int):
        # Persistent view: no timeout so buttons keep working
        super().__init__(timeout=None)
        self.per_page = per_page

        prev_button = discord.ui.Button(style=discord.ButtonStyle.gray, emoji="◀️", custom_id="lb_prev")
        next_button = discord.ui.Button(style=discord.ButtonStyle.gray, emoji="▶️", custom_id="lb_next")

        # Initialize disabled state based on provided page counters
        prev_button.disabled = current_page <= 1
        next_button.disabled = current_page >= max(1, total_pages)

        self.add_item(prev_button)
        self.add_item(next_button)