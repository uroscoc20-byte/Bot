# utils/transcript.py
import discord
from datetime import datetime
from setup import CONFIG

async def generate_ticket_transcript(ticket_info, bot, rewarded=False):
    """
    ticket_info: dict with keys:
        - embed_msg
        - requestor
        - helpers
        - category
    """
    channel = ticket_info["embed_msg"].channel
    transcript_text = f"Ticket Transcript for {ticket_info['category']}\n"
    transcript_text += f"Requestor: <@{ticket_info['requestor']}>\n"
    transcript_text += f"Helpers: {', '.join(f'<@{h}>' for h in ticket_info['helpers'] if h)}\n"
    transcript_text += f"Opened at: {channel.created_at}\n"
    transcript_text += f"Closed at: {datetime.utcnow()}\n"
    transcript_text += f"Rewarded: {'Yes' if rewarded else 'No'}\n\n"

    # Fetch last 100 messages
    messages = await channel.history(limit=100, oldest_first=True).flatten()
    for msg in messages:
        transcript_text += f"[{msg.created_at}] {msg.author}: {msg.content}\n"

    # Send transcript to configured transcript channel
    transcript_channel_id = CONFIG.get("transcript_channel")
    if not transcript_channel_id:
        return
    guild = channel.guild
    transcript_channel = guild.get_channel(transcript_channel_id)
    if transcript_channel:
        # Send as file
        from io import StringIO
        file = discord.File(StringIO(transcript_text), filename=f"transcript-{channel.name}.txt")
        await transcript_channel.send(file=file)
