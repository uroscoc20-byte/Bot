# leaderboard.py
import discord
from discord.ext import commands
from database import db

ACCENT = 0x5865F2
PER_PAGE = 10
TOP_EMOJIS = ["🥇", "🥈", "🥉"]

# ------------------------
# Leaderboard Embed
# ------------------------
async def create_leaderboard_embed(page: int = 1, per_page: int = PER_PAGE) -> discord.Embed:
    rows = await db.get_leaderboard()
    sorted_points = sorted(rows, key=lambda x: x[1], reverse=True)
    total_pages = max(1, (len(sorted_points) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page

    lines = []
    for idx, (user_id, pts) in enumerate(sorted_points[start:end], start=start + 1):
        prefix = f"#{idx} "
        if idx <= 3:
            prefix += f"{TOP_EMOJIS[idx - 1]} "
        # visually nice: bold names and points
        lines.append(f"{prefix}**<@{user_id}>** — `{pts} pts`")

    description = "\n".join(lines) if lines else "No entries yet."
    
    # Load custom title from DB if set
    cfg = await db.load_config("leaderboard_title")
    title = cfg.get("title") if cfg else "🏆 Helper's Leaderboard"

    embed = discord.Embed(
        title=title,
        description=description,
        color=ACCENT,
    )
    embed.set_footer(text=f"Page {page}/{total_pages} • Use arrows to navigate")
    return embed

# ------------------------
# Leaderboard Pagination View
# ------------------------
class LeaderboardView(discord.ui.View):
    def __init__(self, current_page: int, total_pages: int, per_page: int = PER_PAGE):
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

# ------------------------
# Points & Leaderboard Cog
# ------------------------
class PointsModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ------------------------
    # /points command
    # ------------------------
    @commands.slash_command(name="points", description="Check your points or another user's points")
    async def points(self, ctx: discord.ApplicationContext, user: discord.Option(discord.User, "Select a user", required=False)):
        target = user or ctx.user
        pts = await db.get_points(target.id)
        avatar = target.display_avatar.url if target.display_avatar else None
        embed = discord.Embed(
            title=f"🏅 Points for {target.display_name}",
            description=f"**{pts} pts**",
            color=ACCENT
        )
        if avatar:
            embed.set_thumbnail(url=avatar)
        embed.set_footer(text="Use /leaderboard to view rankings")
        await ctx.respond(embed=embed)

    # ------------------------
    # /leaderboard command
    # ------------------------
    @commands.slash_command(name="leaderboard", description="Show points leaderboard")
    async def leaderboard(self, ctx: discord.ApplicationContext, page: discord.Option(int, "Page number", required=False, default=1)):
        await ctx.defer()
        rows = await db.get_leaderboard()
        if not rows:
            await ctx.followup.send("Leaderboard is empty.")
            return

        total_pages = max(1, (len(rows) + PER_PAGE - 1) // PER_PAGE)
        embed = await create_leaderboard_embed(page)
        view = LeaderboardView(page, total_pages)
        await ctx.followup.send(embed=embed, view=view)

    # ------------------------
    # /leaderboard_rename command
    # ------------------------
    @commands.slash_command(name="leaderboard_rename", description="Rename the leaderboard title (Admin only)")
    async def leaderboard_rename(self, ctx: discord.ApplicationContext, title: discord.Option(str, "New leaderboard title")):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.")
            return
        await db.save_config("leaderboard_title", {"title": title})
        await ctx.respond(f"✅ Leaderboard renamed to: **{title}**")

    # ------------------------
    # Admin point commands (add, remove, set, remove_user, reset)
    # ------------------------
    # Keep your existing admin commands here

# ------------------------
# Setup
# ------------------------
def setup(bot):
    bot.add_cog(PointsModule(bot))
