"""
Central hub for the ticket system - imports and re-exports all ticket functionality
"""

import discord
import traceback

try:
    from tickets_modals import TicketModal
    from tickets_buttons_actions import TicketActionView, DeleteChannelView
    from tickets_buttons_panel import TicketView
    from tickets_commands import setup_tickets
    from tickets_embeds import create_ticket_embed
    from tickets_utils import generate_join_commands
    
    # Re-export everything main.py needs
    __all__ = [
        'TicketView',
        'TicketActionView',
        'DeleteChannelView',
        'setup_tickets',
        'TicketModal',
        'create_ticket_embed',
        'generate_join_commands'
    ]
    
    print("✅ Tickets module loaded successfully")
    
except ImportError as e:
    print(f"❌ Error loading tickets module: {e}")
    traceback.print_exc()
