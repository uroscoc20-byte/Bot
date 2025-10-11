# talk.py
import discord
from discord.ext import commands

def parse_color(color_str: str, default: int = 0x5865F2) -> int:
    if not color_str:
        return default
    try:
        s = color_str.strip()
        if s.lower().startswith("0x"):
            return int(s, 16)
        return int(s.lstrip("#"), 16)
    except Exception:
        return default

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
        file_attachment: discord.Option(discord.Attachment, "Optional file (image/video)", required=False),
        as_embed: discord.Option(bool, "Send as embed?", required=False, default=True),
        embed_title: discord.Option(str, "Embed title", required=False),
        embed_color: discord.Option(str, "Embed color hex like #5865F2", required=False),
        embed_footer: discord.Option(str, "Embed footer text", required=False),
        thumbnail_url: discord.Option(str, "Thumbnail URL", required=False),
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

        file_to_send = None
        filename_for_embed = None
        if file_attachment:
            try:
                file_to_send = await file_attachment.to_file()
                filename_for_embed = file_attachment.filename
            except Exception:
                file_to_send = None

        if as_embed:
            color_value = parse_color(embed_color, default=0x5865F2)
            embed = discord.Embed(
                title=embed_title if embed_title else None,
                description=content,
                color=color_value,
            )
            if embed_footer:
                embed.set_footer(text=embed_footer)
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

            # Prefer explicit image_url; otherwise if attached file is an image, show it in embed
            if image_url:
                embed.set_image(url=image_url)
            elif file_attachment and file_attachment.content_type and file_attachment.content_type.startswith("image/"):
                # Display attached image inside embed
                embed.set_image(url=f"attachment://{filename_for_embed}")

            await target_channel.send(embed=embed, file=file_to_send)
        else:
            text_out = content if not image_url else f"{content}\n{image_url}"
            await target_channel.send(text_out, file=file_to_send)

        await ctx.respond(f"Message sent to {target_channel.mention}!", ephemeral=True)

# ---------- SETUP ----------
def setup(bot):
    bot.add_cog(TalkModule(bot))