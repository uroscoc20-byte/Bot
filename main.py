# main.py
# Discord Helper Ticket Bot - Main Entry Point

import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
from database import Database

# Load environment variables
load_dotenv()

# Import webserver for uptime monitoring
try:
    import webserver
    webserver.start()
    print("✅ Webserver started for uptime monitoring")
except Exception as e:
    print(f"⚠️ Webserver not started: {e}")

# Bot configuration
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_BOT_TOKEN not found in environment variables!")

# Initialize bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(
    command_prefix="!",  # Prefix for text commands (mainly using slash commands)
    intents=intents,
    help_command=None,  # We'll create custom help
)

# Initialize database
db = Database()

# Store database in bot for access in modules
bot.db = db


@bot.event
async def on_ready():
    """Called when bot successfully connects to Discord"""
    print(f"✅ Bot logged in as {bot.user.name} (ID: {bot.user.id})")
    print(f"📊 Connected to {len(bot.guilds)} guild(s)")
    
    # Initialize database
    await bot.db.init()
    print("✅ Database initialized")
    
    # Import and register persistent views (CRITICAL - FIXES BUTTON FAILURES)
    from tickets import TicketView, TicketActionView, DeleteChannelView
    from verification import VerificationView, VerificationActionView
    from leaderboard import LeaderboardView
    
    bot.add_view(TicketView())
    bot.add_view(TicketActionView())
    bot.add_view(DeleteChannelView())
    bot.add_view(VerificationView())
    bot.add_view(VerificationActionView())
    bot.add_view(LeaderboardView())
    
    print("✅ Persistent views registered - Buttons will work after restarts!")
    
    # Setup all modules
    from tickets import setup_tickets
    from verification import setup_verification
    from leaderboard import setup_leaderboard
    from admin import setup_admin
    
    await setup_tickets(bot)
    print("✅ Ticket system loaded")
    
    await setup_verification(bot)
    print("✅ Verification system loaded")
    
    await setup_leaderboard(bot)
    print("✅ Leaderboard system loaded")
    
    await setup_admin(bot)
    print("✅ Admin system loaded")
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"⚠️ Failed to sync commands: {e}")
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="tickets | /panel"
        )
    )
    print("✅ Bot is ready!")


@bot.event
async def on_error(event, *args, **kwargs):
    """Global error handler"""
    print(f"❌ Error in {event}: {args} {kwargs}")


@bot.event
async def on_command_error(ctx, error):
    """Command error handler"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.", ephemeral=True)
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore unknown commands
    else:
        print(f"❌ Command error: {error}")


@bot.event
async def on_member_remove(member: discord.Member):
    """Auto-delete user points and leaderboard entry when they leave"""
    try:
        from points_logger import log_member_left
        deleted = await bot.db.delete_user_points(member.id)
        if deleted:
            print(f"✅ Auto-removed points for {member.name} (ID: {member.id}) - Left server")
            await log_member_left(bot, member.id, member.name)
    except Exception as e:
        print(f"⚠️ Error auto-removing points for {member.name}: {e}")


if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("\n👋 Bot shutting down...")
    except Exception as e:
        print(f"❌ Fatal error: {e}")