# apprentice_tickets.py
# Apprentice Class Ticket System - SAFE VERSION (no persistent views)

import discord
from discord.ext import commands
import asyncio
import config

# ------------------------------
# PANEL VIEW
# ------------------------------
class ApprenticeTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Open Class Ticket",
        style=discord.ButtonStyle.primary,
        emoji="🎫"
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

        restricted = interaction.guild.get_role(config.ROLE_IDS["RESTRICTED"])
        if restricted and restricted in interaction.user.roles:
            await interaction.response.send_message(
                "❌ You are restricted and cannot open class tickets.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(ApprenticeTicketModal())


# ------------------------------
# MODAL
# ------------------------------
class ApprenticeTicketModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Open Apprentice Class Ticket")

        self.topic = discord.ui.TextInput(label="Class topic")
        self.server = discord.ui.TextInput(label="Server")
        self.room = discord.ui.TextInput(label="Room", required=False)
        self.extra = discord.ui.TextInput(
            label="Extra info",
            required=False,
            style=discord.TextStyle.paragraph
        )

        for item in (self.topic, self.server, self.room, self.extra):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        teacher = interaction.user
        category = guild.get_channel(config.CHANNEL_IDS["APPRENTICE_TICKET_CATEGORY"])

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            teacher: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        apprentice = guild.get_role(config.ROLE_IDS["APPRENTICE"])
        if apprentice:
            overwrites[apprentice] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True
            )

        for key in ("ADMIN", "STAFF", "OFFICER"):
            role = guild.get_role(config.ROLE_IDS[key])
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                )

        restricted = guild.get_role(config.ROLE_IDS["RESTRICTED"])
        if restricted:
            overwrites[restricted] = discord.PermissionOverwrite(view_channel=False)

        channel = await category.create_text_channel(
            f"class-{teacher.name}".lower(),
            overwrites=overwrites
        )

        embed = discord.Embed(
            title="🎫 Apprentice Class Ticket",
            description=(
                f"**Teacher:** {teacher.mention}\n"
                f"**Topic:** {self.topic.value}\n"
                f"**Server:** {self.server.value}\n"
                f"**Room:** {self.room.value or 'N/A'}\n"
                f"**Extra:** {self.extra.value or 'None'}"
            ),
            color=config.COLORS.get("INFO", 0x00ffdd)
        )

        view = ApprenticeCloseView(teacher.id)

        await channel.send(
            content=apprentice.mention if apprentice else None,
            embed=embed,
            view=view
        )

        await interaction.followup.send(
            f"✅ Class ticket created: {channel.mention}",
            ephemeral=True
        )


# ------------------------------
# CLOSE BUTTON
# ------------------------------
class ApprenticeCloseView(discord.ui.View):
    def __init__(self, teacher_id: int):
        super().__init__(timeout=None)
        self.teacher_id = teacher_id

    @discord.ui.button(
        label="Close Class Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🗑️"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

        member = interaction.user

        is_teacher = member.id == self.teacher_id
        is_staff = any(
            member.get_role(config.ROLE_IDS[r])
            for r in ("ADMIN", "STAFF", "OFFICER")
        )

        if not (is_teacher or is_staff):
            await interaction.response.send_message(
                "❌ Only teacher or staff can close this ticket.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "✅ Closing ticket in 5 seconds..."
        )
        await asyncio.sleep(5)
        await interaction.channel.delete()


# ------------------------------
# COMMAND
# ------------------------------
async def setup(bot: commands.Bot):

    @bot.tree.command(
        name="apprentice_ticket_panel",
        description="Post apprentice class ticket panel"
    )
    async def apprentice_ticket_panel(interaction: discord.Interaction):

        if not any(
            interaction.user.get_role(config.ROLE_IDS[r])
            for r in ("ADMIN", "STAFF")
        ):
            await interaction.response.send_message(
                "❌ You don't have permission.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🎫 Apprentice Class Tickets",
            description="Click below to open a class for apprentices.",
            color=config.COLORS.get("INFO", 0x00ffdd)
        )

        await interaction.response.send_message(
            embed=embed,
            view=ApprenticeTicketView()
        )
