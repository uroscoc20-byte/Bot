# audit_log.py
import discord
from discord.ext import commands
from database import db
from datetime import datetime

def _flatten_options_from_interaction(interaction: discord.Interaction) -> list[str]:
    try:
        data = getattr(interaction, "data", None) or {}
        def walk(opts):
            items = []
            for o in opts or []:
                if o.get("options"):
                    items.extend(walk(o.get("options")))
                elif "value" in o:
                    items.append(f"{o.get('name')}={o.get('value')}")
            return items
        return walk(data.get("options", []))
    except Exception:
        return []

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

    @commands.Cog.listener()
    async def on_application_command_completion(self, ctx: discord.ApplicationContext):
        # Fires for ALL slash commands that finish successfully (including /panel, /points_add, etc.)
        try:
            guild = ctx.guild
            if not guild:
                return
            ch = await self._get_audit_channel(guild)
            if not ch:
                return

            cmd_name = ctx.command.qualified_name if ctx.command else "unknown"

            # Collect args from ctx or interaction
            opts = []
            if hasattr(ctx, "options") and ctx.options:
                try:
                    for k, v in ctx.options.items():
                        opts.append(f"{k}={v}")
                except Exception:
                    pass
            if not opts and hasattr(ctx, "interaction"):
                opts = _flatten_options_from_interaction(ctx.interaction)

            opts_str = ", ".join(opts) if opts else "no-args"

            embed = discord.Embed(
                title="🛡️ Command Used",
                description=f"`/{cmd_name}`",
                color=0x2F3136,
                timestamp=datetime.utcnow(),
            )
            embed.add_field(name="User", value=f"{ctx.user.mention} (`{ctx.user.id}`)", inline=False)
            embed.add_field(name="Channel", value=f"{ctx.channel.mention} (`{ctx.channel.id}`)", inline=False)
            embed.add_field(name="Args", value=opts_str, inline=False)
            await ch.send(embed=embed)
        except Exception:
            # Never break user flow due to audit issues
            pass

def setup(bot):
    bot.add_cog(AuditLogModule(bot))