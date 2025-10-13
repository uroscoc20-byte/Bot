# verification.py
import discord
from discord.ext import commands
from discord.ui import Modal, InputText
from database import db
from datetime import datetime

class VerificationModal(Modal):
    def __init__(self):
        super().__init__(title="Verification Ticket")
        self.add_item(InputText(label="In-game name?", required=True))
        self.add_item(InputText(label="Invited by?", required=True))

    async def callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

        guild = interaction.guild
        if guild is None:
            return

        # Use the same parent category as normal tickets
        parent_category = None
        try:
            cat_id = await db.get_ticket_category()
            cand = guild.get_channel(cat_id) if cat_id else None
            parent_category = cand if isinstance(cand, discord.CategoryChannel) else None
        except Exception:
            parent_category = None

        # Channel overwrites: requestor, staff, admin visible
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        roles_cfg = await db.get_roles()
        staff_role = guild.get_role(roles_cfg.get("staff")) if roles_cfg else None
        admin_role = guild.get_role(roles_cfg.get("admin")) if roles_cfg else None
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        # Create channel
        try:
            ch_name = f"verify-{interaction.user.name.lower().replace(' ', '-')}-{interaction.user.discriminator if hasattr(interaction.user,'discriminator') else interaction.user.id}"
            channel = await guild.create_text_channel(
                name=ch_name[:90],
                category=parent_category,
                overwrites=overwrites,
                reason=f"Verification ticket for {interaction.user}",
            )
        except Exception as e:
            await interaction.followup.send(f"Could not create verification channel: {e}", ephemeral=True)
            return

        # Build embed
        embed = discord.Embed(
            title="Verification Request",
            description=f"Requester: {interaction.user.mention}",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow(),
        )
        in_game = self.children[0].value
        invited_by = self.children[1].value
        embed.add_field(name="In-game name", value=in_game, inline=False)
        embed.add_field(name="Invited by", value=invited_by, inline=False)

        mention = staff_role.mention if staff_role else (admin_role.mention if admin_role else "")
        msg = await channel.send(content=mention, embed=embed)
        try:
            await msg.pin()
        except Exception:
            pass

        await interaction.followup.send(f"✅ Verification ticket created: {channel.mention}", ephemeral=True)

class VerificationModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="verify", description="Open a verification modal")
    async def verify(self, ctx: discord.ApplicationContext):
        await ctx.interaction.response.send_modal(VerificationModal())

def setup(bot):
    bot.add_cog(VerificationModule(bot))