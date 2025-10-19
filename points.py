import discord
from discord.ext import commands
from leaderboard import create_leaderboard_embed, LeaderboardView
from database import db

ACCENT = 0x5865F2

class PointsModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def reward_ticket_helpers(ticket_info):
        helpers = [h for h in ticket_info.get("helpers", []) if h]
        category = ticket_info.get("category")
        points = ticket_info.get("points", 10)
        for uid in helpers:
            current = await db.get_points(uid)
            await db.set_points(uid, current + points)
        channel = ticket_info.get("embed_msg").channel
        await channel.send(f"Helpers have been rewarded for **{category}** ticket!")

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

    @commands.slash_command(name="leaderboard", description="Show points leaderboard")
    async def leaderboard(
        self,
        ctx: discord.ApplicationContext,
        page: discord.Option(int, "Page number", required=False, default=1),
    ):
        rows = await db.get_leaderboard()
        per_page = 15
        total_pages = max(1, (len(rows) + per_page - 1) // per_page)
        if not rows:
            await ctx.respond("Leaderboard is empty.")
            return
        embed = await create_leaderboard_embed(page=page, per_page=per_page)
        view = LeaderboardView()
        await ctx.respond(embed=embed, view=view)

    @commands.slash_command(name="leaderboard_refresh", description="Refresh the leaderboard message (admin/staff only)")
    async def leaderboard_refresh(self, ctx: discord.ApplicationContext):
        roles = await db.get_roles()
        staff_id = roles.get("staff") if roles else None
        admin_id = roles.get("admin") if roles else None
        is_allowed = ctx.user.guild_permissions.administrator or (admin_id and any(r.id == admin_id for r in ctx.user.roles)) or (staff_id and any(r.id == staff_id for r in ctx.user.roles))
        if not is_allowed:
            await ctx.respond("You don't have permission to refresh the leaderboard.", ephemeral=True)
            return

        # Try to delete old leaderboard embeds in channel and send a fresh one
        deleted = 0
        try:
            async for msg in ctx.channel.history(limit=200):
                if msg.author.id != ctx.bot.user.id:
                    continue
                if msg.embeds and msg.embeds[0].title and "Leaderboard" in msg.embeds[0].title:
                    try:
                        await msg.delete()
                        deleted += 1
                    except Exception:
                        pass
        except Exception:
            pass

        rows = await db.get_leaderboard()
        if not rows:
            await ctx.respond("Leaderboard is empty.")
            return
        embed = await create_leaderboard_embed(page=1, per_page=15)
        view = LeaderboardView()
        await ctx.respond(f"Refreshed leaderboard (removed {deleted} old).", ephemeral=True)
        await ctx.channel.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        custom_id = interaction.data.get("custom_id") if interaction.data else None
        if custom_id not in {"lb_prev", "lb_next"}:
            return

        # If the original view already handled it, skip
        if interaction.response.is_done():
            return

        msg = interaction.message
        embed = msg.embeds[0] if msg and msg.embeds else None
        if not embed:
            await interaction.response.defer()
            return

        footer = (embed.footer.text or "") if embed.footer else ""
        import re
        m = re.search(r"(\d+)\s*/\s*(\d+)", footer)
        try:
            current_page = int(m.group(1)) if m else 1
            total_pages = int(m.group(2)) if m else 1
        except Exception:
            current_page, total_pages = 1, 1

        if custom_id == "lb_prev" and current_page <= 1:
            await interaction.response.defer()
            return
        if custom_id == "lb_next" and current_page >= total_pages:
            await interaction.response.defer()
            return

        target_page = current_page - 1 if custom_id == "lb_prev" else current_page + 1
        embed = await create_leaderboard_embed(page=target_page, per_page=15)
        await interaction.response.edit_message(embed=embed, view=LeaderboardView())

    @commands.slash_command(name="points_reset", description="Reset all points (Admin only)")
    async def points_reset(self, ctx: discord.ApplicationContext):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.", ephemeral=True)
            return
        await db.reset_points()
        await ctx.respond("Leaderboard has been reset!", ephemeral=True)

    @commands.slash_command(name="points_add", description="Add points to a user (Admin only)")
    async def points_add(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, "User"),
        amount: discord.Option(int, "Amount"),
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.", ephemeral=True)
            return
        if amount <= 0:
            await ctx.respond("Amount must be positive.", ephemeral=True)
            return
        current = await db.get_points(user.id)
        await db.set_points(user.id, current + amount)
        await ctx.respond(f"Added {amount} points to {user.mention}.", ephemeral=True)

    @commands.slash_command(name="points_remove", description="Remove points from a user (Admin only)")
    async def points_remove(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, "User"),
        amount: discord.Option(int, "Amount"),
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.", ephemeral=True)
            return
        if amount <= 0:
            await ctx.respond("Amount must be positive.", ephemeral=True)
            return
        current = await db.get_points(user.id)
        await db.set_points(user.id, max(0, current - amount))
        await ctx.respond(f"Removed {amount} points from {user.mention}.", ephemeral=True)

    @commands.slash_command(name="points_set", description="Set user's points to exact value (Admin only)")
    async def points_set(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, "User"),
        amount: discord.Option(int, "Amount"),
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.", ephemeral=True)
            return
        if amount < 0:
            await ctx.respond("Amount cannot be negative.", ephemeral=True)
            return
        await db.set_points(user.id, amount)
        await ctx.respond(f"Set {user.mention}'s points to {amount}.", ephemeral=True)

    @commands.slash_command(name="points_remove_user", description="Remove a user from leaderboard (Admin only)")
    async def points_remove_user(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, "User"),
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.", ephemeral=True)
            return
        await db.delete_user_points(user.id)
        await ctx.respond(f"Removed {user.mention} from the leaderboard.", ephemeral=True)

def setup(bot):
    bot.add_cog(PointsModule(bot))