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
        per_page = 10
        total_pages = max(1, (len(rows) + per_page - 1) // per_page)
        if not rows:
            await ctx.respond("Leaderboard is empty.")
            return
        embed = await create_leaderboard_embed(page=page, per_page=per_page)
        view = LeaderboardView(per_page)
        # Initialize button disabled state for the first render
        try:
            view._sync_buttons(page, total_pages)
        except Exception:
            pass
        msg = None
        try:
            msg = await ctx.respond(embed=embed, view=view)
        except Exception:
            # Some impls return no message from respond(); try original_response
            await ctx.respond(embed=embed, view=view)
        # Attempt to record the message for auto-refresh maintenance
        try:
            # For libraries that support retrieving original response
            if hasattr(ctx, "interaction") and hasattr(ctx.interaction, "original_response"):
                try:
                    msg = await ctx.interaction.original_response()
                except Exception:
                    pass
            if msg is not None and hasattr(msg, "id"):
                data = await db.load_config("leaderboard_messages") or []
                # Ensure structure is a list of dicts
                if not isinstance(data, list):
                    data = []
                entry = {"channel_id": getattr(msg.channel, "id", None), "message_id": msg.id}
                if entry["channel_id"] and entry not in data:
                    data.append(entry)
                    await db.save_config("leaderboard_messages", data)
        except Exception:
            # Non-fatal if we can't record
            pass

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