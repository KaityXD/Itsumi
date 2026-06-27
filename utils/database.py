import asyncio
import json
import os
import time
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

import aiosqlite

from config import config

from .assets import assets
from .logger import logger

T = TypeVar("T")

class BaseRepository:
    """Base class for domain-specific database operations."""
    def __init__(self, db: "Database"):
        self.db = db

    async def execute(self, sql: str, parameters: tuple = ()) -> aiosqlite.Cursor:
        return await self.db.execute(sql, parameters)

    async def fetchone(self, sql: str, parameters: tuple = ()) -> Optional[aiosqlite.Row]:
        return await self.db.fetchone(sql, parameters)

    async def fetchall(self, sql: str, parameters: tuple = ()) -> List[aiosqlite.Row]:
        return await self.db.fetchall(sql, parameters)


class SettingsRepository(BaseRepository):
    """Handles guild-specific settings with caching."""
    def __init__(self, db: "Database"):
        super().__init__(db)
        self._cache = {} # (guild_id, key) -> value

    async def get(self, key: str, guild_id: int) -> Optional[str]:
        cache_key = (guild_id, key)
        if cache_key in self._cache:
            return self._cache[cache_key]

        row = await self.fetchone(
            "SELECT value FROM settings WHERE key = ? AND guild_id = ?", (key, guild_id)
        )
        val = row["value"] if row else None
        self._cache[cache_key] = val
        return val

    async def set(self, key: str, value: str, guild_id: int):
        await self.execute(
            "INSERT OR REPLACE INTO settings (guild_id, key, value) VALUES (?, ?, ?)",
            (guild_id, key, value),
        )
        self._cache[(guild_id, key)] = value


class TagRepository(BaseRepository):
    """Handles custom server tags with usage tracking and caching."""
    def __init__(self, db: "Database"):
        super().__init__(db)
        self._cache = {} # (guild_id, name.lower()) -> row

    async def create(
        self,
        name: str,
        content: str,
        creator_id: int,
        creator_name: str,
        guild_id: int,
        is_embed: bool = False,
        thumbnail_url: Optional[str] = None,
    ):
        await self.execute(
            "INSERT INTO tags (guild_id, name, content, creator_id, creator_name, is_embed, thumbnail_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                guild_id,
                name.lower(),
                content,
                creator_id,
                creator_name,
                1 if is_embed else 0,
                thumbnail_url,
            ),
        )
        self._cache.pop((guild_id, name.lower()), None)

    async def get(self, name: str, guild_id: int) -> Optional[aiosqlite.Row]:
        tag_key = (guild_id, name.lower())
        if tag_key in self._cache:
            # Update use counter asynchronously
            asyncio.create_task(self.db.execute(
                "UPDATE tags SET uses = uses + 1 WHERE name = ? AND guild_id = ?",
                (name.lower(), guild_id),
            ))
            return self._cache[tag_key]

        row = await self.fetchone(
            "SELECT * FROM tags WHERE name = ? AND guild_id = ?",
            (name.lower(), guild_id),
        )
        if row:
            self._cache[tag_key] = row
            asyncio.create_task(self.db.execute(
                "UPDATE tags SET uses = uses + 1 WHERE name = ? AND guild_id = ?",
                (name.lower(), guild_id),
            ))
        return row

    async def edit(
        self,
        name: str,
        content: str,
        guild_id: int,
        is_embed: bool = False,
        thumbnail_url: Optional[str] = None,
    ):
        await self.execute(
            "UPDATE tags SET content = ?, is_embed = ?, thumbnail_url = ? WHERE name = ? AND guild_id = ?",
            (content, 1 if is_embed else 0, thumbnail_url, name.lower(), guild_id),
        )
        self._cache.pop((guild_id, name.lower()), None)

    async def delete(self, name: str, guild_id: int):
        await self.execute(
            "DELETE FROM tags WHERE name = ? AND guild_id = ?", (name.lower(), guild_id)
        )
        self._cache.pop((guild_id, name.lower()), None)

    async def list_all(self, guild_id: int) -> List[aiosqlite.Row]:
        return await self.fetchall(
            "SELECT name, creator_name, uses, is_embed FROM tags WHERE guild_id = ? ORDER BY name ASC",
            (guild_id,),
        )

    async def list_names(self, guild_id: int) -> List[str]:
        rows = await self.fetchall(
            "SELECT name FROM tags WHERE guild_id = ?", (guild_id,)
        )
        return [row["name"] for row in rows]

    async def search(self, query: str, guild_id: int) -> List[str]:
        rows = await self.fetchall(
            "SELECT name FROM tags WHERE name LIKE ? AND guild_id = ? LIMIT 25",
            (f"%{query.lower()}%", guild_id),
        )
        return [row["name"] for row in rows]


class ModerationRepository(BaseRepository):
    """Handles moderation cases and audit logging storage."""
    async def create_case(
        self,
        case_type: str,
        user_id: int,
        user_name: str,
        mod_id: int,
        mod_name: str,
        reason: str,
        v_id: str,
        duration: Optional[str] = None,
        guild_id: int = 0,
    ) -> int:
        cursor = await self.execute(
            """
            INSERT INTO cases (guild_id, type, user_id, user_name, moderator_id, moderator_name, reason, duration, v_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                case_type,
                user_id,
                user_name,
                mod_id,
                mod_name,
                reason,
                duration,
                v_id,
            ),
        )
        return cursor.lastrowid

    async def get_case(self, case_id: int, guild_id: int) -> Optional[aiosqlite.Row]:
        return await self.fetchone(
            "SELECT * FROM cases WHERE id = ? AND guild_id = ?", (case_id, guild_id)
        )

    async def update_reason(self, case_id: int, reason: str, guild_id: int):
        await self.execute(
            "UPDATE cases SET reason = ? WHERE id = ? AND guild_id = ?",
            (reason, case_id, guild_id),
        )

    async def update_log_meta(
        self, case_id: int, r_id: str, message_id: int, guild_id: int
    ):
        await self.execute(
            "UPDATE cases SET r_id = ?, log_message_id = ? WHERE id = ? AND guild_id = ?",
            (r_id, message_id, case_id, guild_id),
        )


class PermissionRepository(BaseRepository):
    """Handles dynamic permission levels, overrides, and v5 Security Groups."""
    def __init__(self, db: "Database"):
        super().__init__(db)
        self._cache_levels = {} 

    # --- Legacy Tier Methods ---
    async def set_level(self, entity_id: int, entity_type: str, level: int, guild_id: int):
        await self.execute(
            "INSERT OR REPLACE INTO permissions (guild_id, entity_id, entity_type, level) VALUES (?, ?, ?, ?)",
            (guild_id, entity_id, entity_type, level),
        )
        self._cache_levels[(guild_id, entity_id)] = level

    async def get_level(self, entity_id: int, guild_id: int) -> int:
        cache_key = (guild_id, entity_id)
        if cache_key in self._cache_levels:
            return self._cache_levels[cache_key]
        row = await self.fetchone("SELECT level FROM permissions WHERE entity_id = ? AND guild_id = ?", (entity_id, guild_id))
        lvl = row["level"] if row else 0
        self._cache_levels[cache_key] = lvl
        return lvl

    async def delete_level(self, entity_id: int, guild_id: int):
        await self.execute("DELETE FROM permissions WHERE entity_id = ? AND guild_id = ?", (entity_id, guild_id))
        self._cache_levels.pop((guild_id, entity_id), None)

    # --- v5 Security Group Methods ---
    async def create_group(self, guild_id: int, name: str, perms: int = 0, color: int = 0) -> int:
        cursor = await self.execute(
            "INSERT INTO security_groups (guild_id, name, permissions_bitfield, color) VALUES (?, ?, ?, ?)",
            (guild_id, name, perms, color)
        )
        return cursor.lastrowid

    async def delete_group(self, group_id: int, guild_id: int):
        await self.execute("DELETE FROM security_groups WHERE id = ? AND guild_id = ?", (group_id, guild_id))

    async def list_groups(self, guild_id: int) -> List[aiosqlite.Row]:
        return await self.fetchall("SELECT * FROM security_groups WHERE guild_id = ? ORDER BY priority DESC", (guild_id,))

    async def get_group(self, group_id: int) -> Optional[aiosqlite.Row]:
        return await self.fetchone("SELECT * FROM security_groups WHERE id = ?", (group_id,))

    async def update_group_perms(self, group_id: int, perms: int):
        await self.execute("UPDATE security_groups SET permissions_bitfield = ? WHERE id = ?", (perms, group_id))

    async def add_group_member(self, group_id: int, guild_id: int, entity_id: int, entity_type: str):
        await self.execute(
            "INSERT OR IGNORE INTO group_members (group_id, guild_id, entity_id, entity_type) VALUES (?, ?, ?, ?)",
            (group_id, guild_id, entity_id, entity_type)
        )

    async def remove_group_member(self, group_id: int, entity_id: int):
        await self.execute("DELETE FROM group_members WHERE group_id = ? AND entity_id = ?", (group_id, entity_id))

    async def get_entity_groups(self, entity_id: int, guild_id: int) -> List[aiosqlite.Row]:
        return await self.fetchall(
            "SELECT g.* FROM security_groups g JOIN group_members m ON g.id = m.group_id WHERE m.entity_id = ? AND m.guild_id = ?",
            (entity_id, guild_id)
        )

    # --- Override Methods ---
    async def set_override(self, node: str, level: int, guild_id: int):
        await self.execute(
            "INSERT OR REPLACE INTO perm_overrides (guild_id, node, required_level) VALUES (?, ?, ?)",
            (guild_id, node, level),
        )

    async def get_override(self, node: str, guild_id: int) -> Optional[int]:
        row = await self.fetchone("SELECT required_level FROM perm_overrides WHERE node = ? AND guild_id = ?", (node, guild_id))
        return row["required_level"] if row else None

    async def list_guild(self, guild_id: int) -> List[aiosqlite.Row]:
        return await self.fetchall("SELECT * FROM permissions WHERE guild_id = ?", (guild_id,))

    async def list_overrides(self, guild_id: int) -> List[aiosqlite.Row]:
        return await self.fetchall("SELECT * FROM perm_overrides WHERE guild_id = ?", (guild_id,))

    async def delete_override(self, node: str, guild_id: int):
        await self.execute("DELETE FROM perm_overrides WHERE node = ? AND guild_id = ?", (node, guild_id))


class MinigameRepository(BaseRepository):
    """Handles statistics for fun minigames like Roulette and Backflips."""
    async def get_roulette(self, user_id: int, guild_id: int) -> Dict[str, int]:
        row = await self.fetchone(
            "SELECT survived, died FROM roulette WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        )
        if row:
            return {"survived": row["survived"], "died": row["died"]}
        return {"survived": 0, "died": 0}

    async def update_roulette(
        self, user_id: int, survived: bool, guild_id: int
    ) -> Dict[str, int]:
        data = await self.get_roulette(user_id, guild_id)
        survived_count = data["survived"] + (1 if survived else 0)
        died_count = data["died"] + (0 if survived else 1)

        await self.execute(
            """
            INSERT INTO roulette (user_id, guild_id, survived, died)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET
                survived = excluded.survived,
                died = excluded.died
            """,
            (user_id, guild_id, survived_count, died_count),
        )
        return {"survived": survived_count, "died": died_count}

    async def get_backflip(self, user_id: int, guild_id: int) -> Dict[str, int]:
        row = await self.fetchone(
            "SELECT current_streak, best_streak FROM backflips WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        )
        if row:
            return {"current": row["current_streak"], "best": row["best_streak"]}
        return {"current": 0, "best": 0}

    async def update_backflip(
        self, user_id: int, success: bool, guild_id: int
    ) -> Dict[str, int]:
        data = await self.get_backflip(user_id, guild_id)
        if success:
            new_current = data["current"] + 1
            new_best = max(new_current, data["best"])
        else:
            new_current = 0
            new_best = data["best"]

        await self.execute(
            """
            INSERT INTO backflips (user_id, guild_id, current_streak, best_streak)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET
                current_streak = excluded.current_streak,
                best_streak = excluded.best_streak
            """,
            (user_id, guild_id, new_current, new_best),
        )
        return {"current": new_current, "best": new_best}


class RegistryRepository(BaseRepository):
    """Handles permanent snapshots for the Universal Registry."""
    async def save_snapshot(
        self,
        snapshot_id: str,
        snapshot_type: str,
        data: Dict[str, Any],
        guild_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ):
        await self.execute(
            "INSERT OR REPLACE INTO registry_snapshots (id, type, guild_id, user_id, data) VALUES (?, ?, ?, ?, ?)",
            (snapshot_id, snapshot_type, guild_id, user_id, json.dumps(data)),
        )

    async def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        row = await self.fetchone(
            "SELECT * FROM registry_snapshots WHERE id = ?", (snapshot_id,)
        )
        if row:
            data = json.loads(row["data"])
            data["_db_meta"] = {
                "type": row["type"],
                "created_at": row["created_at"],
                "guild_id": row["guild_id"],
                "user_id": row["user_id"],
            }
            return data
        return None


class Database:
    """
    Asynchronous Database handler for Itsumi-pycord.
    Now utilizes the Repository Pattern for domain-specific operations.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(assets.get_path("database"), "itsumi.db")
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

        # Domain Repositories
        self.settings = SettingsRepository(self)
        self.tags = TagRepository(self)
        self.moderation = ModerationRepository(self)
        self.permissions = PermissionRepository(self)
        self.minigames = MinigameRepository(self)
        self.registry = RegistryRepository(self)

    async def connect(self):
        """Initializes the database connection and sets up tables."""
        async with self._lock:
            if self._conn:
                return

            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._conn = await aiosqlite.connect(self.db_path)
            self._conn.row_factory = aiosqlite.Row

            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._conn.commit()
            await self._conn.execute("PRAGMA synchronous=NORMAL")
            await self._conn.commit()

            await self._setup_tables()
            logger.info(f"Database connected and modernized: {self.db_path}")

    async def _setup_tables(self):
        schema_path = os.path.join(config.PROJECT_ROOT, "assets", "database", "schema.sql")
        if os.path.exists(schema_path):
            with open(schema_path, "r") as f:
                schema = f.read()
            await self._conn.executescript(schema)
        else:
            logger.warning("Schema file not found! Database might be incomplete.")

    async def close(self):
        """Closes the database connection safely."""
        async with self._lock:
            if self._conn:
                await self._conn.close()
                self._conn = None
                logger.info("Database connection closed.")

    async def execute(self, sql: str, parameters: tuple = ()) -> aiosqlite.Cursor:
        """Executes a SQL command and commits the change."""
        if not self._conn: await self.connect()
        cursor = await self._conn.execute(sql, parameters)
        await self._conn.commit()
        return cursor

    async def fetchone(self, sql: str, parameters: tuple = ()) -> Optional[aiosqlite.Row]:
        """Fetches a single row from the database."""
        if not self._conn: await self.connect()
        async with self._conn.execute(sql, parameters) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, sql: str, parameters: tuple = ()) -> List[aiosqlite.Row]:
        """Fetches all rows matching the query."""
        if not self._conn: await self.connect()
        async with self._conn.execute(sql, parameters) as cursor:
            return await cursor.fetchall()

# Singleton instance
db = Database()
