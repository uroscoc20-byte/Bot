# apprentice_tickets.py
# Apprentice Class Ticket System - Eternal Panel

import discord
from discord.ext import commands
import config
import asyncio

# ------------------------------
# Persistent Panel + Button
# ------------------------------
class ApprenticeTicketView(discord.ui.View):
    """Persistent view for eternal apprentice ticket panel"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Open Class Ticket",
        style=discord.ButtonStyle.primary,
        emoji="🎫",
        custom_id="apprentice_class_open"
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

        # ❌ Restricted can't open
        restricted_role = interaction.guild.get_role(config.ROLE_IDS.get("RESTRICTED"))
        if restricted_role and restricted_role in interaction.user.roles:
            await interaction.response.send_message(
                "❌ You are restricted and cannot open class tickets.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(ApprenticeTicketModal())


# ------------------------------
# Modal for Teacher Input
# ------------------------------
class ApprenticeTicketModal(discord.ui.Modal):
    """Modal for class ticket information"""
    def __init__(self):
        super().__init__(title="Open Apprentice Class Ticket")

        self.topic = discord.ui.TextInput(
            label="Class topic?",
            placeholder="Example: Ultra Dage solo strategy",
            required=True,
            max_length=100
        )
        self.add_item(self.topic)

        self.server = discord.ui.TextInput(
            label="Server?",
            placeholder="Example: Artix / Galanoth / Yorumi",
            required=True,
            max_length=100
        )
        self.add_item(self.server)

        self.room = discord.ui.TextInput(
            label="Room number?",
            placeholder="Example: 9999",
            required=False,
            max_length=20
        )
        self.add_item(self.room)

        self.extra = discord.ui.TextInput(
            label="Additional info?",
            placeholder="Optional notes",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.extra)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        category = guild.get_channel(config.CHANNEL_IDS.get("APPRENTICE_TICKET_CATEGORY"))
        if not category:
            await interaction.followup.send("❌ Ticket category not found.", ephemeral=True)
            return

        teacher = interaction.user
        channel_name = f"class-{teacher.name}".lower().replace(" ", "-")[:50]

        # ------------------------------
        # Permissions
        # ------------------------------
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            teacher: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        apprentice_role = guild.get_role(config.ROLE_IDS.get("APPRENTICE"))
        if apprentice_role:
            overwrites[apprentice_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True
            )

        # Staff / Admin / Officer can see
        for key in ("ADMIN", "STAFF", "OFFICER"):
            role = guild.get_role(config.ROLE_IDS.get(key))
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                )

        # Restricted can't see
        restricted_role = guild.get_role(config.ROLE_IDS.get("RESTRICTED"))
        if restricted_role:
            overwrites[restricted_role] = discord.PermissionOverwrite(view_channel=False)

        channel = await category.create_text_channel(
            name=channel_name,
            overwrites=overwrites
        )

        embed = discord.Embed(
            title="🎫 Apprentice Class Ticket",
            description=(
                f"**Teacher:** {teacher.mention}\n"
                f"**Topic:** {self.topic.value}\n"
                f"**Server:** {self.server.value}\n"
                f"**Room:** {self.room.value or 'N/A'}\n"
                f"**Extra info:** {self.extra.value or 'None'}\n\n"
                "Only the teacher or staff can close this ticket."
            ),
            color=config.COLORS.get("INFO", 0x00ffdd),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=teacher.display_avatar.url)

        view = ApprenticeTicketActionView(teacher.id)

        ping = apprentice_role.mention if apprentice_role else ""
        await channel.send(
            content=f"{ping}\n{teacher.mention} started a class ticket!",
            embed=embed,
            view=view
        )

        await interaction.followup.send(
            f"✅ Class ticket created: {channel.mention}",
            ephemeral=True
        )


# ------------------------------
# Action View for Closing Ticket
# ------------------------------
class ApprenticeTicketActionView(discord.ui.View):
    def __init__(self, teacher_id: int):
        super().__init__(timeout=None)
        self.teacher_id = teacher_id

    @discord.ui.button(
        label="Close Class Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
        custom_id="apprentice_class_close"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

        member = interaction.user

        is_teacher = member.id == self.teacher_id
        is_staff = any(
            member.get_role(config.ROLE_IDS.get(r))
            for r in ("ADMIN", "STAFF", "OFFICER")
        )

        if not (is_teacher or is_staff):
            await interaction.response.send_message(
                "❌ Only the teacher or staff can close this class ticket.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Class ticket closed by {member.mention}. Deleting channel in 5 seconds..."
        )
        await asyncio.sleep(5)
        await interaction.channel.delete()


# ------------------------------
# Setup function (UNCHANGED)
# ------------------------------
async def setup_apprentice_tickets(bot):

    @bot.tree.command(
        name="apprentice_ticket_panel",
        description="Post the eternal apprentice class ticket panel"
    )
    async def apprentice_ticket_panel(interaction: discord.Interaction):

        is_staff = any(
            interaction.user.get_role(rid)
            for rid in (
                config.ROLE_IDS.get("ADMIN"),
                config.ROLE_IDS.get("STAFF"),
            )
            if rid
        )

        if not is_staff:
            await interaction.response.send_message(
                "❌ You don't have permission to post the apprentice ticket panel.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=False)

        embed = discord.Embed(
            title="🎫 Apprentice Class Tickets",
            description=(
                "Skilled players can open a class ticket to teach apprentices.\n\n"
                "Click **Open Class Ticket** and fill out the modal."
            ),
            color=config.COLORS.get("INFO", 0x00ffdd)
        )

        await interaction.followup.send(
            embed=embed,
            view=ApprenticeTicketView()
        )
