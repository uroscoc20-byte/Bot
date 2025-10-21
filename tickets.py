import discord
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, InputText
import logging
import re
from points import PointsModule
from database import db
from datetime import datetime
from io import StringIO

# Set up logger
logger = logging.getLogger(__name__)

# ---------- DEFAULTS ----------
DEFAULT_POINT_VALUES = {
    "Ultra Speaker Express": 8,
    "UltraSpeaker Express": 8,  # Match panel name
    "Ultra Gramiel Express": 7,
    "4-Man Ultra Daily Express": 4,
    "Daily 4-Man Express": 4,  # Match panel name
    "7-Man Ultra Daily Express": 10,
    "Daily 7-Man Express": 10,  # Match panel name
    "Ultra Weekly Express": 12,
    "Weekly Ultra Express": 12,  # Match panel name
    "Grim Express": 10,
    "GrimChallenge Express": 10,  # Match panel name
    "Daily Temple Express": 6,
}
DEFAULT_HELPER_SLOTS = {"Daily 7-Man Express": 6, "GrimChallenge Express": 6}
DEFAULT_SLOTS = 3
DEFAULT_QUESTIONS = ["In-game name?*", "Server name?*", "Room?*", "Anything else?"]

def get_fallback_category(category_name: str):
    points = DEFAULT_POINT_VALUES.get(category_name, 0)
    print(f"[FALLBACK DEBUG] Category: '{category_name}' -> Points: {points}")
    
    # Warn if category not found
    if points == 0 and category_name not in DEFAULT_POINT_VALUES:
        print(f"[FALLBACK DEBUG] WARNING: Category '{category_name}' not found in DEFAULT_POINT_VALUES!")
        print(f"[FALLBACK DEBUG] Available categories: {list(DEFAULT_POINT_VALUES.keys())}")
    
    return {
        "name": category_name,
        "questions": DEFAULT_QUESTIONS,
        "points": points,
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
async def generate_ticket_transcript(ticket_info, rewarded=False, closer_id=None):
    channel = ticket_info["embed_msg"].channel
    transcript_lines = []
    image_urls = []
    
    async for msg in channel.history(limit=100, oldest_first=True):
        content = msg.content or ""
        transcript_lines.append(f"[{msg.created_at}] {msg.author}: {content}")
        
        # Collect image URLs for transcript (RAM optimized - only URLs, not actual images)
        if msg.attachments:
            for attachment in msg.attachments:
                if attachment.content_type and attachment.content_type.startswith('image/'):
                    image_urls.append(f"[{msg.created_at}] {msg.author}: {attachment.url}")
        if msg.embeds:
            for embed in msg.embeds:
                if embed.image and embed.image.url:
                    image_urls.append(f"[{msg.created_at}] {msg.author}: {embed.image.url}")
                if embed.thumbnail and embed.thumbnail.url:
                    image_urls.append(f"[{msg.created_at}] {msg.author}: {embed.thumbnail.url}")

    closer_info = f"Closed by: <@{closer_id}>" if closer_id else "Closed by: Unknown"
    
    transcript_text = (
        f"Ticket Transcript for {ticket_info['category']}\n"
        f"Requestor: <@{ticket_info['requestor']}>\n"
        f"Helpers: {', '.join(f'<@{h}>' for h in ticket_info['helpers'] if h)}\n"
        f"Opened at: {channel.created_at}\n"
        f"Closed at: {datetime.utcnow()}\n"
        f"{closer_info}\n"
        f"Rewarded: {'Yes' if rewarded else 'No'}\n\n"
        + "\n".join(transcript_lines)
    )
    
    # Add image URLs section if any were found
    if image_urls:
        transcript_text += "\n\n--- IMAGES ---\n" + "\n".join(image_urls)

    embed = discord.Embed(
        title="📝 Ticket Transcript",
        description=f"Category: **{ticket_info['category']}**",
        color=discord.Color.blurple(),
    )
    closer_info = f"<@{closer_id}>" if closer_id else "Unknown"
    embed.add_field(
        name="ℹ️ Info",
        value=(
            f"Requestor: <@{ticket_info['requestor']}>\n"
            f"Helpers: {', '.join(f'<@{h}>' for h in ticket_info['helpers'] if h) or 'None'}\n"
            f"Opened: {channel.created_at}\n"
            f"Closed: {datetime.utcnow()}\n"
            f"Closed by: {closer_info}\n"
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
            
            # Send main transcript
            await transcript_channel.send(embed=embed, file=file)
            
            # Send images as separate messages for better visibility
            if image_urls:
                await transcript_channel.send("**📷 Images from this ticket:**")
                
                # Send each image as a separate message for maximum visibility
                for img_info in image_urls:
                    try:
                        # Parse timestamp and author from the stored format
                        parts = img_info.split("] ", 1)
                        if len(parts) == 2:
                            timestamp_part = parts[0] + "]"
                            author_and_url = parts[1]
                            author_part, url = author_and_url.rsplit(": ", 1)
                            
                            # Create embed for each image
                            img_embed = discord.Embed(
                                title="📷 Ticket Image",
                                description=f"**{author_part}** - {timestamp_part}",
                                color=discord.Color.blue()
                            )
                            img_embed.set_image(url=url)
                            
                            # Send each image as a separate message
                            await transcript_channel.send(embed=img_embed)
                            
                    except Exception as e:
                        logger.warning(f"Failed to send image {img_info}: {e}")
                        # Fallback: send as text with clickable link
                        await transcript_channel.send(f"📷 {img_info}")

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
                number = await db.get_global_ticket_number()
            except Exception as e:
                logger.warning(f"Failed to get global ticket number: {e}")
                number = 1
            channel_name = f"ticket-{number}"

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            }

            parent_category = None
            try:
                cat_id = await db.get_ticket_category()
                cand = guild.get_channel(cat_id) if cat_id else None
                parent_category = cand if isinstance(cand, discord.CategoryChannel) else None
            except Exception as e:
                logger.warning(f"Failed to get ticket category: {e}")
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
        self.add_item(Button(label="Close", style=discord.ButtonStyle.red, custom_id="close_ticket", emoji="🔒"))


class DeleteConfirmationView(View):
    def __init__(self, channel_id: int):
        super().__init__(timeout=60)
        self.channel_id = channel_id

    @discord.ui.button(label="Yes, Delete Channel", style=discord.ButtonStyle.red, custom_id="confirm_delete")
    async def confirm_delete(self, button: discord.ui.Button, interaction: discord.Interaction):
        ticket_info = active_tickets.get(self.channel_id)
        if not ticket_info:
            await interaction.response.send_message("Ticket not found.", ephemeral=True)
            return
        
        # Mark as confirmed and proceed with deletion
        ticket_info["close_confirmed"] = True
        
        # Call the final close method
        try:
            await interaction.response.send_message("✅ Confirmed. Deleting ticket channel...", ephemeral=True)
            active_tickets.pop(interaction.channel.id, None)
            try:
                await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
            except Exception:
                pass
        except Exception as e:
            logger.exception(f"Error during final close: {e}")
            await interaction.followup.send("⚠️ Error deleting channel. Please try again.", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray, custom_id="cancel_delete")
    async def cancel_delete(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("Channel deletion cancelled.", ephemeral=True)


# ---------- RECOVERY / PARSING HELPERS ----------
def _parse_user_ids_from_text(text: str):
    if not text:
        return []
    return [int(m) for m in re.findall(r"<@!?(\d+)>", text)]


async def recover_ticket_from_channel(channel: discord.TextChannel):
    """Attempt to reconstruct ticket_info from the pinned embed in a ticket channel.
    Returns a ticket_info dict compatible with active_tickets or None if not recoverable.
    """
    try:
        # Prefer pinned messages
        pinned = []
        try:
            pinned = await channel.pins()
        except Exception:
            pinned = []

        candidate_msg = None
        for msg in pinned:
            if msg.embeds:
                emb = msg.embeds[0]
                if emb.title and "Ticket #" in emb.title:
                    candidate_msg = msg
                    break

        # Fallback: scan recent history
        if candidate_msg is None:
            async for msg in channel.history(limit=50, oldest_first=True):
                if msg.embeds:
                    emb = msg.embeds[0]
                    if emb.title and "Ticket #" in emb.title:
                        candidate_msg = msg
                        break

        if candidate_msg is None or not candidate_msg.embeds:
            return None

        embed = candidate_msg.embeds[0]
        # Extract category from title like: "🎫 {category} Ticket #{number}"
        title = embed.title or ""
        title_no_emoji = re.sub(r"^\s*[\W_]+\s*", "", title)
        category = title_no_emoji.split(" Ticket #", 1)[0].strip() or "Unknown"

        # Extract requestor id from description
        requestor_id = None
        desc = embed.description or ""
        ids = _parse_user_ids_from_text(desc)
        if ids:
            requestor_id = ids[0]

        # Extract helpers from fields
        helpers = []
        for f in embed.fields:
            name = (f.name or "").strip()
            if "Helper Slot" in name:
                value = (f.value or "").strip()
                ids = _parse_user_ids_from_text(value)
                helpers.append(ids[0] if ids else None)

        if not helpers:
            # If no helper fields detected, assume default slots
            helpers = [None] * DEFAULT_SLOTS

        ticket_info = {
            "category": category,
            "requestor": requestor_id,
            "helpers": helpers,
            "embed_msg": candidate_msg,
            "closed_stage": 0,
            "rewarded": None,
            "answers": {},
        }
        return ticket_info
    except Exception as e:
        logger.warning(f"Failed to recover ticket in #{channel}: {e}")
        return None

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
        
        try:
            category = ticket_info["category"]
            cat_data = await db.get_category(category)
            fallback_data = get_fallback_category(category)
            
            # Always use fallback points to ensure correct values
            # Database might have 0 points or wrong values
            points_value = fallback_data["points"]
            
            # Log what we're using
            if cat_data and cat_data.get("points", 0) > 0:
                print(f"[REWARD DEBUG] Database has {cat_data['points']} points, but using fallback {points_value}")
            else:
                print(f"[REWARD DEBUG] Using fallback points: {points_value} (database had: {cat_data.get('points', 'None') if cat_data else 'None'})")
            
            logger.info(f"Rewarding helpers for '{category}' ticket")
            logger.info(f"Database category data: {cat_data}")
            logger.info(f"Fallback category data: {fallback_data}")
            logger.info(f"Final points value: {points_value}")
            logger.info(f"Helpers to reward: {[h for h in ticket_info.get('helpers', []) if h]}")
            
            # Print to console for immediate debugging
            print(f"[REWARD DEBUG] Category: '{category}'")
            print(f"[REWARD DEBUG] Database data: {cat_data}")
            print(f"[REWARD DEBUG] Fallback data: {fallback_data}")
            print(f"[REWARD DEBUG] Points value: {points_value}")
            print(f"[REWARD DEBUG] Available in DEFAULT_POINT_VALUES: {category in DEFAULT_POINT_VALUES}")
            if category in DEFAULT_POINT_VALUES:
                print(f"[REWARD DEBUG] DEFAULT_POINT_VALUES['{category}'] = {DEFAULT_POINT_VALUES[category]}")
            
            if points_value == 0:
                logger.warning(f"Points value is 0 for category '{category}' - this might be a configuration issue")
                print(f"[REWARD DEBUG] WARNING: Points value is 0 for '{category}'!")
            
            await PointsModule.reward_ticket_helpers({**ticket_info, "points": points_value})
            ticket_info["rewarded"] = True
            ticket_info["closed_stage"] = 2
            await interaction.response.send_message(f"✅ Helpers rewarded with {points_value} points each. Click Close again to generate transcript.", ephemeral=True)
            
        except Exception as e:
            logger.exception(f"Error in reward_yes: {e}")
            await interaction.response.send_message(f"⚠️ Error rewarding helpers: {e}", ephemeral=True)

    @discord.ui.button(label="No reward", style=discord.ButtonStyle.gray, custom_id="reward_no")
    async def reward_no(self, button: discord.ui.Button, interaction: discord.Interaction):
        ticket_info = active_tickets.get(self.ticket_channel_id)
        if not ticket_info:
            await interaction.response.send_message("Ticket context missing.", ephemeral=True)
            return
        ticket_info["rewarded"] = False
        ticket_info["closed_stage"] = 2
        await interaction.response.send_message("No rewards given. Click Close again to generate transcript.", ephemeral=True)

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
        
        # Only block if user has a restricted role AND no admin/staff role
        if any(rid in member_role_ids for rid in restricted_ids):
            # Check if user has admin or staff role to override restriction
            admin_role_id = roles_cfg.get("admin") if roles_cfg else None
            staff_role_id = roles_cfg.get("staff") if roles_cfg else None
            
            has_override_role = False
            if admin_role_id and any(r.id == admin_role_id for r in interaction.user.roles):
                has_override_role = True
            if staff_role_id and any(r.id == staff_role_id for r in interaction.user.roles):
                has_override_role = True
            
            if not has_override_role:
                await interaction.response.send_message("You cannot open a ticket due to your role restrictions.", ephemeral=True)
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
        else:
            # Force correct slot numbers from fallback configuration
            fallback_slots = DEFAULT_HELPER_SLOTS.get(category_name, DEFAULT_SLOTS)
            cat_data["slots"] = fallback_slots
        await interaction.response.send_modal(TicketModal(category_name, cat_data["questions"], interaction.user.id, cat_data["slots"]))

class TicketPanelView(View):
    def __init__(self, categories):
        super().__init__(timeout=None)
        # Create a button per category instead of a select menu
        for cat in categories[:25]:  # Discord max 25 buttons per view
            name = cat.get("name", "Category")
            panel_id = cat.get("id", 0)
            label = f"{panel_id}. {name}" if panel_id > 0 else name
            custom_id = f"open_ticket::{name}"
            # Custom darker red button with URE emoji
            self.add_item(Button(
                label=label, 
                style=discord.ButtonStyle.secondary, 
                custom_id=custom_id,
                emoji="<:URE:1429522388395233331>"
            ))

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
            # Use the exact category names from the panel text
            panel_categories = [
                {"name": "UltraSpeaker Express", "id": 1},
                {"name": "Ultra Gramiel Express", "id": 2}, 
                {"name": "Daily 4-Man Express", "id": 3},
                {"name": "Daily 7-Man Express", "id": 4},
                {"name": "Weekly Ultra Express", "id": 5},
                {"name": "GrimChallenge Express", "id": 6},
                {"name": "Daily Temple Express", "id": 7}
            ]
            categories = [{
                "name": cat["name"],
                "id": cat["id"],
                "questions": DEFAULT_QUESTIONS,
                "points": DEFAULT_POINT_VALUES.get(cat["name"], 5),
                "slots": DEFAULT_HELPER_SLOTS.get(cat["name"], DEFAULT_SLOTS),
            } for cat in panel_categories]
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
            "# CHOOSE YOUR TICKET TYPE🚂 💨 \n"
            "**Pick the ticket type that fits your request📜 **\n"
            "- https://discord.com/channels/1345073229026562079/1358536986679443496\n"
            "------------------------------------------------------------\n"
            "**1. UltraSpeaker Express**\n"
            "-# - The First Speaker\n"
            "**2. Ultra Gramiel Express**\n"
            "-# - Ultra Gramiel\n"
            "**3. Daily 4-Man Express**\n"
            "-# - Daily 4-Man Ultra Bosses\n"
            "**4. Daily 7-Man Express**\n"
            "-# - Daily 7-Man Ultra Bosses\n"
            "**5. Weekly Ultra Express**\n"
            "-# - Weekly Ultra Bosses (excluding speaker, grim and gramiel)\n"
            "**6. GrimChallenge Express**\n"
            "-# - Mechabinky & Raxborg 2.0\n"
            "**7. Daily Temple Express**\n"
            "-# - Daily TempleShrine\n"
            "-----------------------------------------------------------\n"
            "## How it works📢 \n"
            "- ✅ Select a \"ticket type\"\n"
            "- 📝 Fill out the form\n"
            "- 💁 Helpers join\n"
            "- 🎉 Get help in your private ticket"
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

    @commands.slash_command(name="reset_ticket_counter", description="Reset ticket counter to 1 (admin only)")
    async def reset_ticket_counter(self, ctx: discord.ApplicationContext):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission to use this.", ephemeral=True)
            return
        
        try:
            # Reset all category counters to 1
            categories = ["UltraSpeaker Express", "Ultra Gramiel Express", "Daily 4-Man Express", 
                         "Daily 7-Man Express", "Weekly Ultra Express", "GrimChallenge Express", "Daily Temple Express"]
            
            for category in categories:
                await db.set_ticket_number(category, 1)
            
            await ctx.respond("✅ Ticket counter reset to 1 for all categories.", ephemeral=True)
        except Exception as e:
            logger.exception(f"Error resetting ticket counter: {e}")
            await ctx.respond(f"❌ Error resetting counter: {e}", ephemeral=True)

    @commands.slash_command(name="give_points", description="Give points to helpers who joined a specific ticket panel (admin only)")
    async def give_points(
        self,
        ctx: discord.ApplicationContext,
        panel_id: discord.Option(int, "Panel ID (1-8) to reward helpers from"),
        points: discord.Option(int, "Points to give each helper", required=True),
        helpers: discord.Option(str, "Comma-separated list of helper user IDs or mentions", required=True)
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission to use this.", ephemeral=True)
            return
        
        if panel_id < 1 or panel_id > 8:
            await ctx.respond("❌ Panel ID must be between 1 and 8.", ephemeral=True)
            return
        
        try:
            # Parse helper IDs from the input
            helper_ids = []
            for helper_str in helpers.split(','):
                helper_str = helper_str.strip()
                # Remove <@ and > if it's a mention
                if helper_str.startswith('<@') and helper_str.endswith('>'):
                    helper_str = helper_str[2:-1]
                # Remove ! if it's a nickname mention
                if helper_str.startswith('!'):
                    helper_str = helper_str[1:]
                
                try:
                    helper_id = int(helper_str)
                    helper_ids.append(helper_id)
                except ValueError:
                    await ctx.respond(f"❌ Invalid helper ID: {helper_str}", ephemeral=True)
                    return
            
            if not helper_ids:
                await ctx.respond("❌ No valid helper IDs provided.", ephemeral=True)
                return
            
            # Get helper usernames for confirmation
            helper_names = []
            for helper_id in helper_ids:
                try:
                    helper = ctx.guild.get_member(helper_id)
                    if helper:
                        helper_names.append(helper.display_name)
                    else:
                        helper_names.append(f"Unknown User ({helper_id})")
                except Exception:
                    helper_names.append(f"Unknown User ({helper_id})")
            
            # Give points to each helper
            points_given = 0
            for helper_id in helper_ids:
                try:
                    current_points = await db.get_points(helper_id)
                    new_points = current_points + points
                    await db.set_points(helper_id, new_points)
                    points_given += 1
                except Exception as e:
                    logger.warning(f"Failed to give points to {helper_id}: {e}")
            
            await ctx.respond(
                f"✅ **Panel {panel_id} Rewards**\n"
                f"**Points given:** {points} to each helper\n"
                f"**Helpers rewarded:** {points_given}/{len(helper_ids)}\n"
                f"**Helper names:** {', '.join(helper_names)}",
                ephemeral=True
            )
            
        except Exception as e:
            logger.exception(f"Error in give_points: {e}")
            await ctx.respond(f"❌ Error giving points: {e}", ephemeral=True)

    @commands.slash_command(name="reward_here", description="Reward helpers in this ticket channel automatically")
    async def reward_here(self, ctx: discord.ApplicationContext):
        if not ctx.user.guild_permissions.manage_messages and not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.", ephemeral=True)
            return

        channel_id = ctx.channel.id
        ticket_info = active_tickets.get(channel_id)
        if not ticket_info:
            # Attempt recovery from embed
            recovered = await recover_ticket_from_channel(ctx.channel)
            if recovered:
                active_tickets[channel_id] = recovered
                ticket_info = recovered
        if not ticket_info:
            await ctx.respond("This channel is not a recognized ticket.", ephemeral=True)
            return

        try:
            category = ticket_info.get("category")
            cat_data = await db.get_category(category)
            fallback_data = get_fallback_category(category)
            points_value = fallback_data["points"]
            await PointsModule.reward_ticket_helpers({**ticket_info, "points": points_value})
            ticket_info["rewarded"] = True
            await ctx.respond(f"✅ Helpers rewarded for **{category}** (\+{points_value} each).", ephemeral=True)
        except Exception as e:
            logger.exception("Error in /reward_here: %s", e)
            await ctx.respond(f"❌ Error rewarding helpers: {e}", ephemeral=True)

    async def _first_close(self, interaction: discord.Interaction, ticket_info):
        """First close: remove helpers/requestor, move to stage 1"""
        try:
            removed_users = []
            
            # Remove all helpers who joined via button (except staff/admin)
            roles_cfg = await db.get_roles()
            staff_role_id = roles_cfg.get("staff") if roles_cfg else None
            admin_role_id = roles_cfg.get("admin") if roles_cfg else None
            staff_role = interaction.guild.get_role(staff_role_id) if staff_role_id else None
            admin_role = interaction.guild.get_role(admin_role_id) if admin_role_id else None
            
            for helper_id in ticket_info["helpers"]:
                if helper_id:
                    try:
                        helper = interaction.guild.get_member(helper_id)
                        if helper:
                            # Check if helper has staff or admin role (immune to removal)
                            is_staff = False
                            if staff_role and staff_role in helper.roles:
                                is_staff = True
                            if admin_role and admin_role in helper.roles:
                                is_staff = True
                            if helper.guild_permissions.administrator:
                                is_staff = True
                            
                            if not is_staff:
                                await interaction.channel.set_permissions(helper, view_channel=False, send_messages=False)
                                removed_users.append(f"Helper: {helper.display_name}")
                            else:
                                removed_users.append(f"Helper: {helper.display_name} (STAFF - kept in channel)")
                    except Exception:
                        pass
            
            # Remove all members with helper role
            helper_role_id = roles_cfg.get("helper") if roles_cfg else None
            if helper_role_id:
                helper_role = interaction.guild.get_role(helper_role_id)
                if helper_role:
                    # Remove helper role permissions from channel
                    try:
                        await interaction.channel.set_permissions(helper_role, view_channel=False, send_messages=False)
                        removed_users.append(f"Helper Role: {helper_role.name} (role permissions removed)")
                    except Exception:
                        pass
                    
                    # Remove individual members with helper role (except staff/admin)
                    for member in interaction.channel.members:
                        if helper_role in member.roles:
                            # Check if member has staff or admin role (immune to removal)
                            is_staff = False
                            if staff_role and staff_role in member.roles:
                                is_staff = True
                            if admin_role and admin_role in member.roles:
                                is_staff = True
                            if member.guild_permissions.administrator:
                                is_staff = True
                            
                            if not is_staff:
                                try:
                                    await interaction.channel.set_permissions(member, view_channel=False, send_messages=False)
                                    removed_users.append(f"Helper Role Member: {member.display_name}")
                                except Exception:
                                    pass
                            else:
                                removed_users.append(f"Helper Role Member: {member.display_name} (STAFF - kept in channel)")
            
            # Remove requestor (unless they have staff/admin role)
            try:
                requestor = interaction.guild.get_member(ticket_info["requestor"])
                if requestor:
                    # Check if requestor has staff or admin role (immune to removal)
                    is_staff = False
                    if staff_role and staff_role in requestor.roles:
                        is_staff = True
                    if admin_role and admin_role in requestor.roles:
                        is_staff = True
                    if requestor.guild_permissions.administrator:
                        is_staff = True
                    
                    if not is_staff:
                        await interaction.channel.set_permissions(requestor, view_channel=False, send_messages=False)
                        removed_users.append(f"Requestor: {requestor.display_name}")
                    else:
                        removed_users.append(f"Requestor: {requestor.display_name} (STAFF - kept in channel)")
            except Exception:
                pass
            
            # Move to stage 1
            ticket_info["closed_stage"] = 1
            
            removed_text = "\n".join(removed_users) if removed_users else "No users to remove"
            await interaction.response.send_message(f"✅ Ticket closed. Removed from channel:\n{removed_text}\n\nUse `/give_points` to reward helpers, then click Close again to generate transcript.", ephemeral=True)
                
        except Exception as e:
            logger.exception(f"Error during first close: {e}")
            await interaction.response.send_message("⚠️ Error closing ticket. Please try again.", ephemeral=True)

    async def _second_close(self, interaction: discord.Interaction, ticket_info):
        """Second close: generate transcript and show confirmation"""
        try:
            # Generate transcript
            await generate_ticket_transcript(ticket_info, rewarded=False, closer_id=interaction.user.id)
            
            # Move to stage 2
            ticket_info["closed_stage"] = 2
            
            # Show confirmation dialog
            embed = discord.Embed(
                title="⚠️ Confirm Channel Deletion",
                description=(
                    "**Are you sure you want to delete this ticket channel?**\n\n"
                    "**This will:**\n"
                    "• **PERMANENTLY DELETE** the ticket channel\n"
                    "• Remove all messages and history\n"
                    "• **This action cannot be undone!**\n\n"
                    "**Transcript has been generated and saved.**"
                ),
                color=discord.Color.red()
            )
            
            view = DeleteConfirmationView(interaction.channel.id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                
        except Exception as e:
            logger.exception(f"Error during second close: {e}")
            await interaction.response.send_message("⚠️ Error generating transcript. Please try again.", ephemeral=True)

    async def _final_close(self, interaction: discord.Interaction, ticket_info):
        """Final close: delete the channel"""
        await interaction.response.send_message("Deleting ticket channel...", ephemeral=True)
        active_tickets.pop(interaction.channel.id, None)
        try:
            await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
        except Exception:
            pass

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
            try:
                category_name = custom_id.split("::", 1)[1]
                logger.info(f"User {interaction.user} clicked ticket button for category: {category_name}")
                
                # Check for restricted roles (only block if explicitly restricted)
                member_role_ids = [role.id for role in interaction.user.roles]
                roles_cfg = await db.get_roles()
                restricted_raw = roles_cfg.get("restricted", []) if roles_cfg else []
                restricted_ids = []
                for r in restricted_raw:
                    try:
                        restricted_ids.append(int(r))
                    except Exception:
                        pass
                
                # Only block if user has a restricted role AND no admin/staff role
                if any(rid in member_role_ids for rid in restricted_ids):
                    # Check if user has admin or staff role to override restriction
                    admin_role_id = roles_cfg.get("admin") if roles_cfg else None
                    staff_role_id = roles_cfg.get("staff") if roles_cfg else None
                    
                    has_override_role = False
                    if admin_role_id and any(r.id == admin_role_id for r in interaction.user.roles):
                        has_override_role = True
                    if staff_role_id and any(r.id == staff_role_id for r in interaction.user.roles):
                        has_override_role = True
                    
                    if not has_override_role:
                        logger.info(f"User {interaction.user} blocked by restricted role")
                        await interaction.response.send_message("You cannot open a ticket due to your role restrictions.", ephemeral=True)
                        return

                # Check bot permissions
                if not bot_can_manage_channels(interaction):
                    logger.warning(f"Bot lacks manage channels permission in {interaction.guild}")
                    await interaction.response.send_message(
                        "I need the 'Manage Channels' permission to create your ticket. Please ask an admin to grant it.",
                        ephemeral=True,
                    )
                    return

                cat_data = await db.get_category(category_name)
                if not cat_data:
                    cat_data = get_fallback_category(category_name)
                    logger.info(f"Using fallback category for: {category_name}")
                else:
                    # Force correct slot numbers from fallback configuration
                    fallback_slots = DEFAULT_HELPER_SLOTS.get(category_name, DEFAULT_SLOTS)
                    cat_data["slots"] = fallback_slots
                    logger.info(f"Using database category for: {category_name}, forced slots: {fallback_slots}")
                
                logger.info(f"Sending modal for category: {category_name}, slots: {cat_data['slots']}")
                await interaction.response.send_modal(TicketModal(category_name, cat_data["questions"], interaction.user.id, cat_data["slots"]))
                return
            except Exception as e:
                logger.exception(f"Error handling panel button click: {e}")
                try:
                    await interaction.response.send_message("⚠️ Something went wrong. Please try again.", ephemeral=True)
                except Exception:
                    pass
                return

        if not ticket_info:
            # Try to recover from the channel if this looks like a ticket
            recovered = None
            try:
                if isinstance(interaction.channel, discord.TextChannel):
                    recovered = await recover_ticket_from_channel(interaction.channel)
            except Exception:
                recovered = None
            if recovered:
                active_tickets[channel_id] = recovered
                ticket_info = recovered
            else:
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
            
            # Check if user is already helping in another ticket
            for ticket_id, other_ticket in active_tickets.items():
                if ticket_id != channel_id and interaction.user.id in [h for h in other_ticket["helpers"] if h]:
                    await interaction.response.send_message("You can only join one ticket at a time. Leave your current ticket first.", ephemeral=True)
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

        elif custom_id == "submit_proof":
            # Only allow the requestor to submit proof
            if interaction.user.id != ticket_info["requestor"]:
                await interaction.response.send_message("Only the ticket requestor can submit proof.", ephemeral=True)
                return
            
            # Check if proof already submitted
            if ticket_info.get("proof_url"):
                await interaction.response.send_message("Proof has already been submitted for this ticket.", ephemeral=True)
                return
            
            await interaction.response.send_modal(ProofInstructionsModal(interaction.channel.id))
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
            
            # Check current stage
            stage = ticket_info.get("closed_stage", 0)
            if stage == 0:
                # First close: remove helpers/requestor, move to stage 1
                await self._first_close(interaction, ticket_info)
            elif stage == 1:
                # Second close: generate transcript + confirmation, move to stage 2
                await self._second_close(interaction, ticket_info)
            else:
                # Final stage: delete channel
                await self._final_close(interaction, ticket_info)

def setup(bot):
    bot.add_cog(TicketModule(bot))