import discord
from discord.ext import commands, tasks
from database import db
from leaderboard import create_leaderboard_embed, LeaderboardView
import asyncio

class PersistentPanels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auto_refresh.start()

    def cog_unload(self):
        self.auto_refresh.cancel()

    @tasks.loop(minutes=15)
    async def auto_refresh(self):
        """Auto-refresh all persistent panels every 15 minutes"""
        try:
            panels = await db.get_persistent_panels()
            for panel in panels:
                try:
                    channel = self.bot.get_channel(panel["channel_id"])
                    if not channel:
                        continue
                    
                    message = await channel.fetch_message(panel["message_id"])
                    if not message:
                        continue
                    
                    if panel["panel_type"] == "leaderboard":
                        # Refresh leaderboard
                        page = panel["data"].get("page", 1)
                        per_page = panel["data"].get("per_page", 10)
                        embed = await create_leaderboard_embed(page=page, per_page=per_page)
                        view = LeaderboardView(page, panel["data"].get("total_pages", 1), per_page)
                        await message.edit(embed=embed, view=view)
                    
                    # Add more panel types here as needed
                    
                except discord.NotFound:
                    # Message was deleted, remove from database
                    await db.delete_persistent_panel(panel["message_id"])
                except Exception as e:
                    print(f"Error refreshing panel {panel['message_id']}: {e}")
                    
        except Exception as e:
            print(f"Error in auto_refresh: {e}")

    @auto_refresh.before_loop
    async def before_auto_refresh(self):
        await self.bot.wait_until_ready()

    @commands.slash_command(name="persistent_leaderboard", description="Create a persistent leaderboard that auto-refreshes")
    async def persistent_leaderboard(
        self,
        ctx: discord.ApplicationContext,
        page: discord.Option(int, "Page number", required=False, default=1),
    ):
        """Create a persistent leaderboard that survives bot restarts and auto-refreshes"""
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.", ephemeral=True)
            return
        
        rows = await db.get_leaderboard()
        per_page = 10
        total_pages = max(1, (len(rows) + per_page - 1) // per_page)
        
        if not rows:
            await ctx.respond("Leaderboard is empty.")
            return
        
        embed = await create_leaderboard_embed(page=page, per_page=per_page)
        view = LeaderboardView(page, total_pages, per_page)
        
        # Send the message
        message = await ctx.respond(embed=embed, view=view)
        if hasattr(message, 'message'):
            message = message.message
        
        # Save to database for persistence
        panel_data = {
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages
        }
        await db.save_persistent_panel(
            channel_id=ctx.channel.id,
            message_id=message.id,
            panel_type="leaderboard",
            data=panel_data
        )
        
        await ctx.followup.send("✅ Persistent leaderboard created! It will auto-refresh every 15 minutes.", ephemeral=True)

    @commands.slash_command(name="remove_persistent_panel", description="Remove a persistent panel (Admin only)")
    async def remove_persistent_panel(
        self,
        ctx: discord.ApplicationContext,
        message_id: discord.Option(str, "Message ID of the panel to remove"),
    ):
        """Remove a persistent panel"""
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.", ephemeral=True)
            return
        
        try:
            message_id_int = int(message_id)
            await db.delete_persistent_panel(message_id_int)
            await ctx.respond(f"✅ Removed persistent panel {message_id}.", ephemeral=True)
        except ValueError:
            await ctx.respond("Invalid message ID.", ephemeral=True)

    @commands.slash_command(name="list_persistent_panels", description="List all persistent panels (Admin only)")
    async def list_persistent_panels(self, ctx: discord.ApplicationContext):
        """List all persistent panels"""
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("You do not have permission.", ephemeral=True)
            return
        
        panels = await db.get_persistent_panels()
        if not panels:
            await ctx.respond("No persistent panels found.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📋 Persistent Panels",
            color=0x5865F2
        )
        
        for panel in panels:
            channel = self.bot.get_channel(panel["channel_id"])
            channel_name = channel.name if channel else "Unknown Channel"
            embed.add_field(
                name=f"{panel['panel_type'].title()} Panel",
                value=f"Channel: #{channel_name}\nMessage ID: {panel['message_id']}",
                inline=False
            )
        
        await ctx.respond(embed=embed, ephemeral=True)

    async def restore_persistent_panels(self):
        """Restore all persistent panels on bot startup"""
        try:
            panels = await db.get_persistent_panels()
            for panel in panels:
                try:
                    channel = self.bot.get_channel(panel["channel_id"])
                    if not channel:
                        continue
                    
                    message = await channel.fetch_message(panel["message_id"])
                    if not message:
                        continue
                    
                    if panel["panel_type"] == "leaderboard":
                        # Restore leaderboard view
                        page = panel["data"].get("page", 1)
                        per_page = panel["data"].get("per_page", 10)
                        total_pages = panel["data"].get("total_pages", 1)
                        embed = await create_leaderboard_embed(page=page, per_page=per_page)
                        view = LeaderboardView(page, total_pages, per_page)
                        await message.edit(embed=embed, view=view)
                    
                    # Add more panel types here as needed
                    
                except discord.NotFound:
                    # Message was deleted, remove from database
                    await db.delete_persistent_panel(panel["message_id"])
                except Exception as e:
                    print(f"Error restoring panel {panel['message_id']}: {e}")
                    
        except Exception as e:
            print(f"Error restoring persistent panels: {e}")

def setup(bot):
    bot.add_cog(PersistentPanels(bot))
