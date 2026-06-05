import datetime
import logging
import os
import sys

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from utils.logger import setup_logger

# Initialize minimal colored logger
logger = setup_logger()


class ItsumiBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=".",
            intents=discord.Intents.all(),
            debug=True,
        )
        self.load_all_cogs()
        self.cleanup_task.start()

    @tasks.loop(hours=24)
    async def cleanup_task(self):
        """Automatically cleanup logs once a day."""
        logger.info("Running automated log cleanup...")
        # Since we don't have a ctx here, we just call a simple version of the logic
        import shutil
        import time

        from config import LOG_RETENTION_DAYS

        count = 0
        now = time.time()
        retention_seconds = LOG_RETENTION_DAYS * 24 * 60 * 60

        for base_dir in ["logs/errors", "logs/audit"]:
            if not os.path.exists(base_dir):
                continue
            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                try:
                    if os.path.isdir(item_path):
                        folder_date = datetime.datetime.strptime(item, "%Y-%m-%d")
                        if (
                            datetime.datetime.now() - folder_date
                        ).days > LOG_RETENTION_DAYS:
                            shutil.rmtree(item_path)
                            count += 1
                    elif os.path.getmtime(item_path) < (now - retention_seconds):
                        os.remove(item_path)
                        count += 1
                except:
                    pass
        logger.info(f"Automated cleanup finished. Removed {count} items.")

    @cleanup_task.before_loop
    async def before_cleanup(self):
        await self.wait_until_ready()

    def load_all_cogs(self):
        logger.info("Loading extensions...")
        cogs_dir = "./cogs"

        if not os.path.exists(cogs_dir):
            logger.error(f"Cogs directory '{cogs_dir}' not found.")
            return

        loaded_count = 0
        for filename in os.listdir(cogs_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                try:
                    self.load_extension(f"cogs.{filename[:-3]}")
                    logger.info(f"  └─ Loaded: {filename[:-3]}")
                    loaded_count += 1
                except Exception as e:
                    logger.error(f"  └─ Failed to load {filename[:-3]}: {e}")

        logger.info(f"Total extensions loaded: {loaded_count}")

    async def on_ready(self):
        logger.info("=" * 30)
        logger.info(f"Logged in as: {self.user.name}#{self.user.discriminator}")
        logger.info(f"ID:           {self.user.id}")
        logger.info(f"Pycord:       {discord.__version__}")
        logger.info(f"Python:       {sys.version.split(' ')[0]}")
        logger.info("=" * 30)

        # Set a fun status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="the squirrels backflip"
            )
        )
        logger.info("Bot is ready and watching the squirrels!")


if __name__ == "__main__":
    load_dotenv()
    token = os.getenv("TOKEN")

    if not token:
        logger.critical("No TOKEN found in .env file. Please add it and restart.")
        sys.exit(1)

    bot = ItsumiBot()

    try:
        bot.run(token)
    except discord.LoginFailure:
        logger.critical("Invalid TOKEN provided. Please check your .env file.")
    except Exception as e:
        logger.critical(f"An unexpected error occurred during startup: {e}")
