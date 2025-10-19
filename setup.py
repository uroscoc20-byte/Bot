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

    @commands.slash_command(name="setup_panel", description="Customize panel text/color and auto-refresh (Admin only)")
    async def setup_panel(
        self,
        ctx: discord.ApplicationContext,
        text: discord.Option(str, "Panel description text", required=False),
        color_hex: discord.Option(str, "Color hex like #5865F2", required=False),
        auto_refresh_enabled: discord.Option(bool, "Enable periodic re-posting?", required=False),
        auto_refresh_minutes: discord.Option(int, "Minutes between refresh (>=5)", required=False),
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You are not allowed to run this.", ephemeral=True)
            return
        try:
            color_val = None
            if color_hex:
                raw = color_hex.strip().lstrip("#")
                color_val = int(raw, 16)
            if text is not None or color_val is not None:
                await db.set_panel_config(text=text, color=color_val)
            if auto_refresh_enabled is not None or auto_refresh_minutes is not None:
                minutes = max(5, (auto_refresh_minutes if auto_refresh_minutes is not None else 720))
                await db.set_panel_autorefresh(bool(auto_refresh_enabled) if auto_refresh_enabled is not None else False, minutes)
            cfg = await db.get_panel_config()
            arcfg = await db.get_panel_autorefresh()
            embed = discord.Embed(title="✅ Panel configuration updated", color=cfg.get("color", 0x5865F2))
            embed.add_field(name="Text", value=cfg.get("text") or "—", inline=False)
            embed.add_field(name="Color", value=f"#{cfg.get('color', 0x5865F2):06X}")
            embed.add_field(name="Auto-refresh", value=f"Enabled: {arcfg['enabled']} / Every {arcfg['interval_minutes']} min")
            await ctx.respond(embed=embed, ephemeral=True)
        except Exception as e:
            await ctx.respond(f"Failed to update panel settings: {e}", ephemeral=True)

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

    @commands.slash_command(name="setup_verification_category", description="Set default category for verification tickets (Admin only)")
    async def setup_verification_category(
        self,
        ctx: discord.ApplicationContext,
        category: discord.Option(discord.CategoryChannel, "Verification parent category")
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You are not allowed to run this.", ephemeral=True)
            return
        await db.save_config("verification_category", {"id": category.id})
        await ctx.respond(f"✅ Verification category set to {category.mention}")

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

def setup(bot):
    bot.add_cog(SetupModule(bot))