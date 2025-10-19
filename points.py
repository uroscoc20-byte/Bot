import discord
from discord.ext import commands
from leaderboard import create_leaderboard_embed, LeaderboardView
from database import db

ACCENT = 0x5865F2
LB_PER_PAGE = 20

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
        per_page = LB_PER_PAGE
        total_pages = max(1, (len(rows) + per_page - 1) // per_page)
        if not rows:
            await ctx.respond("Leaderboard is empty.")
            return
        embed = await create_leaderboard_embed(page=page, per_page=per_page)
        view = LeaderboardView(page, total_pages, per_page)
        await ctx.respond(embed=embed, view=view)

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

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        # Handle leaderboard pagination via custom_id so buttons keep working indefinitely
        try:
            if interaction.type != discord.InteractionType.component:
                return
            data = getattr(interaction, "data", None) or {}
            custom_id = data.get("custom_id")
            if custom_id not in {"lb_prev", "lb_next"}:
                return

            message = interaction.message
            if not message or not message.embeds:
                await interaction.response.defer()
                return

            # Parse current page from footer like "Page X/Y"
            footer_text = (message.embeds[0].footer.text or "").strip() if message.embeds[0].footer else ""
            current_page = 1
            if footer_text.lower().startswith("page") and "/" in footer_text:
                try:
                    left = footer_text.split()[1]  # "X/Y"
                    current_page = int(left.split("/")[0])
                except Exception:
                    current_page = 1

            rows = await db.get_leaderboard()
            per_page = LB_PER_PAGE
            total_pages = max(1, (len(rows) + per_page - 1) // per_page)

            if custom_id == "lb_prev":
                new_page = max(1, current_page - 1)
            else:
                new_page = min(total_pages, current_page + 1)

            if new_page == current_page:
                await interaction.response.defer()
                return

            embed = await create_leaderboard_embed(page=new_page, per_page=per_page)
            # Replace the view to update disabled states while keeping persistent custom_ids
            view = LeaderboardView(new_page, total_pages, per_page)
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception:
            # Best-effort safety: don't break other interactions
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer()
            except Exception:
                pass

def setup(bot):
    bot.add_cog(PointsModule(bot))