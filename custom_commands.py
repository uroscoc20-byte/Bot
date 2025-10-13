# custom_simple.py
import re
import discord
from discord.ext import commands
from database import db

PREFIX = "!"
SAFE_NAME_RE = re.compile(r"[^a-z0-9_-]")

def sanitize(name: str) -> str:
    s = (name or "").strip().lower().replace(" ", "_")
    s = SAFE_NAME_RE.sub("", s)[:32]
    return s

class CustomSimpleCreateModal(discord.ui.Modal):
    def __init__(self, cog: "CustomSimpleModule"):
        super().__init__(title="Create Custom (!) Command")
        self.cog = cog
        self.trigger = discord.ui.InputText(label="Trigger (without !, e.g. hello)", required=True, max_length=32)
        self.text = discord.ui.InputText(label="Response text", style=discord.InputTextStyle.long, required=True)
        self.image = discord.ui.InputText(label="Image URL (optional)", required=False)
        self.add_item(self.trigger)
        self.add_item(self.text)
        self.add_item(self.image)

    async def callback(self, interaction: discord.Interaction):
        try:
            trig = sanitize(self.trigger.value)
            if not trig:
                await interaction.response.send_message("Invalid trigger. Use letters, numbers, '-' or '_'.", ephemeral=True)
                return
            text = self.text.value
            image = (self.image.value or "").strip() or None

            await db.add_custom_command(trig, text, image)
            self.cog.cache[trig] = {"text": text, "image": image}

            await interaction.response.send_message(f"✅ Custom command `!{trig}` created.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to create command: {e}", ephemeral=True)

class CustomSimpleModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cache: dict[str, dict] = {}

    async def load_cache(self):
        rows = await db.get_custom_commands()
        self.cache = {r["name"]: {"text": r["text"], "image": r["image"]} for r in rows}

    @commands.Cog.listener()
    async def on_ready(self):
        await self.load_cache()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        content = message.content.strip()
        if not content.startswith(PREFIX):
            return
        trig = sanitize(content.split()[0][len(PREFIX):])
        if not trig:
            return
        data = self.cache.get(trig)
        if not data:
            return
        embed = discord.Embed(title=f"{PREFIX}{trig}", description=data["text"], color=0xFFD700)
        if data.get("image"):
            embed.set_image(url=data["image"])
        try:
            await message.channel.send(embed=embed)
        except Exception:
            # fallback to text
            await message.channel.send(data["text"])

    @commands.slash_command(name="custom_simple_create", description="Open modal to create a (!) custom command")
    async def custom_simple_create(self, ctx: discord.ApplicationContext):
        await ctx.interaction.response.send_modal(CustomSimpleCreateModal(self))

    @commands.slash_command(name="custom_simple_list", description="List all (!) custom commands")
    async def custom_simple_list(self, ctx: discord.ApplicationContext, page: discord.Option(int, "Page", required=False, default=1)):
        cmds = sorted(self.cache.items(), key=lambda kv: kv[0])
        if not cmds:
            await ctx.respond("No custom (!) commands configured.")
            return

        per_page = 15
        total_pages = max(1, (len(cmds) + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        lines = [f"`{PREFIX}{name}`" for name, _ in cmds[start:start+per_page]]

        embed = discord.Embed(
            title="✨ Custom (!) Commands",
            description="\n".join(lines),
            color=0xAA00FF
        )
        embed.set_footer(text=f"Page {page}/{total_pages}")
        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(CustomSimpleModule(bot))