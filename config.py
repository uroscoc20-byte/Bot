# config.py
# Discord Helper Ticket Bot Configuration
# Replace all IDs with your actual Discord server IDs

# ============================================================================
# ROLE IDS - Replace with your Discord role IDs
# ============================================================================
ROLE_IDS = {
    "ADMIN": 1345073680610496602,      # Admin role ID
    "STAFF": 1374821509268373686,      # Staff role ID
    "OFFICER": 1445116463253033053,    # Officer role ID (NEW!)
    "HELPER": 1393262175170334750,     # Helper role ID
    "RESTRICTED": 1405930080256921732, # Restricted role - can't open tickets or use buttons (NEW!)
}

# ============================================================================
# CHANNEL/CATEGORY IDS - Replace with your Discord channel/category IDs
# ============================================================================
CHANNEL_IDS = {
    "TICKET_PANEL": 1358536986679443496,        # Channel where ticket panel is posted
    "RULES": 1395830522877579304,               # Rules channel
    "VERIFICATION_CATEGORY": 1351864881585852479,  # Category for verification tickets
    "TICKETS_CATEGORY": 1357314571525816442,    # Category for helper tickets
    "TRANSCRIPT": 1357314848253542570,          # Transcript channel
}

# ============================================================================
# CUSTOM EMOJI - Your server's custom emoji
# ============================================================================
CUSTOM_EMOJI = "<:URE:1429522388395233331>"  # Replace with your custom emoji

# ============================================================================
# TICKET CATEGORIES - Define your ticket types
# ============================================================================
CATEGORIES = [
    "UltraSpeaker Express",
    "Ultra Gramiel Express",
    "Daily 4-Man Express",
    "Daily 7-Man Express",
    "Weekly Ultra Express",
    "GrimChallenge Express",
    "Daily Temple Express",
]

# Category metadata with descriptions
CATEGORY_METADATA = {
    "UltraSpeaker Express": {
        "description": "The First Speaker",
        "prefix": "UltraSpeaker",
    },
    "Ultra Gramiel Express": {
        "description": "Ultra Gramiel",
        "prefix": "UltraGramiel",
    },
    "Daily 4-Man Express": {
        "description": "Daily 4-Man Ultra Bosses",
        "prefix": "4Man",
    },
    "Daily 7-Man Express": {
        "description": "Daily 7-Man Ultra Bosses",
        "prefix": "7Man",
    },
    "Weekly Ultra Express": {
        "description": "Weekly Ultra Bosses (excluding speaker, grim and gramiel)",
        "prefix": "Weekly",
    },
    "GrimChallenge Express": {
        "description": "Mechabinky & Raxborg 2.0",
        "prefix": "GrimChallenge",
    },
    "Daily Temple Express": {
        "description": "Daily TempleShrine",
        "prefix": "TempleShrine",
    },
}

# ============================================================================
# HELPER SLOTS - Maximum helpers per category (UPDATED!)
# ============================================================================
HELPER_SLOTS = {
    "GrimChallenge Express": 6,
    "Daily 7-Man Express": 6,
    "Weekly Ultra Express": 3,        # CHANGED FROM 6 TO 3!
    "UltraSpeaker Express": 3,
    "Ultra Gramiel Express": 3,
    "Daily 4-Man Express": 3,
    "Daily Temple Express": 3,
}

# ============================================================================
# POINT VALUES - Points awarded per category
# ============================================================================
POINT_VALUES = {
    "GrimChallenge Express": 10,
    "UltraSpeaker Express": 8,
    "Weekly Ultra Express": 12,
    "Daily 7-Man Express": 10,
    "Daily 4-Man Express": 4,
    "Daily Temple Express": 6,
    "Ultra Gramiel Express": 7,
}

# ============================================================================
# BOSS LISTS - For generating /join commands (UPDATED ORDER!)
# ============================================================================
# 4-Man Order: Dage, Tyndarius, Engineer, Warden, Ezrajal
DAILY_4MAN_BOSSES = [
    "Ultra Dage",
    "Ultra Tyndarius",
    "Ultra Engineer",
    "Ultra Warden",
    "Ultra Ezrajal",
]

# 7-Man Order: Lich, Beast, Deimos, Flibbi, Bane, Xyfrag, Kathool, Astral, Azalith
DAILY_7MAN_BOSSES = [
    "Ultra Lich",
    "Ultra Beast",
    "Ultra Deimos",
    "Ultra Flibbi",
    "Ultra Bane",
    "Ultra Xyfrag",
    "Ultra Kathool",
    "Ultra Astral",
    "Ultra Azalith",
]

# Boss-specific join commands for 7-Man (Lich = frozenlair!)
BOSS_7MAN_COMMANDS = {
    "Ultra Lich": ["frozenlair"],     # UPDATED!
    "Ultra Beast": ["Beast"],
    "Ultra Deimos": ["Deimos"],
    "Ultra Flibbi": ["Flibbi"],
    "Ultra Bane": ["Bane"],
    "Ultra Xyfrag": ["Xyfrag"],
    "Ultra Kathool": ["Kathool"],
    "Ultra Astral": ["Astral"],
    "Ultra Azalith": ["Azalith"],
}

# Weekly Order: Dage > Nulgath > Drago > Darkon > CDrakath
WEEKLY_ULTRA_BOSSES = [
    "Ultra Dage",
    "Ultra Nulgath",
    "Ultra Drago",
    "Ultra Darkon",
    "Ultra Champion Drakath",
]

# ============================================================================
# COLORS - Embed colors (Discord color codes)
# ============================================================================
COLORS = {
    "PRIMARY": 0x5865F2,    # Discord Blurple
    "SUCCESS": 0x57F287,    # Green
    "WARNING": 0xFEE75C,    # Yellow
    "DANGER": 0xED4245,     # Red
    "GOLD": 0xFFD700,       # Gold for leaderboard
}

# ============================================================================
# HARDCODED COMMANDS - Pre-defined command responses
# ============================================================================
HARDCODED_COMMANDS = {
    "rrules": {
        "text": (
            "## :inbox_tray: Ticket Rules for Requestors :inbox_tray:\n\n"
            "### :crossed_swords: Respect Comes First\n"
            "Toxicity, harassment, discrimination, or any disrespectful behavior is not allowed.\n\n"
            "### :date: Ticket Opening Limits\n"
            "You can open each ticket category only **twice per reset period** — daily categories up to **2 times per day**, and weekly categories up to **2 times per week**.\n\n"
            "### :bust_in_silhouette: No Premade Allowed\n"
            "You may only open a ticket if you're **alone**. Absolutely no premade teams. **Only Helpers + YOU**\n\n"
            "### :closed_lock_with_key: Always Use a Private Room\n"
            "Tickets must be opened in a **private room** e.g. `ultraspeaker-2310`. If you use a public room number and anyone else is in the room, the ticket is disqualified.\n\n"
            "### :performing_arts: Skill Issue ≠ Trolling\n"
            "It's okay to be bad. However, **sabotaging the run intentionally** or **trolling** in any form is not tolerated. If it happens multiple times, your ability to open tickets may be revoked. (Proof or staff confirmation is required in any complains). **Always listen to helper's calls**\n\n"
            "### :camera_with_flash: You Must Take the Screenshot\n"
            "Requestors are **responsible for taking the final screenshot**. If you fail to do this multiple times, you may be banned from opening tickets.\n\n"
            "### :scales: Use Common Sense\n"
            "Attempting to exploit loopholes or bend the rules for any reason will be punished without mercy."
        )
    },
    
    "hrules": {
        "text": (
            "## :inbox_tray: Ticket Rules for Helpers :inbox_tray:\n\n"
            "### :crossed_swords: Respect Comes First\n"
            "Toxicity, harassment, discrimination, or any disrespectful behavior is not allowed.\n\n"
            "### :no_entry_sign: No Ticket-Hopping\n"
            "You **cannot leave a ticket** to join another one for better chances or rewards.\n\n"
            "**The only exception:** If your ticket has no available helpers, and another ticket urgently needs help to proceed. In this case, you may assist there so the group can finish and free up helpers for others.\n\n"
            "### :robot: Botting = Cheating\n"
            "Using bots, scripts, premium clients or whichever automation tools is considered **cheating in-game** and is **not allowed** inside tickets.\n\n"
            "### :performing_arts: No Trolling\n"
            "Helpers are **not allowed to troll or sabotage** under any circumstance. Unlike requestors, skill issue is **not a valid excuse**. Helpers must be reliable.\n\n"
            "Trolling will result in your Helper role being revoked (if confirmed by staff or with valid proof).\n\n"
            "### :camera_with_flash: Stay for the Screenshot\n"
            "**Leaving before the screenshot means you won't be counted.** Helpers must stay until the very end.\n\n"
            "### :scales: Use Common Sense\n"
            "Attempting to exploit loopholes or bend the rules for any reason will be punished without mercy.\n\n"
            "### :saluting_face: Be a Good Helper\n"
            "- Try your best **not to rush other helpers** during tickets. Wait till everyone is ready before beginning the fight.\n"
            "- Use **meta classes and proper comps** for fast and reliable clears.\n"
            "- **Adjust to comps:**\n"
            "  - *Example:* You are phasing the boss at `/Astralshrine` and you notice the classes **VDK, LR, LOO, LH, CSS, AF** are already present. **Do not equip VDK** and expect the previous wearer to adjust — **do it yourself!**"
        )
    },
    
    "proof": {
        "text": (
            "## :camera_with_flash: Submit Your Proof\n\n"
            "After requesting a ticket and completing the objective, make sure to provide proof!\n\n"
            "### :x: No Proof = No Points\n\n"
            "**1️⃣ Take a screenshot** of the **Helpers' names** and the **quests they completed**.\n\n"
            "**2️⃣ Send the screenshot** in your designated proof channel.\n\n"
            "### :white_check_mark: Example screenshot below:\n"
            "- **Left side:** Available Quests showing **completed quests** in green\n"
            "- **Right side:** Users in your area showing **Helper names** and their classes"
        ),
        "image": "https://cdn.discordapp.com/attachments/1363169040738291872/1408178490662060032/image.png?ex=692ca1ea&is=692b506a&hm=b94d7264eb4552b05d15e9eb37d831cb2a3c0b5141f76f7d26645b10dfd8c567&"
    }
}

# ============================================================================
# BOT SETTINGS
# ============================================================================
DEFAULT_PREFIX = "!"  # Command prefix (if using text commands)
LEADERBOARD_PER_PAGE = 10  # Number of entries per leaderboard page