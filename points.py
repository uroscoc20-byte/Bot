import discord
from discord.ext import commands
from leaderboard import create_leaderboard_embed  # Modern embed
from database import db

# ---------- COG ----------
class PointsModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- REWARD HELPERS ----------
    @staticmethod
    async def reward_ticket_helpers(ticket_info):
        helpers = [h for h in ticket_info.get("helpers", []) if h]
        category = ticket_info.get("category")
        points = ticket_info.get("points", 10)  # fallback
        for uid in helpers:
            current = await db.get_points(uid)
            await db.set_points(uid, current + points)

        # Notify channel
        channel = ticket_info.get("embed_msg").channel
        await channel.send(f"Helpers have been rewarded for **{category}** ticket!")

    # ---------- /points ----------
    @commands.slash_command(name="points", description="Check your points or another user's points")
    async def points(self, ctx: discord.ApplicationContext, user: discord.Option(discord.User, "Select a user", required=False)):
        target = user or ctx.user
        pts = await db.get_points(target.id)
        embed = discord.Embed(
            title=f"Points for {target.display_name}",
            description=f"**{pts} points**",
            color=0x00FFAA
        )
        await ctx.respond(embed=embed)

    # ---------- /leaderboard ----------
    @commands.slash_command(name="leaderboard", description="Show points leaderboard")
    async def leaderboard(self, ctx: discord.ApplicationContext, page: discord.Option(int, "Page number", required=False, default=1)):
        rows = await db.get_leaderboard()
        if not rows:
            await ctx.respond("Leaderboard is empty.")
            return
        embed = await create_leaderboard_embed(page=page, per_page=10)
        await ctx.respond(embed=embed)

    # ---------- /points_reset (admin only) ----------
    @commands.slash_command(name="points_reset", description="Reset all points (Admin only)")
    async def points_reset(self, ctx: discord.ApplicationContext):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.", ephemeral=True)
            return
        await db.reset_points()
        await ctx.respond("Leaderboard has been reset!")

# ---------- SETUP ----------
def setup(bot):
    bot.add_cog(PointsModule(bot))