import os
from dataclasses import dataclass, field
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]


def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


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
    external_ocr_endpoint: str | None = field(default_factory=lambda: os.getenv("LIFESNAP_OCR_ENDPOINT"))
    external_ocr_api_key: str | None = field(default_factory=lambda: os.getenv("LIFESNAP_OCR_API_KEY"))
    external_ocr_provider: str = field(default_factory=lambda: os.getenv("LIFESNAP_OCR_PROVIDER", "external_http"))
    external_ocr_timeout_seconds: float = field(
        default_factory=lambda: _env_float("LIFESNAP_OCR_TIMEOUT_SECONDS", 15.0)
    )

    @property
    def real_ocr_enabled(self) -> bool:
        return bool(self.external_ocr_endpoint)

    @property
    def ocr_provider_name(self) -> str:
        return self.external_ocr_provider if self.real_ocr_enabled else "stored_text_stub"


settings = Settings()
