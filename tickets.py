import discord
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, InputText
from points import PointsModule
from database import db  # <-- Use DB
from datetime import datetime
from io import StringIO

# ---------- DEFAULTS (used when DB has no categories) ----------
DEFAULT_POINT_VALUES = {
    "Ultra Speaker Express": 8,
    "Ultra Gramiel Express": 7,
    "4-Man Ultra Daily Express": 4,
    "7-Man Ultra Daily Express": 10,
    "Ultra Weekly Express": 12,
    "Grim Express": 10,
    "Daily Temple Express": 6,
}

DEFAULT_HELPER_SLOTS = {
    "7-Man Ultra Daily Express": 6,
    "Grim Express": 6,
}
DEFAULT_SLOTS = 3
DEFAULT_QUESTIONS = [
    "In-game name?*",
    "Server name?*",
    "Room number?*",
    "Anything else?",
]

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
    return cleaned, required

# ---------- STORAGE ----------
tickets_counter = {}  # category_name -> last ticket number
active_tickets = {}   # channel_id -> ticket info

# ---------- UTILITY ----------
async def generate_ticket_transcript(ticket_info, rewarded=False):
    channel = ticket_info["embed_msg"].channel
    transcript_text = f"Ticket Transcript for {ticket_info['category']}\n"
    transcript_text += f"Requestor: <@{ticket_info['requestor']}>\n"
    transcript_text += f"Helpers: {', '.join(f'<@{h}>' for h in ticket_info['helpers'] if h)}\n"
    transcript_text += f"Opened at: {channel.created_at}\n"
    transcript_text += f"Closed at: {datetime.utcnow()}\n"
    transcript_text += f"Rewarded: {'Yes' if rewarded else 'No'}\n\n"

    async for msg in channel.history(limit=100, oldest_first=True):
        transcript_text += f"[{msg.created_at}] {msg.author}: {msg.content}\n"

    transcript_channel_id = await db.get_transcript_channel()
    if transcript_channel_id:
        guild = channel.guild
        transcript_channel = guild.get_channel(transcript_channel_id)
        if transcript_channel:
            file = discord.File(StringIO(transcript_text), filename=f"transcript-{channel.name}.txt")
            await transcript_channel.send(file=file)

# ---------- TICKET MODAL ----------
class TicketModal(Modal):
    def __init__(self, category, questions, requestor_id, slots):
        super().__init__(title=f"{category} Ticket")
        self.category = category
        self.requestor_id = requestor_id
        self.slots = slots
        self.inputs = []
        for q in questions:
            label, required = parse_question_required(q)
            ti = InputText(label=label, style=discord.InputTextStyle.long, required=required)
            self.add_item(ti)
            self.inputs.append(ti)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        # Persisted counter via DB to avoid resets on restarts
        number = await db.increment_ticket_number(self.category)
        channel_name = f"{self.category.lower().replace(' ', '-')}-{number}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        parent_category_id = await db.get_ticket_category()
        parent_category = guild.get_channel(parent_category_id) if parent_category_id else None
        ticket_channel = await guild.create_text_channel(channel_name, overwrites=overwrites, category=parent_category)

        embed = discord.Embed(
            title=f"{self.category} Ticket #{number}",
            description=f"Requestor: {interaction.user.mention}",
            color=0x00FF00
        )
        for ti in self.inputs:
            embed.add_field(name=ti.label, value=ti.value, inline=False)

        for i in range(self.slots):
            embed.add_field(name=f"Helper Slot {i+1}", value="Empty", inline=True)

        view = TicketView(self.category, interaction.user.id)
        msg = await ticket_channel.send(embed=embed, view=view)

        active_tickets[ticket_channel.id] = {
            "category": self.category,
            "requestor": interaction.user.id,
            "helpers": [None]*self.slots,
            "embed_msg": msg,
            "closed_once": False
        }

        await interaction.response.send_message(f"Ticket created: {ticket_channel.mention}", ephemeral=True)

# ---------- TICKET VIEW ----------
class TicketView(View):
    def __init__(self, category, requestor_id):
        super().__init__(timeout=None)
        self.category = category
        self.requestor_id = requestor_id
        self.add_item(Button(label="Join Ticket", style=discord.ButtonStyle.green, custom_id="join_ticket"))
        self.add_item(Button(label="Remove Helper", style=discord.ButtonStyle.red, custom_id="remove_helper"))
        self.add_item(Button(label="Close Ticket", style=discord.ButtonStyle.gray, custom_id="close_ticket"))

# ---------- SELECT MENU ----------
class TicketSelect(Select):
    def __init__(self, categories):
        options = [discord.SelectOption(label=cat["name"]) for cat in categories]
        super().__init__(placeholder="Choose ticket type...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        member_roles = [role.id for role in interaction.user.roles]
        roles = await db.get_roles()
        if any(r in roles.get("restricted", []) for r in member_roles):
            await interaction.response.send_message("You cannot open a ticket.", ephemeral=True)
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
        roles = await db.get_roles()
        staff_role, admin_role = roles.get("staff"), roles.get("admin")
        if not any(r.id == staff_role or r.id == admin_role for r in ctx.user.roles):
            await ctx.respond("You don't have permission to deploy ticket panel.", ephemeral=True)
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
        # List services with points
        services = []
        for cat in categories:
            services.append(f"- **{cat['name']}** — {cat.get('points', 0)} points")
        embed.add_field(name="📋 Available Services", value="**" + ("\n".join(services) or "No services configured") + "**", inline=False)
        embed.add_field(name="ℹ️ How it works", value="1. Select a service\n2. Fill out the form\n3. Helpers join\n4. Get help in your private ticket!", inline=False)
        await ctx.respond(embed=embed, view=view)

    # ---------- BUTTON HANDLER ----------
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        channel_id = interaction.channel.id
        ticket_info = active_tickets.get(channel_id)
        if not ticket_info:
            return

        custom_id = interaction.data["custom_id"]

        # Join Ticket
        if custom_id == "join_ticket":
            if interaction.user.id == ticket_info["requestor"]:
                await interaction.response.send_message("You cannot join your own ticket.", ephemeral=True)
                return
            for i in range(len(ticket_info["helpers"])):
                if ticket_info["helpers"][i] is None:
                    ticket_info["helpers"][i] = interaction.user.id
                    break
            embed = ticket_info["embed_msg"].embeds[0]
            base_index = len(embed.fields) - len(ticket_info["helpers"])  # helper fields are last
            for i, helper_id in enumerate(ticket_info["helpers"]):
                value = f"<@{helper_id}>" if helper_id else "Empty"
                embed.set_field_at(base_index + i, name=f"Helper Slot {i+1}", value=value, inline=True)
            await ticket_info["embed_msg"].edit(embed=embed)
            await interaction.response.send_message("You joined the ticket!", ephemeral=True)

        # Remove Helper
        elif custom_id == "remove_helper":
            roles = await db.get_roles()
            staff_role, admin_role = roles.get("staff"), roles.get("admin")
            if not any(r.id == staff_role or r.id == admin_role for r in interaction.user.roles):
                await interaction.response.send_message("Only staff/admin can remove helpers.", ephemeral=True)
                return
            for i in range(len(ticket_info["helpers"])):
                if ticket_info["helpers"][i]:
                    ticket_info["helpers"][i] = None
                    break
            embed = ticket_info["embed_msg"].embeds[0]
            base_index = len(embed.fields) - len(ticket_info["helpers"])  # helper fields are last
            for i, helper_id in enumerate(ticket_info["helpers"]):
                value = f"<@{helper_id}>" if helper_id else "Empty"
                embed.set_field_at(base_index + i, name=f"Helper Slot {i+1}", value=value, inline=True)
            await ticket_info["embed_msg"].edit(embed=embed)
            await interaction.response.send_message("Helper removed from embed.", ephemeral=True)

        # Close Ticket
        elif custom_id == "close_ticket":
            roles = await db.get_roles()
            staff_role, admin_role = roles.get("staff"), roles.get("admin")
            if not any(r.id == staff_role or r.id == admin_role for r in interaction.user.roles):
                await interaction.response.send_message("Only staff/admin can close ticket.", ephemeral=True)
                return
            if not ticket_info.get("closed_once"):
                ticket_info["closed_once"] = True
                await interaction.channel.set_permissions(interaction.guild.default_role, view_channel=False)
                await interaction.response.send_message("Ticket closed. Click again to reward helpers.", ephemeral=True)
            else:
                helpers = [h for h in ticket_info["helpers"] if h]
                category = ticket_info["category"]

                # Reward points using PointsModule static method with fallback
                cat_data = await db.get_category(category)
                points_value = (cat_data or get_fallback_category(category))["points"]
                await PointsModule.reward_ticket_helpers({**ticket_info, "points": points_value})

                # Generate transcript
                await generate_ticket_transcript(ticket_info, rewarded=True)

                await interaction.response.send_message(
                    "Ticket closed second time. Helpers rewarded and transcript generated.", ephemeral=True
                )

# ---------- SETUP ----------
def setup(bot):
    bot.add_cog(TicketModule(bot))