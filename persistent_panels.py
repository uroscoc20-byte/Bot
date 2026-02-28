# persistent_panels.py
import discord
import asyncio

class PersistentPanels:
    """Helper to manage persistent panels across restarts"""

    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    async def register_panel(self, view: discord.ui.View, message: discord.Message, panel_type: str, data=None):
        """Save panel in DB and register view"""
        await self.db.db.execute(
            "INSERT OR REPLACE INTO persistent_panels (id, channel_id, message_id, panel_type, data) VALUES (?, ?, ?, ?, ?)",
            (message.id, message.channel.id, message.id, panel_type, data or "{}")
        )
        await self.db.db.commit()
        self.bot.add_view(view, message_id=message.id)

    async def load_all_panels(self):
        """Load all panels from DB and re-add their views"""
        async with self.db.db.execute("SELECT channel_id, message_id, panel_type, data FROM persistent_panels") as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                channel_id, message_id, panel_type, data = row
                try:
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        continue
                    message = await channel.fetch_message(message_id)
                except:
                    continue

                # Re-add the appropriate view per panel type
                if panel_type == "ticket":
                    from tickets import TicketView
                    self.bot.add_view(TicketView(), message_id=message.id)
                elif panel_type == "leaderboard":
                    from leaderboard import LeaderboardView
                    self.bot.add_view(LeaderboardView(), message_id=message.id)
                elif panel_type == "verification":
                    from verification import VerificationView
                    self.bot.add_view(VerificationView(), message_id=message.id)
                elif panel_type == "apprentice_ticket":
                    from apprentice_tickets import ApprenticeTicketView
                    self.bot.add_view(ApprenticeTicketView(), message_id=message.id)
                # Add other panel types here as needed