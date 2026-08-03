from dataclasses import dataclass
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    app_name: str = "LifeSnap AI API"
    app_version: str = "0.1.0"
    local_snapshot_path: Path = BACKEND_DIR / "data" / "local_snapshot.json"


settings = Settings()
