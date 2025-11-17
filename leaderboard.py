# leaderboard.py
import discord
from discord.ext import commands
from database import db

ACCENT = 0x5865F2
TOP_EMOJIS = ["🥇", "🥈", "🥉"]
PER_PAGE = 10
GUILD_ID = 1345073229026562079  # Your server ID

# ------------------------
# Leaderboard Embed
# ------------------------
async def create_leaderboard_embed(bot, guild: discord.Guild, page: int = 1, per_page: int = PER_PAGE):
    rows = await db.get_leaderboard()
    sorted_points = sorted(rows, key=lambda x: x[1], reverse=True)
    total_pages = max(1, (len(sorted_points) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page

    lines = []
    for idx, (user_id, pts) in enumerate(sorted_points[start:end], start=start + 1):
        member = guild.get_member(user_id)
        name = member.display_name if member else f"<@{user_id}>"
        prefix = f"#{idx} "
        if idx <= 3:
            prefix += f"{TOP_EMOJIS[idx - 1]} "
        lines.append(f"{prefix}{name} — **{pts} pts**")

    description = "\n".join(lines) if lines else "No entries yet."
    cfg = await db.load_config("leaderboard_title")
    title = cfg.get("title") if cfg else "🏆 Helper's Leaderboard"

    embed = discord.Embed(title=title, description=description, color=ACCENT)
    embed.set_footer(text=f"Page {page}/{total_pages}")
    return embed

# ------------------------
# Leaderboard View
# ------------------------
class LeaderboardView(discord.ui.View):
    def __init__(self, bot, guild, current_page: int, total_pages: int, per_page: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild = guild
        self.current_page = current_page
        self.total_pages = total_pages
        self.per_page = per_page
        self._sync_buttons()

    def _sync_buttons(self):
        for b in self.children:
            if isinstance(b, discord.ui.Button):
                b.disabled = (
                    b.custom_id == "lb_prev" and self.current_page <= 1
                ) or (
                    b.custom_id == "lb_next" and self.current_page >= self.total_pages
                )

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji="◀️", custom_id="lb_prev")
    async def prev_page(self, button, interaction: discord.Interaction):
        if self.current_page <= 1:
            await interaction.response.defer()
            return
        self.current_page -= 1
        embed = await create_leaderboard_embed(self.bot, self.guild, self.current_page, self.per_page)
        self._sync_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji="▶️", custom_id="lb_next")
    async def next_page(self, button, interaction: discord.Interaction):
        if self.current_page >= self.total_pages:
            await interaction.response.defer()
            return
        self.current_page += 1
        embed = await create_leaderboard_embed(self.bot, self.guild, self.current_page, self.per_page)
        self._sync_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

# ------------------------
# Points & Leaderboard Cog
# ------------------------
class PointsModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ------------------------
    # /points
    # ------------------------
    @commands.slash_command(guild_ids=[GUILD_ID], name="points", description="Check your points or another user's points")
    async def points(self, ctx: discord.ApplicationContext, user: discord.Option(discord.User, "Select a user", required=False)):
        target = user or ctx.user
        pts = await db.get_points(target.id)
        avatar = target.display_avatar.url if target.display_avatar else None
        embed = discord.Embed(
            title=f"🏅 Points for {target.display_name}",
            description=f"**{pts} points**",
            color=ACCENT
        )
        if avatar:
            embed.set_thumbnail(url=avatar)
        embed.set_footer(text="Use /leaderboard to view rankings")
        await ctx.respond(embed=embed)

    # ------------------------
    # /leaderboard
    # ------------------------
    @commands.slash_command(guild_ids=[GUILD_ID], name="leaderboard", description="Show points leaderboard")
    async def leaderboard(self, ctx: discord.ApplicationContext, page: discord.Option(int, "Page number", required=False, default=1)):
        await ctx.defer()
        guild = ctx.guild
        if not guild:
            await ctx.followup.send("This command can only be used in a server.")
            return

        rows = await db.get_leaderboard()
        if not rows:
            await ctx.followup.send("Leaderboard is empty.")
            return

        embed = await create_leaderboard_embed(self.bot, guild, page)
        total_pages = max(1, (len(rows) + PER_PAGE - 1) // PER_PAGE)
        view = LeaderboardView(self.bot, guild, page, total_pages, PER_PAGE)
        await ctx.followup.send(embed=embed, view=view)

    # ------------------------
    # /leaderboard_rename
    # ------------------------
    @commands.slash_command(guild_ids=[GUILD_ID], name="leaderboard_rename", description="Rename the leaderboard title (Admin only)")
    async def leaderboard_rename(self, ctx: discord.ApplicationContext, title: discord.Option(str, "New leaderboard title")):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.")
            return
        await db.save_config("leaderboard_title", {"title": title})
        await ctx.respond(f"✅ Leaderboard renamed to: **{title}**")

    # ------------------------
    # Admin /points commands
    # ------------------------
    @commands.slash_command(guild_ids=[GUILD_ID], name="points_add", description="Add points to a user (Admin only)")
    async def points_add(self, ctx: discord.ApplicationContext, user: discord.Option(discord.User), amount: discord.Option(int)):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("No permission."); return
        if amount <= 0:
            await ctx.respond("Amount must be positive."); return
        current = await db.get_points(user.id)
        await db.set_points(user.id, current + amount)
        await ctx.respond(f"Added {amount} points to {user.mention}.")

    @commands.slash_command(guild_ids=[GUILD_ID], name="points_remove", description="Remove points from a user (Admin only)")
    async def points_remove(self, ctx: discord.ApplicationContext, user: discord.Option(discord.User), amount: discord.Option(int)):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("No permission."); return
        if amount <= 0:
            await ctx.respond("Amount must be positive."); return
        current = await db.get_points(user.id)
        await db.set_points(user.id, max(0, current - amount))
        await ctx.respond(f"Removed {amount} points from {user.mention}.")

    @commands.slash_command(guild_ids=[GUILD_ID], name="points_set", description="Set points of a user (Admin only)")
    async def points_set(self, ctx: discord.ApplicationContext, user: discord.Option(discord.User), amount: discord.Option(int)):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("No permission."); return
        if amount < 0:
            await ctx.respond("Cannot be negative."); return
        await db.set_points(user.id, amount)
        await ctx.respond(f"Set {user.mention}'s points to {amount}.")

    @commands.slash_command(guild_ids=[GUILD_ID], name="points_remove_user", description="Remove user from leaderboard (Admin only)")
    async def points_remove_user(self, ctx: discord.ApplicationContext, user: discord.Option(discord.User)):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("No permission."); return
        await db.delete_user_points(user.id)
        await ctx.respond(f"Removed {user.mention} from leaderboard.")

    @commands.slash_command(guild_ids=[GUILD_ID], name="points_reset", description="Reset all points (Admin only)")
    async def points_reset(self, ctx: discord.ApplicationContext):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("No permission."); return
        await db.reset_points()
        await ctx.respond("Leaderboard has been reset!")

# ------------------------
# Setup
# ------------------------
def setup(bot):
    bot.add_cog(PointsModule(bot))
