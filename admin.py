# admin.py
# Admin Commands - Points Management

import discord
from discord.ext import commands
from discord import app_commands
import config


def is_admin_or_staff(interaction: discord.Interaction) -> bool:
    """Check if user has admin or staff role"""
    member = interaction.user
    return any(
        member.get_role(rid) 
        for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF")] 
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
    
    @bot.tree.command(name="points_reset", description="Reset all points (Admin only)")
    async def points_reset(interaction: discord.Interaction):
        """Reset all points - requires confirmation"""
        if not is_admin_or_staff(interaction):
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
    
    @bot.tree.command(name="points_remove_user", description="Remove a user from the leaderboard (Admin only)")
    @app_commands.describe(user="User to remove from leaderboard")
    async def points_remove_user(interaction: discord.Interaction, user: discord.Member):
        """Remove user from leaderboard entirely"""
        if not is_admin_or_staff(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        deleted = await bot.db.delete_user_points(user.id)
        
        if deleted:
            embed = discord.Embed(
                title="✅ User Removed",
                description=f"Removed {user.mention} from the leaderboard",
                color=config.COLORS["SUCCESS"]
            )
        else:
            embed = discord.Embed(
                title="ℹ️ User Not Found",
                description=f"{user.mention} was not in the leaderboard",
                color=config.COLORS["WARNING"]
            )
        
        embed.set_footer(text=f"Modified by {interaction.user}")
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="ticket_kick", description="Remove a helper from the current ticket")
    @app_commands.describe(user="Helper to remove from this ticket")
    async def ticket_kick(interaction: discord.Interaction, user: discord.Member):
        """Remove a helper from a ticket"""
        ticket = await bot.db.get_ticket(interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message(
                "❌ This command can only be used in ticket channels.",
                ephemeral=True
            )
            return
        
        # Check permissions (staff/admin or requestor)
        is_staff = is_admin_or_staff(interaction)
        is_requestor = interaction.user.id == ticket["requestor_id"]
        
        if not (is_staff or is_requestor):
            await interaction.response.send_message(
                "❌ Only staff or the ticket creator can remove helpers.",
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
        
        # Remove channel permissions
        try:
            await interaction.channel.set_permissions(
                user,
                overwrite=None  # Reset to default (no access)
            )
        except:
            pass
        
        # Update ticket embed
        from tickets import create_ticket_embed
        import json
        
        selected_bosses = json.loads(ticket.get("selected_bosses", "[]"))
        embed = create_ticket_embed(
            category=ticket["category"],
            requestor_id=ticket["requestor_id"],
            in_game_name=ticket.get("in_game_name", "N/A"),
            concerns=ticket.get("concerns", "None"),
            helpers=ticket["helpers"],
            random_number=ticket["random_number"],
            selected_bosses=selected_bosses
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