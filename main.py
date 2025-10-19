# main.py
import discord
from discord.ext import commands
import os
import webserver
import asyncio
import re
from database import db
from leaderboard import register_persistent_views, create_leaderboard_embed
from verification import VerificationPanelView

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
    except Exception as e:
        print(f"❌ Slash command sync failed: {e}")
    # Register persistent views so leaderboard/verification controls keep working after restarts
    try:
        register_persistent_views(bot)
        bot.add_view(VerificationPanelView(None))
        print("✅ Persistent views registered.")
    except Exception as e:
        print(f"⚠️ Persistent view registration failed: {e}")

# ---------- EXTENSIONS ----------
initial_extensions = [
    "setup",
    "tickets",
    "points",
    "custom_commands",
    "custom_simple",  # manage !custom text commands and edit via modal
    "audit_log",      # log slash and prefix commands
    "verification",   # verification panel/tickets
    "bot_speak"  # optional
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

    # Start background tasks after bot is running
    async def background_tasks():
        # Auto-refresh leaderboard messages every 15 minutes
        await bot.wait_until_ready()
        print("✅ Background tasks starting...")
        while not bot.is_closed():
            try:
                cfg = await db.load_config("leaderboard_messages") or []
                if isinstance(cfg, list):
                    for entry in cfg[:25]:  # limit per cycle to avoid rate limits
                        try:
                            channel_id = entry.get("channel_id")
                            message_id = entry.get("message_id")
                            if not channel_id or not message_id:
                                continue
                            channel = bot.get_channel(int(channel_id))
                            if not channel:
                                continue
                            try:
                                msg = await channel.fetch_message(int(message_id))
                            except Exception:
                                continue
                            # Determine current page from footer if possible
                            page = 1
                            if msg.embeds:
                                footer_text = (msg.embeds[0].footer and msg.embeds[0].footer.text) or ""
                                m = re.search(r"Page\s+(\d+)\/(\d+)", footer_text or "")
                                if m:
                                    try:
                                        page = max(1, int(m.group(1)))
                                    except Exception:
                                        page = 1
                            new_embed = await create_leaderboard_embed(page=page, per_page=10)
                            try:
                                await msg.edit(embed=new_embed)
                            except Exception:
                                pass
                else:
                    # If malformed, reset it
                    await db.save_config("leaderboard_messages", [])
            except Exception as e:
                print(f"⚠️ Leaderboard auto-refresh task error: {e}")
            # 15 minutes
            try:
                await asyncio.sleep(15 * 60)
            except Exception:
                break

    bot.loop.create_task(background_tasks())

    await bot.start(TOKEN)

# ---------- RUN ----------
if __name__ == "__main__":
    asyncio.run(main())