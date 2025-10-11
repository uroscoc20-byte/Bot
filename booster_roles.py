import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, InputText
from database import db

ACCENT = 0xEB459E  # pink

class BoosterRoleModal(Modal):
    def __init__(self, requester: discord.Member):
        super().__init__(title="Create Your Booster Role")
        self.requester = requester
        self.name_input = InputText(label="Role name", placeholder="e.g., Super Booster", required=True)
        self.color_input = InputText(label="Hex color (e.g., #FF66CC)", required=False)
        self.emoji_url_input = InputText(label="Emoji/Badge image URL (optional)", required=False)
        self.add_item(self.name_input)
        self.add_item(self.color_input)
        self.add_item(self.emoji_url_input)

    def _parse_color(self, value: str) -> int | None:
        if not value:
            return None
        s = value.strip()
        try:
            if s.lower().startswith("0x"):
                return int(s, 16)
            return int(s.lstrip("#"), 16)
        except Exception:
            return None

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        # basic permission check for bot
        if not guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message("I need 'Manage Roles' to create roles.", ephemeral=True)
            return

        role_name = self.name_input.value.strip()
        color_value = self._parse_color(self.color_input.value)
        try:
            role = await guild.create_role(
                name=role_name,
                colour=discord.Colour(color_value) if color_value is not None else discord.Colour.default(),
                reason=f"Booster role created by {self.requester}"
            )
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to create roles.", ephemeral=True)
            return
        except Exception as e:
            await interaction.response.send_message(f"Failed to create role: {e}", ephemeral=True)
            return

        # try assign to requester
        try:
            await self.requester.add_roles(role, reason="Booster role assignment")
        except Exception:
            pass

        # Acknowledge
        await interaction.response.send_message(f"✅ Created role {role.mention} and assigned to you!", ephemeral=True)

class BoosterStartView(View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=300)
        self.guild = guild

    @discord.ui.button(label="Start", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        roles_cfg = await db.get_roles()
        booster_role_id = roles_cfg.get("booster")
        if not booster_role_id:
            await interaction.response.send_message("Booster role not configured. Ask an admin to run /setup_roles.", ephemeral=True)
            return
        # user gate
        booster_role = interaction.guild.get_role(booster_role_id)
        if not booster_role or booster_role not in interaction.user.roles:
            await interaction.response.send_message("You must have the booster role to create a custom role.", ephemeral=True)
            return
        # open modal
        await interaction.response.send_modal(BoosterRoleModal(interaction.user))

class BoosterRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="makerole", description="Open booster role creation flow")
    async def makerole(self, ctx: discord.ApplicationContext):
        # Only admins can post the start panel
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission to post this.", ephemeral=True)
            return
        embed = discord.Embed(
            title="✨ Booster Role Creator",
            description=(
                "Press Start to design your role. You'll be asked for:\n"
                "• Role name\n"
                "• Hex color (e.g., #FF66CC)\n"
                "• Optional emoji/badge URL\n\n"
                "Note: You must have the booster role to proceed."
            ),
            color=ACCENT,
        )
        await ctx.respond(embed=embed, view=BoosterStartView(ctx.guild))


def setup(bot):
    bot.add_cog(BoosterRoles(bot))
