import os
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

class Settings:
    """
    Itsumi Configuration Engine.
    Centralized access to all bot settings and environment variables.
    """
    
    # --- Bot Identity ---
    VERSION: str = "1.2.0"
    AUTHOR: str = "Kazehara KaiTy"
    BOT_ID: int = 1378603697755521044
    DEVELOPER_GUILD: int = 1497894768330539028
    
    # --- Security ---
    TOKEN: str = os.getenv("TOKEN", "")
    OWNERS: List[int] = [int(id_.strip()) for id_ in os.getenv("OWNERS", "1378603697755521044").split(",") if id_.strip()]
    
    # --- UI Colors ---
    DEFAULT_COLOR: int = 0x3498DB
    SUCCESS_COLOR: int = 0x2ECC71
    ERROR_COLOR: int = 0xE74C3C
    WARN_COLOR: int = 0xF1C40F
    SYSTEM_COLOR: int = 0xA372FB
    
    # --- Infrastructure Paths ---
    PROJECT_ROOT: str = os.path.dirname(os.path.abspath(__file__))
    ASSETS_DIR: str = os.path.join(PROJECT_ROOT, "assets")
    LOGS_DIR: str = os.path.join(ASSETS_DIR, "logs")
    DATABASE_DIR: str = os.path.join(ASSETS_DIR, "database")
    
    # --- Network ---
    PROXY: Optional[str] = os.getenv("PROXY")
    
    # --- Maintenance ---
    LOG_RETENTION_DAYS: int = int(os.getenv("LOG_RETENTION_DAYS", "7"))
    MAX_STREAK_LEADERBOARD: int = 10
    ENV: str = os.getenv("ENV", "production")

    def __init__(self):
        # Guarantee critical attributes exist
        # even if they were commented out or missing in a customized local config
        if not hasattr(self, "OWNERS"):
            self.OWNERS = [1378603697755521044]
        if not hasattr(self, "TOKEN"):
            self.TOKEN = os.getenv("TOKEN", "")
        if not hasattr(self, "DEFAULT_COLOR"):
            self.DEFAULT_COLOR = 0x3498DB
        if not hasattr(self, "SUCCESS_COLOR"):
            self.SUCCESS_COLOR = 0x2ECC71
        if not hasattr(self, "ERROR_COLOR"):
            self.ERROR_COLOR = 0xE74C3C
        if not hasattr(self, "WARN_COLOR"):
            self.WARN_COLOR = 0xF1C40F
        if not hasattr(self, "SYSTEM_COLOR"):
            self.SYSTEM_COLOR = 0xA372FB

    @property
    def IS_DEV(self) -> bool:
        return self.ENV.lower() == "development"

    @property
    def PROXY_URL(self) -> Optional[str]:
        if not self.PROXY:
            return None
        return self.PROXY.split(",")[0].strip()

# Singleton instance
config = Settings()
