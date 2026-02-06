# apprentice_tickets.py
# Apprentice Ticket System - Panel, Modal, Channel Creation, Review

import discord
from discord.ext import commands
import config
import asyncio


class ApprenticeTicketView(discord.ui.View):
    """Persistent view for apprentice ticket panel"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Open Apprentice Ticket",
        style=discord.ButtonStyle.primary,
        emoji="🎫",
        custom_id="apprentice_ticket_open"
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal for apprentice ticket"""
        await interaction.response.send_modal(ApprenticeTicketModal())


class ApprenticeTicketModal(discord.ui.Modal):
    """Modal for apprentice ticket information"""
    def __init__(self):
        super().__init__(title="Apprentice Help Ticket")

        self.server = discord.ui.TextInput(
            label="What server?",
            placeholder="Example: Artix / Galanoth / Yorumi",
            required=True,
            max_length=100,
            style=discord.TextStyle.short
        )
        self.add_item(self.server)

        self.room = discord.ui.TextInput(
            label="Room number?",
            placeholder="Example: 9999",
            required=True,
            max_length=20,
            style=discord.TextStyle.short
        )
        self.add_item(self.room)

        self.boss = discord.ui.TextInput(
            label="What boss?",
            placeholder="Example: Ultra Dage",
            required=True,
            max_length=100,
            style=discord.TextStyle.short
        )
        self.add_item(self.boss)

        self.extra = discord.ui.TextInput(
            label="Anything else?",
            placeholder="Optional: party size, requirements, notes",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.extra)

    async def on_submit(self, interaction: discord.Interaction):
        """Create the apprentice ticket channel"""
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        category_id = config.CHANNEL_IDS.get("APPRENTICE_TICKET_CATEGORY")
        if not category_id:
            await interaction.followup.send("❌ Apprentice ticket category not configured!", ephemeral=True)
            return

        category = guild.get_channel(category_id)
        if not category:
            await interaction.followup.send("❌ Apprentice ticket category not found!", ephemeral=True)
            return

        channel_name = f"apprentice-{interaction.user.name}".lower().replace(" ", "-")[:50]

        # Set channel permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        apprentice_role = guild.get_role(config.ROLE_IDS.get("APPRENTICE"))
        if apprentice_role:
            overwrites[apprentice_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True
            )

        try:
            channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to create ticket: {e}", ephemeral=True)
            return

        # Embed in the ticket channel
        embed = discord.Embed(
            title="🎫 Apprentice Help Request",
            description=(
                f"**User:** {interaction.user.mention}\n"
                f"**Server:** {self.server.value}\n"
                f"**Room:** {self.room.value}\n"
                f"**Boss:** {self.boss.value}\n"
                f"**Extra info:** {self.extra.value or 'None'}\n\n"
                "**Apprentice:** Please assist with this request.\n"
                "Close the ticket when finished."
            ),
            color=config.COLORS.get("INFO", 0x00ffdd),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"User ID: {interaction.user.id}")

        view = ApprenticeTicketActionView()

        ping = apprentice_role.mention if apprentice_role else ""
        await channel.send(
            content=f"{ping}\n{interaction.user.mention} opened an apprentice ticket!",
            embed=embed,
            view=view
        )

        await interaction.followup.send(
            f"✅ Apprentice ticket created: {channel.mention}",
            ephemeral=True
        )


class ApprenticeTicketActionView(discord.ui.View):
    """Buttons to close apprentice tickets"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Apprentice Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
        custom_id="apprentice_ticket_close"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        apprentice_role = interaction.guild.get_role(config.ROLE_IDS.get("APPRENTICE"))

        # Only ticket opener or apprentice role can close
        if apprentice_role not in interaction.user.roles and interaction.user != interaction.channel.permissions_for(interaction.user).read_messages:
            await interaction.response.send_message(
                "❌ Only Apprentices or ticket opener can close this ticket.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Apprentice ticket closed by {interaction.user.mention}.\nDeleting channel in 5 seconds..."
        )

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Apprentice ticket closed by {interaction.user}")
        except:
            pass


async def setup_apprentice_tickets(bot):
    """Register panel command for apprentices"""
    @bot.tree.command(
        name="apprentice_ticket_panel",
        description="Post the apprentice ticket panel (Staff/Admin only)"
    )
    async def apprentice_ticket_panel(interaction: discord.Interaction):
        member = interaction.user
        is_staff = any(
            member.get_role(rid)
            for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF")]
            if rid
        )

        if not is_staff:
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        # ✅ Defer to avoid "The application did not respond"
        await interaction.response.defer(ephemeral=True)

        view = ApprenticeTicketView()
        embed = discord.Embed(
            title="🎫 Apprentice Tickets",
            description=(
                "Need help with a boss or activity?\n\n"
                "Click **Open Apprentice Ticket** and provide:\n"
                "- Server\n"
                "- Room number\n"
                "- Boss name\n"
                "- Any extra info\n\n"
                "An **Apprentice** will assist you shortly."
            ),
            color=config.COLORS.get("INFO", 0x00ffdd)
        )

        await interaction.followup.send(embed=embed, view=view)
