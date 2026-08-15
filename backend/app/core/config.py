from dataclasses import dataclass
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    app_name: str = "LifeSnap AI API"
    app_version: str = "0.1.0"
    local_snapshot_path: Path = BACKEND_DIR / "data" / "local_snapshot.json"
    local_bill_path: Path = BACKEND_DIR / "data" / "bills.json"
    local_task_path: Path = BACKEND_DIR / "data" / "tasks.json"
    local_diary_path: Path = BACKEND_DIR / "data" / "diaries.json"
    local_settings_path: Path = BACKEND_DIR / "data" / "settings.json"
    local_bill_candidate_path: Path = BACKEND_DIR / "data" / "bill_candidates.json"
    local_task_candidate_path: Path = BACKEND_DIR / "data" / "task_candidates.json"
    local_attachment_path: Path = BACKEND_DIR / "data" / "attachments.json"
    local_attachment_file_dir: Path = BACKEND_DIR / "data" / "attachment_files"
    local_audit_path: Path = BACKEND_DIR / "data" / "audit_events.json"
    local_idempotency_path: Path = BACKEND_DIR / "data" / "idempotency.json"


settings = Settings()
