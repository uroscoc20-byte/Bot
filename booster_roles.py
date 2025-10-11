import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, InputText
from database import db

THEME_COLOR = 0x5865F2

class BoosterGuideView(View):
    def __init__(self, required_role_id: int | None):
        super().__init__(timeout=None)
        self.required_role_id = required_role_id
        self.add_item(StartButton(self.required_role_id))

class StartButton(Button):
    def __init__(self, required_role_id: int | None):
        super().__init__(label="Start", style=discord.ButtonStyle.primary, emoji="🚀")
        self.required_role_id = required_role_id

    async def callback(self, interaction: discord.Interaction):
        # Gate by booster role if configured
        if self.required_role_id:
            role = interaction.guild.get_role(self.required_role_id)
            if role and role not in interaction.user.roles:
                await interaction.response.send_message("❌ You don't have the required role to create a custom role.", ephemeral=True)
                return
        await interaction.response.send_modal(BoosterRoleModal())

class BoosterRoleModal(Modal):
    def __init__(self):
        super().__init__(title="Create Your Booster Role")
        self.name = InputText(label="Role name", placeholder="e.g., Super Booster", required=True, max_length=100)
        self.color = InputText(label="Hex color (e.g., #FF00AA)", required=True, max_length=7)
        self.image = InputText(label="Image URL (optional)", required=False)
        self.add_item(self.name)
        self.add_item(self.color)
        self.add_item(self.image)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.name.value.strip()
        color_str = self.color.value.strip()
        image_url = self.image.value.strip() if self.image.value else None
        try:
            color_value = int(color_str.lstrip("#"), 16)
        except Exception:
            await interaction.response.send_message("❌ Invalid color. Use a hex like #FF00AA", ephemeral=True)
            return
        try:
            new_role = await interaction.guild.create_role(name=name, colour=discord.Colour(color_value), reason=f"Custom booster role for {interaction.user}")
            # Move role just below bot's top role if possible
            try:
                me = interaction.guild.me
                bot_top = max(me.roles, key=lambda r: r.position)
                await new_role.edit(position=bot_top.position - 1)
            except Exception:
                pass
            # Optionally set image as role icon (server must be boosted enough)
            if image_url and hasattr(new_role, "edit"):
                try:
                    # role icons require Nitro/boost level; ignore failures
                    await new_role.edit(display_icon=image_url)
                except Exception:
                    pass
            # Give the role to the user
            await interaction.user.add_roles(new_role, reason="Granted custom booster role")
            embed = discord.Embed(title="🎉 Role Created", description=f"Your role `{name}` has been created!", color=THEME_COLOR)
            embed.add_field(name="Color", value=f"#{color_value:06X}")
            if image_url:
                embed.set_thumbnail(url=image_url)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to create roles.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error creating role: {e}", ephemeral=True)

class BoosterRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.required_role_id: int | None = None

    @commands.slash_command(name="booster_setup", description="Set required role for /booster_guide (Admin only)")
    async def booster_setup(self, ctx: discord.ApplicationContext, role: discord.Option(discord.Role, "Required role", required=False)):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You are not allowed to run this.", ephemeral=True)
            return
        self.required_role_id = role.id if role else None
        await ctx.respond("✅ Booster role requirement updated.")

    @commands.slash_command(name="booster_guide", description="Show booster role guide with Start button")
    async def booster_guide(self, ctx: discord.ApplicationContext):
        embed = discord.Embed(
            title="✨ Custom Booster Roles",
            description=(
                "Create your own role with a custom name and color.\n\n"
                "Press Start to begin. You'll enter:\n"
                "• Role name\n"
                "• Hex color (e.g., #FF00AA)\n"
                "• Optional image (thumbnail)\n"
            ),
            color=THEME_COLOR,
        )
        await ctx.respond(embed=embed, view=BoosterGuideView(self.required_role_id))


def setup(bot):
    bot.add_cog(BoosterRoles(bot))
