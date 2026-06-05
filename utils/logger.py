import logging
import sys


class MinimalColorFormatter(logging.Formatter):
    # ANSI escape codes for colors
    GREY = "\x1b[90m"
    BLUE = "\x1b[34m"
    YELLOW = "\x1b[33m"
    RED = "\x1b[31m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"

    LEVEL_COLORS = {
        logging.DEBUG: GREY,
        logging.INFO: BLUE,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: BOLD_RED,
    }

    def format(self, record):
        time_str = self.formatTime(record, "%H:%M:%S")
        level_color = self.LEVEL_COLORS.get(record.levelno, self.RESET)

        # [TIME] | [LEVEL] | MESSAGE
        # Only the level and the separator are colored
        s = f"{self.GREY}{time_str}{self.RESET} | {level_color}{record.levelname:<8}{self.RESET} | {record.getMessage()}"

        if record.exc_info:
            s += "\n" + self.formatException(record.exc_info)
        return s


def setup_logger():
    # Setup root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Prevent duplicate handlers if setup_logger is called twice
    if logger.hasHandlers():
        logger.handlers.clear()

    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(MinimalColorFormatter())
    logger.addHandler(handler)

    # Mute some noisy libraries
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    logging.getLogger("discord.client").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)

    return logging.getLogger("bot")
