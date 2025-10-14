import aiosqlite
import json
import os
from pathlib import Path
import shutil

DEFAULT_DB_FILE = "bot_data.db"
DB_FILE = os.getenv("DB_FILE", DEFAULT_DB_FILE)

class Database:
    def __init__(self):
        self.db = None

    async def init(self):
        # Ensure parent directory exists when using a custom DB path
        try:
            db_path = Path(DB_FILE)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            # One-time migration: if switching to a new DB_FILE and old default exists, copy it
            if DB_FILE != DEFAULT_DB_FILE:
                src = Path(DEFAULT_DB_FILE)
                if src.exists() and not db_path.exists():
                    shutil.copy2(src, db_path)
        except Exception:
            pass

        # Connect and log absolute DB location
        self.db = await aiosqlite.connect(DB_FILE)
        try:
            print(f"Using SQLite at: {Path(DB_FILE).resolve()}")
        except Exception:
            pass
        await self.create_tables()

    async def create_tables(self):
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS user_points (
            user_id INTEGER PRIMARY KEY,
            points INTEGER
        )
        """)
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS tickets_counter (
            category TEXT PRIMARY KEY,
            last_number INTEGER
        )
        """)
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            name TEXT PRIMARY KEY,
            questions TEXT,
            points INTEGER,
            slots INTEGER
        )
        """)
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS custom_commands (
            name TEXT PRIMARY KEY,
            text TEXT,
            image TEXT
        )
        """)
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS transcript (
            id INTEGER PRIMARY KEY,
            channel_id INTEGER
        )
        """)
        await self.db.commit()

    # ---------- ROLES ----------
    async def set_roles(self, admin, staff, helper, restricted_ids):
        roles_data = {
            "admin": admin,
            "staff": staff,
            "helper": helper,
            "restricted": restricted_ids
        }
        await self.save_config("roles", roles_data)

    async def get_roles(self):
        roles = await self.load_config("roles") or {}
        # Normalize types and ensure keys exist
        admin = roles.get("admin")
        staff = roles.get("staff")
        helper = roles.get("helper")
        restricted_raw = roles.get("restricted", []) or []
        restricted: list[int] = []
        for r in restricted_raw:
            try:
                restricted.append(int(r))
            except Exception:
                continue
        return {"admin": admin, "staff": staff, "helper": helper, "restricted": restricted}

    # ---------- TRANSCRIPT ----------
    async def set_transcript_channel(self, channel_id):
        await self.save_config("transcript_channel", {"id": channel_id})

    async def get_transcript_channel(self):
        data = await self.load_config("transcript_channel")
        try:
            return int((data or {}).get("id")) if data and data.get("id") is not None else None
        except Exception:
            return None

    # ---------- PANEL CONFIG / MAINTENANCE ----------
    async def set_panel_config(self, text: str = None, color: int = None):
        current = await self.load_config("panel_config") or {}
        if text is not None:
            current["text"] = text
        if color is not None:
            current["color"] = color
        await self.save_config("panel_config", current)

    async def get_panel_config(self):
        cfg = await self.load_config("panel_config") or {}
        text = cfg.get("text", "Ticket panel")
        color = cfg.get("color", 0x7289DA)
        try:
            color = int(color)
        except Exception:
            color = 0x7289DA
        return {"text": text, "color": color}

    async def set_maintenance(self, enabled: bool, message: str = None):
        await self.save_config("maintenance", {"enabled": enabled, "message": message or "Tickets are temporarily disabled."})

    async def get_maintenance(self):
        data = await self.load_config("maintenance") or {}
        return {"enabled": bool(data.get("enabled", False)), "message": data.get("message", "Tickets are temporarily disabled.")}

    # ---------- PREFIX (custom text commands, optional) ----------
    async def set_prefix(self, prefix: str):
        await self.save_config("prefix", {"value": prefix})

    async def get_prefix(self):
        data = await self.load_config("prefix") or {}
        value = data.get("value", "!")
        try:
            return str(value)
        except Exception:
            return "!"

    # ---------- TICKET CATEGORY ----------
    async def set_ticket_category(self, category_id: int):
        await self.save_config("ticket_category", {"id": category_id})

    async def get_ticket_category(self):
        data = await self.load_config("ticket_category")
        try:
            return int((data or {}).get("id")) if data and data.get("id") is not None else None
        except Exception:
            return None

    # ---------- CATEGORIES ----------
    async def add_category(self, name, questions, points, slots):
        questions_json = json.dumps(questions)
        await self.db.execute(
            "INSERT INTO categories(name, questions, points, slots) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET questions=excluded.questions, points=excluded.points, slots=excluded.slots",
            (name, questions_json, points, slots)
        )
        await self.db.commit()

    async def remove_category(self, name):
        cursor = await self.db.execute("DELETE FROM categories WHERE name = ?", (name,))
        await self.db.commit()
        return cursor.rowcount > 0

    async def get_category(self, name):
        async with self.db.execute("SELECT name, questions, points, slots FROM categories WHERE name = ?", (name,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"name": row[0], "questions": json.loads(row[1]), "points": row[2], "slots": row[3]}
            return None

    async def get_categories(self):
        async with self.db.execute("SELECT name, questions, points, slots FROM categories") as cursor:
            rows = await cursor.fetchall()
            return [{"name": r[0], "questions": json.loads(r[1]), "points": r[2], "slots": r[3]} for r in rows]

    # ---------- CUSTOM COMMANDS ----------
    async def add_custom_command(self, name, text, image=None):
        await self.db.execute(
            "INSERT INTO custom_commands(name, text, image) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET text=excluded.text, image=excluded.image",
            (name, text, image)
        )
        await self.db.commit()

    async def remove_custom_command(self, name):
        cursor = await self.db.execute("DELETE FROM custom_commands WHERE name = ?", (name,))
        await self.db.commit()
        return cursor.rowcount > 0

    async def get_custom_commands(self):
        async with self.db.execute("SELECT name, text, image FROM custom_commands") as cursor:
            rows = await cursor.fetchall()
            return [{"name": r[0], "text": r[1], "image": r[2]} for r in rows]

    # ---------- CONFIG (generic) ----------
    async def save_config(self, key, value_dict):
        value_json = json.dumps(value_dict)
        await self.db.execute(
            "INSERT INTO config(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value_json)
        )
        await self.db.commit()

    async def load_config(self, key):
        async with self.db.execute("SELECT value FROM config WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None

    # ---------- USER POINTS ----------
    async def set_points(self, user_id, points):
        await self.db.execute(
            "INSERT INTO user_points(user_id, points) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET points=excluded.points",
            (user_id, points)
        )
        await self.db.commit()

    async def get_points(self, user_id):
        async with self.db.execute("SELECT points FROM user_points WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def reset_points(self):
        await self.db.execute("DELETE FROM user_points")
        await self.db.commit()

    async def get_leaderboard(self):
        async with self.db.execute("SELECT user_id, points FROM user_points ORDER BY points DESC") as cursor:
            rows = await cursor.fetchall()
            return [(uid, pts) for uid, pts in rows]

    async def delete_user_points(self, user_id):
        await self.db.execute("DELETE FROM user_points WHERE user_id = ?", (user_id,))
        await self.db.commit()

    # ---------- TICKET COUNTER ----------
    async def get_ticket_number(self, category):
        async with self.db.execute("SELECT last_number FROM tickets_counter WHERE category = ?", (category,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def increment_ticket_number(self, category):
        last = await self.get_ticket_number(category) + 1
        await self.db.execute(
            "INSERT INTO tickets_counter(category, last_number) VALUES (?, ?) "
            "ON CONFLICT(category) DO UPDATE SET last_number = excluded.last_number",
            (category, last)
        )
        await self.db.commit()
        return last


db = Database()