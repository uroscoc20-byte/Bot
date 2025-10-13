# audit_log.py
import discord
from discord.ext import commands
from collections import deque
from datetime import datetime
from database import db

def _flatten_options(options) -> list[str]:
    if not options:
        return []
    tokens: list[str] = []
    for opt in options:
        t = opt.get("type")
        n = opt.get("name")
        if t in (1, 2):  # subcommand / subcommand group
            if n:
                tokens.append(str(n))
            tokens.extend(_flatten_options(opt.get("options")))
        else:
            if n is not None:
                v = opt.get("value")
                tokens.append(f"{n}={v}")
    return tokens

def _build_path_and_args(data: dict) -> tuple[str, str]:
    if not data:
        return ("unknown", "no-args")
    name = data.get("name", "unknown")
    tokens = _flatten_options(data.get("options") or [])
    path_tokens = [name] + [t for t in tokens if "=" not in t]
    args_tokens = [t for t in tokens if "=" in t]
    return (" ".join(path_tokens), " ".join(args_tokens) if args_tokens else "no-args")

class AuditLogModule(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._recent: deque[int] = deque(maxlen=1024)

    async def _get_audit_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        cfg = await db.load_config("audit_channel")
        channel_id = (cfg or {}).get("id")
        if not channel_id:
            return None
        ch = guild.get_channel(int(channel_id))
        return ch if isinstance(ch, discord.TextChannel) else None

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        # Log ALL slash commands
        try:
            if interaction.type != discord.InteractionType.application_command:
                return
            if not interaction.guild:
                return
            if interaction.id in self._recent:
                return
            self._recent.append(interaction.id)

            data = interaction.data or {}
            path, args = _build_path_and_args(data)
            target = await self._get_audit_channel(interaction.guild) or interaction.channel
            if not target:
                return

            utc_now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            ch_label = target.mention if hasattr(target, "mention") else "DM/Unknown"
            msg = f"🛡️ [{utc_now}] /{path} by {interaction.user.mention} (ID {interaction.user.id}) in {ch_label} args: {args}"
            try:
                await target.send(msg)
            except discord.Forbidden:
                if interaction.channel and interaction.channel != target:
                    try:
                        await interaction.channel.send(msg)
                    except Exception:
                        pass
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Log simple custom (!) commands usage too
        try:
            if message.author.bot:
                return
            if not message.guild:
                return
            content = message.content.strip()
            if not content.startswith("!"):
                return
            trigger = content.split()[0][1:]  # without '!'
            if not trigger:
                return

            target = await self._get_audit_channel(message.guild) or message.channel
            if not target:
                return

            utc_now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            msg = f"🛡️ [{utc_now}] !{trigger} by {message.author.mention} (ID {message.author.id}) in {message.channel.mention}"
            try:
                await target.send(msg)
            except Exception:
                pass
        except Exception:
            pass

def setup(bot: commands.Bot):
    bot.add_cog(AuditLogModule(bot))