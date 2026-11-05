"""Configuration settings for Task 3 Association Rule Mining application."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv_if_present() -> None:
    env_file = BASE_DIR / ".env"
    if not env_file.is_file():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


_load_dotenv_if_present()

APP_HOST: str = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT: int = int(os.getenv("APP_PORT", "8003"))

DATA_DIR: Path = BASE_DIR / os.getenv("DATA_DIR", "arm_task")
OUTPUT_DIR: Path = BASE_DIR / os.getenv("OUTPUT_DIR", "output")
DB_PATH: Path = BASE_DIR / os.getenv("DB_PATH", "data/arm_analytics.db")
FRONTEND_DIR: Path = BASE_DIR / "frontend"

DEFAULT_MIN_SUPPORT: float = float(os.getenv("DEFAULT_MIN_SUPPORT", "0.003"))
DEFAULT_MIN_CONFIDENCE: float = float(os.getenv("DEFAULT_MIN_CONFIDENCE", "0.6"))

