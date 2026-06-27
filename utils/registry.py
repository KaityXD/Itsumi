import asyncio
import json
import os
import time
import uuid
import weakref
from collections import deque
from datetime import datetime
from typing import Any, Dict, Optional, Union

import discord
from .logger import logger
from .database import db


class UniversalRegistry:
    """
    The central brain for identifying and managing all bot components.
    Tracks Views, Errors, and Tasks by their unique IDs.
    """

    def __init__(self):
        # Weak references so we don't prevent garbage collection of inactive views
        self._active_views = weakref.WeakValueDictionary()
        # History of recent error IDs for quick lookup
        self._error_history = {}
        # Track background tasks
        self._tasks = {}
        # Active user sessions {user_id: {"id": sess_id, "last_active": timestamp}}
        self._sessions = {}
        # Chronological list of IDs for autocomplete (max 100)
        self._recent_ids = deque(maxlen=100)
        # Start time for uptime/lifetime tracking
        self._start_time = time.time()

    def get_session(self, user_id: int) -> str:
        """Gets or creates a session ID for a user. Sessions expire after 30 mins."""
        now = time.time()
        sess = self._sessions.get(user_id)

        if not sess or (now - sess["last_active"] > 1800):
            sess_id = f"sess-{str(uuid.uuid4())[:8]}"
            self._sessions[user_id] = {"id": sess_id, "last_active": now}
            logger.trace(f"Started new session for {user_id}: {sess_id}")
        else:
            self._sessions[user_id]["last_active"] = now

        return self._sessions[user_id]["id"]

    def _add_to_recent(self, any_id: str):
        if any_id not in self._recent_ids:
            self._recent_ids.appendleft(any_id)

    def register_interaction(
        self, v_id: str, data: Dict[str, Any], user_id: Optional[int] = None, guild_id: Optional[int] = None
    ):
        """Saves any interaction data permanently to the database snapshots."""
        self._add_to_recent(v_id)

        data["v_id"] = v_id
        data["logged_at"] = datetime.now().isoformat()

        # Link to user session if available
        if user_id:
            data["session_id"] = self.get_session(user_id)

        # Fire and forget database write to keep the loop fast
        snapshot_type = data.get("type", "INTERACTION")
        
        # We use asyncio.create_task if a loop is running, otherwise we might have issues
        try:
            asyncio.create_task(db.registry.save_snapshot(v_id, snapshot_type, data, guild_id, user_id))
        except RuntimeError:
            # No loop running (e.g. during startup/shutdown), ignore for now or log
            pass

    def register_response(
        self, 
        response_type: str, 
        content: Any, 
        interaction: Optional[Union[discord.Interaction, discord.ApplicationContext, discord.Message]] = None,
        ephemeral: bool = False,
        message: Optional[discord.Message] = None
    ) -> str:
        """
        Creates a permanent record of a bot response and returns a unique r-id.
        """
        r_id = f"r-{str(uuid.uuid4())[:8]}"
        
        user = None
        guild = None
        parent_v_id = None
        
        target = message or interaction
        
        if isinstance(target, (discord.Interaction, discord.ApplicationContext)):
            user = target.user if isinstance(target, discord.Interaction) else target.author
            guild = target.guild
            # Try to find a parent v-id (e.g. from the command context or interaction)
            if hasattr(target, "view") and hasattr(target.view, "view_id"):
                parent_v_id = target.view.view_id
            elif isinstance(target, discord.ApplicationContext) and hasattr(target, "interaction"):
                 if hasattr(target.interaction, "data") and target.interaction.data:
                    # If it's a component interaction, we can sometimes trace it
                    pass
        elif isinstance(target, discord.Message):
            user = target.author
            guild = target.guild
        
        snapshot = {
            "type": "RESPONSE",
            "r_id": r_id,
            "parent_id": parent_v_id,
            "response_type": response_type,
            "ephemeral": ephemeral,
            "user": {"name": str(user), "id": user.id} if user else None,
            "guild": {"name": guild.name, "id": guild.id} if guild and hasattr(guild, "id") else "DM",
            "content": str(content) if not isinstance(content, (dict, list)) else content,
            "logged_at": datetime.now().isoformat()
        }
        
        self.register_interaction(
            r_id, 
            snapshot, 
            user_id=user.id if user else None, 
            guild_id=guild.id if guild and hasattr(guild, "id") else None
        )
        return r_id

    # --- TRACING ---
    async def trace(self, start_id: str) -> List[Dict[str, Any]]:
        """
        Traces the chain of custody for an ID by following parent_id links.
        Returns a list of snapshots in chronological order (oldest to newest).
        """
        chain = []
        current_id = start_id
        visited = set()

        while current_id and current_id not in visited:
            visited.add(current_id)
            info = await self.identify(current_id)
            
            if info["type"] == "UNKNOWN":
                break
            
            # Add metadata to the data for the trace UI
            data = info.get("data", {})
            data["_trace_type"] = info["type"]
            data["_trace_status"] = info["status"]
            data["_trace_id"] = current_id
            
            chain.append(data)
            
            # Move to parent
            current_id = data.get("parent_id") or data.get("parent_v_id")

        # Reverse so it's chronological (Parent -> Child)
        return list(reversed(chain))

    # --- VIEW MANAGEMENT ---
    def register_view(self, view_id: str, view_obj: Any):
        """Registers an active interaction view and prepares it for disk persistence."""
        self._active_views[view_id] = view_obj

        user_id = None
        guild_id = None
        
        if hasattr(view_obj, "ctx") and hasattr(view_obj.ctx, "author"):
            user_id = view_obj.ctx.author.id
            guild_id = view_obj.ctx.guild_id
        elif hasattr(view_obj, "user"):
            user_id = view_obj.user.id

        # To restore a view after restart, we need its class path and init kwargs
        cls = view_obj.__class__
        class_path = f"{cls.__module__}.{cls.__name__}"
        
        # We attempt to capture common initialization attributes
        # Developers can define __get_init_args__ to provide custom restoration data
        init_args = {}
        if hasattr(view_obj, "__get_init_args__"):
            init_args = view_obj.__get_init_args__()
        else:
            # Fallback: try to capture common attributes
            for attr in ["timeout", "ctx", "user", "message", "parent_v_id", "view_id"]:
                if hasattr(view_obj, attr):
                    val = getattr(view_obj, attr)
                    if isinstance(val, (int, str, float, bool, list, dict)) or val is None:
                        init_args[attr] = val
                    elif isinstance(val, (discord.User, discord.Member, discord.Role, discord.TextChannel)):
                        init_args[attr] = val.id

        view_info = {
            "type": "VIEW",
            "class_path": class_path,
            "init_args": init_args,
            "timeout": view_obj.timeout,
            "items": [str(i) for i in view_obj.children],
            "active": True
        }
        self.register_interaction(view_id, view_info, user_id=user_id, guild_id=guild_id)
        logger.trace(f"Registered view-id for persistence: {view_id} ({class_path})")

    async def get_active_views(self) -> List[Dict[str, Any]]:
        """Fetches all views that should be restored from the database."""
        # We only restore views created in the last 24 hours to keep it performant
        yesterday = (datetime.now().replace(day=datetime.now().day-1)).isoformat()
        
        rows = await db.fetchall(
            "SELECT * FROM registry_snapshots WHERE type = 'VIEW' AND created_at > ?",
            (yesterday,)
        )
        
        active_views = []
        for row in rows:
            data = json.loads(row["data"])
            if data.get("active") and "class_path" in data:
                data["v_id"] = row["id"]
                active_views.append(data)
        return active_views

    def get_view(self, view_id: str) -> Optional[Any]:
        """Retrieves an active view by its ID."""
        return self._active_views.get(view_id)

    # --- ERROR MANAGEMENT ---
    def register_error(self, error_id: str, error_data: Dict[str, Any]):
        """Registers a captured error for quick lookup and permanent storage."""
        self._error_history[error_id] = {"timestamp": time.time(), "data": error_data}

        error_snapshot = {
            "type": "ERROR",
            "error_type": error_data.get("error_type"),
            "message": error_data.get("error_message"),
            "location": error_data.get("location"),
            "context": error_data.get("context"),
        }
        self.register_interaction(error_id, error_snapshot)

        if len(self._error_history) > 100:
            oldest = min(
                self._error_history.keys(),
                key=lambda k: self._error_history[k]["timestamp"],
            )
            del self._error_history[oldest]
        logger.trace(f"Registered error-id: {error_id}")

    def get_error(self, error_id: str) -> Optional[Dict[str, Any]]:
        return self._error_history.get(error_id)

    # --- TASK MANAGEMENT ---
    def register_task(self, name: str, task_obj: Any):
        self._tasks[name] = task_obj
        logger.trace(f"Registered task: {name}")

    def get_task(self, name: str) -> Optional[Any]:
        return self._tasks.get(name)

    def get_recent_ids(self) -> list[str]:
        return list(self._recent_ids)

    def log_task_run(
        self, task_name: str, status: str, metadata: Dict[str, Any] = None
    ):
        """Logs a single execution of a background task."""
        run_id = f"run-{str(uuid.uuid4())[:8]}"
        log_data = {
            "run_id": run_id,
            "task": task_name,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
            "type": "TASK"
        }

        # Save to database using background task
        try:
            asyncio.create_task(db.registry.save_snapshot(run_id, "TASK", log_data))
        except RuntimeError:
            pass

        return run_id

    # --- GLOBAL INSPECTOR ---
    async def identify(self, any_id: str) -> Dict[str, Any]:
        """
        Attempts to identify what a random ID belongs to.
        Checks active memory first, then queries the database.
        """
        # 1. Check active view memory
        view = self.get_view(any_id)
        if view:
            return {"type": "VIEW", "obj": view, "status": "ACTIVE"}

        # 2. Check recent error history in memory
        error = self.get_error(any_id)
        if error:
            return {"type": "ERROR", "data": error["data"], "status": "LOGGED"}

        # 3. Fallback: Search Database
        data = await db.registry.get_snapshot(any_id)
        if data:
            meta = data.pop("_db_meta")
            return {
                "type": meta["type"], 
                "data": data, 
                "status": "ARCHIVED",
                "created_at": meta["created_at"]
            }

        return {"type": "UNKNOWN", "id": any_id}


# Global singleton
registry = UniversalRegistry()
