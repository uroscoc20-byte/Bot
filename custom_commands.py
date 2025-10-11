# custom_commands.py
import discord
from discord.ext import commands
from database import db

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
        await self.bot.tree.sync()

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
        # Register dynamically
        if not self.bot.tree.get_command(name):
            self.bot.tree.add_command(
                discord.app_commands.Command(
                    name=name,
                    description=f"Custom command: {name}",
                    callback=self.dynamic_command
                )
            )
        await self.bot.tree.sync()

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
        # Remove from bot tree
        if self.bot.tree.get_command(name):
            self.bot.tree.remove_command(name)
        await self.bot.tree.sync()

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

# ---------- SETUP ----------
async def setup(bot):
    await bot.add_cog(CustomCommandsModule(bot))