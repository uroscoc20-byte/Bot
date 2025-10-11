import discord
from database import db

async def create_leaderboard_embed(page=1, per_page=10):
    rows = await db.get_leaderboard()  # [(user_id, points), ...]
    sorted_points = sorted(rows, key=lambda x: x[1], reverse=True)
    total_pages = max(1, (len(sorted_points) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page

    embed = discord.Embed(
        title="🏆 Points Leaderboard",
        description=f"Page {page}/{total_pages}",
        color=0x00FFAA,
    )

    top_emojis = ["🥇", "🥈", "🥉"]
    for idx, (user_id, pts) in enumerate(sorted_points[start:end], start=start + 1):
        emoji = top_emojis[idx - 1] if idx <= 3 else ""
        embed.add_field(
            name=f"{emoji} #{idx}",
            value=f"<@{user_id}> — **{pts} points**",
            inline=False,
        )

    if total_pages > 1:
        embed.set_footer(text="Use /leaderboard [page] to see other pages")
    return embed
