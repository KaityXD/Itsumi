import os
import time
from .logger import FastLogger

class AuditLogger(FastLogger):
    """
    A specialized high-velocity logger for audit events.
    Writes to both console and a dedicated audit file using low-level calls.
    """
    def __init__(self, filename="audit.log"):
        super().__init__(name="audit")
        self.log_file = filename
        # Ensure the directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        self._file_fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_APPEND)

    def _log(self, level_num, msg):
        # We still want the console output (inherited)
        super()._log(level_num, msg)
        
        # And we write to the file without colors and with a full timestamp
        full_time = time.strftime("%Y-%m-%d %H:%M:%S")
        level_name = next((k for k, v in self.LEVELS.items() if v == level_num), "INFO")
        
        file_payload = f"[{full_time}] [{level_name}] {msg}\n".encode()
        os.write(self._file_fd, file_payload)

    def __del__(self):
        if hasattr(self, "_file_fd"):
            os.close(self._file_fd)

# We'll instantiate this when needed or provide a global one
# For this project, let's make it easy to get a guild-specific one
_audit_loggers = {}

def get_audit_logger(guild_id=None):
    key = guild_id or "global"
    if key not in _audit_loggers:
        from .assets import assets
        if guild_id:
            path = assets.get_path("logs", "guilds", str(guild_id), "audit.log")
        else:
            path = assets.get_path("logs", "global", "audit.log")
        _audit_loggers[key] = AuditLogger(path)
    return _audit_loggers[key]
