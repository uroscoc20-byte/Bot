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

    # ---------- TEXT COMMANDS (aliases for slash) ----------
    @commands.command(name="leaderboard", aliases=["lb"])
    async def leaderboard_text(self, ctx: commands.Context, page: int = 1):
        rows = await db.get_leaderboard()
        if not rows:
            await ctx.send("Leaderboard is empty.")
            return
        embed = await create_leaderboard_embed(page=page, per_page=10)
        await ctx.send(embed=embed)

    @commands.command(name="mypoints")
    async def mypoints_text(self, ctx: commands.Context):
        pts = await db.get_points(ctx.author.id)
        embed = discord.Embed(title="📊 Your Points", description=f"**{pts} points**", color=0x5865F2)
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name="points")
    async def points_text(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        pts = await db.get_points(target.id)
        embed = discord.Embed(title=f"Points for {target.display_name}", description=f"**{pts} points**", color=0x5865F2)
        await ctx.send(embed=embed)

    @commands.command(name="add")
    @commands.has_permissions(administrator=True)
    async def add_points_text(self, ctx: commands.Context, user: discord.Member, amount: int):
        if amount <= 0:
            await ctx.send("Amount must be positive.")
            return
        current = await db.get_points(user.id)
        await db.set_points(user.id, current + amount)
        await ctx.send(f"✅ Added **{amount}** points to {user.mention}.")

    @commands.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def remove_points_text(self, ctx: commands.Context, user: discord.Member, amount: int):
        if amount <= 0:
            await ctx.send("Amount must be positive.")
            return
        current = await db.get_points(user.id)
        await db.set_points(user.id, max(0, current - amount))
        await ctx.send(f"✅ Removed **{amount}** points from {user.mention}.")

    @commands.command(name="setpoints")
    @commands.has_permissions(administrator=True)
    async def set_points_text(self, ctx: commands.Context, user: discord.Member, amount: int):
        if amount < 0:
            await ctx.send("Amount cannot be negative.")
            return
        await db.set_points(user.id, amount)
        await ctx.send(f"✅ Set {user.mention}'s points to **{amount}**.")

    @commands.command(name="resetpoints")
    @commands.has_permissions(administrator=True)
    async def reset_points_text(self, ctx: commands.Context, user: discord.Member = None):
        if user:
            await db.set_points(user.id, 0)
            await ctx.send(f"✅ Reset points for {user.mention}.")
        else:
            await ctx.send("Provide a user to reset or use `/points_reset` or `!restartleaderboard` to reset all.")

    @commands.command(name="removeuser")
    @commands.has_permissions(administrator=True)
    async def remove_user_text(self, ctx: commands.Context, user: discord.Member):
        await db.delete_user_points(user.id)
        await ctx.send(f"✅ Removed {user.mention} from the leaderboard.")

    @commands.command(name="restartleaderboard")
    @commands.has_permissions(administrator=True)
    async def restart_leaderboard_text(self, ctx: commands.Context):
        await db.reset_points()
        await ctx.send("✅ Leaderboard has been reset.")

    # ---------- /points_reset (admin only) ----------
    @commands.slash_command(name="points_reset", description="Reset all points (Admin only)")
    async def points_reset(self, ctx: discord.ApplicationContext):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.", ephemeral=True)
            return
        await db.reset_points()
        await ctx.respond("Leaderboard has been reset!")

    # ---------- /points_add (admin only) ----------
    @commands.slash_command(name="points_add", description="Add points to a user (Admin only)")
    async def points_add(self, ctx: discord.ApplicationContext, user: discord.Option(discord.User, "User"), amount: discord.Option(int, "Amount")):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.", ephemeral=True)
            return
        if amount <= 0:
            await ctx.respond("Amount must be positive.", ephemeral=True)
            return
        current = await db.get_points(user.id)
        await db.set_points(user.id, current + amount)
        await ctx.respond(f"Added {amount} points to {user.mention}.")

    # ---------- /points_remove (admin only) ----------
    @commands.slash_command(name="points_remove", description="Remove points from a user (Admin only)")
    async def points_remove(self, ctx: discord.ApplicationContext, user: discord.Option(discord.User, "User"), amount: discord.Option(int, "Amount")):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.", ephemeral=True)
            return
        if amount <= 0:
            await ctx.respond("Amount must be positive.", ephemeral=True)
            return
        current = await db.get_points(user.id)
        await db.set_points(user.id, max(0, current - amount))
        await ctx.respond(f"Removed {amount} points from {user.mention}.")

    # ---------- /points_set (admin only) ----------
    @commands.slash_command(name="points_set", description="Set user's points to exact value (Admin only)")
    async def points_set(self, ctx: discord.ApplicationContext, user: discord.Option(discord.User, "User"), amount: discord.Option(int, "Amount")):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.", ephemeral=True)
            return
        if amount < 0:
            await ctx.respond("Amount cannot be negative.", ephemeral=True)
            return
        await db.set_points(user.id, amount)
        await ctx.respond(f"Set {user.mention}'s points to {amount}.")

    # ---------- /points_remove_user (admin only) ----------
    @commands.slash_command(name="points_remove_user", description="Remove a user from leaderboard (Admin only)")
    async def points_remove_user(self, ctx: discord.ApplicationContext, user: discord.Option(discord.User, "User")):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.", ephemeral=True)
            return
        await db.delete_user_points(user.id)
        await ctx.respond(f"Removed {user.mention} from the leaderboard.")

# ---------- SETUP ----------
def setup(bot):
    bot.add_cog(PointsModule(bot))
