import discord
from database import db

ACCENT = 0x5865F2
ENTRIES_PER_PAGE = 10

async def create_leaderboard_embed(bot: discord.Bot, page: int = 1) -> discord.Embed:
    rows = await db.get_leaderboard()
    sorted_points = sorted(rows, key=lambda x: x[1], reverse=True)
    total_pages = max(1, (len(sorted_points) + ENTRIES_PER_PAGE - 1) // ENTRIES_PER_PAGE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * ENTRIES_PER_PAGE
    end = start + ENTRIES_PER_PAGE

    # Fetch leaderboard title from DB
    cfg = await db.load_config("leaderboard_title")
    title = cfg.get("title") if cfg else "🏆 Helper's Leaderboard"

    embed = discord.Embed(
        title=title,
        color=ACCENT
    )

    description_lines = []
    top_emojis = ["🥇", "🥈", "🥉"]

    for idx, (user_id, pts) in enumerate(sorted_points[start:end], start=start + 1):
        # Fetch user
        user = bot.get_user(user_id)
        if not user:
            try:
                user = await bot.fetch_user(user_id)
            except:
                user = None

        display_name = f"{user}" if user else f"<@{user_id}>"

        prefix = f"#{idx} "
        if idx <= 3:
            prefix += f"{top_emojis[idx - 1]} "

        # Small graphical bar for points
        max_points = sorted_points[0][1] if sorted_points else 1
        bar_length = int((pts / max_points) * 10)
        bar = "▰" * bar_length + "▱" * (10 - bar_length)

        description_lines.append(f"{prefix}{display_name} — **{pts} pts** | {bar}")

    embed.description = "\n".join(description_lines) if description_lines else "No entries yet."
    embed.set_footer(text=f"Page {page}/{total_pages} — Total users: {len(sorted_points)}")
    return embed
