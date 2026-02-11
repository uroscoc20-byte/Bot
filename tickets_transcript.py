"""Transcript generation for closed tickets"""

import discord
import io
import config


async def generate_transcript(channel: discord.TextChannel, bot, ticket: dict, is_cancelled: bool = False):
    """Generate transcript and save to transcript channel"""
    transcript_channel_id = config.CHANNEL_IDS.get("TRANSCRIPT")
    
    if not transcript_channel_id:
        return
    
    transcript_channel = bot.get_channel(transcript_channel_id)
    if not transcript_channel:
        return
    
    messages = []
    async for msg in channel.history(limit=500, oldest_first=True):
        messages.append(msg)
    
    status = "CANCELLED" if is_cancelled else "CLOSED"
    
    transcript_lines = [
        f"=== TRANSCRIPT FOR {channel.name.upper()} ===",
        f"Status: {status}",
        f"Category: {ticket['category']}",
        f"Requestor: {ticket['requestor_id']}",
        f"Room Number: {ticket['random_number']}",
        f"Created: {channel.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "=" * 50,
        ""
    ]
    
    for msg in messages:
        timestamp = msg.created_at.strftime('%Y-%m-%d %H:%M:%S')
        author = f"{msg.author.name}#{msg.author.discriminator}" if msg.author.discriminator != "0" else msg.author.name
        content = msg.content or "[Embed/Attachment]"
        
        transcript_lines.append(f"[{timestamp}] {author}: {content}")
        
        if msg.embeds:
            for embed in msg.embeds:
                if embed.title:
                    transcript_lines.append(f"  └─ Embed: {embed.title}")
    
    transcript_text = "\n".join(transcript_lines)
    
    file = discord.File(
        io.BytesIO(transcript_text.encode('utf-8')),
        filename=f"transcript-{channel.name}-{ticket['random_number']}.txt"
    )
    
    title_status = "Cancelled" if is_cancelled else "Closed"
    
    embed = discord.Embed(
        title=f"📄 Transcript: {channel.name} ({title_status})",
        description=f"**Category:** {ticket['category']}\n**Room Number:** {ticket['random_number']}\n**Status:** {title_status}",
        color=config.COLORS["DANGER"] if is_cancelled else config.COLORS["PRIMARY"],
        timestamp=discord.utils.utcnow()
    )
    
    await transcript_channel.send(embed=embed, file=file)