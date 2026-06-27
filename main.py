import sys
import asyncio
from utils.bot import ItsumiBot
from utils.logger import setup_logger
from config import config

# Initialize global logger
logger = setup_logger()

def main():
    """Main entry point for the bot."""
    
    # Optional: Configure event loop policy for performance
    try:
        import uvloop
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*set_event_loop_policy.*")
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        logger.info("Using uvloop event loop policy.")
    except ImportError:
        pass

    # Ensure token exists
    if not config.TOKEN:
        logger.critical("No TOKEN found in environment. Boot aborted.")
        sys.exit(1)

    # Initialize and boot
    bot = ItsumiBot()

    try:
        bot.run(config.TOKEN)
    except Exception as e:
        logger.critical(f"Unexpected shutdown: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
