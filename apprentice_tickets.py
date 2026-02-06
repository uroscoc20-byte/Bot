# apprentice_tickets.py
# Apprentice Class Ticket System - Eternal Panel (FINAL)

import discord
from discord.ext import commands
import asyncio
import config

# ======================================================
# PERSISTENT PANEL VIEW
# ======================================================
class ApprenticeTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Open Class Ticket",
        emoji="🎫",
        style=discord.ButtonStyle.primary,
        custom_id="apprentice:open"
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

        member = interaction.user

        # ❌ Restricted cannot open
        restricted = interaction.guild.get_role(config.ROLE_IDS.get("RESTRICTED"))
        if restricted and restricted in member.roles:
            await interaction.response.send_message(
                "❌ You are restricted and cannot open class tickets.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(ApprenticeTicketModal())


# ======================================================
# MODAL
# ======================================================
class ApprenticeTicketModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Open Apprentice Class")

        self.topic = discord.ui.TextInput(
            label="Class topic",
            placeholder="Ultra Dage solo, farming guide, etc.",
            max_length=100
        )
        self.server = discord.ui.TextInput(
            label="Server",
            placeholder="Artix / Galanoth / Yorumi",
            max_length=50
        )
        self.room = discord.ui.TextInput(
            label="Room",
            placeholder="9999",
            required=False,
            max_length=20
        )
        self.extra = discord.ui.TextInput(
            label="Extra info",
            placeholder="Optional notes",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=500
        )

        for item in (self.topic, self.server, self.room, self.extra):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        teacher = interaction.user

        category = guild.get_channel(config.CHANNEL_IDS.get("APPRENTICE_TICKET_CATEGORY"))
        if not category:
            await interaction.followup.send("❌ Ticket category not found.", ephemeral=True)
            return

        # --------------------------------------------------
        # PERMISSIONS
        # --------------------------------------------------
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            teacher: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        apprentice = guild.get_role(config.ROLE_IDS.get("APPRENTICE"))
        if apprentice:
            overwrites[apprentice] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True
            )

        for key in ("ADMIN", "STAFF", "OFFICER"):
            role = guild.get_role(config.ROLE_IDS.get(key))
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                )

        restricted = guild.get_role(config.ROLE_IDS.get("RESTRICTED"))
        if restricted:
            overwrites[restricted] = discord.PermissionOverwrite(view_channel=False)

        channel = await category.create_text_channel(
            name=f"class-{teacher.name}".lower().replace(" ", "-")[:50],
            overwrites=overwrites
        )

        # --------------------------------------------------
        # EMBED
        # --------------------------------------------------
        embed = discord.Embed(
            title="🎫 Apprentice Class Ticket",
            color=config.COLORS.get("INFO", 0x00ffdd),
            description=(
                f"**Teacher:** {teacher.mention}\n"
                f"**Topic:** {self.topic.value}\n"
                f"**Server:** {self.server.value}\n"
                f"**Room:** {self.room.value or 'N/A'}\n"
                f"**Extra:** {self.extra.value or 'None'}\n\n"
                "Only teacher or staff can close this ticket."
            ),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=teacher.display_avatar.url)

        view = ApprenticeTicketCloseView(teacher.id)

        ping = apprentice.mention if apprentice else ""
        await channel.send(
            content=f"{ping}\n{teacher.mention} started a class!",
            embed=embed,
            view=view
        )

        await interaction.followup.send(
            f"✅ Class ticket created: {channel.mention}",
            ephemeral=True
        )


# ======================================================
# CLOSE BUTTON VIEW
# ======================================================
class ApprenticeTicketCloseView(discord.ui.View):
    def __init__(self, teacher_id: int):
        super().__init__(timeout=None)
        self.teacher_id = teacher_id

    @discord.ui.button(
        label="Close Class Ticket",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
        custom_id="apprentice:close"
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
                "❌ Only the teacher or staff can close this ticket.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Closed by {member.mention}. Deleting in 5 seconds..."
        )
        await asyncio.sleep(5)
        await interaction.channel.delete()


# ======================================================
# PANEL COMMAND
# ======================================================
async def setup(bot: commands.Bot):

    @bot.tree.command(
        name="apprentice_ticket_panel",
        description="Post the apprentice class ticket panel"
    )
    async def apprentice_ticket_panel(interaction: discord.Interaction):

        member = interaction.user

        if not any(
            member.get_role(config.ROLE_IDS.get(r))
            for r in ("ADMIN", "STAFF")
        ):
            await interaction.response.send_message(
                "❌ You don't have permission.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🎫 Apprentice Class Tickets",
            color=config.COLORS.get("INFO", 0x00ffdd),
            description=(
                "Skilled players can open a class for apprentices.\n\n"
                "Fill the form with class details.\n"
                "Only teacher or staff may close tickets."
            )
        )

        await interaction.response.send_message(
            embed=embed,
            view=ApprenticeTicketView()
        )


# ======================================================
# REQUIRED: REGISTER PERSISTENT VIEWS
# ======================================================
def register_views(bot: commands.Bot):
    bot.add_view(ApprenticeTicketView())
