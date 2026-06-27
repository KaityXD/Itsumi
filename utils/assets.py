import json
import os
import aiofiles
import asyncio
from types import SimpleNamespace
from typing import Any, Dict, List, Union

from config import config
from .logger import logger


class AssetNode(SimpleNamespace):
    """A recursive namespace for asset access."""

    def __getattr__(self, name: str) -> Any:
        # Instead of returning None, we must raise AttributeError
        # so hasattr() works correctly during registration.
        raise AttributeError(f"AssetNode has no attribute '{name}'")


class Assets:
    """
    Centralized utility for managing and loading project assets.
    Utilizes non-blocking aiofiles for high-performance I/O.
    """

    BASE_DIR = config.ASSETS_DIR

    def __init__(self):
        self._registry = AssetNode()
        self.load_registry()

    def load_registry(self):
        """Recursively maps the assets directory to the registry structure."""
        logger.trace(f"Starting asset discovery in {self.BASE_DIR}...")
        count = 0

        for root, dirs, files in os.walk(self.BASE_DIR):
            rel_path = os.path.relpath(root, self.BASE_DIR)
            if rel_path == ".":
                current_node = self._registry
            else:
                parts = rel_path.split(os.sep)
                current_node = self._registry
                for part in parts:
                    if not hasattr(current_node, part):
                        setattr(current_node, part, AssetNode())
                    current_node = getattr(current_node, part)

            for file in files:
                if file.endswith(".json"):
                    name = file[:-5]
                    path = os.path.join(root, file)
                    # Use the async loader
                    setattr(current_node, name, self._make_loader(path))
                    count += 1

        logger.success(f"Asset registry initialized with {count} items.")

    def _make_loader(self, path):
        """Returns an async function that loads the JSON data."""

        async def loader():
            async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
                content = await f.read()
                return json.loads(content)

        return loader

    @staticmethod
    def get_path(*paths: str) -> str:
        """Constructs an absolute path relative to the assets directory."""
        return os.path.join(Assets.BASE_DIR, *paths)

    @staticmethod
    async def load_json(*paths: str) -> Union[Dict[str, Any], List[Any]]:
        """Loads and returns the content of a JSON asset asynchronously."""
        path = Assets.get_path(*paths)
        if not path.endswith(".json"):
            path += ".json"
        async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
            content = await f.read()
            return json.loads(content)

    @staticmethod
    def get_message_path(category: str, filename: str) -> str:
        """Specifically gets the path for a message asset."""
        return Assets.get_path("messages", category, filename)

    @staticmethod
    async def load_message(category: str, filename: str) -> Union[Dict[str, Any], List[Any]]:
        """Loads a message asset asynchronously from assets/messages/{category}/{filename}."""
        if not filename.endswith(".json"):
            filename += ".json"
        return await Assets.load_json("messages", category, filename)

    @staticmethod
    def ensure_dir(*paths: str) -> str:
        """Ensures a directory exists within assets and returns its path."""
        path = Assets.get_path(*paths)
        os.makedirs(path, exist_ok=True)
        return path

    def __getattr__(self, name: str) -> Any:
        return getattr(self._registry, name)


# Singleton access
assets = Assets()
