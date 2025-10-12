import discord
from discord.ext import commands
from database import db

class SetupModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
        restricted_ids = [int(r.strip()) for r in (restricted or "").split(",") if r and r.strip().isdigit()] if restricted else []
        await db.set_roles(admin.id, staff.id, helper.id, restricted_ids)
        await ctx.respond("✅ Roles configuration updated!")

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

    @commands.slash_command(name="setup_audit_channel", description="Set audit log channel (Admin only)")
    async def setup_audit_channel(
        self, ctx: discord.ApplicationContext,
        channel: discord.Option(discord.TextChannel, "Select audit log channel")
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You are not allowed to run this.", ephemeral=True)
            return
        await db.save_config("audit_channel", {"id": channel.id})
        await ctx.respond(f"✅ Audit channel set to {channel.mention}")

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
        await ctx.respond(embed=embed, ephemeral=True)

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
        cursor_deleted = await db.remove_category(name)
        if cursor_deleted:
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

def setup(bot):
    bot.add_cog(SetupModule(bot))