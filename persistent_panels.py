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

    @tasks.loop(minutes=10)
    async def auto_refresh(self):
        """Auto-refresh and recreate all persistent panels every 10 minutes"""
        try:
            panels = await db.get_persistent_panels()
            for panel in panels:
                try:
                    channel = self.bot.get_channel(panel["channel_id"])
                    if not channel:
                        continue
                    
                    # Try to fetch the message first
                    try:
                        message = await channel.fetch_message(panel["message_id"])
                    except discord.NotFound:
                        # Message was deleted, remove from database
                        await db.delete_persistent_panel(panel["message_id"])
                        continue
                    
                    # Delete old message and create new one to ensure buttons always work
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    
                    # Create new panel
                    if panel["panel_type"] == "leaderboard":
                        # Recreate leaderboard
                        page = panel["data"].get("page", 1)
                        per_page = panel["data"].get("per_page", 10)
                        embed = await create_leaderboard_embed(page=page, per_page=per_page)
                        view = LeaderboardView(page, panel["data"].get("total_pages", 1), per_page)
                        new_message = await channel.send(embed=embed, view=view)
                        
                        # Update database with new message ID
                        await db.delete_persistent_panel(panel["message_id"])
                        await db.save_persistent_panel(
                            channel_id=channel.id,
                            message_id=new_message.id,
                            panel_type="leaderboard",
                            data=panel["data"]
                        )
                    
                    elif panel["panel_type"] == "verification":
                        # Recreate verification panel
                        from verification import VerificationPanelView
                        category_id = panel["data"].get("category_id")
                        embed = discord.Embed(
                            title="🛡️ VERIFICATION PANEL 🛡️",
                            description=(
                                "Welcome to the server!\n"
                                "To gain access, please complete the short verification process below.\n\n"
                                "Click Verify and provide the following information:\n\n"
                                "- In-Game Name – The name you use in the game.\n\n"
                                "- Who Invited You – The name of the person who invited you to the server (if anyone).\n\n"
                                "⚠️ Please make sure the information is accurate and complete.\n"
                                "Once submitted, a staff member will review your verification and grant access as soon as possible."
                            ),
                            color=discord.Color.green(),
                        )
                        view = VerificationPanelView(category_id)
                        new_message = await channel.send(embed=embed, view=view)
                        
                        # Update database with new message ID
                        await db.delete_persistent_panel(panel["message_id"])
                        await db.save_persistent_panel(
                            channel_id=channel.id,
                            message_id=new_message.id,
                            panel_type="verification",
                            data=panel["data"]
                        )
                    
                    elif panel["panel_type"] == "ticket":
                        # Recreate ticket panel
                        from tickets import TicketPanelView
                        categories = panel["data"].get("categories", [])
                        panel_config = panel["data"].get("panel_config", {})
                        embed = discord.Embed(
                            title="🎮 IN-GAME ASSISTANCE 🎮",
                            description=panel_config.get("text", "Select a service below to create a help ticket. Our helpers will assist you!"),
                            color=panel_config.get("color", 0x5865F2),
                        )
                        services = [f"- **{cat['name']}** — {cat.get('points', 0)} points" for cat in categories]
                        embed.add_field(name="📋 Available Services", value="**" + ("\n".join(services) or "No services configured") + "**", inline=False)
                        embed.add_field(
                            name="ℹ️ How it works",
                            value="1. Select a service\n2. Fill out the form\n3. Helpers join\n4. Get help in your private ticket!",
                            inline=False,
                        )
                        view = TicketPanelView(categories)
                        new_message = await channel.send(embed=embed, view=view)
                        
                        # Update database with new message ID
                        await db.delete_persistent_panel(panel["message_id"])
                        await db.save_persistent_panel(
                            channel_id=channel.id,
                            message_id=new_message.id,
                            panel_type="ticket",
                            data=panel["data"]
                        )
                    
                    # Add more panel types here as needed
                    
                except Exception as e:
                    print(f"Error recreating panel {panel['message_id']}: {e}")
                    
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
        
        await ctx.followup.send("✅ **Persistent leaderboard created!** It will auto-refresh every 10 minutes.", ephemeral=True)

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
        """Restore all persistent panels on bot startup by recreating them"""
        try:
            panels = await db.get_persistent_panels()
            for panel in panels:
                try:
                    channel = self.bot.get_channel(panel["channel_id"])
                    if not channel:
                        continue
                    
                    # Delete old message and create new one
                    try:
                        message = await channel.fetch_message(panel["message_id"])
                        await message.delete()
                    except discord.NotFound:
                        pass
                    except Exception:
                        pass
                    
                    # Create new panel
                    if panel["panel_type"] == "leaderboard":
                        # Recreate leaderboard
                        page = panel["data"].get("page", 1)
                        per_page = panel["data"].get("per_page", 10)
                        embed = await create_leaderboard_embed(page=page, per_page=per_page)
                        view = LeaderboardView(page, panel["data"].get("total_pages", 1), per_page)
                        new_message = await channel.send(embed=embed, view=view)
                        
                        # Update database with new message ID
                        await db.delete_persistent_panel(panel["message_id"])
                        await db.save_persistent_panel(
                            channel_id=channel.id,
                            message_id=new_message.id,
                            panel_type="leaderboard",
                            data=panel["data"]
                        )
                    
                    elif panel["panel_type"] == "verification":
                        # Recreate verification panel
                        from verification import VerificationPanelView
                        category_id = panel["data"].get("category_id")
                        embed = discord.Embed(
                            title="🛡️ VERIFICATION PANEL 🛡️",
                            description=(
                                "Welcome to the server!\n"
                                "To gain access, please complete the short verification process below.\n\n"
                                "Click Verify and provide the following information:\n\n"
                                "- In-Game Name – The name you use in the game.\n\n"
                                "- Who Invited You – The name of the person who invited you to the server (if anyone).\n\n"
                                "⚠️ Please make sure the information is accurate and complete.\n"
                                "Once submitted, a staff member will review your verification and grant access as soon as possible."
                            ),
                            color=discord.Color.green(),
                        )
                        view = VerificationPanelView(category_id)
                        new_message = await channel.send(embed=embed, view=view)
                        
                        # Update database with new message ID
                        await db.delete_persistent_panel(panel["message_id"])
                        await db.save_persistent_panel(
                            channel_id=channel.id,
                            message_id=new_message.id,
                            panel_type="verification",
                            data=panel["data"]
                        )
                    
                    elif panel["panel_type"] == "ticket":
                        # Recreate ticket panel
                        from tickets import TicketPanelView
                        categories = panel["data"].get("categories", [])
                        panel_config = panel["data"].get("panel_config", {})
                        embed = discord.Embed(
                            title="🎮 IN-GAME ASSISTANCE 🎮",
                            description=panel_config.get("text", "Select a service below to create a help ticket. Our helpers will assist you!"),
                            color=panel_config.get("color", 0x5865F2),
                        )
                        services = [f"- **{cat['name']}** — {cat.get('points', 0)} points" for cat in categories]
                        embed.add_field(name="📋 Available Services", value="**" + ("\n".join(services) or "No services configured") + "**", inline=False)
                        embed.add_field(
                            name="ℹ️ How it works",
                            value="1. Select a service\n2. Fill out the form\n3. Helpers join\n4. Get help in your private ticket!",
                            inline=False,
                        )
                        view = TicketPanelView(categories)
                        new_message = await channel.send(embed=embed, view=view)
                        
                        # Update database with new message ID
                        await db.delete_persistent_panel(panel["message_id"])
                        await db.save_persistent_panel(
                            channel_id=channel.id,
                            message_id=new_message.id,
                            panel_type="ticket",
                            data=panel["data"]
                        )
                    
                    # Add more panel types here as needed
                    
                except Exception as e:
                    print(f"Error recreating panel {panel['message_id']}: {e}")
                    
        except Exception as e:
            print(f"Error restoring persistent panels: {e}")

def setup(bot):
    bot.add_cog(PersistentPanels(bot))
