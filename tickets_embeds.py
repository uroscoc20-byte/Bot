import discord

class TicketEmbed:
    def __init__(self, title, description, color=0x00ff00):
        self.title = title
        self.description = description
        self.color = color

    def create_embed(self):
        embed = discord.Embed(title=self.title, description=self.description, color=self.color)
        return embed

# Example of usage:
# ticket_embed = TicketEmbed("Ticket Title", "Ticket Description")
# embed = ticket_embed.create_embed()