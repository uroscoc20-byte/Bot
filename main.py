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

GUILD_ID = 123456789012345678  # <-- Replace with your server ID

# ---------- BOT INTENTS ----------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# ---------- EVENTS ----------
@bot.event
async def on_ready():
    try:
        # Sync commands for your guild only (instant availability)
        guild = discord.Object(id=GUILD_ID)
        await bot.tree.sync(guild=guild)
        print("✅ Slash commands synced for guild.")

        # Restore persistent panels if cog loaded
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
    "setup",
    "tickets",
    "points",
    "custom_commands",
    "custom_simple",      # manage !custom text commands and edit via modal
    "audit_log",          # log slash and prefix commands
    "verification",       # verification panel/tickets
    "persistent_panels",  # persistent panels with auto-refresh
    "bot_speak",          # optional
    "leaderboard"         # points/leaderboard cog with rename support
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
