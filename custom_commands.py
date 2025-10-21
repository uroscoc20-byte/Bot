# custom_commands.py
import discord
from discord.ext import commands
from database import db
from tickets import DEFAULT_POINT_VALUES

class CustomCommandsModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.custom_commands = {}

    async def load_commands(self):
        # Legacy support only; dynamic slash custom commands are disabled.
        self.custom_commands = {}

    @commands.Cog.listener()
    async def on_ready(self):
        await self.load_commands()

    # Dynamic slash custom commands are disabled.

    @commands.slash_command(name="custom_add", description="Add a custom command (Admin only)")
    async def custom_add(
        self,
        ctx: discord.ApplicationContext,
        name: discord.Option(str, "Command name"),
        text: discord.Option(str, "Text to display"),
        image: discord.Option(str, "Optional image URL", required=False),
    ):
        await ctx.respond(
            "Custom command creation is disabled. Use `/custom_text_edit` to configure `!proof`, `!rrules`, `!hrules`.",
            ephemeral=True,
        )

    @commands.slash_command(name="custom_remove", description="Remove a custom command (Admin only)")
    async def custom_remove(self, ctx: discord.ApplicationContext, name: discord.Option(str, "Command name")):
        await ctx.respond(
            "Custom command removal is disabled. Only `!proof`, `!rrules`, `!hrules` are supported via `/custom_text_edit`.",
            ephemeral=True,
        )

    @commands.slash_command(name="custom_list", description="List all custom commands")
    async def custom_list(self, ctx: discord.ApplicationContext):
        embed = discord.Embed(title="Custom Commands", color=0xAA00FF)
        embed.description = "`!proof`, `!rrules`, `!hrules`\nEdit with `/custom_text_edit`."
        await ctx.respond(embed=embed)

    @commands.slash_command(name="info", description="Show bot commands and info")
    async def info(self, ctx: discord.ApplicationContext):
        embed = discord.Embed(
            title="✨ Bot Commands & Help",
            description="All available commands grouped by feature.",
            color=0x5865F2,
        )
        embed.add_field(
            name="🎫 Ticket Commands",
            value=(
                "`/panel` — Post ticket panel (admin/staff)\n"
                "`/verification_panel` — Post verification panel (admin/staff)\n"
                "`/ticket_kick @user [Also remove channel access?]` — Remove from embed, optional channel\n"
                "`/setup_ticket_category` — Set parent category for tickets (admin)"
            ),
            inline=False,
        )
        embed.add_field(
            name="📊 Points & Leaderboard",
            value=(
                "`/leaderboard [page]` — View top helpers\n"
                "`/points [user]` — See someone's points\n"
                "`/points_add @user amount` — Add points (admin)\n"
                "`/points_remove @user amount` — Remove points (admin)\n"
                "`/points_set @user amount` — Set points (admin)\n"
                "`/points_remove_user @user` — Remove user from leaderboard (admin)\n"
                "`/points_reset` — Reset all leaderboard (admin)\n"
                "`/give_points [points] [helpers]` — Auto reward from a ticket or manual list (admin)"
            ),
            inline=False,
        )
        services = "\n".join([f"- {name} — {pts} pts" for name, pts in DEFAULT_POINT_VALUES.items()])
        embed.add_field(name="🎮 Service Types & Points", value=services, inline=False)
        embed.add_field(
            name="🧰 Utility",
            value=(
                "`/talk` — Send a message/embed/file to a channel or thread (admin)\n"
                "Hardcoded text commands: `!proof`, `!rrules`, `!hrules`\n"
                "Edit them with: `/custom_text_edit` (Manage Messages/Admin)\n"
                "Set prefix with: `/setup_prefix`"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚙️ Setup",
            value=(
                "`/setup_roles` — Configure roles (admin)\n"
                "`/setup_roles_show` — Show current roles\n"
                "`/setup_transcript` — Set transcript channel\n"
                "`/setup_panel` — Customize panel text/color\n"
                "`/setup_maintenance` — Toggle ticket availability\n"
                "`/setup_category_add|remove|list` — Manage categories\n"
                "`/custom_add|custom_remove|custom_list` — Manage custom slash commands\n"
                "`/setup_audit_channel` — Set audit log channel (admin)"
            ),
            inline=False,
        )
        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(CustomCommandsModule(bot))