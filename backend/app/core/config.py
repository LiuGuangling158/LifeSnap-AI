import os
from dataclasses import dataclass, field
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("LIFESNAP_DATA_DIR", str(BACKEND_DIR / "data"))).resolve()


def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


def _env_optional_str(name: str) -> str | None:
    raw_value = os.getenv(name)
    if raw_value is None:
        return None
    value = raw_value.strip()
    return value or None


def _default_llm_base_url() -> str | None:
    configured_base_url = _env_optional_str("LIFESNAP_LLM_BASE_URL")
    if configured_base_url:
        return configured_base_url
    configured_model = _env_optional_str("LIFESNAP_LLM_MODEL") or _env_optional_str(
        "LIFESNAP_LLM_FINE_TUNED_MODEL"
    )
    if _env_optional_str("LIFESNAP_LLM_API_KEY") and configured_model:
        return "https://api.openai.com/v1"
    return None


@dataclass(frozen=True)
class Settings:
    app_name: str = "LifeSnap AI API"
    app_version: str = "0.1.0"
    local_snapshot_path: Path = DATA_DIR / "local_snapshot.json"
    local_bill_path: Path = DATA_DIR / "bills.json"
    local_task_path: Path = DATA_DIR / "tasks.json"
    local_diary_path: Path = DATA_DIR / "diaries.json"
    local_settings_path: Path = DATA_DIR / "settings.json"
    local_budget_settings_path: Path = DATA_DIR / "budget.json"
    local_category_settings_path: Path = DATA_DIR / "categories.json"
    local_tag_settings_path: Path = DATA_DIR / "tags.json"
    local_bill_candidate_path: Path = DATA_DIR / "bill_candidates.json"
    local_task_candidate_path: Path = DATA_DIR / "task_candidates.json"
    local_diary_candidate_path: Path = DATA_DIR / "diary_candidates.json"
    local_attachment_path: Path = DATA_DIR / "attachments.json"
    local_attachment_file_dir: Path = DATA_DIR / "attachment_files"
    local_audit_path: Path = DATA_DIR / "audit_events.json"
    local_idempotency_path: Path = DATA_DIR / "idempotency.json"
    external_ocr_endpoint: str | None = field(default_factory=lambda: os.getenv("LIFESNAP_OCR_ENDPOINT"))
    external_ocr_api_key: str | None = field(default_factory=lambda: os.getenv("LIFESNAP_OCR_API_KEY"))
    external_ocr_provider: str = field(default_factory=lambda: os.getenv("LIFESNAP_OCR_PROVIDER", "external_http"))
    external_ocr_timeout_seconds: float = field(
        default_factory=lambda: _env_float("LIFESNAP_OCR_TIMEOUT_SECONDS", 15.0)
    )
    external_ai_parser_endpoint: str | None = field(
        default_factory=lambda: os.getenv("LIFESNAP_AI_PARSE_ENDPOINT")
    )
    external_ai_parser_api_key: str | None = field(
        default_factory=lambda: os.getenv("LIFESNAP_AI_PARSE_API_KEY")
    )
    external_ai_parser_provider: str = field(
        default_factory=lambda: os.getenv("LIFESNAP_AI_PARSE_PROVIDER", "external_http")
    )
    external_ai_parser_timeout_seconds: float = field(
        default_factory=lambda: _env_float("LIFESNAP_AI_PARSE_TIMEOUT_SECONDS", 20.0)
    )
    llm_agent_base_url: str | None = field(default_factory=_default_llm_base_url)
    llm_agent_api_key: str | None = field(
        default_factory=lambda: _env_optional_str("LIFESNAP_LLM_API_KEY")
    )
    llm_agent_model: str | None = field(
        default_factory=lambda: _env_optional_str("LIFESNAP_LLM_MODEL")
    )
    llm_agent_fine_tuned_model: str | None = field(
        default_factory=lambda: _env_optional_str("LIFESNAP_LLM_FINE_TUNED_MODEL")
    )
    llm_agent_fine_tuning_job_id: str | None = field(
        default_factory=lambda: _env_optional_str("LIFESNAP_LLM_FINE_TUNING_JOB_ID")
    )
    llm_agent_provider: str = field(
        default_factory=lambda: os.getenv("LIFESNAP_LLM_PROVIDER", "openai_compatible")
    )
    llm_agent_timeout_seconds: float = field(
        default_factory=lambda: _env_float("LIFESNAP_LLM_TIMEOUT_SECONDS", 20.0)
    )
    llm_agent_temperature: float = field(
        default_factory=lambda: _env_float("LIFESNAP_LLM_TEMPERATURE", 0.0)
    )
    llm_agent_response_format: str = field(
        default_factory=lambda: os.getenv("LIFESNAP_LLM_RESPONSE_FORMAT", "json_object")
    )

    @property
    def real_ocr_enabled(self) -> bool:
        return bool(self.external_ocr_endpoint)

    @property
    def ocr_provider_name(self) -> str:
        return self.external_ocr_provider if self.real_ocr_enabled else "stored_text_stub"

    @property
    def real_ai_parser_enabled(self) -> bool:
        return self.real_llm_agent_enabled or bool(self.external_ai_parser_endpoint)

    @property
    def ai_parser_provider_name(self) -> str:
        if self.real_llm_agent_enabled:
            return self.llm_agent_provider
        if self.external_ai_parser_endpoint:
            return self.external_ai_parser_provider
        return "rule_based"

    @property
    def real_llm_agent_enabled(self) -> bool:
        return bool(self.llm_agent_base_url and self.llm_agent_runtime_model)

    @property
    def llm_agent_runtime_model(self) -> str | None:
        return self.llm_agent_fine_tuned_model or self.llm_agent_model

    @property
    def fine_tuned_llm_agent_enabled(self) -> bool:
        return bool(self.llm_agent_fine_tuned_model)


settings = Settings()
