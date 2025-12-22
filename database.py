# database.py - UPDATED with ticket methods (your existing data is safe!)
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
        
        # EXISTING TABLES (keeping all your data)
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
        
        # NEW TABLES FOR TICKET SYSTEM (won't affect existing data)
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS active_tickets (
            channel_id INTEGER PRIMARY KEY,
            category TEXT NOT NULL,
            requestor_id INTEGER NOT NULL,
            helpers TEXT DEFAULT '[]',
            points INTEGER DEFAULT 0,
            random_number INTEGER,
            proof_submitted INTEGER DEFAULT 0,
            proof TEXT,
            embed_message_id INTEGER,
            in_game_name TEXT,
            concerns TEXT,
            selected_bosses TEXT DEFAULT '[]',
            selected_server TEXT,
            is_closed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS ticket_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER,
            category TEXT,
            requestor_id INTEGER,
            helpers TEXT,
            points_per_helper INTEGER,
            total_points_awarded INTEGER,
            closed_by INTEGER,
            closed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        await self.db.commit()

    async def _fs_run(self, func):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func)

    # ---------- STATS ----------
    async def get_total_tickets(self):
        """Get total number of tickets (starts at 15114)"""
        START_VALUE = 15114
        
        data = await self.load_config("total_tickets_counter")
        try:
            val = int(data)
            return max(val, START_VALUE)
        except:
            return START_VALUE

    async def increment_total_tickets(self):
        """Increment the total ticket counter by 1"""
        current = await self.get_total_tickets()
        new_val = current + 1
        await self.save_config("total_tickets_counter", str(new_val))
        return new_val

    async def get_tickets_last_24h(self):
        """Get total tickets completed in last 24 hours"""
        if self.backend != "sqlite":
            return 0
        
        try:
            # Using datetime('now') in SQLite (UTC)
            async with self.db.execute(
                "SELECT COUNT(*) FROM ticket_history WHERE closed_at > datetime('now', '-24 hours')"
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
        except Exception as e:
            print(f"⚠️ Error getting 24h stats: {e}")
            return 0

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
        cursor = await self.db.execute("DELETE FROM custom_commands WHERE name = ?", (name,))
        await self.db.commit()
        return cursor.rowcount > 0

    async def get_custom_command(self, name):
        if self.backend == "firestore":
            try:
                def _op():
                    snap = self.fs.collection("custom_commands").document(str(name)).get()
                    return snap.to_dict() if snap.exists else None
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        async with self.db.execute("SELECT name, text, image FROM custom_commands WHERE name = ?", (name,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"name": row[0], "text": row[1], "image": row[2]}
            return None

    async def get_custom_commands(self):
        if self.backend == "firestore":
            try:
                def _op():
                    docs = self.fs.collection("custom_commands").stream()
                    return [d.to_dict() for d in docs]
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        async with self.db.execute("SELECT name, text, image FROM custom_commands") as cursor:
            rows = await cursor.fetchall()
            return [{"name": r[0], "text": r[1], "image": r[2]} for r in rows]

    # ---------- CONFIG ----------
    async def save_config(self, key, value):
        if self.backend == "firestore":
            try:
                def _op():
                    self.fs.collection("config").document(str(key)).set({"value": value})
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        value_json = json.dumps(value)
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
                    if snap.exists:
                        return snap.to_dict().get("value")
                    return None
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        async with self.db.execute("SELECT value FROM config WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None

    # ---------- POINTS ----------
    async def get_points(self, user_id):
        if self.backend == "firestore":
            try:
                def _op():
                    snap = self.fs.collection("user_points").document(str(user_id)).get()
                    if snap.exists:
                        return snap.to_dict().get("points", 0)
                    return 0
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        async with self.db.execute("SELECT points FROM user_points WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def add_points(self, user_id, amount):
        current = await self.get_points(user_id)
        new = current + amount
        await self.set_points(user_id, new)
        return new

    async def remove_points(self, user_id, amount):
        current = await self.get_points(user_id)
        new = max(0, current - amount)
        await self.set_points(user_id, new)
        return new

    async def set_points(self, user_id, points):
        if self.backend == "firestore":
            try:
                def _op():
                    self.fs.collection("user_points").document(str(user_id)).set({"user_id": user_id, "points": points})
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        await self.db.execute(
            "INSERT INTO user_points(user_id, points) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET points=excluded.points",
            (user_id, points)
        )
        await self.db.commit()

    async def reset_all_points(self):
        if self.backend == "firestore":
            try:
                def _op():
                    docs = self.fs.collection("user_points").stream()
                    for doc in docs:
                        doc.reference.delete()
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        await self.db.execute("DELETE FROM user_points")
        await self.db.commit()

    async def delete_user_points(self, user_id):
        if self.backend == "firestore":
            try:
                def _op():
                    self.fs.collection("user_points").document(str(user_id)).delete()
                    return True
                await self._fs_run(_op)
                return True
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        cursor = await self.db.execute("DELETE FROM user_points WHERE user_id = ?", (user_id,))
        await self.db.commit()
        return cursor.rowcount > 0

    async def get_leaderboard(self):
        if self.backend == "firestore":
            try:
                def _op():
                    docs = self.fs.collection("user_points").order_by("points", direction=firestore.Query.DESCENDING).stream()
                    return [d.to_dict() for d in docs]
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        async with self.db.execute("SELECT user_id, points FROM user_points ORDER BY points DESC") as cursor:
            rows = await cursor.fetchall()
            return [{"user_id": r[0], "points": r[1]} for r in rows]

    # ---------- TICKETS ----------
    async def save_ticket(self, ticket_data):
        """Save or update a ticket"""
        if self.backend == "firestore":
            try:
                def _op():
                    doc_id = str(ticket_data["channel_id"])
                    self.fs.collection("active_tickets").document(doc_id).set(ticket_data)
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        
        helpers_json = json.dumps(ticket_data.get("helpers", []))
        selected_bosses_json = ticket_data.get("selected_bosses", "[]")
        if isinstance(selected_bosses_json, list):
            selected_bosses_json = json.dumps(selected_bosses_json)
        
        await self.db.execute("""
            INSERT INTO active_tickets 
            (channel_id, category, requestor_id, helpers, points, random_number, 
             proof_submitted, proof, embed_message_id, in_game_name, concerns, 
             selected_bosses, selected_server, is_closed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(channel_id) DO UPDATE SET
                helpers=excluded.helpers,
                proof_submitted=excluded.proof_submitted,
                proof=excluded.proof,
                is_closed=excluded.is_closed
        """, (
            ticket_data["channel_id"],
            ticket_data["category"],
            ticket_data["requestor_id"],
            helpers_json,
            ticket_data.get("points", 0),
            ticket_data.get("random_number"),
            ticket_data.get("proof_submitted", False),
            ticket_data.get("proof"),
            ticket_data.get("embed_message_id"),
            ticket_data.get("in_game_name", "N/A"),
            ticket_data.get("concerns", "None"),
            selected_bosses_json,
            ticket_data.get("selected_server", "Unknown"),
            ticket_data.get("is_closed", False)
        ))
        await self.db.commit()

    async def save_ticket_history(self, history_data):
        """Save ticket history"""
        if self.backend == "firestore":
            try:
                def _op():
                    self.fs.collection("ticket_history").add(history_data)
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        
        await self.db.execute("""
            INSERT INTO ticket_history 
            (channel_id, category, requestor_id, helpers, points_per_helper, 
             total_points_awarded, closed_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            history_data["channel_id"],
            history_data["category"],
            history_data["requestor_id"],
            history_data["helpers"],
            history_data["points_per_helper"],
            history_data["total_points_awarded"],
            history_data["closed_by"]
        ))
        await self.db.commit()

    async def delete_ticket(self, channel_id):
        """Delete ticket from active"""
        if self.backend == "firestore":
            try:
                def _op():
                    self.fs.collection("active_tickets").document(str(channel_id)).delete()
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        
        await self.db.execute("DELETE FROM active_tickets WHERE channel_id = ?", (channel_id,))
        await self.db.commit()

    async def get_ticket(self, channel_id):
        """Get ticket by channel ID"""
        if self.backend == "firestore":
            try:
                def _op():
                    snap = self.fs.collection("active_tickets").document(str(channel_id)).get()
                    if snap.exists:
                        data = snap.to_dict()
                        # Ensure helpers is list
                        if isinstance(data.get("helpers"), str):
                            try:
                                data["helpers"] = json.loads(data["helpers"])
                            except:
                                data["helpers"] = []
                        return data
                    return None
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        
        async with self.db.execute("""
            SELECT channel_id, category, requestor_id, helpers, points, random_number, 
                   proof_submitted, proof, embed_message_id, in_game_name, concerns, 
                   selected_bosses, selected_server, is_closed
            FROM active_tickets WHERE channel_id = ?
        """, (channel_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                helpers = []
                try:
                    helpers = json.loads(row[3])
                except:
                    pass
                    
                return {
                    "channel_id": row[0],
                    "category": row[1],
                    "requestor_id": row[2],
                    "helpers": helpers,
                    "points": row[4],
                    "random_number": row[5],
                    "proof_submitted": bool(row[6]),
                    "proof": row[7],
                    "embed_message_id": row[8],
                    "in_game_name": row[9],
                    "concerns": row[10],
                    "selected_bosses": row[11],
                    "selected_server": row[12],
                    "is_closed": bool(row[13])
                }
            return None

    async def get_all_tickets(self):
        """Get all active tickets"""
        if self.backend == "firestore":
            try:
                def _op():
                    docs = self.fs.collection("active_tickets").stream()
                    tickets = []
                    for d in docs:
                        data = d.to_dict()
                        if isinstance(data.get("helpers"), str):
                            try:
                                data["helpers"] = json.loads(data["helpers"])
                            except:
                                data["helpers"] = []
                        tickets.append(data)
                    return tickets
                return await self._fs_run(_op)
            except Exception as e:
                await self._fallback_to_sqlite(str(e))
        
        async with self.db.execute("""
            SELECT channel_id, category, requestor_id, helpers, points, random_number, 
                   proof_submitted, proof, embed_message_id, in_game_name, concerns, 
                   selected_bosses, selected_server, is_closed
            FROM active_tickets
        """) as cursor:
            rows = await cursor.fetchall()
            tickets = []
            for row in rows:
                helpers = []
                try:
                    helpers = json.loads(row[3])
                except:
                    pass
                
                tickets.append({
                    "channel_id": row[0],
                    "category": row[1],
                    "requestor_id": row[2],
                    "helpers": helpers,
                    "points": row[4],
                    "random_number": row[5],
                    "proof_submitted": bool(row[6]),
                    "proof": row[7],
                    "embed_message_id": row[8],
                    "in_game_name": row[9],
                    "concerns": row[10],
                    "selected_bosses": row[11],
                    "selected_server": row[12],
                    "is_closed": bool(row[13])
                })
            return tickets
