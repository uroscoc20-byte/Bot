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
DEFAULT_QUESTIONS = ["In-game name?*", "Server name?*", "Room?*", "Anything else?"]

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
    if len(cleaned) > 45:
        cleaned = cleaned[:45]
    return cleaned, required

# ---------- STORAGE ----------
active_tickets = {}
logger = logging.getLogger(__name__)

# ---------- PERMISSIONS ----------
def bot_can_manage_channels(interaction: discord.Interaction) -> bool:
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
        title="📝 Ticket Transcript",
        description=f"Category: **{ticket_info['category']}**",
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="ℹ️ Info",
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
        embed.add_field(name="💬 Messages (recent)", value=f"```\n{snippet}\n```", inline=False)

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
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
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
                title=f"🎫 {self.category} Ticket #{number}",
                description=f"Requester: **{interaction.user.mention}**",
                color=0x00FF00,
            )
            embed.timestamp = datetime.utcnow()

            # Collect answers for later ephemeral display to helpers
            form_answers: dict[str, str] = {}
            for ti in self.inputs:
                label_clean = (ti.label or "").strip()
                value_text = (ti.value or "—").strip() or "—"
                label_lower = label_clean.lower()

                # Map known fields to canonical keys
                if label_lower.startswith("in-game name") or label_lower.startswith("in game name"):
                    form_answers["in_game_name"] = value_text
                elif label_lower.startswith("server name"):
                    form_answers["server_name"] = value_text
                elif label_lower.startswith("room"):
                    form_answers["room"] = value_text
                elif label_lower.startswith("anything else"):
                    form_answers["anything_else"] = value_text
                else:
                    # Fallback for any additional custom questions
                    form_answers[label_lower] = value_text

                # Show all fields on embed except "Room" which should be hidden until joining
                if label_lower.startswith("room"):
                    embed.add_field(name=label_clean, value="Revealed after joining", inline=False)
                else:
                    embed.add_field(name=label_clean, value=value_text, inline=False)

            # Add helper slots
            for i in range(self.slots):
                embed.add_field(name=f"👤 Helper Slot {i+1}", value="Empty", inline=True)

            roles_cfg = await db.get_roles()
            helper_role_id = roles_cfg.get("helper") if roles_cfg else None
            staff_role_id = roles_cfg.get("staff") if roles_cfg else None
            admin_role_id = roles_cfg.get("admin") if roles_cfg else None
            helper_role = guild.get_role(helper_role_id) if helper_role_id else None
            staff_role = guild.get_role(staff_role_id) if staff_role_id else None
            admin_role = guild.get_role(admin_role_id) if admin_role_id else None

            try:
                if helper_role:
                    await ticket_channel.set_permissions(
                        helper_role,
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        attach_files=True,
                    )
                if staff_role:
                    await ticket_channel.set_permissions(
                        staff_role,
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        manage_messages=True,
                        attach_files=True,
                    )
                if admin_role:
                    await ticket_channel.set_permissions(
                        admin_role,
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        manage_messages=True,
                        manage_channels=True,
                        attach_files=True,
                    )
            except Exception:
                pass

            view = TicketView(self.category, interaction.user.id)
            mention_text = helper_role.mention if helper_role else ""
            allowed = None
            if helper_role:
                try:
                    allowed = discord.AllowedMentions(roles=[helper_role])
                except Exception:
                    allowed = None
            msg = await ticket_channel.send(content=mention_text, embed=embed, view=view, allowed_mentions=allowed)
            try:
                await msg.pin(reason="Pin ticket for visibility")
            except Exception:
                pass

            active_tickets[ticket_channel.id] = {
                "category": self.category,
                "requestor": interaction.user.id,
                "helpers": [None] * self.slots,
                "embed_msg": msg,
                "closed_stage": 0,
                "rewarded": None,
                "answers": form_answers,
            }

            await interaction.followup.send(f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)

        except Exception as e:
            logger.exception("Error during ticket modal submit: %s", e)
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("⚠️ Something went wrong while processing your ticket.", ephemeral=True)
                else:
                    await interaction.response.send_message("⚠️ Something went wrong while processing your ticket.", ephemeral=True)
            except Exception:
                pass

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
        self.add_item(Button(label="Join", style=discord.ButtonStyle.green, custom_id="join_ticket", emoji="➕"))
        self.add_item(Button(label="Close", style=discord.ButtonStyle.gray, custom_id="close_ticket", emoji="🧹"))

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
        # Create a button per category instead of a select menu
        for cat in categories[:25]:  # Discord max 25 buttons per view
            label = cat.get("name", "Category")
            custom_id = f"open_ticket::{label}"
            self.add_item(Button(label=label, style=discord.ButtonStyle.blurple, custom_id=custom_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    async def on_timeout(self):
        pass

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
                "points": DEFAULT_POINT_VALUES[name],
                "slots": DEFAULT_HELPER_SLOTS.get(name, DEFAULT_SLOTS),
            } for name in DEFAULT_POINT_VALUES.keys()]
        panel_cfg = await db.get_panel_config()
        view = TicketPanelView(categories)
        embed = discord.Embed(
            title="🎮 IN-GAME ASSISTANCE 🎮",
            description=panel_cfg.get("text", "Select a service below to create a help ticket. Our helpers will assist you!"),
            color=panel_cfg.get("color", 0x5865F2),
        )
        # Custom panel content per request
        embed.clear_fields()
        embed.description = (
            "## Ticket types\n"
            "**GrimChallenge Express**\n"
            "- Mechabinky & Raxborg 2.0\n"
            "**UltraSpeaker Express**\n"
            "- The First Speaker\n"
            "**Weekly Ultra Express**\n"
            "- Weekly Ultra Bosses\n"
            "  - Darkon, Drakath, Dage, Nulgath, Drago\n"
            "**Daily 7-Man Express**\n"
            "- Daily 7-Man Ultra Bosses\n"
            "  - Astralshrine, KathoolDepths, Originul, ApexAzalith, Lich Lord/Beast/Deimos (Daily Exercises 2 through 4), Lavarockshore\n"
            "**Daily 4-Man Express**\n"
            "- Daily 4-Man Ultra Bosses\n"
            "  - Ezrajal, Warden, Engineer, Tyndarius, Dage (Daily Exercise 6), Iara, Kala\n"
            "**Daily Temple Express**\n"
            "- Daily TempleShrine\n"
            "  - Left Dungeon, Right Dungeon, Middle Dungeon\n"
            "**Ultra Gramiel Express**\n"
            "- Ultra Gramiel\n\n"
            "## ℹ️ How it works\n"
            "- Select a \"ticket type\"\n"
            "- Fill out the form\n"
            "- Helpers join\n"
            "- Get help in your private ticket"
        )
        embed.clear_fields()
        embed.description = (
            "## Ticket types\n"
            "**GrimChallenge Express**\n"
            "- Mechabinky & Raxborg 2.0\n"
            "**UltraSpeaker Express**\n"
            "- The First Speaker\n"
            "**Weekly Ultra Express**\n"
            "- Weekly Ultra Bosses\n"
            "  - Darkon, Drakath, Dage, Nulgath, Drago\n"
            "**Daily 7-Man Express**\n"
            "- Daily 7-Man Ultra Bosses\n"
            "  - Astralshrine, KathoolDepths, Originul, ApexAzalith, Lich Lord/Beast/Deimos (Daily Exercises 2 through 4), Lavarockshore\n"
            "**Daily 4-Man Express**\n"
            "- Daily 4-Man Ultra Bosses\n"
            "  - Ezrajal, Warden, Engineer, Tyndarius, Dage (Daily Exercise 6), Iara, Kala\n"
            "**Daily Temple Express**\n"
            "- Daily TempleShrine\n"
            "  - Left Dungeon, Right Dungeon, Middle Dungeon\n"
            "**Ultra Gramiel Express**\n"
            "- Ultra Gramiel\n\n"
            "## ℹ️ How it works\n"
            "- Select a \"ticket type\"\n"
            "- Fill out the form\n"
            "- Helpers join\n"
            "- Get help in your private ticket"
        )
        message = await ctx.respond(embed=embed, view=view)
        
        # Save to database for persistence
        if hasattr(message, 'message'):
            message = message.message
        
        panel_data = {
            "categories": categories,
            "panel_config": panel_cfg,
            "panel_type": "ticket"
        }
        await db.save_persistent_panel(
            channel_id=ctx.channel.id,
            message_id=message.id,
            panel_type="ticket",
            data=panel_data
        )
        
        await ctx.followup.send("✅ **Persistent ticket panel created!** It will auto-refresh every 10 minutes.", ephemeral=True)

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
        # Panel buttons are outside ticket channels

        custom_id = interaction.data["custom_id"]

        # Handle panel category buttons
        if custom_id.startswith("open_ticket::"):
            category_name = custom_id.split("::", 1)[1]
            cat_data = await db.get_category(category_name)
            if not cat_data:
                cat_data = get_fallback_category(category_name)
            await interaction.response.send_modal(TicketModal(category_name, cat_data["questions"], interaction.user.id, cat_data["slots"]))
            return

        if not ticket_info:
            return
        if custom_id == "join_ticket":
            if interaction.user.id == ticket_info["requestor"]:
                await interaction.response.send_message("You cannot join your own ticket.", ephemeral=True)
                return
            roles_cfg = await db.get_roles()
            restricted_ids = roles_cfg.get("restricted", []) if roles_cfg else []
            member_role_ids = [r.id for r in interaction.user.roles]
            if any(rid in member_role_ids for rid in restricted_ids):
                await interaction.response.send_message("You cannot join this ticket.", ephemeral=True)
                return
            # Prevent duplicate joins and enforce capacity
            if interaction.user.id in [h for h in ticket_info["helpers"] if h]:
                await interaction.response.send_message("You are already listed as a helper on this ticket.", ephemeral=True)
                return
            if all(h is not None for h in ticket_info["helpers"]):
                await interaction.response.send_message("This ticket is full. No helper slots left.", ephemeral=True)
                return
            for i in range(len(ticket_info["helpers"])):
                if ticket_info["helpers"][i] is None:
                    ticket_info["helpers"][i] = interaction.user.id
                    break
            try:
                await interaction.channel.set_permissions(interaction.user, view_channel=True, send_messages=True)
            except Exception:
                pass
            try:
                embed = ticket_info["embed_msg"].embeds[0]
                base_index = len(embed.fields) - len(ticket_info["helpers"])
                for i, helper_id in enumerate(ticket_info["helpers"]):
                    value = f"<@{helper_id}>" if helper_id else "Empty"
                    embed.set_field_at(base_index + i, name=f"Helper Slot {i+1}", value=value, inline=True)
                await ticket_info["embed_msg"].edit(embed=embed)
            except Exception:
                pass

            # Send ephemeral details to the joining helper, including hidden fields like Room
            details = ticket_info.get("answers", {}) or {}
            in_game = details.get("in_game_name", "—")
            server_name = details.get("server_name", "—")
            room = details.get("room", "—")
            anything_else = details.get("anything_else", "—")
            category = ticket_info.get("category", "—")
            requestor_id = ticket_info.get("requestor")
            requester_text = f"<@{requestor_id}>" if requestor_id else "—"

            try:
                priv = discord.Embed(
                    title=f"Ticket details (private) — {category}",
                    color=discord.Color.blurple(),
                )
                priv.add_field(name="Requester", value=requester_text, inline=False)
                priv.add_field(name="In‑game name", value=in_game, inline=True)
                priv.add_field(name="Server name", value=server_name, inline=True)
                priv.add_field(name="Room", value=room, inline=False)
                if anything_else and anything_else != "—":
                    # Keep this not inline to allow longer text
                    priv.add_field(name="Anything else", value=anything_else[:1024], inline=False)
                await interaction.response.send_message(embed=priv, ephemeral=True)
            except Exception:
                # Fallback to plain text ephemeral
                text_lines = [
                    f"Requester: {requester_text}",
                    f"In-game name: {in_game}",
                    f"Server name: {server_name}",
                    f"Room: {room}",
                ]
                if anything_else and anything_else != "—":
                    text_lines.append(f"Anything else: {anything_else}")
                await interaction.response.send_message("\n".join(text_lines), ephemeral=True)

        elif custom_id == "remove_helper":
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
            is_requestor = interaction.user.id == ticket_info["requestor"]
            if not (is_staff or is_requestor):
                await interaction.response.send_message("Only staff, admins, or the requestor can close this ticket.", ephemeral=True)
                return
            stage = ticket_info.get("closed_stage", 0)
            if stage == 0:
                # 1st close: remove helpers and requestor access; keep staff/admin only
                helpers = [h for h in ticket_info["helpers"] if h]
                # Revoke helper role view access for the channel
                helper_role_id = roles_cfg.get("helper") if roles_cfg else None
                if helper_role_id:
                    helper_role = interaction.guild.get_role(helper_role_id)
                    if helper_role:
                        try:
                            await interaction.channel.set_permissions(helper_role, view_channel=False, send_messages=False)
                        except Exception:
                            pass
                # Revoke per-user access for non-staff/non-admin helpers
                staff_role_id = roles_cfg.get("staff") if roles_cfg else None
                admin_role_id = roles_cfg.get("admin") if roles_cfg else None
                for uid in helpers:
                    member = interaction.guild.get_member(uid)
                    if not member:
                        continue
                    try:
                        is_admin = bool(admin_role_id and any(r.id == admin_role_id for r in member.roles))
                        is_staff_member = bool(staff_role_id and any(r.id == staff_role_id for r in member.roles))
                        if not (is_admin or is_staff_member):
                            await interaction.channel.set_permissions(member, view_channel=False, send_messages=False)
                    except Exception:
                        pass
                # Revoke requestor access too
                try:
                    requestor_member = interaction.guild.get_member(ticket_info["requestor"]) if ticket_info.get("requestor") else None
                    if requestor_member:
                        await interaction.channel.set_permissions(requestor_member, view_channel=False, send_messages=False)
                except Exception:
                    pass
                ticket_info["closed_stage"] = 1
                await interaction.response.send_message("Helpers removed from channel. Click again to choose reward.", ephemeral=True)
            elif stage == 1:
                # Only staff/admin can decide rewards
                roles_cfg = await db.get_roles()
                staff_role_id = roles_cfg.get("staff") if roles_cfg else None
                admin_role_id = roles_cfg.get("admin") if roles_cfg else None
                is_staff = interaction.user.guild_permissions.administrator
                if admin_role_id:
                    is_staff = is_staff or any(r.id == admin_role_id for r in interaction.user.roles)
                if staff_role_id:
                    is_staff = is_staff or any(r.id == staff_role_id for r in interaction.user.roles)
                if not is_staff:
                    await interaction.response.send_message("Only staff/admin can decide rewards.", ephemeral=True)
                    return
                # Prevent double reward prompt if already decided
                if ticket_info.get("rewarded") is not None:
                    await interaction.response.send_message("Reward decision already made.", ephemeral=True)
                    return
                view = RewardChoiceView(interaction.channel.id)
                await interaction.response.send_message("Reward helpers?", view=view, ephemeral=True)
            else:
                await interaction.response.send_message("Deleting ticket channel...", ephemeral=True)
                active_tickets.pop(channel_id, None)
                try:
                    await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
                except Exception:
                    pass

def setup(bot):
    bot.add_cog(TicketModule(bot))