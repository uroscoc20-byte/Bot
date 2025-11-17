import discord
from discord.ext import commands
from database import db

ACCENT = 0x5865F2

# ------------------------
# Leaderboard Embed
# ------------------------
async def create_leaderboard_embed(bot, page: int = 1, per_page: int = 10) -> discord.Embed:
    rows = await db.get_leaderboard()
    sorted_points = sorted(rows, key=lambda x: x[1], reverse=True)
    total_pages = max(1, (len(sorted_points) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page

    lines = []
    top_emojis = ["🥇", "🥈", "🥉"]

    # Build a dict of all guild members to avoid multiple get_user calls
    guild_members = {}
    for guild in bot.guilds:
        for member in guild.members:
            guild_members[member.id] = member

    for idx, (user_id, pts) in enumerate(sorted_points[start:end], start=start + 1):
        member = guild_members.get(user_id)
        name = member.display_name if member else f"<@{user_id}>"
        prefix = f"#{idx} "
        if idx <= 3:
            prefix += f"{top_emojis[idx - 1]} "
        lines.append(f"{prefix}{name} — **{pts}**")

    description = "\n".join(lines) if lines else "No entries yet."

    # Load leaderboard title from DB
    cfg = await db.load_config("leaderboard_title")
    title = cfg.get("title") if cfg else "🏆 Helper's Leaderboard"

    embed = discord.Embed(
        title=title,
        description=description,
        color=ACCENT,
    )
    embed.set_footer(text=f"Page {page}/{total_pages}")
    return embed


# ------------------------
# Leaderboard View (Pagination)
# ------------------------
class LeaderboardView(discord.ui.View):
    def __init__(self, bot, current_page: int, total_pages: int, per_page: int):
        super().__init__(timeout=120)
        self.bot = bot
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
        embed = await create_leaderboard_embed(self.bot, self.current_page, self.per_page)
        self._sync_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji="▶️", custom_id="lb_next")
    async def next_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.current_page >= self.total_pages:
            await interaction.response.defer()
            return
        self.current_page += 1
        embed = await create_leaderboard_embed(self.bot, self.current_page, self.per_page)
        self._sync_buttons()
        await interaction.response.edit_message(embed=embed, view=self)


# ------------------------
# Points Module
# ------------------------
class PointsModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # -------------
    # /points
    # -------------
    @commands.slash_command(name="points", description="Check your points or another user's points")
    async def points(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, "Select a user", required=False),
    ):
        target = user or ctx.user
        pts = await db.get_points(target.id)
        avatar = target.display_avatar.url if target.display_avatar else None
        embed = discord.Embed(title=f"🏅 Points for {target.display_name}", description=f"**{pts} points**", color=ACCENT)
        if avatar:
            embed.set_thumbnail(url=avatar)
        embed.set_footer(text="Use /leaderboard to view rankings")
        await ctx.respond(embed=embed)

    # -------------
    # /leaderboard
    # -------------
    @commands.slash_command(name="leaderboard", description="Show points leaderboard")
    async def leaderboard(
        self,
        ctx: discord.ApplicationContext,
        page: discord.Option(int, "Page number", required=False, default=1),
    ):
        rows = await db.get_leaderboard()
        per_page = 10
        total_pages = max(1, (len(rows) + per_page - 1) // per_page)
        if not rows:
            await ctx.respond("Leaderboard is empty.")
            return
        embed = await create_leaderboard_embed(self.bot, page=page, per_page=per_page)
        view = LeaderboardView(self.bot, page, total_pages, per_page)
        await ctx.respond(embed=embed, view=view)

    # -------------
    # /leaderboard_rename
    # -------------
    @commands.slash_command(name="leaderboard_rename", description="Rename the leaderboard title (Admin only)")
    async def leaderboard_rename(
        self,
        ctx: discord.ApplicationContext,
        title: discord.Option(str, "New leaderboard title")
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.")
            return
        await db.save_config("leaderboard_title", {"title": title})
        await ctx.respond(f"✅ Leaderboard renamed to: **{title}**")

    # -------------
    # Admin point commands
    # -------------
    @commands.slash_command(name="points_add", description="Add points to a user (Admin only)")
    async def points_add(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, "User"),
        amount: discord.Option(int, "Amount"),
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.")
            return
        if amount <= 0:
            await ctx.respond("Amount must be positive.")
            return
        current = await db.get_points(user.id)
        await db.set_points(user.id, current + amount)
        await ctx.respond(f"Added {amount} points to {user.mention}.")

    @commands.slash_command(name="points_remove", description="Remove points from a user (Admin only)")
    async def points_remove(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, "User"),
        amount: discord.Option(int, "Amount"),
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.")
            return
        if amount <= 0:
            await ctx.respond("Amount must be positive.")
            return
        current = await db.get_points(user.id)
        await db.set_points(user.id, max(0, current - amount))
        await ctx.respond(f"Removed {amount} points from {user.mention}.")

    @commands.slash_command(name="points_set", description="Set user's points to exact value (Admin only)")
    async def points_set(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, "User"),
        amount: discord.Option(int, "Amount"),
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.")
            return
        if amount < 0:
            await ctx.respond("Amount cannot be negative.")
            return
        await db.set_points(user.id, amount)
        await ctx.respond(f"Set {user.mention}'s points to {amount}.")

    @commands.slash_command(name="points_remove_user", description="Remove a user from leaderboard (Admin only)")
    async def points_remove_user(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, "User"),
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.")
            return
        await db.delete_user_points(user.id)
        await ctx.respond(f"Removed {user.mention} from the leaderboard.")

    @commands.slash_command(name="points_reset", description="Reset all points (Admin only)")
    async def points_reset(self, ctx: discord.ApplicationContext):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.")
            return
        await db.reset_points()
        await ctx.respond("Leaderboard has been reset!")


# ------------------------
# Setup
# ------------------------
def setup(bot):
    bot.add_cog(PointsModule(bot))
