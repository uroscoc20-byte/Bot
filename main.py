import discord
from discord.ext import commands
import asyncio
import os

# ---------------------------
# BOT SETUP
# ---------------------------

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.guilds = True
INTENTS.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=INTENTS
)

# ---------------------------
# LOAD COGS
# ---------------------------

async def load_extensions():
    await bot.load_extension("leaderboard")  # leaderboard.py


# ---------------------------
# SYNC SLASH COMMANDS
# ---------------------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    # sync slash commands globally
    try:
        synced = await bot.tree.sync()
        print(f"Synchronized {len(synced)} slash commands.")
    except Exception as e:
        print("Slash sync error:", e)

    print("Bot is ready!")


# ---------------------------
# RUN BOT
# ---------------------------

async def main():
    async with bot:
        await load_extensions()

        # Get token from env OR edit directly here
        TOKEN = os.getenv("DISCORD_BOT_TOKEN") or "YOUR_BOT_TOKEN_HERE"

        await bot.start(TOKEN)


# ---------------------------
# START
# ---------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot shutting down...")
