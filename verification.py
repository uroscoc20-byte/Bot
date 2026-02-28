# verification.py
# Verification System - Panel, Modal, Channel Creation, Review

import discord
from discord.ext import commands
from discord import app_commands
import config
import asyncio


class VerificationView(discord.ui.View):
    """Persistent view for verification panel"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verify",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="verify_open"
    )
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = VerificationModal()
        await interaction.response.send_modal(modal)


class VerificationModal(discord.ui.Modal):
    """Modal for verification information"""
    def __init__(self):
        super().__init__(title="Verification Ticket")

        self.in_game_name = discord.ui.TextInput(
            label="In-game name?",
            placeholder="Enter your in-game name",
            required=True,
            max_length=100
        )
        self.add_item(self.in_game_name)

        self.invited_by = discord.ui.TextInput(
            label="Who invited you?",
            placeholder="Optional",
            required=False,
            max_length=200
        )
        self.add_item(self.invited_by)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        category_id = config.CHANNEL_IDS.get("VERIFICATION_CATEGORY")

        if not category_id:
            await interaction.followup.send("❌ Verification category not configured.", ephemeral=True)
            return

        category = guild.get_channel(category_id)
        if not category:
            await interaction.followup.send("❌ Verification category not found.", ephemeral=True)
            return

        channel_name = f"verify-{interaction.user.name}".lower().replace(" ", "-")[:50]

        admin_role   = guild.get_role(config.ROLE_IDS.get("ADMIN"))
        staff_role   = guild.get_role(config.ROLE_IDS.get("STAFF"))
        officer_role = guild.get_role(config.ROLE_IDS.get("OFFICER"))

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        if officer_role:
            overwrites[officer_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        try:
            channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to create ticket: {e}", ephemeral=True)
            return

        embed = discord.Embed(
            title="🛡️ Verification Request",
            description=(
                f"**User:** {interaction.user.mention}\n"
                f"**In-game name:** {self.in_game_name.value}\n"
                f"**Invited by:** {self.invited_by.value or 'Not specified'}\n\n"
                "**Staff:** Please review this verification request."
            ),
            color=config.COLORS["SUCCESS"],
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"User ID: {interaction.user.id}")

        view = VerificationActionView()

        mentions = [interaction.user.mention]
        if staff_role:
            mentions.append(staff_role.mention)
        if officer_role:
            mentions.append(officer_role.mention)
        if admin_role:
            mentions.append(admin_role.mention)

        await channel.send(
            content=" ".join(mentions),
            embed=embed,
            view=view
        )

        await interaction.followup.send(
            f"✅ Verification ticket created: {channel.mention}",
            ephemeral=True
        )


class VerificationActionView(discord.ui.View):
    """Action buttons for verification ticket"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Verification",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
        custom_id="close_verification"
    )
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user

        allowed_roles = [
            config.ROLE_IDS.get("ADMIN"),
            config.ROLE_IDS.get("STAFF"),
            config.ROLE_IDS.get("OFFICER"),
        ]

        if not any(member.get_role(rid) for rid in allowed_roles if rid):
            await interaction.response.send_message(
                "❌ Only staff can close verification tickets.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Verification closed by {interaction.user.mention}.\n"
            "Channel will be deleted in 5 seconds."
        )

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(
                reason=f"Verification closed by {interaction.user}"
            )
        except:
            pass


async def setup_verification(bot: commands.Bot):
    """Setup verification commands"""

    @bot.tree.command(
        name="verification_panel",
        description="Post the verification panel (Admin / Staff / Officer)"
    )
    async def verification_panel(interaction: discord.Interaction):
        member = interaction.user

        allowed_roles = [
            config.ROLE_IDS.get("ADMIN"),
            config.ROLE_IDS.get("STAFF"),
            config.ROLE_IDS.get("OFFICER"),
        ]

        if not any(member.get_role(rid) for rid in allowed_roles if rid):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

embed = discord.Embed(
    title="🛡️ Verification Panel",
    description=(
        "Welcome to the server!\n\n"
        "To gain access, please complete the short verification process below.\n\n"
        "Click **Verify** and provide the following information:\n\n"
        "- **In-Game Name** – The name you use in the game.\n"
        "- **Who Invited You** – The name of the person who invited you to the server (if anyone).\n\n"
        "⚠️ Please make sure the information is accurate and complete.\n"
        "Once submitted, a staff member will review your verification and grant access as soon as possible."
    ),
    color=config.COLORS["SUCCESS"]
)

        await interaction.channel.send(embed=embed, view=VerificationView())
        await interaction.response.send_message(
            "✅ Verification panel posted!",
            ephemeral=True
        )
