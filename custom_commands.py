# custom_commands.py
import re
import discord
from discord.ext import commands
from database import db

SAFE_NAME_RE = re.compile(r"[^a-z0-9_-]")

def sanitize_command_name(name: str) -> str:
    s = (name or "").strip().lower().replace(" ", "_")
    s = SAFE_NAME_RE.sub("", s)[:32]
    return s or "cmd"

class CustomCommandsModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Map sanitized_name -> {"text": str, "image": str|None, "display": original}
        self.custom_commands: dict[str, dict] = {}

    async def _register_for_guild(self, guild: discord.Guild, name: str):
        if not guild:
            return
        if self.bot.tree.get_command(name, guild=guild):
            return
        self.bot.tree.add_command(
            discord.app_commands.Command(
                name=name,
                description=f"Custom command: {name}",
                callback=self._dynamic_command_callback(name),
            ),
            guild=guild,
        )
        try:
            await self.bot.tree.sync(guild=guild)
        except Exception:
            pass

    def _dynamic_command_callback(self, sanitized_name: str):
        async def cb(interaction: discord.Interaction):
            data = self.custom_commands.get(sanitized_name)
            if not data:
                await interaction.response.send_message("Command not found.", ephemeral=True)
                return
            embed = discord.Embed(title=data.get("display") or sanitized_name, description=data["text"], color=0xFFD700)
            if data.get("image"):
                embed.set_image(url=data["image"])
            await interaction.response.send_message(embed=embed)
        return cb

    async def load_commands(self):
        rows = await db.get_custom_commands()
        # Normalize into sanitized map
        self.custom_commands.clear()
        for r in rows:
            raw_name = r["name"]
            sname = sanitize_command_name(raw_name)
            self.custom_commands[sname] = {"text": r["text"], "image": r["image"], "display": raw_name}

    @commands.Cog.listener()
    async def on_ready(self):
        await self.load_commands()
        # Register for all guilds for instant availability
        for guild in self.bot.guilds:
            for sname in self.custom_commands.keys():
                await self._register_for_guild(guild, sname)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        # Register existing commands in newly joined guilds
        for sname in self.custom_commands.keys():
            await self._register_for_guild(guild, sname)

    @commands.slash_command(name="custom_add", description="Add a custom command (Admin only)")
    async def custom_add(
        self,
        ctx: discord.ApplicationContext,
        name: discord.Option(str, "Command name (letters, numbers, - or _)"),
        text: discord.Option(str, "Text to display"),
        image: discord.Option(str, "Optional image URL", required=False),
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You are not allowed to run this.", ephemeral=True)
            return

        sname = sanitize_command_name(name)
        if not sname:
            await ctx.respond("Invalid command name. Use letters, numbers, '-' or '_'.", ephemeral=True)
            return

        # Persist to DB
        await db.add_custom_command(sname, text, image)
        # Update in-memory
        self.custom_commands[sname] = {"text": text, "image": image, "display": name}

        # Register in current guild instantly
        await self._register_for_guild(ctx.guild, sname)

        await ctx.respond(f"✅ Custom command `/{sname}` added.", ephemeral=True)

    @commands.slash_command(name="custom_remove", description="Remove a custom command (Admin only)")
    async def custom_remove(self, ctx: discord.ApplicationContext, name: discord.Option(str, "Command name")):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You are not allowed to run this.", ephemeral=True)
            return

        sname = sanitize_command_name(name)
        if sname not in self.custom_commands:
            await ctx.respond(f"⚠ Custom command `/{sname}` does not exist.", ephemeral=True)
            return

        # Remove from cache and DB
        self.custom_commands.pop(sname, None)
        await db.remove_custom_command(sname)

        # Remove from this guild's tree
        if self.bot.tree.get_command(sname, guild=ctx.guild):
            self.bot.tree.remove_command(sname, guild=ctx.guild)
            try:
                await self.bot.tree.sync(guild=ctx.guild)
            except Exception:
                pass

        await ctx.respond(f"✅ Custom command `/{sname}` removed.", ephemeral=True)

    @commands.slash_command(name="custom_list", description="List all custom commands")
    async def custom_list(self, ctx: discord.ApplicationContext, page: discord.Option(int, "Page", required=False, default=1)):
        cmds = sorted(self.custom_commands.items(), key=lambda kv: kv[0])
        if not cmds:
            await ctx.respond("No custom commands configured.")
            return

        per_page = 15
        total_pages = max(1, (len(cmds) + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        end = start + per_page
        slice_cmds = cmds[start:end]

        lines = []
        for sname, data in slice_cmds:
            display = data.get("display") or sname
            lines.append(f"/{sname} — {display}")

        embed = discord.Embed(title="Custom Commands", color=0xAA00FF, description="\n".join(lines))
        embed.set_footer(text=f"Page {page}/{total_pages}")
        await ctx.respond(embed=embed)

    # Backward-compatible dynamic handler if commands were added before this refactor:
    def _legacy_dynamic_callback(self, interaction: discord.Interaction):
        sname = (interaction.data or {}).get("name")
        data = self.custom_commands.get(sname)
        return data

def setup(bot):
    bot.add_cog(CustomCommandsModule(bot))