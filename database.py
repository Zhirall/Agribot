import sqlite3
import time


class Database:
    def __init__(self, path="farmbot.db"):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.cursor = self.conn.cursor()
        self.setup()

    def setup(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS farm_timers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            crop TEXT,
            end_time INTEGER,
            emoji TEXT,
            channel_id INTEGER
        )
        """)
        self.conn.commit()

    def add_timer(self, user_id: int, crop: str, end_time: int, emoji: str, channel_id: int):
        self.cursor.execute(
            "INSERT INTO farm_timers (user_id, crop, end_time, emoji, channel_id) VALUES (?, ?, ?, ?, ?)",
            (user_id, crop, end_time, emoji, channel_id)
        )
        self.conn.commit()

    def get_active_timers(self):
        now = int(time.time())
        self.cursor.execute("SELECT * FROM farm_timers WHERE end_time > ?", (now,))
        return self.cursor.fetchall()

    def get_all_timers(self):
        self.cursor.execute("SELECT * FROM farm_timers")
        return self.cursor.fetchall()

    def remove_timer(self, timer_id: int):
        self.cursor.execute("DELETE FROM farm_timers WHERE id = ?", (timer_id,))
        self.conn.commit()

    def clear_all(self):
        self.cursor.execute("DELETE FROM farm_timers")
        self.conn.commit()

    def close(self):
        self.conn.close()