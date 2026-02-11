"""Utility functions for ticket system"""
from typing import List
import config

def format_boss_name_for_select(boss: str) -> str:
    boss_select_names = {"Ultra Lich": "Lich Lord", "Ultra Beast": "Beast", "Ultra Deimos": "Deimos", "Ultra Flibbi": "Void Flibbi", "Ultra Bane": "Void Nightbane", "Ultra Xyfrag": "Void Xyfrag", "Ultra Kathool": "Kathool", "Ultra Astral": "Astral Shrine", "Ultra Champion Drakath": "Champion Drakath"}
    return boss_select_names.get(boss, boss)

def format_boss_name_for_embed(boss: str) -> str:
    boss_embed_names = {"Ultra Lich": "lichlord", "Ultra Beast": "beast", "Ultra Deimos": "deimos", "Ultra Flibbi": "voidflibbi", "Ultra Bane": "voidnightbane", "Ultra Xyfrag": "voidxyfrag", "Ultra Kathool": "kathool", "Ultra Astral": "astralshrine", "Ultra Champion Drakath": "championdrakath", "Ultra Dage": "ultradage", "Ultra Tyndarius": "ultratyndarius", "Ultra Engineer": "ultraengineer", "Ultra Warden": "ultrawarden", "Ultra Ezrajal": "ultraezrajal", "Ultra Nulgath": "ultranulgath", "Ultra Drago": "ultradrago", "Ultra Darkon": "ultradarkon"}
    return boss_embed_names.get(boss, boss.lower().replace(" ", ""))

def generate_join_commands(category: str, selected_bosses: List[str], room_number: int, server: str) -> str:
    commands = []
    if category == "Daily 4-Man Express":
        boss_order = ["Ultra Dage", "Ultra Tyndarius", "Ultra Engineer", "Ultra Warden", "Ultra Ezrajal"]
        for boss in boss_order:
            if boss in selected_bosses:
                commands.append(f"`/join ultra{boss.replace('Ultra ', '').lower()}-{room_number}`")
    elif category == "Daily 7-Man Express":
        boss_order = ["Ultra Lich", "Ultra Beast", "Ultra Deimos", "Ultra Flibbi", "Ultra Bane", "Ultra Xyfrag", "Ultra Kathool", "Ultra Astral"]
        for boss in boss_order:
            if boss in selected_bosses:
                if boss == "Ultra Lich":
                    commands.append(f"`/join frozenlair-{room_number}`")
                elif boss == "Ultra Beast":
                    commands.append(f"`/join sevencircleswar-{room_number}`")
                elif boss == "Ultra Deimos":
                    commands.append(f"`/join deimos-{room_number}`")
                elif boss == "Ultra Flibbi":
                    commands.append(f"`/join voidflibbi-{room_number}`")
                elif boss == "Ultra Bane":
                    commands.append(f"`/join voidnightbane-{room_number}`")
                elif boss == "Ultra Xyfrag":
                    commands.append(f"`/join voidxyfrag-{room_number}`")
                elif boss == "Ultra Kathool":
                    commands.append(f"`/join kathooldepths-{room_number}`")
                elif boss == "Ultra Astral":
                    commands.append(f"`/join astralshrine-{room_number}`")
    elif category == "Weekly Ultra Express":
        boss_order = ["Ultra Dage", "Ultra Nulgath", "Ultra Drago", "Ultra Darkon", "Ultra Champion Drakath"]
        for boss in boss_order:
            if boss in selected_bosses:
                if boss == "Ultra Champion Drakath":
                    commands.append(f"`/join championdrakath-{room_number}`")
                else:
                    commands.append(f"`/join ultra{boss.replace('Ultra ', '').lower()}-{room_number}`")
    elif category == "UltraSpeaker Express":
        commands.append(f"`/join ultraspeaker-{room_number}`")
    elif category == "Ultra Gramiel Express":
        commands.append(f"`/join ultragramiel-{room_number}`")
    elif category == "GrimChallenge Express":
        commands.append(f"`/join grimchallenge-{room_number}`")
    elif category == "Daily Temple Express":
        commands.append(f"`/join templeshrine-{room_number}`")
    return "\n".join(commands) if commands else ""