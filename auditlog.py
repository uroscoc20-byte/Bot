# audit_log.py
import discord
from discord.ext import commands
from collections import deque
from datetime import datetime
from database import db

def _flatten_options(options) -> list[str]:
    """
    Recursively flatten interaction 'options' (handles subcommands/groups).
    Produces tokens like: group subcmd key=value ...
    """
    if not options:
        return []
    tokens: list[str] = []
    for opt in options:
        opt_type = opt.get("type")
        name = opt.get("name")
        # 1 = SUB_COMMAND, 2 = SUB_COMMAND_GROUP
        if opt_type in (1, 2):
            if name:
                tokens.append(str(name))
            tokens.extend(_flatten_options(opt.get("options")))
        else:
            if name is not None:
                value = opt.get("value")
                tokens.append(f"{name}={value}")
    return tokens

class AuditLogModule(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._recent_interaction_ids: deque[int] = deque(maxlen=512)

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
        Logs ALL slash commands as soon as Discord delivers the interaction
        (works for /panel, /points_add, etc., regardless of success).
        """
        try:
            if interaction.type != discord.InteractionType.application_command:
                return
            if not interaction.guild:
                return

            if interaction.id in self._recent_interaction_ids:
                return
            self._recent_interaction_ids.append(interaction.id)

            ch = await self._get_audit_channel(interaction.guild)
            if not ch:
                return

            data = interaction.data or {}
            cmd_name = data.get("name", "unknown")
            tokens = _flatten_options(data.get("options"))
            args_str = " ".join(tokens) if tokens else "no-args"

            user = interaction.user
            channel = interaction.channel
            embed = discord.Embed(
                title="🛡️ Command Used",
                description=f"`/{cmd_name}`",
                color=0x2F3136,
                timestamp=datetime.utcnow(),
            )
            embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=False)
            if isinstance(channel, (discord.TextChannel, discord.Thread)):
                embed.add_field(name="Channel", value=f"{channel.mention} (`{channel.id}`)", inline=False)
            else:
                embed.add_field(name="Channel", value="DM or unknown", inline=False)
            embed.add_field(name="Args", value=args_str, inline=False)

            path_tokens = [t for t in tokens if "=" not in t]
            if path_tokens:
                embed.set_footer(text=f"path: {cmd_name} {' '.join(path_tokens)}")

            await ch.send(embed=embed)
        except Exception:
            pass

def setup(bot: commands.Bot):
    bot.add_cog(AuditLogModule(bot))