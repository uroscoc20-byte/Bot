# audit_log.py
import discord
from discord.ext import commands
from datetime import datetime
from database import db

def build_command_path_and_args(data: dict) -> tuple[str, str]:
    """
    Build a human-readable path (/group subcmd ...) and a simple args string.
    Handles subcommand groups and subcommands (type 2 and 1).
    """
    if not data:
        return ("unknown", "no-args")

    name = data.get("name", "unknown")
    options = data.get("options") or []

    path_parts = [name]
    args_parts = []

    def walk(opts):
        for o in opts or []:
            t = o.get("type")
            n = o.get("name")
            if t in (1, 2):  # SUB_COMMAND or SUB_COMMAND_GROUP
                if n:
                    path_parts.append(n)
                walk(o.get("options"))
            else:
                if n is not None:
                    v = o.get("value")
                    args_parts.append(f"{n}={v}")

    walk(options)

    path = " ".join(path_parts) if path_parts else name
    args = " ".join(args_parts) if args_parts else "no-args"
    return (path, args)

class AuditLogModule(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_audit_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        cfg = await db.load_config("audit_channel")
        channel_id = (cfg or {}).get("id")
        if not channel_id:
            return None
        ch = guild.get_channel(int(channel_id))
        return ch if isinstance(ch, discord.TextChannel) else None

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """
        Log ALL application command uses as soon as Discord delivers the interaction.
        Posts a plain message so it works even without Embed Links permission.
        """
        try:
            if interaction.type != discord.InteractionType.application_command:
                return
            if not interaction.guild:
                return

            audit_ch = await self._get_audit_channel(interaction.guild)
            if not audit_ch:
                return

            data = interaction.data or {}
            cmd_path, args = build_command_path_and_args(data)

            user = interaction.user
            channel = interaction.channel
            utc_now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

            # Plain text log line for maximum reliability
            msg = (
                f"🛡️ [{utc_now}] /{cmd_path} by {user.mention} (ID {user.id}) "
                f"in {channel.mention if hasattr(channel, 'mention') else 'DM/Unknown'} "
                f"args: {args}"
            )
            await audit_ch.send(msg)
        except Exception:
            # Never break the user flow due to audit failures
            pass

def setup(bot: commands.Bot):