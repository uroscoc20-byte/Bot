# talk.py
import discord
from discord.ext import commands

class TalkModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="talk", description="Bot sends a message in specified channel/thread")
    async def talk(
        self,
        ctx: discord.ApplicationContext,
        channel_input: discord.Option(str, "Channel or thread ID or name"),
        content: discord.Option(str, "Text to send"),
        image_url: discord.Option(str, "Optional image URL", required=False),
        as_embed: discord.Option(bool, "Send as embed?", required=False, default=True)
    ):
        # Check admin/staff
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission to use this.", ephemeral=True)
            return

        guild = ctx.guild
        target_channel = None

        # Try by ID (channel or thread)
        if channel_input.isdigit():
            cid = int(channel_input)
            target_channel = guild.get_channel(cid) or guild.get_thread(cid)
        # Try by name (text channels only)
        if not target_channel:
            for ch in guild.channels:
                if hasattr(ch, "name") and ch.name == channel_input:
                    target_channel = ch
                    break

        if not target_channel:
            await ctx.respond("Channel not found.", ephemeral=True)
            return

        if as_embed:
            embed = discord.Embed(description=content, color=0x5865F2)
            if image_url:
                embed.set_image(url=image_url)
            await target_channel.send(embed=embed)
        else:
            if image_url:
                await target_channel.send(f"{content}\n{image_url}")
            else:
                await target_channel.send(content)
        await ctx.respond(f"Message sent to {target_channel.mention}!", ephemeral=True)

# ---------- SETUP ----------
def setup(bot):
    bot.add_cog(TalkModule(bot))
