# apprentice_tickets.py
# Apprentice Class Ticket System - Eternal Panel with proper close permissions

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
        """Open modal for class ticket"""
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
            max_length=100,
            style=discord.TextStyle.short
        )
        self.add_item(self.topic)

        self.server = discord.ui.TextInput(
            label="Server?",
            placeholder="Example: Artix / Galanoth / Yorumi",
            required=True,
            max_length=100,
            style=discord.TextStyle.short
        )
        self.add_item(self.server)

        self.room = discord.ui.TextInput(
            label="Room number?",
            placeholder="Example: 9999",
            required=False,
            max_length=20,
            style=discord.TextStyle.short
        )
        self.add_item(self.room)

        self.extra = discord.ui.TextInput(
            label="Additional info?",
            placeholder="Optional: party size, notes, requirements",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.extra)

    async def on_submit(self, interaction: discord.Interaction):
        """Create the private class ticket channel"""
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        category_id = config.CHANNEL_IDS.get("APPRENTICE_TICKET_CATEGORY")
        if not category_id:
            await interaction.followup.send("❌ Class ticket category not configured!", ephemeral=True)
            return

        category = guild.get_channel(category_id)
        if not category:
            await interaction.followup.send("❌ Class ticket category not found!", ephemeral=True)
            return

        # Create channel name
        channel_name = f"class-{interaction.user.name}".lower().replace(" ", "-")[:50]

        # Permissions: only teacher + apprentice + bot
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

        # Create channel and store ticket opener ID in topic
        try:
            channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                topic=str(interaction.user.id)  # store opener ID
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to create class ticket: {e}", ephemeral=True)
            return

        # Send embed in the class channel
        embed = discord.Embed(
            title="🎫 Apprentice Class Ticket",
            description=(
                f"**Teacher:** {interaction.user.mention}\n"
                f"**Topic:** {self.topic.value}\n"
                f"**Server:** {self.server.value}\n"
                f"**Room:** {self.room.value or 'N/A'}\n"
                f"**Extra info:** {self.extra.value or 'None'}\n\n"
                "**Apprentices:** Join and learn from this class.\n"
                "Teacher can close this ticket when class is over."
            ),
            color=config.COLORS.get("INFO", 0x00ffdd),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"User ID: {interaction.user.id}")

        view = ApprenticeTicketActionView()

        ping = apprentice_role.mention if apprentice_role else ""
        await channel.send(
            content=f"{ping}\n{interaction.user.mention} started a class ticket!",
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
    """Close ticket button"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Class Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
        custom_id="apprentice_class_close"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Allowed roles: ADMIN, STAFF, OFFICER
        allowed_roles = [
            config.ROLE_IDS.get("ADMIN"),
            config.ROLE_IDS.get("STAFF"),
            config.ROLE_IDS.get("OFFICER")
        ]
        member_roles = [role.id for role in interaction.user.roles]
        is_staff = any(role_id in member_roles for role_id in allowed_roles)

        # Ticket opener ID from channel topic
        opener_id = int(interaction.channel.topic) if interaction.channel.topic else None
        is_opener = opener_id == interaction.user.id

        # Only teacher (opener) or allowed staff/admin/officer can close
        if not (is_staff or is_opener):
            await interaction.response.send_message(
                "❌ Only the teacher who opened the ticket or staff/admin/officer can close this ticket.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Class ticket closed by {interaction.user.mention}. Deleting channel in 5 seconds..."
        )
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Class ticket closed by {interaction.user}")
        except:
            pass


# ------------------------------
# Setup function to register panel command
# ------------------------------
async def setup_apprentice_tickets(bot):
    @bot.tree.command(
        name="apprentice_ticket_panel",
        description="Post the eternal apprentice class ticket panel"
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
                "❌ You don't have permission to post the apprentice ticket panel.",
                ephemeral=True
            )
            return

        # Panel is public
        await interaction.response.defer(ephemeral=False)

        view = ApprenticeTicketView()
        embed = discord.Embed(
            title="🎫 Apprentice Class Tickets",
            description=(
                "Skilled players can open a class ticket to teach apprentices.\n\n"
                "Click **Open Class Ticket** and fill out the modal:\n"
                "- Topic\n"
                "- Server\n"
                "- Room\n"
                "- Extra notes\n\n"
                "Apprentices will join and learn from the teacher."
            ),
            color=config.COLORS.get("INFO", 0x00ffdd)
        )

        await interaction.followup.send(embed=embed, view=view)
