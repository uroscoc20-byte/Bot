# main.py
import discord
from discord.ext import commands
import os
import webserver
import asyncio
from database import db

# ---------- DISCORD TOKEN ----------
# Token is stored in Render's Environment Variables
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("ERROR: DISCORD_BOT_TOKEN not set in Render Environment Variables!")
    exit(1)

# ---------- BOT INTENTS ----------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# ---------- COG EXTENSIONS ----------
initial_extensions = [
    "setup",
    "tickets",
    "points",
    "custom_commands",
    "talk"  # optional
]

# ---------- ASYNC MAIN ----------
async def main():
    # Initialize database
    await db.init()
    print("✅ Database initialized.")

    # Load all extensions
    for ext in initial_extensions:
        try:
            bot.load_extension(ext)
            print(f"✅ Loaded extension: {ext}")
        except Exception as e:
            print(f"❌ Failed to load extension {ext}: {e}")

    # Start Render webserver for healthchecks
    webserver.start()
    print("✅ Webserver started for Render healthchecks.")

    # Start Discord bot
    await bot.start(TOKEN)

# ---------- RUN ----------
if __name__ == "__main__":
    asyncio.run(main())
