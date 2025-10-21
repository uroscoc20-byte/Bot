import aiosqlite
import json
import os
from pathlib import Path
import shutil
import asyncio

DEFAULT_DB_FILE = "bot_data.db"
DB_FILE = os.getenv("DB_FILE", DEFAULT_DB_FILE)

firebase_admin = None
firestore = None


class Database:
    def __init__(self):
        self.db = None
        self.fs = None
        self.backend = "sqlite"

    async def init(self):
        await self._maybe_init_firebase()
        if self.fs:
            self.backend = "firestore"
            print("Using Firestore for persistence")
            return
        await self._ensure_sqlite_connected()

    async def _ensure_sqlite_connected(self):
        try:
            db_path = Path(DB_FILE)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            if DB_FILE != DEFAULT_DB_FILE:
                src = Path(DEFAULT_DB_FILE)
                if src.exists() and not db_path.exists():
                    shutil.copy2(src, db_path)
        except Exception:
            pass
        if not self.db:
            self.db = await aiosqlite.connect(DB_FILE)
            try:
                print(f"Using SQLite at: {Path(DB_FILE).resolve()}")
            except Exception:
                pass
            await self.create_tables()

    async def _fallback_to_sqlite(self, reason: str = ""):
        if self.backend != "sqlite":
            print(f"⚠️ Firestore error, falling back to SQLite. Reason: {reason}")
            await self._ensure_sqlite_connected()
            self.backend = "sqlite"

    async def _maybe_init_firebase(self):
        global firebase_admin, firestore
        creds_json_str = os.getenv("FIREBASE_CREDENTIALS")
        creds_file = os.getenv("FIREBASE_CREDENTIALS_FILE")
        if not creds_json_str and not creds_file:
            return
        try:
            import firebase_admin as _fa
            from firebase_admin import credentials, firestore as _fs
            firebase_admin = _fa
            firestore = _fs
            if not firebase_admin._apps:
                if creds_json_str:
                    data = json.loads(creds_json_str)
                    cred = credentials.Certificate(data)
                else:
                    cred = credentials.Certificate(creds_file)
                firebase_admin.initialize_app(cred)
            self.fs = firestore.client()
        except Exception as e:
            print(f"⚠️ Firebase init failed, falling back to SQLite: {e}")
            self.fs = None

    async def create_tables(self):
        if self.backend != "sqlite":
            return
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
        CREATE TABLE IF NOT EXISTS global_ticket_counter (
            id INTEGER PRIMARY KEY CHECK (id = 1),
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
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS persistent_panels (
            id INTEGER PRIMARY KEY,
            channel_id INTEGER,
            message_id INTEGER,
            panel_type TEXT,
            data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        await self.db.commit()

    async def _fs_run(self, func):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func)

    # ---------- ROLES ----------
    async def set_roles(self, admin, staff, helper, restricted_ids):
        roles_data = {"admin": admin, "staff": staff, "helper": helper, "restricted": restricted_ids}
        await self.save_config("roles", roles_data)

    async def get_roles(self):
        data = await self.load_config("roles") or {}
        admin = data.get("admin")
        staff = data.get("staff")
        helper = data.get("helper")
        raw = data.get("restricted", []) or []
        restricted = []
        for r in raw:
            try:
                restricted.append(int(r))
            except Exception:
                pass
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

    # ---------- PREFIX ----------
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
        if self.backend == "firestore":
            try:
                def _op():
                    self.fs.collection("categories").document(str(name)).set({
                        "name": name, "questions": questions, "points": points, "slots": slots,
                    })
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        questions_json = json.dumps(questions)
        await self.db.execute(
            "INSERT INTO categories(name, questions, points, slots) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET questions=excluded.questions, points=excluded.points, slots=excluded.slots",
            (name, questions_json, points, slots)
        )
        await self.db.commit()

    async def remove_category(self, name):
        if self.backend == "firestore":
            try:
                def _op():
                    self.fs.collection("categories").document(str(name)).delete()
                    return True
                await self._fs_run(_op)
                return True
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        cursor = await self.db.execute("DELETE FROM categories WHERE name = ?", (name,))
        await self.db.commit()
        return cursor.rowcount > 0

    async def get_category(self, name):
        if self.backend == "firestore":
            try:
                def _op():
                    snap = self.fs.collection("categories").document(str(name)).get()
                    return snap.to_dict() if snap.exists else None
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        async with self.db.execute("SELECT name, questions, points, slots FROM categories WHERE name = ?", (name,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"name": row[0], "questions": json.loads(row[1]), "points": row[2], "slots": row[3]}
            return None

    async def get_categories(self):
        if self.backend == "firestore":
            try:
                def _op():
                    docs = self.fs.collection("categories").stream()
                    return [d.to_dict() for d in docs]
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        async with self.db.execute("SELECT name, questions, points, slots FROM categories") as cursor:
            rows = await cursor.fetchall()
            return [{"name": r[0], "questions": json.loads(r[1]), "points": r[2], "slots": r[3]} for r in rows]

    # ---------- CUSTOM COMMANDS ----------
    async def add_custom_command(self, name, text, image=None):
        if self.backend == "firestore":
            try:
                def _op():
                    self.fs.collection("custom_commands").document(str(name)).set({
                        "name": name, "text": text, "image": image,
                    })
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        await self.db.execute(
            "INSERT INTO custom_commands(name, text, image) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET text=excluded.text, image=excluded.image",
            (name, text, image)
        )
        await self.db.commit()

    async def remove_custom_command(self, name):
        if self.backend == "firestore":
            try:
                def _op():
                    self.fs.collection("custom_commands").document(str(name)).delete()
                    return True
                await self._fs_run(_op)
                return True
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        else:
            cursor = await self.db.execute("DELETE FROM custom_commands WHERE name = ?", (name,))
            await self.db.commit()
        return True

    async def get_custom_commands(self):
        if self.backend == "firestore":
            try:
                def _op():
                    docs = self.fs.collection("custom_commands").stream()
                    out = []
                    for d in docs:
                        data = d.to_dict() or {}
                        out.append({"name": d.id, "text": data.get("text"), "image": data.get("image")})
                    return out
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        async with self.db.execute("SELECT name, text, image FROM custom_commands") as cursor:
            rows = await cursor.fetchall()
            return [{"name": r[0], "text": r[1], "image": r[2]} for r in rows]

    # ---------- CONFIG ----------
    async def save_config(self, key, value_dict):
        if self.backend == "firestore":
            try:
                def _op():
                    self.fs.collection("config").document(str(key)).set(value_dict)
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        value_json = json.dumps(value_dict)
        await self.db.execute(
            "INSERT INTO config(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value_json)
        )
        await self.db.commit()

    async def load_config(self, key):
        if self.backend == "firestore":
            try:
                def _op():
                    snap = self.fs.collection("config").document(str(key)).get()
                    return snap.to_dict() if snap.exists else None
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        async with self.db.execute("SELECT value FROM config WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None

    # ---------- USER POINTS ----------
    async def set_points(self, user_id, points):
        if self.backend == "firestore":
            try:
                def _op():
                    self.fs.collection("user_points").document(str(user_id)).set({
                        "user_id": int(user_id), "points": int(points)
                    })
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        await self.db.execute(
            "INSERT INTO user_points(user_id, points) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET points=excluded.points",
            (user_id, points)
        )
        await self.db.commit()

    async def get_points(self, user_id):
        if self.backend == "firestore":
            try:
                def _op():
                    snap = self.fs.collection("user_points").document(str(user_id)).get()
                    if snap.exists:
                        data = snap.to_dict() or {}
                        return int(data.get("points", 0))
                    return 0
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        async with self.db.execute("SELECT points FROM user_points WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def reset_points(self):
        if self.backend == "firestore":
            try:
                def _op():
                    docs = list(self.fs.collection("user_points").stream())
                    for d in docs:
                        d.reference.delete()
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        await self.db.execute("DELETE FROM user_points")
        await self.db.commit()

    async def get_leaderboard(self):
        if self.backend == "firestore":
            try:
                def _op():
                    docs = self.fs.collection("user_points").stream()
                    rows = []
                    for d in docs:
                        data = d.to_dict() or {}
                        rows.append((int(data.get("user_id", d.id)), int(data.get("points", 0))))
                    rows.sort(key=lambda x: x[1], reverse=True)
                    return rows
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        async with self.db.execute("SELECT user_id, points FROM user_points ORDER BY points DESC") as cursor:
            rows = await cursor.fetchall()
            return [(uid, pts) for uid, pts in rows]

    async def delete_user_points(self, user_id):
        if self.backend == "firestore":
            try:
                def _op():
                    self.fs.collection("user_points").document(str(user_id)).delete()
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        await self.db.execute("DELETE FROM user_points WHERE user_id = ?", (user_id,))
        await self.db.commit()

    # ---------- TICKET COUNTER ----------
    async def get_ticket_number(self, category):
        if self.backend == "firestore":
            try:
                def _op():
                    snap = self.fs.collection("tickets_counter").document(str(category)).get()
                    if snap.exists:
                        data = snap.to_dict() or {}
                        return int(data.get("last_number", 0))
                    return 0
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        async with self.db.execute("SELECT last_number FROM tickets_counter WHERE category = ?", (category,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def increment_ticket_number(self, category):
        if self.backend == "firestore":
            try:
                def _op():
                    doc = self.fs.collection("tickets_counter").document(str(category))
                    snap = doc.get()
                    last = 0
                    if snap.exists:
                        data = snap.to_dict() or {}
                        last = int(data.get("last_number", 0))
                    last += 1
                    doc.set({"category": category, "last_number": last})
                    return last
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        last = await self.get_ticket_number(category) + 1
        await self.db.execute(
            "INSERT INTO tickets_counter(category, last_number) VALUES (?, ?) "
            "ON CONFLICT(category) DO UPDATE SET last_number = excluded.last_number",
            (category, last)
        )
        await self.db.commit()
        return last

    async def set_ticket_number(self, category, number):
        if self.backend == "firestore":
            try:
                def _op():
                    self.fs.collection("tickets_counter").document(str(category)).set({
                        "category": category, 
                        "last_number": int(number)
                    })
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        await self.db.execute(
            "INSERT INTO tickets_counter(category, last_number) VALUES (?, ?) "
            "ON CONFLICT(category) DO UPDATE SET last_number = excluded.last_number",
            (category, number)
        )
        await self.db.commit()
        return number

    async def get_global_ticket_number(self):
        """Get the next global ticket number (not category-specific)"""
        if self.backend == "firestore":
            try:
                def _op():
                    doc = self.fs.collection("global_ticket_counter").document("counter")
                    snap = doc.get()
                    last = 0
                    if snap.exists:
                        data = snap.to_dict() or {}
                        last = int(data.get("last_number", 0))
                    last += 1
                    doc.set({"last_number": last})
                    return last
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        
        # SQLite fallback
        cursor = await self.db.execute("SELECT last_number FROM global_ticket_counter WHERE id = 1")
        row = await cursor.fetchone()
        last = row[0] if row else 0
        last += 1
        await self.db.execute(
            "INSERT INTO global_ticket_counter(id, last_number) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET last_number = excluded.last_number",
            (last,)
        )
        await self.db.commit()
        return last

    # ---------- PERSISTENT PANELS ----------
    async def save_persistent_panel(self, channel_id, message_id, panel_type, data):
        if self.backend == "firestore":
            try:
                def _op():
                    self.fs.collection("persistent_panels").document(str(message_id)).set({
                        "channel_id": int(channel_id),
                        "message_id": int(message_id),
                        "panel_type": panel_type,
                        "data": json.dumps(data),
                        "created_at": None
                    })
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        data_json = json.dumps(data)
        await self.db.execute(
            "INSERT INTO persistent_panels(channel_id, message_id, panel_type, data) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(message_id) DO UPDATE SET data=excluded.data",
            (channel_id, message_id, panel_type, data_json)
        )
        await self.db.commit()

    async def get_persistent_panels(self, panel_type=None):
        if self.backend == "firestore":
            try:
                def _op():
                    query = self.fs.collection("persistent_panels")
                    if panel_type:
                        query = query.where("panel_type", "==", panel_type)
                    docs = query.stream()
                    panels = []
                    for d in docs:
                        data = d.to_dict() or {}
                        panels.append({
                            "channel_id": int(data.get("channel_id", 0)),
                            "message_id": int(data.get("message_id", 0)),
                            "panel_type": data.get("panel_type", ""),
                            "data": json.loads(data.get("data", "{}"))
                        })
                    return panels
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        if panel_type:
            async with self.db.execute(
                "SELECT channel_id, message_id, panel_type, data FROM persistent_panels WHERE panel_type = ?",
                (panel_type,)
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with self.db.execute(
                "SELECT channel_id, message_id, panel_type, data FROM persistent_panels"
            ) as cursor:
                rows = await cursor.fetchall()
        return [
            {
                "channel_id": row[0],
                "message_id": row[1],
                "panel_type": row[2],
                "data": json.loads(row[3])
            }
            for row in rows
        ]

    async def delete_persistent_panel(self, message_id):
        if self.backend == "firestore":
            try:
                def _op():
                    self.fs.collection("persistent_panels").document(str(message_id)).delete()
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        await self.db.execute("DELETE FROM persistent_panels WHERE message_id = ?", (message_id,))
        await self.db.commit()


db = Database()