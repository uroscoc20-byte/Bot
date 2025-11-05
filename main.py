# main.py
import discord
from discord.ext import commands
import os
import webserver
import asyncio
from database import db

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
        
        # Restore persistent panels
        try:
            persistent_panels_cog = bot.get_cog("PersistentPanels")
            if persistent_panels_cog:
                await persistent_panels_cog.restore_persistent_panels()
                print("✅ Persistent panels restored.")
        except Exception as e:
            print(f"❌ Failed to restore persistent panels: {e}")
            
    except Exception as e:
        print(f"❌ Slash command sync failed: {e}")

# ---------- EXTENSIONS ----------
initial_extensions = [
    "setup",          # setup commands for roles, channels, etc.
    "tickets",        # ticket system
    "points",         # points system (add/remove/check points)
    "leaderboard",    # leaderboard commands
    "custom_commands", # custom command management
    "custom_simple",  # manage !custom text commands and edit via modal
    "auditlog",       # log slash and prefix commands (fixed name)
    "verification",   # verification panel/tickets
    "persistent_panels",  # persistent panels with auto-refresh
    "bot_speak"       # talk command
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