import discord
import os
from discord.ext import commands
from database import db


HOME_GUILD_KEY = "home_guild"


class GuildControl(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._forced_leave_ids = self._parse_forced_leave_ids()

    def _parse_forced_leave_ids(self) -> set[int]:
        raw = os.getenv("FORCE_LEAVE_GUILD_IDS", "")
        out: set[int] = set()
        for token in raw.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                out.add(int(token))
            except Exception:
                pass
        # Always auto-leave this specific guild ID as requested
        try:
            out.add(int(1347484410462732308))
        except Exception:
            pass
        return out

    async def _get_home_guild_id(self) -> int | None:
        # Environment override for redeploys
        env_gid = os.getenv("HOME_GUILD_ID")
        if env_gid:
            try:
                return int(env_gid)
            except Exception:
                pass
        data = await db.load_config(HOME_GUILD_KEY)
        try:
            gid = int((data or {}).get("id")) if data and data.get("id") is not None else None
            return gid
        except Exception:
            return None

    async def _set_home_guild_id(self, guild_id: int):
        await db.save_config(HOME_GUILD_KEY, {"id": int(guild_id)})

    @commands.slash_command(name="set_home_guild", description="Set this server as the bot's only allowed server (Admin only)")
    async def set_home_guild(self, ctx: discord.ApplicationContext):
        if not ctx.guild:
            await ctx.respond("Run this in a server.", ephemeral=True)
            return
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You must be an Administrator to run this.", ephemeral=True)
            return
        await self._set_home_guild_id(ctx.guild.id)
        # Immediately enforce: leave all other guilds now
        left = []
        for g in list(self.bot.guilds):
            if g.id != ctx.guild.id:
                try:
                    await g.leave()
                    left.append(f"{g.name} ({g.id})")
                except Exception:
                    pass
        if left:
            await ctx.respond(
                "✅ Set home guild and left other servers:\n" + "\n".join(left),
                ephemeral=True,
            )
        else:
            await ctx.respond(
                f"✅ Set home guild to: {ctx.guild.name} ({ctx.guild.id}). Already only in this server.",
                ephemeral=True,
            )

    @commands.slash_command(name="leave_here", description="Make the bot leave this server (Admin only)")
    async def leave_here(self, ctx: discord.ApplicationContext):
        if not ctx.guild:
            await ctx.respond("This command must be used in a server.", ephemeral=True)
            return
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You must be an Administrator to run this.", ephemeral=True)
            return
        try:
            await ctx.respond("👋 Leaving this server...", ephemeral=True)
        except Exception:
            pass
        try:
            await ctx.guild.leave()
        except Exception as e:
            try:
                await ctx.respond(f"Failed to leave: {e}", ephemeral=True)
            except Exception:
                pass

    @commands.slash_command(name="leave", description="Make the bot leave this server (Admin only)")
    async def leave(self, ctx: discord.ApplicationContext):
        if not ctx.guild:
            await ctx.respond("This command must be used in a server.", ephemeral=True)
            return
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You must be an Administrator to run this.", ephemeral=True)
            return
        try:
            await ctx.respond("👋 Leaving this server...", ephemeral=True)
        except Exception:
            pass
        try:
            await ctx.guild.leave()
        except Exception as e:
            try:
                await ctx.respond(f"Failed to leave: {e}", ephemeral=True)
            except Exception:
                pass

    @commands.slash_command(name="leave_non_home", description="Leave all servers except the configured home guild (Admin only)")
    async def leave_non_home(self, ctx: discord.ApplicationContext):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You must be an Administrator to run this.", ephemeral=True)
            return
        home_id = await self._get_home_guild_id()
        if not home_id:
            await ctx.respond("Home guild not set. Use /set_home_guild in your desired server.", ephemeral=True)
            return
        left = []
        for g in list(self.bot.guilds):
            if g.id != home_id:
                try:
                    await g.leave()
                    left.append(f"{g.name} ({g.id})")
                except Exception:
                    pass
        if left:
            await ctx.respond("✅ Left non-home servers:\n" + "\n".join(left), ephemeral=True)
        else:
            await ctx.respond("Already only in the home server.", ephemeral=True)

    @commands.slash_command(name="leave_guild", description="Leave a server by its ID (Admin only)")
    async def leave_guild(self, ctx: discord.ApplicationContext, guild_id: discord.Option(str, "Server ID to leave")):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You must be an Administrator to run this.", ephemeral=True)
            return
        try:
            gid = int(guild_id)
        except Exception:
            await ctx.respond("Invalid server ID.", ephemeral=True)
            return
        target = next((g for g in self.bot.guilds if g.id == gid), None)
        if not target:
            await ctx.respond("I'm not in that server or ID not found.", ephemeral=True)
            return
        # Respond BEFORE leaving to avoid losing the interaction after exit
        try:
            await ctx.respond(f"Leaving server: {target.name} ({target.id})...", ephemeral=True)
        except Exception:
            pass
        try:
            await target.leave()
        except Exception as e:
            # Try to notify the invoker in DMs if possible
            try:
                await ctx.user.send(f"Failed to leave guild {gid}: {e}")
            except Exception:
                pass
            return
        # Try to DM confirmation after leaving
        try:
            await ctx.user.send(f"✅ Left server: {target.name} ({gid})")
        except Exception:
            pass

    @commands.slash_command(name="list_guilds", description="List servers the bot is currently in (Admin only)")
    async def list_guilds(self, ctx: discord.ApplicationContext):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You must be an Administrator to run this.", ephemeral=True)
            return
        if not self.bot.guilds:
            await ctx.respond("I'm not in any servers.", ephemeral=True)
            return
        lines = [f"- {g.name} ({g.id})" for g in self.bot.guilds]
        await ctx.respond("Current servers:\n" + "\n".join(lines), ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        # Enforce home guild on startup
        home_id = await self._get_home_guild_id()
        if not home_id:
            # Even if home is not set, still enforce forced leave list
            for g in list(self.bot.guilds):
                if g.id in self._forced_leave_ids:
                    try:
                        await g.leave()
                    except Exception:
                        pass
            return
        for g in list(self.bot.guilds):
            if g.id != home_id or g.id in self._forced_leave_ids:
                try:
                    await g.leave()
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        # Auto-leave any newly joined guild if not the home one
        home_id = await self._get_home_guild_id()
        if guild.id in self._forced_leave_ids:
            try:
                await guild.leave()
            except Exception:
                pass
            return
        if home_id and guild.id != home_id:
            try:
                await guild.leave()
            except Exception:
                pass


def setup(bot: commands.Bot):
    bot.add_cog(GuildControl(bot))


