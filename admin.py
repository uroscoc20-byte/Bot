# admin.py
# Admin Commands - Points Management

import discord
from discord.ext import commands
from discord import app_commands
import config
import json
from points_logger import log_points_added, log_points_removed, log_points_set, log_points_reset, log_user_deleted
from tickets import join_cooldowns, leave_cooldowns


def is_admin_or_staff(interaction: discord.Interaction) -> bool:
    """Check if user has admin or staff role"""
    member = interaction.user
    return any(
        member.get_role(rid) 
        for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF")] 
        if rid
    )


def is_admin_staff_or_officer(interaction: discord.Interaction) -> bool:
    """Check if user has admin, staff, or officer role"""
    member = interaction.user
    return any(
        member.get_role(rid) 
        for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF"), config.ROLE_IDS.get("OFFICER")] 
        if rid
    )


class ConfirmResetView(discord.ui.View):
    """Confirmation view for resetting all points"""
    def __init__(self, bot, admin_user):
        super().__init__(timeout=30)
        self.bot = bot
        self.admin_user = admin_user
    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm reset"""
        if interaction.user.id != self.admin_user.id:
            await interaction.response.send_message(
                "❌ Only the admin who initiated this can confirm.",
                ephemeral=True
            )
            return
        
        await self.bot.db.reset_all_points()
        
        embed = discord.Embed(
            title="✅ Points Reset Complete",
            description="All user points have been reset to 0.",
            color=config.COLORS["SUCCESS"]
        )
        embed.set_footer(text=f"Reset by {interaction.user}")
        
        await interaction.response.edit_message(embed=embed, view=None)
        
        # Log the reset
        await log_points_reset(self.bot, interaction.user.id)
        
        # Disable all buttons
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel reset"""
        if interaction.user.id != self.admin_user.id:
            await interaction.response.send_message(
                "❌ Only the admin who initiated this can cancel.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="❌ Reset Cancelled",
            description="Points reset has been cancelled.",
            color=config.COLORS["WARNING"]
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


async def setup_admin(bot):
    """Setup admin commands"""
    
    @bot.tree.command(name="points_add", description="Add points to a user (Admin only)")
    @app_commands.describe(
        user="User to add points to",
        amount="Amount of points to add"
    )
    async def points_add(
        interaction: discord.Interaction, 
        user: discord.Member, 
        amount: app_commands.Range[int, 1, 100000]
    ):
        """Add points to a user"""
        if not is_admin_or_staff(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        new_points = await bot.db.add_points(user.id, amount)
        
        embed = discord.Embed(
            title="✅ Points Added",
            description=f"Added **{amount:,}** points to {user.mention}",
            color=config.COLORS["SUCCESS"]
        )
        embed.add_field(name="New Total", value=f"**{new_points:,}** points", inline=False)
        embed.set_footer(text=f"Modified by {interaction.user}")
        
        await interaction.response.send_message(embed=embed)
        
        # Log the change
        await log_points_added(bot, user.id, interaction.user.id, amount, new_points)
    
    @bot.tree.command(name="points_remove", description="Remove points from a user (Admin only)")
    @app_commands.describe(
        user="User to remove points from",
        amount="Amount of points to remove"
    )
    async def points_remove(
        interaction: discord.Interaction, 
        user: discord.Member, 
        amount: app_commands.Range[int, 1, 100000]
    ):
        """Remove points from a user"""
        if not is_admin_or_staff(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        current_points = await bot.db.get_points(user.id)
        new_points = await bot.db.remove_points(user.id, amount)
        actual_removed = current_points - new_points
        
        embed = discord.Embed(
            title="✅ Points Removed",
            description=f"Removed **{actual_removed:,}** points from {user.mention}",
            color=config.COLORS["WARNING"]
        )
        embed.add_field(name="New Total", value=f"**{new_points:,}** points", inline=False)
        embed.set_footer(text=f"Modified by {interaction.user}")
        
        await interaction.response.send_message(embed=embed)
        
        # Log the change
        await log_points_removed(bot, user.id, interaction.user.id, actual_removed, new_points)
    
    @bot.tree.command(name="points_set", description="Set user's points to exact value (Admin only)")
    @app_commands.describe(
        user="User to set points for",
        amount="Exact amount of points"
    )
    async def points_set(
        interaction: discord.Interaction, 
        user: discord.Member, 
        amount: app_commands.Range[int, 0, 100000]
    ):
        """Set exact points for a user"""
        if not is_admin_or_staff(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await bot.db.set_points(user.id, amount)
        
        embed = discord.Embed(
            title="✅ Points Set",
            description=f"Set {user.mention}'s points to **{amount:,}**",
            color=config.COLORS["SUCCESS"]
        )
        embed.set_footer(text=f"Modified by {interaction.user}")
        
        await interaction.response.send_message(embed=embed)
        
        # Log the change
        await log_points_set(bot, user.id, interaction.user.id, amount)
    
    @bot.tree.command(name="points_reset", description="Reset all points (Admin only)")
    async def points_reset(interaction: discord.Interaction):
        """Reset all points - requires confirmation"""
        if interaction.user.get_role(config.ROLE_IDS.get("ADMIN")) is None:
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        # Create confirmation view
        view = ConfirmResetView(bot, interaction.user)
        
        embed = discord.Embed(
            title="⚠️ Confirm Points Reset",
            description=(
                "**WARNING:** This will reset ALL user points to 0!\n\n"
                "This action cannot be undone.\n\n"
                "Click **Confirm** to proceed or **Cancel** to abort."
            ),
            color=config.COLORS["DANGER"]
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @bot.tree.command(name="points_remove_user", description="Remove a user from the leaderboard by ID or mention (Admin only)")
    @app_commands.describe(user_id="User ID or mention to remove from leaderboard")
    async def points_remove_user(interaction: discord.Interaction, user_id: str):
        """Remove user from leaderboard entirely - supports ID or mention"""
        if interaction.user.get_role(config.ROLE_IDS.get("ADMIN")) is None:
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        # Parse user_id - handle mentions and raw IDs
        try:
            # If it's a mention like <@123456>, extract the ID
            if user_id.startswith("<@") and user_id.endswith(">"):
                parsed_id = int(user_id[2:-1].replace("!", ""))
            else:
                parsed_id = int(user_id)
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid user ID. Please provide a valid user ID or mention.",
                ephemeral=True
            )
            return
        
        deleted = await bot.db.delete_user_points(parsed_id)
        
        if deleted:
            embed = discord.Embed(
                title="✅ User Removed",
                description=f"Removed user (ID: {parsed_id}) from the leaderboard",
                color=config.COLORS["SUCCESS"]
            )
            
            # Log the removal
            await log_user_deleted(bot, parsed_id, interaction.user.id)
        else:
            embed = discord.Embed(
                title="ℹ️ User Not Found",
                description=f"User (ID: {parsed_id}) was not in the leaderboard",
                color=config.COLORS["WARNING"]
            )
        
        embed.set_footer(text=f"Modified by {interaction.user}")
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="ticket_kick", description="Remove a helper from the current ticket (Officer/Staff/Admin only)")
    @app_commands.describe(user="Helper to remove from this ticket")
    async def ticket_kick(interaction: discord.Interaction, user: discord.Member):
        """Remove a helper from a ticket - OFFICER/STAFF/ADMIN ONLY"""
        ticket = await bot.db.get_ticket(interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message(
                "❌ This command can only be used in ticket channels.",
                ephemeral=True
            )
            return
        
        # Check permissions - OFFICER/STAFF/ADMIN ONLY (requestor CANNOT kick)
        if not is_admin_staff_or_officer(interaction):
            await interaction.response.send_message(
                "❌ Only officers, staff, or admins can remove helpers.",
                ephemeral=True
            )
            return
        
        # Check if user is in helpers
        if user.id not in ticket["helpers"]:
            await interaction.response.send_message(
                f"❌ {user.mention} is not a helper in this ticket.",
                ephemeral=True
            )
            return
        
        # Remove helper
        ticket["helpers"].remove(user.id)
        await bot.db.save_ticket(ticket)
        
        # Remove channel permissions (unless staff/admin/officer)
        guild = interaction.guild
        admin_role = guild.get_role(config.ROLE_IDS.get("ADMIN"))
        staff_role = guild.get_role(config.ROLE_IDS.get("STAFF"))
        officer_role = guild.get_role(config.ROLE_IDS.get("OFFICER"))
        
        is_user_staff = False
        if admin_role and admin_role in user.roles:
            is_user_staff = True
        if staff_role and staff_role in user.roles:
            is_user_staff = True
        if officer_role and officer_role in user.roles:
            is_user_staff = True
        
        if not is_user_staff:
            try:
                await interaction.channel.set_permissions(user, overwrite=None)
            except:
                pass
        
        # Update ticket embed
        from tickets import create_ticket_embed
        
        try:
            selected_bosses_raw = ticket.get("selected_bosses", "[]")
            if isinstance(selected_bosses_raw, str):
                selected_bosses = json.loads(selected_bosses_raw)
            else:
                selected_bosses = selected_bosses_raw or []
        except:
            selected_bosses = []
        
        selected_server = ticket.get("selected_server", "Unknown")
        
        embed = create_ticket_embed(
            category=ticket["category"],
            requestor_id=ticket["requestor_id"],
            in_game_name=ticket.get("in_game_name", "N/A"),
            concerns=ticket.get("concerns", "None"),
            helpers=ticket["helpers"],
            random_number=ticket["random_number"],
            selected_bosses=selected_bosses,
            selected_server=selected_server
        )
        
        # Find and update the ticket message
        try:
            msg = await interaction.channel.fetch_message(ticket["embed_message_id"])
            await msg.edit(embed=embed)
        except:
            pass
        
        await interaction.response.send_message(
            f"✅ Removed {user.mention} from this ticket.",
            ephemeral=False
        )
        
        await interaction.channel.send(f"👢 {user.mention} was kicked from the ticket by {interaction.user.mention}.")

    @bot.tree.command(name="remove_cooldown", description="Remove cooldown from a user (Admin/Staff/Officer only)")
    @app_commands.describe(user="User to remove cooldown from")
    async def remove_cooldown(interaction: discord.Interaction, user: discord.Member):
        """Remove join/leave cooldown from a user"""
        if not is_admin_staff_or_officer(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        removed = False
        if user.id in join_cooldowns:
            del join_cooldowns[user.id]
            removed = True
        
        if user.id in leave_cooldowns:
            del leave_cooldowns[user.id]
            removed = True
            
        if removed:
            await interaction.response.send_message(
                f"✅ Removed ticket cooldowns for {user.mention}.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"ℹ️ {user.mention} has no active cooldowns.",
                ephemeral=True
            )
