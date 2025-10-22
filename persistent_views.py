# persistent_views.py
import discord
from discord.ext import commands
from database import db
from verification import VerificationPanelView

# You can import other views for other panels later
# from ticket_module import TicketPanelView

class PersistentViewsModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        panels = await db.get_persistent_panels()
        restored = 0
        for panel in panels:
            panel_type = panel["panel_type"]
            data = panel.get("data") or {}

            view = None
            # Add here new panel types as needed
            if panel_type == "verification":
                category_id = data.get("category_id")
                if category_id is not None:
                    view = VerificationPanelView(category_id)
            # elif panel_type == "ticket":
            #     view = TicketPanelView(data)

            if view:
                try:
                    self.bot.add_view(view)
                    restored += 1
                except Exception as e:
                    print(f"⚠️ Failed to restore panel {panel['message_id']}: {e}")

        print(f"✅ Restored {restored} persistent views")

def setup(bot):
    bot.add_cog(PersistentViewsModule(bot))
