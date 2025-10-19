# verification.py
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, InputText
from datetime import datetime
from database import db

VERIFICATION_TEXT = (
    "Welcome to the server!\n"
    "To gain access, please complete the short verification process below.\n\n"
    "Click Verify and provide the following information:\n\n"
    "- In-Game Name – The name you use in the game.\n\n"
    "- Who Invited You – The name of the person who invited you to the server (if anyone).\n\n"
    "⚠️ Please make sure the information is accurate and complete.\n"
    "Once submitted, a staff member will review your verification and grant access as soon as possible."
)


class VerificationTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, custom_id="verify_close", emoji="🗑️")
    async def close_btn(self, button: discord.ui.Button, interaction: discord.Interaction):
        roles = await db.get_roles()
        staff_id = roles.get("staff") if roles else None
        admin_id = roles.get("admin") if roles else None
        is_admin = admin_id and any(r.id == admin_id for r in interaction.user.roles)
        is_staff = interaction.user.guild_permissions.administrator or (staff_id and any(r.id == staff_id for r in interaction.user.roles))
        if not (is_admin or is_staff):
            await interaction.response.send_message("Only staff/admin can close verification tickets.", ephemeral=True)
            return
        await interaction.response.send_message("Deleting verification channel...", ephemeral=True)
        try:
            await interaction.channel.delete(reason=f"Verification closed by {interaction.user}")
        except Exception:
            pass


class VerificationModal(Modal):
    def __init__(self, category_id: int | None):
        super().__init__(title="Verification Ticket")
        self.category_id = category_id
        self.add_item(InputText(label="In-game name?", required=True))
        self.add_item(InputText(label="Invited by?", required=False))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            return

        parent_category = None
        cat_id = self.category_id
        if not cat_id:
            cfg = await db.load_config("verification_category")
            cat_id = (cfg or {}).get("id")
        if cat_id:
            cand = guild.get_channel(int(cat_id))
            parent_category = cand if isinstance(cand, discord.CategoryChannel) else None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        roles = await db.get_roles()
        staff_role = guild.get_role(roles.get("staff")) if roles else None
        admin_role = guild.get_role(roles.get("admin")) if roles else None
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True)
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True, manage_channels=True)

        safe_name = f"verify-{interaction.user.name}".lower().replace(" ", "-")
        try:
            ch = await guild.create_text_channel(
                name=safe_name[:90],
                category=parent_category,
                overwrites=overwrites,
                reason=f"Verification ticket for {interaction.user}",
            )
        except Exception as e:
            await interaction.followup.send(f"Could not create verification channel: {e}", ephemeral=True)
            return

        in_game = self.children[0].value
        invited_by = self.children[1].value or "—"
        embed = discord.Embed(
            title="Verification Request",
            description=f"Requester: {interaction.user.mention}",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="In-game name", value=in_game, inline=False)
        embed.add_field(name="Invited by", value=invited_by, inline=False)

        mention = f"{interaction.user.mention} {staff_role.mention if staff_role else (admin_role.mention if admin_role else '')}"
        msg = await ch.send(content=mention, embed=embed, view=VerificationTicketView())
        try:
            await msg.pin()
        except Exception:
            pass

        await interaction.followup.send(f"✅ Verification ticket created: {ch.mention}", ephemeral=True)


class VerificationPanelView(View):
    def __init__(self, category_id: int | None):
        super().__init__(timeout=None)
        self.category_id = category_id

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.green, custom_id="verify_open", emoji="✅")
    async def verify_open(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(VerificationModal(self.category_id))


class VerificationModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="verification_panel", description="Post verification panel (Admin/Staff).")
    async def verification_panel(
        self,
        ctx: discord.ApplicationContext,
        category: discord.Option(discord.CategoryChannel, "Category for verification tickets", required=False)
    ):
        roles = await db.get_roles()
        staff_id = roles.get("staff") if roles else None
        is_allowed = ctx.user.guild_permissions.administrator or (staff_id and any(r.id == staff_id for r in ctx.user.roles))
        if not is_allowed:
            await ctx.respond("You don't have permission to post the verification panel.", ephemeral=True)
            return

        category_id = int(category.id) if category else None
        if category_id:
            await db.save_config("verification_category", {"id": category_id})
        else:
            cfg = await db.load_config("verification_category")
            category_id = (cfg or {}).get("id")

        embed = discord.Embed(
            title="🛡️ VERIFICATION PANEL 🛡️",
            description=VERIFICATION_TEXT,
            color=discord.Color.green(),
        )
        view = VerificationPanelView(category_id)
        message = await ctx.respond(embed=embed, view=view)
        
        # Save to database for persistence
        if hasattr(message, 'message'):
            message = message.message
        
        panel_data = {
            "category_id": category_id,
            "panel_type": "verification"
        }
        await db.save_persistent_panel(
            channel_id=ctx.channel.id,
            message_id=message.id,
            panel_type="verification",
            data=panel_data
        )
        
        await ctx.followup.send("✅ **Persistent verification panel created!** It will auto-refresh every 10 minutes.", ephemeral=True)

def setup(bot):
    bot.add_cog(VerificationModule(bot))