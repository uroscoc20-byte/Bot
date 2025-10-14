# custom_simple.py
import re
import discord
from discord.ext import commands
from database import db

SAFE_NAME_RE = re.compile(r"[^a-z0-9_-]")

ALLOWED_TRIGGERS = {"proof", "rrules", "hrules"}


def sanitize(name: str) -> str:
    s = (name or "").strip().lower().replace(" ", "_")
    s = SAFE_NAME_RE.sub("", s)[:32]
    return s


class CustomTextEditModal(discord.ui.Modal):
    def __init__(self, cog: "CustomSimpleModule", trigger_name: str, current_text: str | None, current_image: str | None):
        super().__init__(title=f"Edit !{trigger_name}")
        self.cog = cog
        self.trigger_name = trigger_name
        self.text = discord.ui.InputText(
            label="Response text",
            style=discord.InputTextStyle.long,
            required=True,
            value=(current_text or "")[:4000],
        )
        self.image = discord.ui.InputText(label="Image URL (optional)", required=False, value=current_image or "")
        self.add_item(self.text)
        self.add_item(self.image)

    async def callback(self, interaction: discord.Interaction):
        try:
            trig = sanitize(self.trigger_name)
            if trig not in ALLOWED_TRIGGERS:
                await interaction.response.send_message("This command cannot be edited.", ephemeral=True)
                return
            text = self.text.value
            image = (self.image.value or "").strip() or None

            await db.add_custom_command(trig, text, image)
            await self.cog.load_cache()

            await interaction.response.send_message(f"✅ Updated `!{trig}`.", ephemeral=True)
        except Exception as e:
            try:
                await interaction.response.send_message(f"❌ Failed to update: {e}", ephemeral=True)
            except Exception:
                pass


class CustomSimpleModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cache: dict[str, dict] = {}
        self.defaults = {
            "proof": {
                "text": "Please attach your proof (screenshots, video, or logs).",
                "image": None,
            },
            "rrules": {
                "text": "Runner rules will be posted here.",
                "image": None,
            },
            "hrules": {
                "text": "Helper rules will be posted here.",
                "image": None,
            },
        }

    async def load_cache(self):
        rows = await db.get_custom_commands()
        raw = {r["name"]: {"text": r["text"], "image": r["image"]} for r in rows}
        # Only keep allowed triggers
        self.cache = {k: v for k, v in raw.items() if k in ALLOWED_TRIGGERS}

    def get_content(self, name: str) -> dict | None:
        name = sanitize(name)
        if name not in ALLOWED_TRIGGERS:
            return None
        return self.cache.get(name) or self.defaults.get(name)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.load_cache()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        content = (message.content or "").strip()
        prefix = await db.get_prefix()
        if not content.startswith(prefix):
            return
        trig_raw = content.split()[0][len(prefix):]
        trig = sanitize(trig_raw)
        if not trig or trig not in ALLOWED_TRIGGERS:
            return
        data = self.get_content(trig)
        if not data:
            return
        embed = discord.Embed(title=f"{prefix}{trig}", description=data.get("text") or "", color=0xFFD700)
        if data.get("image"):
            embed.set_image(url=data["image"])
        try:
            await message.channel.send(embed=embed)
        except Exception:
            await message.channel.send(data["text"])  # fallback to plain text

    @commands.slash_command(name="custom_text_edit", description="Edit !proof / !rrules / !hrules content")
    async def custom_text_edit(
        self,
        ctx: discord.ApplicationContext,
        name: discord.Option(str, "Which command", choices=["proof", "rrules", "hrules"]),
    ):
        if not ctx.user.guild_permissions.manage_messages and not ctx.user.guild_permissions.administrator:
            await ctx.respond("You need Manage Messages or Admin to edit.", ephemeral=True)
            return
        current = self.cache.get(name) or self.defaults.get(name)
        await ctx.interaction.response.send_modal(
            CustomTextEditModal(self, name, (current or {}).get("text"), (current or {}).get("image"))
        )

    @commands.slash_command(name="custom_edit", description="Edit !proof / !rrules / !hrules content")
    async def custom_edit(
        self,
        ctx: discord.ApplicationContext,
        name: discord.Option(str, "Which command", choices=["proof", "rrules", "hrules"]),
    ):
        # alias to custom_text_edit
        await self.custom_text_edit.callback(self, ctx, name)  # type: ignore

    @commands.slash_command(name="proof", description="Send the configured proof message")
    async def proof_cmd(self, ctx: discord.ApplicationContext):
        data = self.get_content("proof")
        if not data:
            await ctx.respond("Not configured.", ephemeral=True)
            return
        embed = discord.Embed(title="!proof", description=data.get("text") or "", color=0xFFD700)
        if data.get("image"):
            embed.set_image(url=data["image"])
        await ctx.respond(embed=embed)

    @commands.slash_command(name="rrules", description="Send the configured runner rules")
    async def rrules_cmd(self, ctx: discord.ApplicationContext):
        data = self.get_content("rrules")
        if not data:
            await ctx.respond("Not configured.", ephemeral=True)
            return
        embed = discord.Embed(title="!rrules", description=data.get("text") or "", color=0xFFD700)
        if data.get("image"):
            embed.set_image(url=data["image"])
        await ctx.respond(embed=embed)

    @commands.slash_command(name="hrules", description="Send the configured helper rules")
    async def hrules_cmd(self, ctx: discord.ApplicationContext):
        data = self.get_content("hrules")
        if not data:
            await ctx.respond("Not configured.", ephemeral=True)
            return
        embed = discord.Embed(title="!hrules", description=data.get("text") or "", color=0xFFD700)
        if data.get("image"):
            embed.set_image(url=data["image"])
        await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(CustomSimpleModule(bot))