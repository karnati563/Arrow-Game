import os
import sqlite3
from datetime import datetime


class ProfileStore:
    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    level INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

    def _safe_name(self, name):
        return (name or "Player 1").strip() or "Player 1"

    def list_profiles(self):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name FROM profiles ORDER BY name ASC"
            ).fetchall()
        return [row["name"] for row in rows]

    def ensure_profile(self, name):
        safe_name = self._safe_name(name)
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT name FROM profiles WHERE name = ?",
                (safe_name,),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO profiles (name, level, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (safe_name, 1, now, now),
                )
        return safe_name

    def set_active_profile(self, name):
        safe_name = self.ensure_profile(name)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES ('active_profile', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (safe_name,),
            )
        return safe_name

    def get_active_profile(self):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = 'active_profile'"
            ).fetchone()
        if row:
            return self.ensure_profile(row["value"])
        default_name = "Player 1"
        return self.ensure_profile(default_name)

    def get_level(self, name=None):
        safe_name = self._safe_name(name or self.get_active_profile())
        with self._connect() as conn:
            row = conn.execute(
                "SELECT level FROM profiles WHERE name = ?",
                (safe_name,),
            ).fetchone()
        if row is None:
            self.ensure_profile(safe_name)
            return 1
        return max(1, int(row["level"]))

    def save_level(self, level, name=None):
        safe_name = self._safe_name(name or self.get_active_profile())
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                "UPDATE profiles SET level = ?, updated_at = ? WHERE name = ?",
                (max(1, int(level)), now, safe_name),
            )
        return safe_name
