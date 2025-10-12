import discord
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, InputText
import logging
from points import PointsModule
from database import db
from datetime import datetime
from io import StringIO

# ---------- DEFAULTS ----------
DEFAULT_POINT_VALUES = {
    "Ultra Speaker Express": 8,
    "Ultra Gramiel Express": 7,
    "4-Man Ultra Daily Express": 4,
    "7-Man Ultra Daily Express": 10,
    "Ultra Weekly Express": 12,
    "Grim Express": 10,
    "Daily Temple Express": 6,
}
DEFAULT_HELPER_SLOTS = {"7-Man Ultra Daily Express": 6, "Grim Express": 6}
DEFAULT_SLOTS = 3
DEFAULT_QUESTIONS = ["In-game name?*", "Server name?*", "Room number?*", "Anything else?"]

def get_fallback_category(category_name: str):
    return {
        "name": category_name,
        "questions": DEFAULT_QUESTIONS,
        "points": DEFAULT_POINT_VALUES.get(category_name, 0),
        "slots": DEFAULT_HELPER_SLOTS.get(category_name, DEFAULT_SLOTS),
    }

def parse_question_required(label: str):
    raw = label.strip()
    required = raw.endswith("*") or raw.startswith("*") or raw.lower().endswith("(required)")
    cleaned = raw.strip("* ")
    if cleaned.lower().endswith("(required)"):
        cleaned = cleaned[: -len("(required)")].strip()
    # Enforce Discord TextInput label length limit
    if len(cleaned) > 45:
        cleaned = cleaned[:45]
    return cleaned, required

# ---------- STORAGE ----------
active_tickets = {}

# Use module-level logger for error visibility in hosting logs
logger = logging.getLogger(__name__)

# ---------- PERMISSIONS ----------
def bot_can_manage_channels(interaction: discord.Interaction) -> bool:
    """
    Prefer interaction.app_permissions; fall back to guild.me.
    """
    perms = getattr(interaction, "app_permissions", None)
    if perms is not None:
        return bool(getattr(perms, "administrator", False) or getattr(perms, "manage_channels", False))
    me = interaction.guild.me if interaction.guild else None
    if not me or not getattr(me, "guild_permissions", None):
        return False
    gp = me.guild_permissions
    return bool(getattr(gp, "administrator", False) or getattr(gp, "manage_channels", False))

# ---------- UTILITY ----------
async def generate_ticket_transcript(ticket_info, rewarded=False):
    channel = ticket_info["embed_msg"].channel
    transcript_lines = []
    async for msg in channel.history(limit=100, oldest_first=True):
        content = msg.content or ""
        transcript_lines.append(f"[{msg.created_at}] {msg.author}: {content}")

    transcript_text = (
        f"Ticket Transcript for {ticket_info['category']}\n"
        f"Requestor: <@{ticket_info['requestor']}>\n"
        f"Helpers: {', '.join(f'<@{h}>' for h in ticket_info['helpers'] if h)}\n"
        f"Opened at: {channel.created_at}\n"
        f"Closed at: {datetime.utcnow()}\n"
        f"Rewarded: {'Yes' if rewarded else 'No'}\n\n"
        + "\n".join(transcript_lines)
    )

    embed = discord.Embed(
        title="Ticket Transcript",
        description=f"Category: **{ticket_info['category']}**",
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="Info",
        value=(
            f"Requestor: <@{ticket_info['requestor']}>\n"
            f"Helpers: {', '.join(f'<@{h}>' for h in ticket_info['helpers'] if h) or 'None'}\n"
            f"Opened: {channel.created_at}\n"
            f"Closed: {datetime.utcnow()}\n"
            f"Rewarded: {'Yes' if rewarded else 'No'}"
        ),
        inline=False,
    )

    if transcript_lines:
        snippet = "\n".join(transcript_lines[-30:])
        if len(snippet) > 1000:
            snippet = snippet[-1000:]
        embed.add_field(name="Messages (recent)", value=f"```\n{snippet}\n```", inline=False)

    transcript_channel_id = await db.get_transcript_channel()
    if transcript_channel_id:
        guild = channel.guild
        transcript_channel = guild.get_channel(transcript_channel_id)
        if transcript_channel:
            file = discord.File(StringIO(transcript_text), filename=f"transcript-{channel.name}.txt")
            await transcript_channel.send(embed=embed, file=file)

# ---------- TICKET MODAL ----------
class TicketModal(Modal):
    def __init__(self, category, questions, requestor_id, slots):
        super().__init__(title=f"{category} Ticket")
        self.category = category
        self.requestor_id = requestor_id
        self.slots = slots
        self.inputs = []
        for q in (questions or [])[:5]:
            label, required = parse_question_required(q)
            ti = InputText(label=label, style=discord.InputTextStyle.long, required=required)
            self.add_item(ti)
            self.inputs.append(ti)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        # Always try to defer quickly and ephemerally to avoid 3s timeouts
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

        try:
            if not bot_can_manage_channels(interaction):
                await interaction.followup.send(
                    "I need the 'Manage Channels' permission to create your ticket. Please ask an admin to grant it.",
                    ephemeral=True,
                )
                return

            try:
                number = await db.increment_ticket_number(self.category)
            except Exception:
                number = 1
            channel_name = f"{self.category.lower().replace(' ', '-')}-{number}"

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            }

            parent_category = None
            try:
                cat_id = await db.get_ticket_category()
                cand = guild.get_channel(cat_id) if cat_id else None
                parent_category = cand if isinstance(cand, discord.CategoryChannel) else None
            except Exception:
                parent_category = None

            ticket_channel = None
            try:
                ticket_channel = await guild.create_text_channel(
                    channel_name, overwrites=overwrites, category=parent_category,
                    reason=f"Ticket created by {interaction.user} for {self.category}",
                )
            except discord.Forbidden:
                try:
                    ticket_channel = await guild.create_text_channel(
                        channel_name, overwrites=overwrites,
                        reason=f"Ticket created by {interaction.user} (no category access)",
                    )
                except Exception as e:
                    await interaction.followup.send(f"Ticket creation failed: {e}. Please contact an admin.", ephemeral=True)
                    return
            except Exception as e:
                await interaction.followup.send(f"Ticket creation failed: {e}. Please contact an admin.", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"{self.category} Ticket #{number}",
                description=f"Requestor: {interaction.user.mention}",
                color=0x00FF00,
            )
            for ti in self.inputs:
                embed.add_field(name=ti.label, value=ti.value or "—", inline=False)
            for i in range(self.slots):
                embed.add_field(name=f"Helper Slot {i+1}", value="Empty", inline=True)

            view = TicketView(self.category, interaction.user.id)
            msg = await ticket_channel.send(embed=embed, view=view)

            active_tickets[ticket_channel.id] = {
                "category": self.category,
                "requestor": interaction.user.id,
                "helpers": [None] * self.slots,
                "embed_msg": msg,
                "closed_stage": 0,
                "rewarded": None,
            }

            await interaction.followup.send(f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)

        except Exception as e:
            # Final safeguard to surface tracebacks instead of Discord's generic error
            logger.exception("Error during ticket modal submit: %s", e)
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "⚠️ Something went wrong while processing your ticket.",
                        ephemeral=True,
                    )
                else:
                    await interaction.response.send_message(
                        "⚠️ Something went wrong while processing your ticket.",
                        ephemeral=True,
                    )
            except Exception:
                pass

    # Py-cord uses `callback` for modal submissions; keep compatibility by delegating
    async def callback(self, interaction: discord.Interaction):
        try:
            await self.on_submit(interaction)
        except Exception as e:
            logger.exception("Unhandled error in TicketModal.callback: %s", e)
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("⚠️ Unexpected error creating your ticket.", ephemeral=True)
                else:
                    await interaction.response.send_message("⚠️ Unexpected error creating your ticket.", ephemeral=True)
            except Exception:
                pass

# ---------- TICKET VIEW ----------
class TicketView(View):
    def __init__(self, category, requestor_id):
        super().__init__(timeout=None)
        self.category = category
        self.requestor_id = requestor_id
        self.add_item(Button(label="Join Ticket", style=discord.ButtonStyle.green, custom_id="join_ticket"))
        # Removed generic remove button; use /ticket_kick for explicit choice
        self.add_item(Button(label="Close Ticket", style=discord.ButtonStyle.gray, custom_id="close_ticket"))


class RewardChoiceView(View):
    def __init__(self, ticket_channel_id: int):
        super().__init__(timeout=60)
        self.ticket_channel_id = ticket_channel_id

    @discord.ui.button(label="Reward helpers", style=discord.ButtonStyle.green, custom_id="reward_yes")
    async def reward_yes(self, button: discord.ui.Button, interaction: discord.Interaction):
        ticket_info = active_tickets.get(self.ticket_channel_id)
        if not ticket_info:
            await interaction.response.send_message("Ticket context missing.", ephemeral=True)
            return
        category = ticket_info["category"]
        cat_data = await db.get_category(category)
        points_value = (cat_data or get_fallback_category(category))["points"]
        await PointsModule.reward_ticket_helpers({**ticket_info, "points": points_value})
        await generate_ticket_transcript(ticket_info, rewarded=True)
        ticket_info["rewarded"] = True
        ticket_info["closed_stage"] = 2
        await interaction.response.send_message("Helpers rewarded and transcript generated. Click Close again to delete.", ephemeral=True)

    @discord.ui.button(label="No reward", style=discord.ButtonStyle.gray, custom_id="reward_no")
    async def reward_no(self, button: discord.ui.Button, interaction: discord.Interaction):
        ticket_info = active_tickets.get(self.ticket_channel_id)
        if not ticket_info:
            await interaction.response.send_message("Ticket context missing.", ephemeral=True)
            return
        await generate_ticket_transcript(ticket_info, rewarded=False)
        ticket_info["rewarded"] = False
        ticket_info["closed_stage"] = 2
        await interaction.response.send_message("Transcript generated without rewards. Click Close again to delete.", ephemeral=True)

# ---------- SELECT MENU ----------
class TicketSelect(Select):
    def __init__(self, categories):
        options = [discord.SelectOption(label=cat["name"]) for cat in categories]
        super().__init__(placeholder="Choose ticket type...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        member_role_ids = [role.id for role in interaction.user.roles]
        roles_cfg = await db.get_roles()
        restricted_raw = roles_cfg.get("restricted", []) if roles_cfg else []
        restricted_ids = []
        for r in restricted_raw:
            try:
                restricted_ids.append(int(r))
            except Exception:
                pass
        if any(rid in member_role_ids for rid in restricted_ids):
            await interaction.response.send_message("You cannot open a ticket.", ephemeral=True)
            return

        if not bot_can_manage_channels(interaction):
            await interaction.response.send_message(
                "I need the 'Manage Channels' permission to create your ticket. Please ask an admin to grant it.",
                ephemeral=True,
            )
            return

        category_name = self.values[0]
        cat_data = await db.get_category(category_name)
        if not cat_data:
            cat_data = get_fallback_category(category_name)
        await interaction.response.send_modal(TicketModal(category_name, cat_data["questions"], interaction.user.id, cat_data["slots"]))

class TicketPanelView(View):
    def __init__(self, categories):
        super().__init__(timeout=None)
        self.add_item(TicketSelect(categories))

# ---------- COG ----------
class TicketModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="panel", description="Deploy ticket panel (staff/admin only)")
    async def panel(self, ctx: discord.ApplicationContext):
        roles_cfg = await db.get_roles()
        staff_role_id = roles_cfg.get("staff")
        admin_role_id = roles_cfg.get("admin")
        is_allowed = ctx.user.guild_permissions.administrator
        if admin_role_id:
            is_allowed = is_allowed or any(r.id == admin_role_id for r in ctx.user.roles)
        if staff_role_id:
            is_allowed = is_allowed or any(r.id == staff_role_id for r in ctx.user.roles)
        if not is_allowed:
            await ctx.respond("You don't have permission to deploy ticket panel.", ephemeral=True)
            return

        if not ctx.guild.me.guild_permissions.manage_channels:
            await ctx.respond(
                "I need the 'Manage Channels' permission to create ticket channels. Please grant it and try again.",
                ephemeral=True,
            )
            return

        maintenance = await db.get_maintenance()
        if maintenance.get("enabled"):
            await ctx.respond(maintenance.get("message", "Tickets are disabled."), ephemeral=True)
            return

        categories = await db.get_categories()
        if not categories:
            categories = [{
                "name": name,
                "questions": DEFAULT_QUESTIONS,
                "points": pts,
                "slots": DEFAULT_HELPER_SLOTS.get(name, DEFAULT_SLOTS),
            } for name, pts in DEFAULT_POINT_VALUES.items()]
        panel_cfg = await db.get_panel_config()
        view = TicketPanelView(categories)
        embed = discord.Embed(
            title="🎮 In-game Assistance",
            description=panel_cfg.get("text", "Select a service below to create a help ticket. Our helpers will assist you!"),
            color=panel_cfg.get("color", 0x5865F2),
        )
        services = [f"- **{cat['name']}** — {cat.get('points', 0)} points" for cat in categories]
        embed.add_field(name="📋 Available Services", value="**" + ("\n".join(services) or "No services configured") + "**", inline=False)
        embed.add_field(
            name="ℹ️ How it works",
            value="1. Select a service\n2. Fill out the form\n3. Helpers join\n4. Get help in your private ticket!",
            inline=False,
        )
        await ctx.respond(embed=embed, view=view)

    @commands.slash_command(name="ticket_kick", description="Remove a user from ticket embed; optionally from channel")
    async def ticket_kick(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.Member, "Member to remove from this ticket"),
        from_channel: discord.Option(bool, "Also remove channel access?", required=False, default=False)
    ):
        roles_cfg = await db.get_roles()
        staff_role_id = roles_cfg.get("staff")
        admin_role_id = roles_cfg.get("admin")
        is_staff = ctx.user.guild_permissions.administrator
        if admin_role_id:
            is_staff = is_staff or any(r.id == admin_role_id for r in ctx.user.roles)
        if staff_role_id:
            is_staff = is_staff or any(r.id == staff_role_id for r in ctx.user.roles)
        if not is_staff:
            await ctx.respond("Only staff/admin can run this.", ephemeral=True)
            return

        channel_id = ctx.channel.id
        ticket_info = active_tickets.get(channel_id)
        if not ticket_info:
            await ctx.respond("This channel is not a ticket.", ephemeral=True)
            return

        # Update helpers list and embed
        changed = False
        for i in range(len(ticket_info["helpers"])):
            if ticket_info["helpers"][i] == user.id:
                ticket_info["helpers"][i] = None
                changed = True
                break

        if from_channel:
            try:
                await ctx.channel.set_permissions(user, view_channel=False, send_messages=False)
            except Exception:
                pass

        if changed:
            try:
                embed = ticket_info["embed_msg"].embeds[0]
                base_index = len(embed.fields) - len(ticket_info["helpers"])
                for i, helper_id in enumerate(ticket_info["helpers"]):
                    value = f"<@{helper_id}>" if helper_id else "Empty"
                    embed.set_field_at(base_index + i, name=f"Helper Slot {i+1}", value=value, inline=True)
                await ticket_info["embed_msg"].edit(embed=embed)
            except Exception:
                pass

        where = "embed only" if not from_channel else "embed and channel"
        await ctx.respond(f"Removed {user.mention} from this ticket ({where}).", ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        channel_id = interaction.channel.id
        ticket_info = active_tickets.get(channel_id)
        if not ticket_info:
            return

        custom_id = interaction.data["custom_id"]

        if custom_id == "join_ticket":
            if interaction.user.id == ticket_info["requestor"]:
                await interaction.response.send_message("You cannot join your own ticket.", ephemeral=True)
                return
            # Block users with restricted roles from joining
            roles_cfg = await db.get_roles()
            restricted_ids = roles_cfg.get("restricted", []) if roles_cfg else []
            member_role_ids = [r.id for r in interaction.user.roles]
            if any(rid in member_role_ids for rid in restricted_ids):
                await interaction.response.send_message("You cannot join this ticket.", ephemeral=True)
                return
            for i in range(len(ticket_info["helpers"])):
                if ticket_info["helpers"][i] is None:
                    ticket_info["helpers"][i] = interaction.user.id
                    break
            try:
                await interaction.channel.set_permissions(interaction.user, view_channel=True, send_messages=True)
            except Exception:
                pass
            embed = ticket_info["embed_msg"].embeds[0]
            base_index = len(embed.fields) - len(ticket_info["helpers"])
            for i, helper_id in enumerate(ticket_info["helpers"]):
                value = f"<@{helper_id}>" if helper_id else "Empty"
                embed.set_field_at(base_index + i, name=f"Helper Slot {i+1}", value=value, inline=True)
            await ticket_info["embed_msg"].edit(embed=embed)
            await interaction.response.send_message("You joined the ticket!", ephemeral=True)

        elif custom_id == "remove_helper":
            # Deprecated path; instruct to use /ticket_kick for explicit choice
            await interaction.response.send_message("Use /ticket_kick to remove a specific member.", ephemeral=True)
            return

        elif custom_id == "close_ticket":
            roles_cfg = await db.get_roles()
            staff_role_id = roles_cfg.get("staff")
            admin_role_id = roles_cfg.get("admin")
            is_staff = interaction.user.guild_permissions.administrator
            if admin_role_id:
                is_staff = is_staff or any(r.id == admin_role_id for r in interaction.user.roles)
            if staff_role_id:
                is_staff = is_staff or any(r.id == staff_role_id for r in interaction.user.roles)
            if not is_staff:
                await interaction.response.send_message("Only staff/admin can close ticket.", ephemeral=True)
                return
            stage = ticket_info.get("closed_stage", 0)
            if stage == 0:
                # 1st close: only remove helpers' channel access; keep embed and helpers list
                helpers = [h for h in ticket_info["helpers"] if h]
                for uid in helpers:
                    member = interaction.guild.get_member(uid)
                    try:
                        if member:
                            await interaction.channel.set_permissions(member, view_channel=False, send_messages=False)
                    except Exception:
                        pass
                ticket_info["closed_stage"] = 1
                await interaction.response.send_message("Helpers removed from channel. Click again to choose reward.", ephemeral=True)
            elif stage == 1:
                # 2nd close: prompt reward/no reward
                view = RewardChoiceView(interaction.channel.id)
                await interaction.response.send_message("Reward helpers?", view=view, ephemeral=True)
            else:
                # 3rd close: delete channel (transcript should be generated on stage 2)
                await interaction.response.send_message("Deleting ticket channel...", ephemeral=True)
                active_tickets.pop(channel_id, None)
                try:
                    await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
                except Exception:
                    pass

def setup(bot):
    bot.add_cog(TicketModule(bot))