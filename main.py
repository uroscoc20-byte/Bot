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
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_BOT_TOKEN not found in environment variables!")

# Initialize bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,
)

# Initialize database and attach to bot
db = Database()
bot.db = db

# ------------------------------
# Import persistent views
# ------------------------------
from tickets import TicketView, TicketActionView, DeleteChannelView, setup_tickets
from verification import VerificationView, VerificationActionView, setup_verification
from leaderboard import LeaderboardView, setup_leaderboard
from apprentice_tickets import (
    ApprenticeTicketView,
    ApprenticeTicketActionView,
    setup_apprentice_tickets,
)
from admin import setup_admin
from stats import setup_stats
from dumb_things import setup_dumb_things

# ------------------------------
# Bot events
# ------------------------------
@bot.event
async def on_ready():
    print(f"✅ Bot logged in as {bot.user} (ID: {bot.user.id})")
    print(f"📊 Connected to {len(bot.guilds)} guild(s)")

    # Initialize database
    await bot.db.init()
    print("✅ Database initialized")


    # Setup all systems/modules
    await setup_tickets(bot)
    print("✅ Ticket system loaded")
    await setup_verification(bot)
    print("✅ Verification system loaded")
    await setup_apprentice_tickets(bot)
    print("✅ Apprentice ticket system loaded")
    await setup_leaderboard(bot)
    print("✅ Leaderboard system loaded")
    await setup_admin(bot)
    print("✅ Admin system loaded")
    await setup_stats(bot)
    print("✅ Stats system loaded")
    await setup_dumb_things(bot)
    print("✅ Dumb things system loaded")

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"⚠️ Failed to sync commands: {e}")

    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="tickets | /panel")
    )
    print("✅ Bot is ready!")


@bot.event
async def on_error(event, *args, **kwargs):
    print(f"❌ Error in {event}: {args} {kwargs}")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"❌ Command error: {error}")


@bot.event
async def on_member_remove(member: discord.Member):
    """Auto-remove user points/leaderboard when they leave"""
    try:
        from points_logger import log_member_left

        # Log points
        await log_member_left(bot, member.id, member.name)

        # Delete points from database
        deleted = await bot.db.delete_user_points(member.id)
        if deleted:
            print(f"✅ Removed points for {member.name} (ID: {member.id})")
    except Exception as e:
        print(f"⚠️ Error auto-removing points for {member.name}: {e}")


# ------------------------------
# Persistent views (MUST be registered before bot starts)
# ------------------------------
bot.add_view(TicketView())
bot.add_view(TicketActionView())
bot.add_view(DeleteChannelView())
bot.add_view(VerificationView())
bot.add_view(VerificationActionView())
bot.add_view(LeaderboardView())
bot.add_view(ApprenticeTicketView())
bot.add_view(ApprenticeTicketActionView())

# ------------------------------
# Start bot + webserver (Render-friendly)
# ------------------------------
if __name__ == "__main__":
    # Start the webserver for Render
    try:
        import webserver
        webserver.start()
        print("✅ Webserver started for uptime monitoring")
    except Exception as e:
        print(f"⚠️ Webserver failed: {e}")

    # Start Discord bot
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("\n👋 Bot shutting down...")
    except Exception as e:
        print(f"❌ Fatal error: {e}")