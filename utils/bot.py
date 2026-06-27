import os
import sys
import asyncio
import aiohttp
from typing import Optional

import discord
from utils.logger import logger
from config import config

class ItsumiBot(discord.AutoShardedBot):
    """
    The core Itsumi Bot engine.
    Handles shard management, extension loading, and global infrastructure initialization.
    """
    def __init__(self):
        super().__init__(
            intents=discord.Intents.all(),
            debug=True,
            shard_count=None,
            proxy=config.PROXY_URL,
        )
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Initialize Global Forensic Automation
        from utils.automation import inject_automation
        inject_automation(self)
        
        self._load_all_extensions()

    async def login(self, *args, **kwargs):
        """Initialize ClientSession during login phase."""
        self.session = aiohttp.ClientSession()
        return await super().login(*args, **kwargs)

    async def close(self):
        """Ensure ClientSession and Database are closed on shutdown."""
        from utils.database import db
        await db.close()
        if self.session:
            await self.session.close()
        return await super().close()

    def _load_all_extensions(self):
        """Recursively discover and load all cogs."""
        logger.info("Initializing Extensions...")
        cogs_dir = os.path.join(config.PROJECT_ROOT, "cogs")

        if not os.path.exists(cogs_dir):
            logger.error(f"Critical: Cog directory '{cogs_dir}' missing.")
            return

        count = 0
        for root, _, files in os.walk(cogs_dir):
            for filename in files:
                if filename.endswith(".py") and not filename.startswith("_"):
                    rel_path = os.path.relpath(os.path.join(root, filename), cogs_dir)
                    ext_path = f"cogs.{rel_path[:-3].replace(os.path.sep, '.')}"

                    try:
                        self.load_extension(ext_path)
                        logger.success(f"  └─ Loaded: {ext_path[5:]}")
                        count += 1
                    except Exception as e:
                        logger.error(f"  └─ Failed to load {ext_path[5:]}: {e}")

        logger.success(f"Infrastructure Active: {count} modules loaded.")

    async def on_shard_ready(self, shard_id: int):
        logger.info(f"💎 Shard #{shard_id} established connection.")

    async def on_ready(self):
        # Database setup
        from utils.database import db
        await db.connect()
        
        # Command synchronization
        await self.sync_commands()

        # Global Persistent UI
        from utils.ui.fun import PersistentFunView
        self.add_view(PersistentFunView())

        # Presence
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, 
                name="the squirrels backflip"
            )
        )

        logger.info("=" * 35)
        logger.info(f"🚀 Session Established: {self.user}")
        logger.info(f"ID:           {self.user.id}")
        logger.info(f"Pycord:       {discord.__version__}")
        logger.info(f"Python:       {sys.version.split(' ')[0]}")
        logger.info("=" * 35)
        logger.success("Itsumi is ready and operational.")
