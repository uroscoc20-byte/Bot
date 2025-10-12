# audit_log.py
import discord
from discord.ext import commands
from database import db
from datetime import datetime

class AuditLogModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _get_audit_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        cfg = await db.load_config("audit_channel")
        channel_id = (cfg or {}).get("id")
        if not channel_id:
            return None
        ch = guild.get_channel(int(channel_id))
        return ch if isinstance(ch, discord.TextChannel) else None

    def _format_options(self, data: dict) -> str:
        # Best-effort format of provided options
        try:
            opts = data.get("options") or []
            parts = []
            for opt in opts:
                name = opt.get("name")
                value = opt.get("value")
                parts.append(f"{name}={value}")
            return ", ".join(parts) if parts else "no-args"
        except Exception:
            return "no-args"

    @commands.Cog.listener()
    async def on_application_command(self, ctx: discord.ApplicationContext):
        try:
            guild = ctx.guild
            if not guild:
                return
            ch = await self._get_audit_channel(guild)
            if not ch:
                return
            cmd_name = ctx.command.qualified_name if ctx.command else "unknown"
            data = getattr(ctx, "data", None)
            if not data and hasattr(ctx, "interaction"):
                data = getattr(ctx.interaction, "data", {}) or {}
            opts_str = self._format_options(data or {})
            ts = datetime.utcnow().isoformat(timespec="seconds")
            embed = discord.Embed(
                title="🛡️ Command Used",
                description=f"`/{cmd_name}`",
                color=0x2F3136,
                timestamp=datetime.utcnow(),
            )
            embed.add_field(name="User", value=f"{ctx.user.mention} (`{ctx.user.id}`)", inline=False)
            embed.add_field(name="Channel", value=f"{ctx.channel.mention} (`{ctx.channel.id}`)", inline=False)
            embed.add_field(name="Args", value=opts_str, inline=False)
            embed.set_footer(text=f"UTC {ts}")
            await ch.send(embed=embed)
        except Exception:
            # Avoid breaking user flows due to audit issues
            pass

def setup(bot):
    bot.add_cog(AuditLogModule(bot))