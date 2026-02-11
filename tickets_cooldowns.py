"""Cooldown management for ticket actions"""
import asyncio
import time
from typing import Optional

ticket_locks = {}
join_cooldowns = {}
leave_cooldowns = {}
COOLDOWN_SECONDS = 120

def get_ticket_lock(channel_id: int):
    if channel_id not in ticket_locks:
        ticket_locks[channel_id] = asyncio.Lock()
    return ticket_locks[channel_id]

def check_cooldown(user_id: int, cooldown_dict: dict) -> Optional[int]:
    if user_id in cooldown_dict:
        elapsed = time.time() - cooldown_dict[user_id]
        if elapsed < COOLDOWN_SECONDS:
            return int(COOLDOWN_SECONDS - elapsed)
    return None

def set_cooldown(user_id: int, cooldown_dict: dict):
    cooldown_dict[user_id] = time.time()