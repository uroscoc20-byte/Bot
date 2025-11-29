# main.py
# Discord Helper Ticket Bot - Main Entry Point

import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
from database import Database

# Load environment variables
load_dotenv()

# Import webserver for uptime monitoring
try:
    import webserver
    webserver.start()
    print("✅ Webserver started for uptime monitoring")
except Exception as e:
    print(f"⚠️ Webserver not started: {e}")

# Bot configuration
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_BOT_TOKEN not found in environment variables!")

# Initialize bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(
    command_prefix="!",  # Prefix for text commands (mainly using slash commands)
    intents=intents,
    help_command=None,  # We'll create custom help
)

# Initialize database
db = Database()

# Store database in bot for access in cogs
bot.db = db


@bot.event
async def on_ready():
    """Called when bot successfully connects to Discord"""
    print(f"✅ Bot logged in as {bot.user.name} (ID: {bot.user.id})")
    print(f"📊 Connected to {len(bot.guilds)} guild(s)")
    
    # Initialize database
    await bot.db.init()
    print("✅ Database initialized")
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"⚠️ Failed to sync commands: {e}")
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="tickets | /help"
        )
    )
    print("✅ Bot is ready!")


@bot.event
async def on_error(event, *args, **kwargs):
    """Global error handler"""
    print(f"❌ Error in {event}: {args} {kwargs}")


@bot.event
async def on_command_error(ctx, error):
    """Command error handler"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.", ephemeral=True)
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore unknown commands
    else:
        print(f"❌ Command error: {error}")


async def load_cogs():
    """Load all cog files"""
    cogs = [
        "cogs.tickets",
        "cogs.verification",
        "cogs.leaderboard",
        "cogs.admin",
    ]
    
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"✅ Loaded {cog}")
        except Exception as e:
            print(f"❌ Failed to load {cog}: {e}")


async def main():
    """Main entry point"""
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot shutting down...")
    except Exception as e:
        print(f"❌ Fatal error: {e}")