# main.py
import discord
from discord.ext import commands
import os
import webserver
import asyncio
from database import db
from tickets import TicketPanelView, DEFAULT_POINT_VALUES, DEFAULT_HELPER_SLOTS, DEFAULT_SLOTS, DEFAULT_QUESTIONS
from verification import VerificationPanelView, VerificationTicketView
from points import LeaderboardView

# ---------- LOAD ENV ----------
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("ERROR: DISCORD_BOT_TOKEN not set!")
    exit(1)

# ---------- BOT INTENTS ----------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# ---------- EVENTS ----------
@bot.event
async def on_ready():
    try:
        if hasattr(bot, "tree"):
            await bot.tree.sync()
        if hasattr(bot, "sync_commands"):
            await bot.sync_commands()
        print("✅ Slash commands synced.")
    except Exception as e:
        print(f"❌ Slash command sync failed: {e}")

    # Register persistent views once so panels/buttons keep working forever
    if not getattr(bot, "_persistent_views_registered", False):
        try:
            # Ticket panel persistent view
            bot.add_view(await TicketPanelView.build_with_current_categories())

            # Verification panel persistent view
            cfg = await db.load_config("verification_category")
            verification_category_id = (cfg or {}).get("id")
            bot.add_view(VerificationPanelView(verification_category_id))

            # Verification ticket close button persistent view
            bot.add_view(VerificationTicketView())

            # Leaderboard persistent view with generic state; page state is inferred from embed footer
            # Provide a safe default of 1 page; buttons will disable appropriately when used
            bot.add_view(LeaderboardView(current_page=1, total_pages=1, per_page=20))

            bot._persistent_views_registered = True
            print("✅ Persistent views registered.")
        except Exception as e:
            print(f"❌ Failed to register persistent views: {e}")

# ---------- EXTENSIONS ----------
initial_extensions = [
    "setup",
    "tickets",
    "points",
    "custom_commands",
    "custom_simple",  # manage !custom text commands and edit via modal
    "audit_log",      # log slash and prefix commands
    "verification",   # verification panel/tickets
    "bot_speak"  # optional
]

# ---------- ASYNC MAIN ----------
async def main():
    await db.init()
    print("✅ Database initialized.")

    for ext in initial_extensions:
        try:
            bot.load_extension(ext)
            print(f"✅ Loaded extension: {ext}")
        except Exception as e:
            print(f"❌ Failed to load extension {ext}: {e}")

    webserver.start()
    print("✅ Webserver started for Render healthchecks.")

    await bot.start(TOKEN)

# ---------- RUN ----------
if __name__ == "__main__":
    asyncio.run(main())