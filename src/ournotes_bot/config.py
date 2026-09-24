from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path | None = None) -> None:
    """Load a small .env file without adding another dependency."""
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    app_id: str
    app_secret: str
    data_base: str
    cache_file: Path
    cache_ttl_hours: float

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        raw_cache = Path(os.getenv("OURNOTES_CACHE_FILE", "data/ournotes-cache.json"))
        if not raw_cache.is_absolute():
            raw_cache = PROJECT_ROOT / raw_cache
        return cls(
            app_id=os.getenv("QQ_APP_ID", "").strip(),
            app_secret=os.getenv("QQ_APP_SECRET", "").strip(),
            data_base=os.getenv("OURNOTES_DATA_BASE", "https://metadata.bdon.moe").rstrip("/"),
            cache_file=raw_cache,
            cache_ttl_hours=float(os.getenv("OURNOTES_CACHE_TTL_HOURS", "6")),
        )
