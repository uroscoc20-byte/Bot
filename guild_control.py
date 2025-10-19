import discord
from discord.ext import commands
from database import db


HOME_GUILD_KEY = "home_guild"


class GuildControl(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_home_guild_id(self) -> int | None:
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
        await ctx.respond(f"✅ Set home guild to: {ctx.guild.name} ({ctx.guild.id}). I will leave other servers.", ephemeral=True)

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

    @commands.Cog.listener()
    async def on_ready(self):
        # Enforce home guild on startup
        home_id = await self._get_home_guild_id()
        if not home_id:
            return
        for g in list(self.bot.guilds):
            if g.id != home_id:
                try:
                    await g.leave()
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        # Auto-leave any newly joined guild if not the home one
        home_id = await self._get_home_guild_id()
        if home_id and guild.id != home_id:
            try:
                await guild.leave()
            except Exception:
                pass


def setup(bot: commands.Bot):
    bot.add_cog(GuildControl(bot))


