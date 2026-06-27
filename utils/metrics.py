import math
import os
import time
from collections import deque
from typing import List, Callable
from functools import wraps

import psutil


class MetricsTracker:
    def __init__(self, history_size=60):
        self.latency_history = deque(maxlen=history_size)
        self.command_timings = deque(maxlen=100) # (name, duration)
        self.command_counts = 0
        self.start_time = time.time()
        self.process = psutil.Process(os.getpid())

        # New counters
        self.guild_count = 0
        self.user_count = 0

    def record_latency(self, latency: float):
        """Records latency in ms."""
        if math.isnan(latency):
            return
        self.latency_history.append(latency)

    def increment_commands(self):
        self.command_counts += 1

    def profile(self, name: str = None):
        """Decorator to profile execution time of a function."""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    res = await func(*args, **kwargs)
                    return res
                finally:
                    elapsed = (time.perf_counter() - start) * 1000
                    self.command_timings.append((name or func.__name__, elapsed))
                    self.increment_commands()
            return wrapper
        return decorator

    @property
    def uptime(self) -> float:
        return time.time() - self.start_time

    @property
    def memory_usage(self) -> float:
        """Returns memory usage in MB."""
        return self.process.memory_info().rss / 1024 / 1024

    @property
    def cpu_usage(self) -> float:
        """Returns CPU usage percentage."""
        return self.process.cpu_percent()

    @property
    def avg_latency(self) -> float:
        if not self.latency_history:
            return 0.0
        return sum(self.latency_history) / len(self.latency_history)

    def get_latency_sparkline(self) -> str:
        """Generates a simple ASCII sparkline of latency history."""
        if not self.latency_history:
            return "No data"

        # Use a few levels of bars
        bars = " ▂▃▄▅▆▇█"
        min_v = min(self.latency_history)
        max_v = max(self.latency_history)
        range_v = max_v - min_v or 1

        sparkline = ""

        for v in list(self.latency_history)[-20:]:  # Last 20 points
            if math.isnan(v):
                sparkline += " "
                continue
            idx = int(((v - min_v) / range_v) * (len(bars) - 1))
            sparkline += bars[idx]
        return sparkline


tracker = MetricsTracker()
