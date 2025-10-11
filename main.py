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
        await bot.tree.sync()
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

    # Load all extensions
    for ext in initial_extensions:
        try:
            await bot.load_extension(ext)  # <-- await is required in discord.py 2.6+
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