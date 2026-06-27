import logging
import os
import sys
import time


class FastLogger:
    """
    A blazingly fast, low-level logger that uses sys.stdout.write for maximum performance.
    Faster than print() and standard logging.
    """

    # ANSI escape codes for colors
    GREY = "\x1b[90m"
    BLUE = "\x1b[34m"
    YELLOW = "\x1b[33m"
    RED = "\x1b[31m"
    BOLD_RED = "\x1b[31;1m"
    PURPLE = "\x1b[35m"
    CYAN = "\x1b[36m"
    RESET = "\x1b[0m"

    LEVELS = {
        "DEBUG": 10,
        "INFO": 20,
        "WARNING": 30,
        "ERROR": 40,
        "CRITICAL": 50,
        "SUCCESS": 25,
        "TRACE": 5,
    }

    def __init__(self, name="bot", level="INFO"):
        self.name = name
        self.level = self.LEVELS.get(level.upper(), 20)
        self._write = sys.stdout.write

        # Pre-cache prefixes as strings
        _tags = {
            5: ("TRCE", self.PURPLE),
            10: ("DEB", self.GREY),
            20: ("INF", self.BLUE),
            25: ("SUCS", self.CYAN),
            30: ("WARN", self.YELLOW),
            40: ("ERR", self.RED),
            50: ("CRIT", self.BOLD_RED),
        }
        max_tag_len = max(len(tag) for tag, _ in _tags.values())
        self._prefixes = {
            lvl: f"{color}[{tag}]{self.RESET}{' ' * (max_tag_len - len(tag) + 2)}"
            for lvl, (tag, color) in _tags.items()
        }

        # Pre-cache time formatting if we want to go really fast,
        # but time.strftime is usually acceptable.
        # We can also store the last timestamp to avoid calling strftime every time in the same second.
        self._last_time = 0
        self._last_time_str = ""

    def _get_time(self):
        now = time.time()
        if int(now) != self._last_time:
            self._last_time = int(now)
            self._last_time_str = time.strftime("%H:%M:%S", time.localtime(now))
        return self._last_time_str

    def _log(self, level_num, msg):
        if level_num < self.level:
            return

        # Using sys.stdout.write with a single f-string is very fast
        # [TIME] | [LEVEL] | MESSAGE
        self._write(
            f"{self.GREY}{self._get_time()}{self.RESET} | {self._prefixes.get(level_num, '')} | {msg}\n"
        )

    def trace(self, msg):
        self._log(5, msg)

    def debug(self, msg):
        self._log(10, msg)

    def info(self, msg):
        self._log(20, msg)

    def success(self, msg):
        self._log(25, msg)

    def warning(self, msg):
        self._log(30, msg)

    def error(self, msg):
        self._log(40, msg)

    def critical(self, msg):
        self._log(50, msg)

    def setLevel(self, level):
        if isinstance(level, str):
            self.level = self.LEVELS.get(level.upper(), 20)
        else:
            self.level = level

    def hasHandlers(self):
        return True

    def addHandler(self, h):
        pass


# Global instance
logger = FastLogger()


def setup_logger():
    logging.basicConfig(level=logging.WARNING)
    for logger_name in ["discord.gateway", "discord.client", "discord.http", "audit"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    return logger


if __name__ == "__main__":
    import timeit

    l = FastLogger()
    print("Benchmarking 100,000 logs (Fair comparison)...")

    msg = "Test message"

    # FastLogger
    t_fast = timeit.timeit(lambda: l.info(msg), number=100000)

    # Standard print with SAME formatting
    def print_with_format(m):
        t = time.strftime("%H:%M:%S")
        print(f"\x1b[90m{t}\x1b[0m | \x1b[34m[INFO]\x1b[0m      | {m}")

    t_print = timeit.timeit(lambda: print_with_format(msg), number=100000)

    # Standard logging
    std_l = logging.getLogger("test")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(
        logging.Formatter(
            "\x1b[90m%(asctime)s\x1b[0m | %(levelname)s | %(message)s", "%H:%M:%S"
        )
    )
    std_l.addHandler(sh)
    std_l.setLevel(logging.INFO)

    # Suppress output for standard logging bench to not flood
    std_l.propagate = False
    sh.stream = open(os.devnull, "w")
    t_std = timeit.timeit(lambda: std_l.info(msg), number=100000)

    # Results
    sys.stderr.write(f"\nResults (100,000 logs):\n")
    sys.stderr.write(f"FastLogger:      {t_fast:.4f}s\n")
    sys.stderr.write(f"print() styled:  {t_print:.4f}s\n")
    sys.stderr.write(f"std logging:     {t_std:.4f}s (to devnull)\n")
