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
        """Load custom commands from DB into memory"""
        rows = await db.get_custom_commands()
        # Normalize to dict for quick lookup
        self.custom_commands = {r["name"]: {"text": r["text"], "image": r["image"]} for r in rows}

    @commands.Cog.listener()
    async def on_ready(self):
        await self.load_commands()
        # Register slash commands dynamically for each custom command
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

    # Text prefix handler (e.g., !proof)
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        prefix = await db.get_prefix()
        content = message.content.strip()
        if not content.startswith(prefix):
            return
        name = content[len(prefix):].split()[0].lower()
        data = self.custom_commands.get(name)
        if not data:
            return
        # Public by default
        text = data.get("text") or ""
        image = data.get("image")
        if image:
            embed = discord.Embed(description=text or name, color=0xFFD700)
            embed.set_image(url=image)
            await message.channel.send(embed=embed)
        else:
            await message.channel.send(text)

    # Add /remove/list commands for admins
    @commands.slash_command(name="custom_add", description="Add a custom command (Admin only)")
    async def custom_add(
        self, ctx: discord.ApplicationContext,
        name: discord.Option(str, "Command name"),
        text: discord.Option(str, "Text to display"),
        image: discord.Option(str, "Optional image URL", required=False)
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You are not allowed to run this.", ephemeral=True)
            return
        await db.add_custom_command(name, text, image)
        self.custom_commands[name] = {"text": text, "image": image}
        await ctx.respond(f"✅ Custom command `{name}` added.")
        if not self.bot.tree.get_command(name):
            self.bot.tree.add_command(
                discord.app_commands.Command(
                    name=name,
                    description=f"Custom command: {name}",
                    callback=self.dynamic_command
                )
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

    @commands.slash_command(name="info", description="Show bot commands and info")
    async def info(self, ctx: discord.ApplicationContext):
        prefix = await db.get_prefix()
        embed = discord.Embed(title="✨ Bot Commands & Help", description="Welcome! Here are all the commands you can use.", color=0x5865F2)
        embed.add_field(
            name="🎫 Ticket Commands",
            value=(
                f"`/panel` — Post ticket panel (admin/staff)\n"
                f"`{prefix}create` — Create ticket panel (admin)\n"
                f"`{prefix}delete <message_id>` — Delete ticket panel (admin)\n"
            ),
            inline=False,
        )
        embed.add_field(
            name="📊 Points & Leaderboard",
            value=(
                f"`/leaderboard [page]` — View top helpers\n"
                f"`/points [user]` — See someone's points\n"
                f"`/points_add @user amount` — Add points (admin)\n"
                f"`/points_remove @user amount` — Remove points (admin)\n"
                f"`/points_set @user amount` — Set points (admin)\n"
                f"`/points_remove_user @user` — Remove user from leaderboard (admin)\n"
                f"`/points_reset` — Reset all leaderboard (admin)\n"
            ),
            inline=False,
        )
        services = "\n".join([f"- {name} — {pts} pts" for name, pts in DEFAULT_POINT_VALUES.items()])
        embed.add_field(name="🎮 Service Types & Points", value=services, inline=False)
        embed.add_field(
            name="📜 Guidelines",
            value="See your guidelines channel for ticket rules.",
            inline=False,
        )
        await ctx.respond(embed=embed)

# ---------- SETUP ----------
def setup(bot):
    bot.add_cog(CustomCommandsModule(bot))