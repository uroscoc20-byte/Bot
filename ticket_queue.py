# ticket_queue.py
# Simple queue info for tickets

async def get_ticket_queue_position(bot)
    
    Returns how many tickets are currently open before the one being created.
    
    # Fetch all open tickets from the database
    open_tickets = await bot.db.get_open_tickets()  # Make sure this returns list of tickets
    # Subtract 1 if counting the ticket being created right now
    return len(open_tickets)
