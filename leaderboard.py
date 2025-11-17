import discord
from discord.ext import commands
from database import db  # make sure your db module has get_leaderboard()

ACCENT = 0x5865F2
PER_PAGE = 10

# ------------------- EMBED CREATOR -------------------
async def create_leaderboard_embed(page: int = 1, per_page: int = PER_PAGE) -> discord.Embed:
    rows = await db.get_leaderboard()  # Should return list of tuples [(user_id, points), ...]
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
        title="🏆 Helper's Leaderboard Season 8",
        description=description,
        color=ACCENT,
    )
    embed.set_footer(text=f"Page {page}/{total_pages}")
    return embed

# ------------------- LEADERBOARD VIEW -------------------
class LeaderboardView(discord.ui.View):
    def __init__(self, current_page: int, total_pages: int):
        super().__init__(timeout=None)  # persistent forever
        self.current_page = current_page
        self.total_pages = max(1, total_pages)
        self._sync_buttons()

    def _sync_buttons(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "lb_prev":
                    child.disabled = self.current_page <= 1
                elif child.custom_id == "lb_next":
                    child.disabled = self.current_page >= self.total_pages

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji="◀️", custom_id="lb_prev", row=0)
    async def prev_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.current_page <= 1:
            await interaction.response.defer()
            return
        self.current_page -= 1
        embed = await create_leaderboard_embed(self.current_page)
        self._sync_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji="▶️", custom_id="lb_next", row=0)
    async def next_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.current_page >= self.total_pages:
            await interaction.response.defer()
            return
        self.current_page += 1
        embed = await create_leaderboard_embed(self.current_page)
        self._sync_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

# ------------------- BOT SETUP -------------------
bot = commands.Bot(command_prefix="!")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.add_view(LeaderboardView(current_page=1, total_pages=1))  # persistent buttons registration

# ------------------- LEADERBOARD COMMAND -------------------
@bot.command()
async def leaderboard(ctx):
    rows = await db.get_leaderboard()
    total_pages = max(1, (len(rows) + PER_PAGE - 1) // PER_PAGE)
    embed = await create_leaderboard_embed(page=1)
    view = LeaderboardView(current_page=1, total_pages=total_pages)
    await ctx.send(embed=embed, view=view)

# ------------------- RUN BOT -------------------
bot.run("YOUR_BOT_TOKEN")
