# bot_speak.py
import discord
from discord.ext import commands
from discord.ui import Modal, InputText

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

class TalkModal(Modal):
    def __init__(self, channel_input: str):
        super().__init__(title="Bot Speak")
        self.channel_input = channel_input
        
        self.content = InputText(
            label="Message Content*",
            placeholder="Type your message here...",
            style=discord.InputTextStyle.long,
            required=True,
            max_length=4000
        )
        self.image_url = InputText(
            label="Image URL",
            placeholder="Optional image URL",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.embed_title = InputText(
            label="Embed Title",
            placeholder="Optional embed title",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.embed_color = InputText(
            label="Embed Color",
            placeholder="Hex color like #5865F2",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.embed_footer = InputText(
            label="Embed Footer",
            placeholder="Optional footer text",
            style=discord.InputTextStyle.short,
            required=False
        )
        self.thumbnail_url = InputText(
            label="Thumbnail URL",
            placeholder="Optional thumbnail URL",
            style=discord.InputTextStyle.short,
            required=False
        )
        
        self.add_item(self.content)
        self.add_item(self.image_url)
        self.add_item(self.embed_title)
        self.add_item(self.embed_color)
        self.add_item(self.embed_footer)
        self.add_item(self.thumbnail_url)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

        guild = interaction.guild
        target_channel = None

        if self.channel_input.isdigit():
            cid = int(self.channel_input)
            target_channel = guild.get_channel(cid) or guild.get_thread(cid)
        if not target_channel:
            for ch in guild.channels:
                if hasattr(ch, "name") and ch.name == self.channel_input:
                    target_channel = ch
                    break

        if not target_channel:
            await interaction.followup.send("Channel not found.", ephemeral=True)
            return

        content = self.content.value or ""
        image_url = self.image_url.value or ""
        embed_title = self.embed_title.value or ""
        embed_color = self.embed_color.value or ""
        embed_footer = self.embed_footer.value or ""
        thumbnail_url = self.thumbnail_url.value or ""

        # Send as embed by default
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
        if image_url:
            embed.set_image(url=image_url)
        
        try:
            await target_channel.send(embed=embed)
            await interaction.followup.send(f"✅ Message sent to {target_channel.mention}!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Failed to send message: {e}", ephemeral=True)

    async def callback(self, interaction: discord.Interaction):
        try:
            await self.on_submit(interaction)
        except Exception as e:
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("⚠️ Error sending message.", ephemeral=True)
                else:
                    await interaction.response.send_message("⚠️ Error sending message.", ephemeral=True)
            except Exception:
                pass

class TalkModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="talk", description="Bot sends a message in specified channel/thread")
    async def talk(
        self,
        ctx: discord.ApplicationContext,
        channel_input: discord.Option(str, "Channel or thread ID or name"),
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission to use this.", ephemeral=True)
            return

        # Show modal popup for message composition
        await ctx.response.send_modal(TalkModal(channel_input))

    @commands.slash_command(name="send_message", description="Send a simple message to a channel by ID (admin only)")
    async def send_message(
        self,
        ctx: discord.ApplicationContext,
        channel_id: discord.Option(int, "Channel ID to send message to"),
        message: discord.Option(str, "Message to send"),
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission to use this.", ephemeral=True)
            return

        try:
            target_channel = ctx.guild.get_channel(channel_id)
            if not target_channel:
                await ctx.respond(f"❌ Channel with ID {channel_id} not found.", ephemeral=True)
                return

            await target_channel.send(message)
            await ctx.respond(f"✅ Message sent to {target_channel.mention}!", ephemeral=True)
        except Exception as e:
            await ctx.respond(f"❌ Failed to send message: {e}", ephemeral=True)

def setup(bot):
    bot.add_cog(TalkModule(bot))