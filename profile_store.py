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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS profile_stats (
                    name TEXT PRIMARY KEY,
                    best_level INTEGER NOT NULL DEFAULT 1,
                    total_stars INTEGER NOT NULL DEFAULT 0,
                    levels_completed INTEGER NOT NULL DEFAULT 0,
                    total_hints_used INTEGER NOT NULL DEFAULT 0,
                    total_play_time_seconds INTEGER NOT NULL DEFAULT 0,
                    last_played_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(name) REFERENCES profiles(name) ON DELETE CASCADE
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

    def ensure_stats(self, name):
        safe_name = self._safe_name(name)
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT name FROM profile_stats WHERE name = ?",
                (safe_name,),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO profile_stats (name, best_level, total_stars, levels_completed, total_hints_used, total_play_time_seconds, last_played_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (safe_name, 1, 0, 0, 0, 0, now, now),
                )
        return safe_name

    def get_stats(self, name=None):
        safe_name = self._safe_name(name or self.get_active_profile())
        self.ensure_profile(safe_name)
        self.ensure_stats(safe_name)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM profile_stats WHERE name = ?",
                (safe_name,),
            ).fetchone()
        if row is None:
            return {
                "name": safe_name,
                "best_level": 1,
                "total_stars": 0,
                "levels_completed": 0,
                "total_hints_used": 0,
                "total_play_time_seconds": 0,
                "last_played_at": None,
            }
        return {
            "name": row["name"],
            "best_level": int(row["best_level"]),
            "total_stars": int(row["total_stars"]),
            "levels_completed": int(row["levels_completed"]),
            "total_hints_used": int(row["total_hints_used"]),
            "total_play_time_seconds": int(row["total_play_time_seconds"]),
            "last_played_at": row["last_played_at"],
        }

    def record_level_result(self, name, level, stars=0, hints_used=0, play_time_seconds=0):
        safe_name = self._safe_name(name or self.get_active_profile())
        self.ensure_profile(safe_name)
        self.ensure_stats(safe_name)
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM profile_stats WHERE name = ?",
                (safe_name,),
            ).fetchone()
            if row is None:
                return self.get_stats(safe_name)
            new_best = max(int(row["best_level"]), max(1, int(level)))
            new_stars = int(row["total_stars"]) + max(0, int(stars))
            new_levels = int(row["levels_completed"]) + 1
            new_hints = int(row["total_hints_used"]) + max(0, int(hints_used))
            new_time = int(row["total_play_time_seconds"]) + max(0, int(play_time_seconds))
            conn.execute(
                "UPDATE profile_stats SET best_level = ?, total_stars = ?, levels_completed = ?, total_hints_used = ?, total_play_time_seconds = ?, last_played_at = ? WHERE name = ?",
                (new_best, new_stars, new_levels, new_hints, new_time, now, safe_name),
            )
        return self.get_stats(safe_name)
