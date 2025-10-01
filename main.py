# main.py
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import webserver
import asyncio
from database import db

# ---------- LOAD ENV ----------
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("ERROR: DISCORD_BOT_TOKEN not set!")
    exit(1)

# ---------- BOT INTENTS ----------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# ---------- EXTENSIONS ----------
initial_extensions = [
    "setup",
    "tickets",
    "points",
    "custom_commands",
    "talk"  # optional, if you have a talk module
]

# ---------- ASYNC MAIN ----------
async def main():
    # Initialize the database
    await db.init()
    print("✅ Database initialized.")

    # Load all extensions
    for ext in initial_extensions:
        try:
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
