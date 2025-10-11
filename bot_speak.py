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
        channel_input: discord.Option(str, "Channel ID or name"),
        content: discord.Option(str, "Text to send"),
        image_url: discord.Option(str, "Optional image URL", required=False)
    ):
        # Check admin/staff
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission to use this.", ephemeral=True)
            return

        guild = ctx.guild
        target_channel = None

        # Try by ID
        if channel_input.isdigit():
            target_channel = guild.get_channel(int(channel_input))
        # Try by name
        if not target_channel:
            for ch in guild.channels:
                if ch.name == channel_input:
                    target_channel = ch
                    break

        if not target_channel:
            await ctx.respond("Channel not found.", ephemeral=True)
            return

        embed = discord.Embed(description=content, color=0x00FFAA)
        if image_url:
            embed.set_image(url=image_url)

        await target_channel.send(embed=embed)
        await ctx.respond(f"Message sent to {target_channel.mention}!", ephemeral=True)

# ---------- SETUP ----------
def setup(bot):
    bot.add_cog(TalkModule(bot))