import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, InputText

def parse_color(color_str: str, default: int = 0x5865F2) -> int:
    try:
        if not color_str:
            return default
        s = color_str.strip()
        if s.lower().startswith("0x"):
            return int(s, 16)
        return int(s.lstrip("#"), 16)
    except Exception:
        return default


class ConfirmView(View):
    def __init__(self, target_channel: discord.abc.Messageable, embed: discord.Embed):
        super().__init__(timeout=60)
        self.target_channel = target_channel
        self.embed = embed

    @discord.ui.button(label="✅ Send Message", style=discord.ButtonStyle.success)
    async def confirm(self, button: Button, interaction: discord.Interaction):
        try:
            await self.target_channel.send(embed=self.embed)
            await interaction.response.edit_message(content=f"✅ Message sent to {self.target_channel.mention}", view=None, embed=None)
        except Exception as e:
            await interaction.response.edit_message(content=f"❌ Failed to send: {e}", view=None)


    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, button: Button, interaction: discord.Interaction):
        await interaction.response.edit_message(content="❌ Cancelled.", view=None, embed=None)


class TalkModal(Modal):
    def __init__(self):
        super().__init__(title="Compose Message")
        self.channel = InputText(label="Channel (name or ID)", required=True)
        self.content = InputText(label="Message Content", style=discord.InputTextStyle.long, required=False)
        self.image_url = InputText(label="Image URL (optional)", required=False)
        self.embed_title = InputText(label="Embed Title (optional)", required=False)
        self.embed_color = InputText(label="Embed Color (#5865F2 by default)", required=False)
        self.embed_footer = InputText(label="Footer Text (optional)", required=False)
        self.add_item(self.channel)
        self.add_item(self.content)
        self.add_item(self.image_url)
        self.add_item(self.embed_title)
        self.add_item(self.embed_color)
        self.add_item(self.embed_footer)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)  # defer first to prevent timeout

        guild = interaction.guild
        channel_input = self.channel.value.strip()
        target = None

        # Lookup channel by ID
        if channel_input.isdigit():
            target = guild.get_channel(int(channel_input)) or guild.get_thread(int(channel_input))
        else:
            # Lookup channel by name
            for ch in guild.channels:
                if getattr(ch, "name", "") == channel_input:
                    target = ch
                    break

        if not target:
            await interaction.followup.send("❌ Channel or thread not found.", ephemeral=True)
            return

        # Build embed preview
        embed = discord.Embed(
            title=self.embed_title.value.strip() or None,
            description=self.content.value.strip() or None,
            color=parse_color(self.embed_color.value.strip()),
        )
        if self.image_url.value.strip():
            embed.set_image(url=self.image_url.value.strip())
        if self.embed_footer.value.strip():
            embed.set_footer(text=self.embed_footer.value.strip())

        # Send ephemeral preview with buttons
        view = ConfirmView(target_channel=target, embed=embed)
        await interaction.followup.send(content=f"📋 **Preview:**\nChannel: {target.mention}", embed=embed, view=view, ephemeral=True)


class TalkView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📝 Create Message", style=discord.ButtonStyle.blurple)
    async def create_message(self, button: Button, interaction: discord.Interaction):
        await interaction.response.send_modal(TalkModal())


class TalkModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="talk", description="Compose and send a bot message with preview")
    async def talk(self, ctx: discord.ApplicationContext):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("❌ You do not have permission.", ephemeral=True)
            return

        await ctx.respond("Click below to compose a message:", view=TalkView(), ephemeral=True)


def setup(bot):
    bot.add_cog(TalkModule(bot))
