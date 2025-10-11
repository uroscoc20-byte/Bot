import discord
from discord.ext import commands
from database import db

# ---------- COG ----------
class SetupModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- Roles Setup ----------
    @commands.slash_command(name="setup_roles", description="Configure bot roles (Admin only)")
    async def setup_roles(
        self, ctx: discord.ApplicationContext,
        admin: discord.Option(discord.Role, "Admin role"),
        staff: discord.Option(discord.Role, "Staff role"),
        helper: discord.Option(discord.Role, "Helper role"),
        restricted: discord.Option(str, "Restricted role IDs comma-separated", required=False)
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You are not allowed to run this.", ephemeral=True)
            return

        restricted_ids = [int(r.strip()) for r in restricted.split(",")] if restricted else []
        await db.set_roles(admin.id, staff.id, helper.id, restricted_ids)
        await ctx.respond("✅ Roles configuration updated!")

    # ---------- Transcript Channel ----------
    @commands.slash_command(name="setup_transcript", description="Set transcript channel (Admin only)")
    async def setup_transcript(
        self, ctx: discord.ApplicationContext,
        channel: discord.Option(discord.TextChannel, "Select transcript channel")
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You are not allowed to run this.", ephemeral=True)
            return
        await db.set_transcript_channel(channel.id)
        await ctx.respond(f"✅ Transcript channel set to {channel.mention}")

    # ---------- Ticket Category (where ticket channels are created) ----------
    @commands.slash_command(name="setup_ticket_category", description="Set Discord category for tickets (Admin only)")
    async def setup_ticket_category(
        self,
        ctx: discord.ApplicationContext,
        category: discord.Option(discord.CategoryChannel, "Select ticket parent category")
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You are not allowed to run this.", ephemeral=True)
            return
        await db.set_ticket_category(category.id)
        await ctx.respond(f"✅ Ticket category set to {category.mention}")

    # ---------- Show current roles ----------
    @commands.slash_command(name="setup_roles_show", description="Show current configured roles")
    async def setup_roles_show(self, ctx: discord.ApplicationContext):
        roles = await db.get_roles()
        guild = ctx.guild

        def fmt(role_id):
            if not role_id:
                return "Not set"
            role = guild.get_role(role_id)
            return role.mention if role else f"`{role_id}`"

        restricted_list = []
        for rid in roles.get("restricted", []) or []:
            try:
                rid_int = int(rid)
            except Exception:
                rid_int = None
            role = guild.get_role(rid_int) if rid_int else None
            restricted_list.append(role.mention if role else f"`{rid}`")
        restricted_text = ", ".join(restricted_list) if restricted_list else "None"

        embed = discord.Embed(title="🔧 Current Role Configuration", color=0x5865F2)
        embed.add_field(name="Admin Role", value=fmt(roles.get("admin")), inline=True)
        embed.add_field(name="Staff Role", value=fmt(roles.get("staff")), inline=True)
        embed.add_field(name="Helper Role", value=fmt(roles.get("helper")), inline=True)
        embed.add_field(name="Restricted Roles", value=restricted_text, inline=False)
        if roles.get("booster") is not None:
            embed.add_field(name="Booster Role", value=fmt(roles.get("booster")), inline=True)
        await ctx.respond(embed=embed, ephemeral=True)

    # ---------- Panel customization ----------
    @commands.slash_command(name="setup_panel", description="Customize ticket panel text and color (Admin only)")
    async def setup_panel(
        self,
        ctx: discord.ApplicationContext,
        text: discord.Option(str, "Panel description text", required=False),
        color: discord.Option(str, "Hex color like #5865F2", required=False)
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You are not allowed to run this.", ephemeral=True)
            return
        color_value = None
        if color:
            try:
                color_value = int(color.lstrip("#"), 16)
            except Exception:
                await ctx.respond("Invalid color. Use hex like #5865F2.", ephemeral=True)
                return
        await db.set_panel_config(text=text, color=color_value)
        await ctx.respond("✅ Panel configuration updated.")

    # ---------- Maintenance toggle ----------
    @commands.slash_command(name="setup_maintenance", description="Enable/disable ticket opening (Admin only)")
    async def setup_maintenance(
        self,
        ctx: discord.ApplicationContext,
        enabled: discord.Option(bool, "Enable maintenance (disable tickets)?"),
        message: discord.Option(str, "Message to show", required=False)
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You are not allowed to run this.", ephemeral=True)
            return
        await db.set_maintenance(enabled, message)
        await ctx.respond("✅ Maintenance settings updated.")

    # ---------- Prefix for custom text commands ----------
    @commands.slash_command(name="setup_prefix", description="Set the text prefix for custom commands (Admin only)")
    async def setup_prefix(
        self,
        ctx: discord.ApplicationContext,
        prefix: discord.Option(str, "Prefix like ! or ?")
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You are not allowed to run this.", ephemeral=True)
            return
        if not prefix or len(prefix) > 3:
            await ctx.respond("Please provide a short prefix (1-3 chars).", ephemeral=True)
            return
        await db.set_prefix(prefix)
        await ctx.respond(f"✅ Prefix set to `{prefix}`")

    # ---------- Category Setup ----------
    @commands.slash_command(name="setup_category_add", description="Add a new ticket category (Admin only)")
    async def setup_category_add(
        self, ctx: discord.ApplicationContext,
        name: discord.Option(str, "Category name"),
        questions: discord.Option(str, "Questions separated by |"),
        points: discord.Option(int, "Points for helpers"),
        slots: discord.Option(int, "Number of helper slots")
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You are not allowed to run this.", ephemeral=True)
            return
        questions_list = [q.strip() for q in questions.split("|")]
        await db.add_category(name, questions_list, points, slots)
        await ctx.respond(f"✅ Category `{name}` added with {slots} slots and {points} points.")

    @commands.slash_command(name="setup_category_remove", description="Remove a ticket category (Admin only)")
    async def setup_category_remove(
        self, ctx: discord.ApplicationContext,
        name: discord.Option(str, "Category name to remove")
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You are not allowed to run this.", ephemeral=True)
            return
        removed = await db.remove_category(name)
        if removed:
            await ctx.respond(f"✅ Category `{name}` removed.")
        else:
            await ctx.respond(f"⚠ Category `{name}` does not exist.", ephemeral=True)

    @commands.slash_command(name="setup_category_list", description="List all ticket categories")
    async def setup_category_list(self, ctx: discord.ApplicationContext):
        categories = await db.get_categories()
        if not categories:
            await ctx.respond("No categories configured.")
            return
        embed = discord.Embed(title="Ticket Categories", color=0x00FFAA)
        for cat in categories:
            questions_text = "\n".join(f"- {q}" for q in cat["questions"])
            embed.add_field(
                name=f"{cat['name']} — {cat['points']} pts — {cat['slots']} slots",
                value=questions_text,
                inline=False
            )
        await ctx.respond(embed=embed)

    # ---------- Custom Commands ----------
    @commands.slash_command(name="setup_custom_add", description="Add a custom command (Admin only)")
    async def setup_custom_add(
        self, ctx: discord.ApplicationContext,
        name: discord.Option(str, "Command name"),
        text: discord.Option(str, "Text to display"),
        image: discord.Option(str, "Optional image URL", required=False)
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You are not allowed to run this.", ephemeral=True)
            return
        await db.add_custom_command(name, text, image)
        await ctx.respond(f"✅ Custom command `{name}` added.")

    @commands.slash_command(name="setup_custom_remove", description="Remove a custom command (Admin only)")
    async def setup_custom_remove(
        self, ctx: discord.ApplicationContext,
        name: discord.Option(str, "Command name to remove")
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You are not allowed to run this.", ephemeral=True)
            return
        removed = await db.remove_custom_command(name)
        if removed:
            await ctx.respond(f"✅ Custom command `{name}` removed.")
        else:
            await ctx.respond(f"⚠ Custom command `{name}` does not exist.", ephemeral=True)

    @commands.slash_command(name="setup_custom_list", description="List all custom commands")
    async def setup_custom_list(self, ctx: discord.ApplicationContext):
        commands_list = await db.get_custom_commands()
        if not commands_list:
            await ctx.respond("No custom commands configured.")
            return
        embed = discord.Embed(title="Custom Commands", color=0xAA00FF)
        for cmd in commands_list:
            img_text = cmd["image"] if cmd["image"] else "No image"
            embed.add_field(name=cmd["name"], value=f"Text: {cmd['text']}\nImage: {img_text}", inline=False)
        await ctx.respond(embed=embed)

# ---------- SETUP ----------
def setup(bot):
    bot.add_cog(SetupModule(bot))
