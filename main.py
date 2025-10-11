# main.py
import discord
from discord.ext import commands
import os
import webserver
import asyncio
import importlib
import inspect
from database import db

# ---------- LOAD ENV ----------
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("ERROR: DISCORD_BOT_TOKEN not set!")
    exit(1)

# ---------- BOT INTENTS ----------
intents = discord.Intents.default()
intents.message_content = True
async def fetch_prefix(bot, message):
    try:
        return await db.get_prefix()
    except Exception:
        return "!"

bot = commands.Bot(command_prefix=fetch_prefix, intents=intents)

# ---------- EVENTS ----------
@bot.event
async def on_ready():
    try:
        # discord.py style
        if hasattr(bot, "tree"):
            await bot.tree.sync()
        # Pycord style
        if hasattr(bot, "sync_commands"):
            await bot.sync_commands()
        print("✅ Slash commands synced.")
    except Exception as e:
        print(f"❌ Slash command sync failed: {e}")

# ---------- EXTENSIONS ----------
initial_extensions = [
    "setup",
    "tickets",
    "points",
    "custom_commands",
    "bot_speak"  # optional
]

# ---------- ASYNC MAIN ----------
async def main():
    # Initialize database
    await db.init()
    print("✅ Database initialized.")

    # Load all extensions (compatible with discord.py and Pycord)
    for ext in initial_extensions:
        try:
            # Prefer synchronous loader since our cogs use sync setup()
            bot.load_extension(ext)
            print(f"✅ Loaded extension: {ext}")
        except Exception as e:
            print(f"❌ Failed to load extension {ext}: {e}")

    # Start Render webserver (healthcheck)
    webserver.start()
    print("✅ Webserver started for Render healthchecks.")

    # Run the bot
    await bot.start(TOKEN)

# ---------- RUN ----------
if __name__ == "__main__":
    asyncio.run(main())
