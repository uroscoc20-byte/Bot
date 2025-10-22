import discord
from discord.ext import commands

class GuildControl(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.slash_command(name="list_guilds", description="List servers the bot is currently in (Admin only)")
    async def list_guilds(self, ctx: discord.ApplicationContext):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You must be an Administrator.", ephemeral=True)
            return
        if not self.bot.guilds:
            await ctx.respond("I'm not in any servers.", ephemeral=True)
            return
        lines = [f"- {g.name} ({g.id})" for g in self.bot.guilds]
        await ctx.respond("Current servers:\n" + "\n".join(lines), ephemeral=True)

    @commands.slash_command(name="leave", description="Make the bot leave a server by ID (Admin only)")
    async def leave(self, ctx: discord.ApplicationContext, guild_id: discord.Option(str, "Server ID to leave")):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You must be an Administrator.", ephemeral=True)
            return
        try:
            gid = int(guild_id)
        except ValueError:
            await ctx.respond("Invalid server ID.", ephemeral=True)
            return
        target = next((g for g in self.bot.guilds if g.id == gid), None)
        if not target:
            await ctx.respond("I'm not in that server.", ephemeral=True)
            return
        await ctx.respond(f"Leaving server: {target.name} ({target.id})...", ephemeral=True)
        try:
            await target.leave()
        except Exception as e:
            try:
                await ctx.user.send(f"Failed to leave server {gid}: {e}")
            except Exception:
                pass

    @commands.slash_command(name="leave_non_home", description="Leave all servers except the one you specify (Admin only)")
    async def leave_non_home(self, ctx: discord.ApplicationContext, home_id: discord.Option(str, "Server ID to stay in")):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You must be an Administrator.", ephemeral=True)
            return
        try:
            home_id_int = int(home_id)
        except ValueError:
            await ctx.respond("Invalid home server ID.", ephemeral=True)
            return
        left = []
        for g in list(self.bot.guilds):
            if g.id != home_id_int:
                try:
                    await g.leave()
                    left.append(f"{g.name} ({g.id})")
                except Exception:
                    pass
        if left:
            await ctx.respond("✅ Left non-home servers:\n" + "\n".join(left), ephemeral=True)
        else:
            await ctx.respond("Already only in the specified server.", ephemeral=True)

def setup(bot: commands.Bot):
    bot.add_cog(GuildControl(bot))
