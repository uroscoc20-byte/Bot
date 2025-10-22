import discord
from discord.ext import commands
from collections import deque
from datetime import datetime
from database import db


def _flatten_options(options) -> list[str]:
    """Recursively extract command path and arguments from Discord options."""
    if not options:
        return []
    tokens = []
    for opt in options:
        t = opt.get("type")
        n = opt.get("name")
        if t in (1, 2):  # Subcommand or group
            if n:
                tokens.append(str(n))
            tokens.extend(_flatten_options(opt.get("options")))
        else:
            if n is not None:
                v = opt.get("value")
                tokens.append(f"{n}={v}")
    return tokens


def _build_path_and_args(data: dict) -> tuple[str, str]:
    """Extracts the full slash command path and arguments."""
    if not data:
        return ("unknown", "no-args")
    name = data.get("name", "unknown")
    tokens = _flatten_options(data.get("options") or [])
    path_tokens = [name] + [t for t in tokens if "=" not in t]
    args_tokens = [t for t in tokens if "=" in t]
    return (" ".join(path_tokens), " ".join(args_tokens) if args_tokens else "no-args")


class AuditLog(commands.Cog):
    """Logs slash commands, prefix commands, and interactive events like buttons/modals."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._recent = deque(maxlen=1024)

    # ------------------------- Helper -------------------------

    async def _get_audit_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        """Fetches the configured audit log channel from the database."""
        try:
            cfg = await db.load_config("audit_channel")
            ch_id = (cfg or {}).get("id")
            if not ch_id:
                print(f"[AuditLog] ⚠️ No audit channel configured for guild '{guild.name}'.")
                return None

            ch = guild.get_channel(int(ch_id))
            if not ch:
                print(f"[AuditLog] ⚠️ Channel {ch_id} not found in guild '{guild.name}'.")
                return None

            if not ch.permissions_for(guild.me).send_messages:
                print(f"[AuditLog] ⚠️ Missing permissions to send in '{ch.name}' ({ch.id}).")
                return None

            return ch
        except Exception as e:
            print(f"[AuditLog] ⚠️ Error loading audit channel: {e}")
            return None

    # ------------------------- Listeners -------------------------

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Logs all slash commands, buttons, dropdowns, and modals."""
        if not interaction.guild or interaction.id in self._recent:
            return
        self._recent.append(interaction.id)

        try:
            ch = await self._get_audit_channel(interaction.guild)
            if not ch:
                return

            utc_now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            user = f"{interaction.user.mention} (`{interaction.user.id}`)"
            itype = str(interaction.type).split(".")[-1]

            if interaction.type == discord.InteractionType.application_command:
                data = interaction.data or {}
                path, args = _build_path_and_args(data)
                msg = f"🧭 **/{path}** by {user} | Args: `{args}`"
            elif interaction.type == discord.InteractionType.component:
                msg = f"🔘 **Button/Menu Interaction** by {user}"
            elif interaction.type == discord.InteractionType.modal_submit:
                msg = f"📝 **Modal Submitted** by {user}"
            else:
                msg = f"⚙️ **Other Interaction ({itype})** by {user}"

            location = (
                interaction.channel.mention
                if getattr(interaction, "channel", None)
                else "DM or Unknown"
            )

            await ch.send(f"🛡️ **[{utc_now}]** {msg} in {location}")

        except Exception as e:
            print(f"[AuditLog] ⚠️ Error logging interaction: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Logs traditional prefix-based commands like !help."""
        if message.author.bot or not message.guild:
            return

        try:
            prefix = await db.get_prefix()
            if not message.content.startswith(prefix):
                return

            ch = await self._get_audit_channel(message.guild)
            if not ch:
                return

            utc_now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            parts = message.content.split()
            trigger = parts[0][len(prefix):] if parts else ""

            await ch.send(
                f"🛡️ **[{utc_now}]** `{prefix}{trigger}` by "
                f"{message.author.mention} in {message.channel.mention} (`{message.author.id}`)"
            )
        except Exception as e:
            print(f"[AuditLog] ⚠️ Error logging message: {e}")

# ------------------------- Setup -------------------------

def setup(bot: commands.Bot):
    bot.add_cog(AuditLog(bot))
