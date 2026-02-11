"""Panel and selection buttons for opening tickets"""

import discord
from typing import Optional, List
import config
from tickets_utils import format_boss_name_for_select


class TicketView(discord.ui.View):
    """Persistent view for ticket panel buttons"""
    def __init__(self):
        super().__init__(timeout=None)
        
        # Add buttons for each category
        for i, category in enumerate(config.CATEGORIES):
            row = i // 4  # 4 buttons per row
            self.add_item(TicketButton(category, row=row))


class TicketButton(discord.ui.Button):
    """Button for each ticket category"""
    def __init__(self, category: str, row: int):
        label = category.replace(" Express", "")
        
        super().__init__(
            label=label,
            style=discord.ButtonStyle.secondary,  # Black/Gray buttons
            custom_id=f"open_ticket::{category}",
            emoji=config.CUSTOM_EMOJI,  # <:URE:1429522388395233331>
            row=row
        )
        self.category = category
    
    async def callback(self, interaction: discord.Interaction):
        """Handle ticket button click"""
        # Check if user has RESTRICTED role - BLOCK THEM
        restricted_role = interaction.guild.get_role(config.ROLE_IDS.get("RESTRICTED"))
        if restricted_role and restricted_role in interaction.user.roles:
            await interaction.response.send_message(
                "❌ You are restricted from opening tickets.",
                ephemeral=True
            )
            return
        
        bot = interaction.client
        all_tickets = await bot.db.get_all_tickets()
        
        # === NEW: CHECK IF USER ALREADY HAS AN ACTIVE TICKET AS REQUESTOR ===
        for ticket in all_tickets:
            if interaction.user.id == ticket["requestor_id"]:
                # Verify channel exists
                channel = interaction.guild.get_channel(ticket["channel_id"])
                if channel:
                    await interaction.response.send_message(
                        f"❌ You already have an active ticket: {channel.mention}\n"
                        "Please close or cancel that ticket before creating a new one.",
                        ephemeral=True
                    )
                    return
        
        # Check if user is a helper in any active ticket - PREVENT CREATING TICKET
        for ticket in all_tickets:
            if interaction.user.id in ticket["helpers"]:
                # Verify channel exists
                channel = interaction.guild.get_channel(ticket["channel_id"])
                if channel:
                    await interaction.response.send_message(
                        f"❌ You cannot create a ticket while you're a helper in another ticket: {channel.mention}\n"
                        "Please complete or leave that ticket first.",
                        ephemeral=True
                    )
                    return
        
        # Check if category needs boss selection
        if self.category in ["Daily 4-Man Express", "Daily 7-Man Express", "Weekly Ultra Express"]:
            # Show boss selection menu
            view = BossSelectView(self.category)
            
            embed = discord.Embed(
                title=f"🎯 Select Bosses - {self.category}",
                description="Choose which bosses you need help with:",
                color=config.COLORS["PRIMARY"]
            )
            
            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True
            )
        else:
            # Direct to server selection modal
            view = ServerSelectView(self.category, selected_bosses=None)
            
            embed = discord.Embed(
                title=f"🌍 Select Server - {self.category}",
                description="Choose which server you're playing on:",
                color=config.COLORS["PRIMARY"]
            )
            
            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True
            )


class BossSelectView(discord.ui.View):
    """View with boss selection dropdown"""
    def __init__(self, category: str):
        super().__init__(timeout=300)  # 5 minute timeout for selection
        self.category = category
        self.add_item(BossSelectMenu(category))


class BossSelectMenu(discord.ui.Select):
    """Dropdown menu for boss selection"""
    def __init__(self, category: str):
        self.category = category
        
        # Get boss list based on category
        if category == "Daily 4-Man Express":
            boss_list = config.DAILY_4MAN_BOSSES
        elif category == "Daily 7-Man Express":
            boss_list = config.DAILY_7MAN_BOSSES
        elif category == "Weekly Ultra Express":
            boss_list = config.WEEKLY_ULTRA_BOSSES
        else:
            boss_list = []
        
        # Create options with CORRECT display names (remove Ultra from non-ultra bosses)
        options = []
        for boss in boss_list:
            display_name = format_boss_name_for_select(boss)
            options.append(discord.SelectOption(label=display_name, value=boss, emoji="⚔️"))
        
        super().__init__(
            placeholder=f"Select bosses (1-{len(boss_list)})",
            min_values=1,
            max_values=len(boss_list),
            options=options,
            custom_id=f"boss_select_{category}"
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle boss selection and show server selection"""
        selected_bosses = self.values
        
        # Show server selection
        view = ServerSelectView(self.category, selected_bosses=selected_bosses)
        
        embed = discord.Embed(
            title=f"🌍 Select Server - {self.category}",
            description="Choose which server you're playing on:",
            color=config.COLORS["PRIMARY"]
        )
        
        await interaction.response.edit_message(embed=embed, view=view)


class ServerSelectView(discord.ui.View):
    """View with server selection dropdown"""
    def __init__(self, category: str, selected_bosses: Optional[List[str]] = None):
        super().__init__(timeout=300)
        self.category = category
        self.selected_bosses = selected_bosses or []
        self.add_item(ServerSelectMenu(category, selected_bosses))


class ServerSelectMenu(discord.ui.Select):
    """Dropdown menu for server selection"""
    def __init__(self, category: str, selected_bosses: Optional[List[str]] = None):
        self.category = category
        self.selected_bosses = selected_bosses or []
        
        # Server options
        servers = ["Swordhaven", "Safiria", "Gravelyn", "Galanoth", "Alteon", "Yorumi"]
        
        options = [
            discord.SelectOption(label=server, value=server, emoji="🌐")
            for server in servers
        ]
        
        super().__init__(
            placeholder="Select your server",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"server_select_{category}"
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle server selection and open modal"""
        selected_server = self.values[0]
        
        # Show modal with selected bosses and server
        from tickets_modals import TicketModal
        modal = TicketModal(self.category, selected_bosses=self.selected_bosses, selected_server=selected_server)
        await interaction.response.send_modal(modal)