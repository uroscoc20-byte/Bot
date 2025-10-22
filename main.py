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
intents.members = True  # needed for verification/tickets
bot = commands.Bot(command_prefix="/", intents=intents)

# ---------- EVENTS ----------
@bot.event
async def on_ready():
    print(f"✅ Bot logged in as {bot.user} ({bot.user.id})")
    try:
        # Sync slash commands globally
        if hasattr(bot, "tree"):
            await bot.tree.sync()
        print("✅ Slash commands synced globally.")

        # Restore persistent panels (leaderboard, ticket, verification, etc.)
        persistent_panels_cog = bot.get_cog("PersistentPanels")
        if persistent_panels_cog:
            await persistent_panels_cog.restore_persistent_panels()
            print("✅ Persistent panels restored.")
    except Exception as e:
        print(f"❌ Error in on_ready: {e}")

# ---------- EXTENSIONS / COGS ----------
initial_extensions = [
    "setup",
    "tickets",            # ticket system + ticket panels
    "points",             # user points & leaderboard
    "custom_commands",    # manage custom commands
    "custom_simple",      # modal-based custom command editing
    "audit_log",          # logs command usage
    "verification",       # verification panel & tickets
    "persistent_panels",  # persistent leaderboard / ticket / verification panels
    "bot_speak",          # /talk and any chat commands
    "guild_control",      # home guild enforcement & leave commands
]

# ---------- ASYNC MAIN ----------
async def main():
    # Initialize database (SQLite or Firestore)
    await db.init()
    print("✅ Database initialized.")

    # Load all extensions / cogs
    for ext in initial_extensions:
        try:
            bot.load_extension(ext)
            print(f"✅ Loaded extension: {ext}")
        except Exception as e:
            print(f"❌ Failed to load extension {ext}: {e}")

    # Start webserver for healthchecks
    try:
        webserver.start()
        print("✅ Webserver started for Render healthchecks.")
    except Exception as e:
        print(f"❌ Failed to start webserver: {e}")

    # Start bot
    await bot.start(TOKEN)

# ---------- RUN ----------
if __name__ == "__main__":
    asyncio.run(main())
