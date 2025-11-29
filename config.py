# config.py
# Discord Helper Ticket Bot Configuration
# Replace all IDs with your actual Discord server IDs

# ============================================================================
# ROLE IDS - Replace with your Discord role IDs
# ============================================================================
ROLE_IDS = {
    "ADMIN": 1345073680610496602,      # Admin role ID
    "STAFF": 1374821509268373686,      # Staff role ID
    "HELPER": 1392803882115010734,     # Helper role ID
}

# ============================================================================
# CHANNEL/CATEGORY IDS - Replace with your Discord channel/category IDs
# ============================================================================
CHANNEL_IDS = {
    "TICKET_PANEL": 1358536986679443496,        # Channel where ticket panel is posted
    "RULES": 1395830522877579304,               # Rules channel
    "VERIFICATION_CATEGORY": 1351864881585852479,  # Category for verification tickets
    "TICKETS_CATEGORY": 1357314571525816442,    # Category for helper tickets
    "TRANSCRIPT": 1357314848253542570,          # Transcript channel (NEW!)
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
# HELPER SLOTS - Maximum helpers per category
# ============================================================================
HELPER_SLOTS = {
    "GrimChallenge Express": 6,
    "Daily 7-Man Express": 6,
    "Weekly Ultra Express": 6,
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
# BOSS LISTS - For generating /join commands
# ============================================================================
DAILY_4MAN_BOSSES = [
    "UltraEzrajal",
    "UltraWarden",
    "UltraEngineer",
    "UltraTyndarius",
    "UltraDage",
    "UltraIara",
    "UltraKala",
]

DAILY_7MAN_BOSSES = [
    "Astralshrine",
    "KathoolDepths",
    "Originul",
    "ApexAzalith",
    "LichLord",
    "Beast",
    "Deimos",
    "Lavarockshore",
]

# Boss-specific join commands for 7-Man (some bosses have multiple commands)
BOSS_7MAN_COMMANDS = {
    "Astralshrine": ["Astralshrine"],
    "KathoolDepths": ["KathoolDepths"],
    "Originul": ["VoidFlibbi", "VoidNightbane", "VoidXyfrag"],
    "ApexAzalith": ["ApexAzalith"],
    "LichLord": ["LichLord"],
    "Beast": ["SevenCirclesWar"],
    "Deimos": ["Deimos"],
    "Lavarockshore": ["Lavarockshore"],
}

WEEKLY_ULTRA_BOSSES = [
    "UltraDarkon",
    "ChampionDrakath",
    "UltraDage",
    "UltraNulgath",
    "UltraDrago",
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
    "proof": {
        "text": (
            "📸 **Proof Submission Guidelines**\n\n"
            "Please attach your proof here:\n"
            "• Screenshot of completion\n"
            "• Video recording\n"
            "• Game logs\n\n"
            "⚠️ Make sure the proof clearly shows the activity was completed."
        ),
        "image": None,
    },
    "rrules": {
        "text": f"📜 **Runner Rules**\n\nPlease check <#{CHANNEL_IDS['RULES']}> for the complete runner rules and guidelines.",
        "image": None,
    },
    "hrules": {
        "text": f"📜 **Helper Rules**\n\nPlease check <#{CHANNEL_IDS['RULES']}> for the complete helper rules and guidelines.",
        "image": None,
    },
}

# ============================================================================
# BOT SETTINGS
# ============================================================================
DEFAULT_PREFIX = "!"  # Command prefix (if using text commands)
LEADERBOARD_PER_PAGE = 10  # Number of entries per leaderboard page