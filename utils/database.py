import os
import sqlite3

from config import DATABASE_PATH


class Database:
    def __init__(self):
        # Ensure directory exists
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.cursor = self.conn.cursor()
        self.setup_tables()

    def setup_tables(self):
        # Table for backflip streaks
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS backflips (
                user_id INTEGER PRIMARY KEY,
                current_streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

    def get_backflip(self, user_id: int):
        self.cursor.execute(
            "SELECT current_streak, best_streak FROM backflips WHERE user_id = ?",
            (user_id,),
        )
        row = self.cursor.fetchone()
        if row:
            return {"current": row[0], "best": row[1]}
        return {"current": 0, "best": 0}

    def update_backflip(self, user_id: int, success: bool):
        data = self.get_backflip(user_id)

        if success:
            new_current = data["current"] + 1
            new_best = max(new_current, data["best"])
        else:
            new_current = 0
            new_best = data["best"]

        self.cursor.execute(
            """
            INSERT INTO backflips (user_id, current_streak, best_streak)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                current_streak = excluded.current_streak,
                best_streak = excluded.best_streak
        """,
            (user_id, new_current, new_best),
        )
        self.conn.commit()
        return {"current": new_current, "best": new_best}


# Singleton instance
db = Database()
