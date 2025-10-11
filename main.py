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
bot = commands.Bot(command_prefix="/", intents=intents)

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
            result = None
            try:
                # Try native loader
                result = bot.load_extension(ext)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                # Fallback: manual import and setup
                module = importlib.import_module(ext)
                setup_fn = getattr(module, "setup", None)
                if setup_fn is None:
                    raise RuntimeError("setup() not found in extension")
                result = setup_fn(bot)
                if inspect.isawaitable(result):
                    await result
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
