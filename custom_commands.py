# custom_commands.py
import discord
from discord.ext import commands
from database import db
from tickets import DEFAULT_POINT_VALUES

class CustomCommandsModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.custom_commands = {}  # cache in memory

    async def load_commands(self):
        rows = await db.get_custom_commands()
        self.custom_commands = {r["name"]: {"text": r["text"], "image": r["image"]} for r in rows}

    @commands.Cog.listener()
    async def on_ready(self):
        await self.load_commands()
        for name in self.custom_commands:
            if not self.bot.tree.get_command(name):
                self.bot.tree.add_command(
                    discord.app_commands.Command(
                        name=name,
                        description=f"Custom command: {name}",
                        callback=self.dynamic_command,
                    )
                )
        try:
            await self.bot.tree.sync()
        except Exception:
            pass

    async def dynamic_command(self, interaction: discord.Interaction):
        command_name = interaction.data.get("name")
        data = self.custom_commands.get(command_name)
        if not data:
            await interaction.response.send_message("Command not found.", ephemeral=True)
            return
        embed = discord.Embed(title=command_name, description=data["text"], color=0xFFD700)
        if data.get("image"):
            embed.set_image(url=data["image"])
        await interaction.response.send_message(embed=embed)

    # Admin manage custom commands
    @commands.slash_command(name="custom_add", description="Add a custom command (Admin only)")
    async def custom_add(
        self,
        ctx: discord.ApplicationContext,
        name: discord.Option(str, "Command name"),
        text: discord.Option(str, "Text to display"),
        image: discord.Option(str, "Optional image URL", required=False),
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You are not allowed to run this.", ephemeral=True)
            return
        await db.add_custom_command(name, text, image)
        self.custom_commands[name] = {"text": text, "image": image}
        await ctx.respond(f"✅ Custom command `{name}` added.")
        if not self.bot.tree.get_command(name):
            self.bot.tree.add_command(
                discord.app_commands.Command(name=name, description=f"Custom command: {name}", callback=self.dynamic_command)
            )
        try:
            await self.bot.tree.sync()
        except Exception:
            pass

    @commands.slash_command(name="custom_remove", description="Remove a custom command (Admin only)")
    async def custom_remove(self, ctx: discord.ApplicationContext, name: discord.Option(str, "Command name")):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You are not allowed to run this.", ephemeral=True)
            return
        if name not in self.custom_commands:
            await ctx.respond(f"⚠ Custom command `{name}` does not exist.", ephemeral=True)
            return
        self.custom_commands.pop(name)
        await db.remove_custom_command(name)
        await ctx.respond(f"✅ Custom command `{name}` removed.")
        if self.bot.tree.get_command(name):
            self.bot.tree.remove_command(name)
        try:
            await self.bot.tree.sync()
        except Exception:
            pass

    @commands.slash_command(name="custom_list", description="List all custom commands")
    async def custom_list(self, ctx: discord.ApplicationContext):
        rows = await db.get_custom_commands()
        if not rows:
            await ctx.respond("No custom commands configured.")
            return
        embed = discord.Embed(title="Custom Commands", color=0xAA00FF)
        for cmd in rows:
            img_text = cmd.get("image") or "No image"
            embed.add_field(name=cmd["name"], value=f"Text: {cmd['text']}\nImage: {img_text}", inline=False)
        await ctx.respond(embed=embed)

    # ---------- /info ----------
    @commands.slash_command(name="info", description="Show bot commands and info")
    async def info(self, ctx: discord.ApplicationContext):
        embed = discord.Embed(
            title="✨ Bot Commands & Help",
            description="Welcome! Here are all the commands you can use.",
            color=0x5865F2,
        )
        embed.add_field(
            name="🎫 Ticket Commands",
            value="`/panel` — Post ticket panel (admin/staff)",
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
            ),
            inline=False,
        )
        services = "\n".join([f"- {name} — {pts} pts" for name, pts in DEFAULT_POINT_VALUES.items()])
        embed.add_field(name="🎮 Service Types & Points", value=services, inline=False)
        embed.add_field(
            name="🧰 Utility",
            value="`/talk` — Send a message/embed (admin)",
            inline=False,
        )
        embed.add_field(
            name="📜 Guidelines",
            value="See your guidelines channel for ticket rules.",
            inline=False,
        )
        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(CustomCommandsModule(bot))