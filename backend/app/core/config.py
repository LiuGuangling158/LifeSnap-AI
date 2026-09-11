import os
from dataclasses import dataclass, field
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent


def _load_env_file(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if not name or any(character.isspace() for character in name):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(name, value)


for _env_path in (ROOT_DIR / ".env", BACKEND_DIR / ".env"):
    _load_env_file(_env_path)

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


def _env_first_optional_str(*names: str) -> str | None:
    for name in names:
        value = _env_optional_str(name)
        if value is not None:
            return value
    return None


def _deepseek_requested() -> bool:
    provider = _env_optional_str("LIFESNAP_LLM_PROVIDER")
    if provider and provider.casefold() == "deepseek":
        return True
    if _env_first_optional_str(
        "LIFESNAP_DEEPSEEK_CHAT_API_KEY",
        "LIFESNAP_CHAT_LLM_API_KEY",
        "DEEPSEEK_CHAT_API_KEY",
        "DEEPSEEK_API_KEY",
        "LIFESNAP_DEEPSEEK_API_KEY",
    ):
        return True
    model = _env_first_optional_str("LIFESNAP_DEEPSEEK_MODEL", "LIFESNAP_LLM_MODEL")
    return bool(model and model.casefold().startswith("deepseek"))


def _default_llm_base_url() -> str | None:
    configured_base_url = _env_first_optional_str(
        "LIFESNAP_LLM_BASE_URL",
        "LIFESNAP_DEEPSEEK_BASE_URL",
    )
    if configured_base_url:
        return configured_base_url
    if _deepseek_requested():
        return "https://api.deepseek.com"
    configured_model = _default_llm_model() or _env_optional_str("LIFESNAP_LLM_FINE_TUNED_MODEL")
    if _default_llm_api_key() and configured_model:
        return "https://api.openai.com/v1"
    return None


def _default_llm_api_key() -> str | None:
    return _default_llm_chat_api_key() or _default_llm_default_api_key()


def _default_llm_chat_api_key() -> str | None:
    if _deepseek_requested():
        return _env_first_optional_str(
            "LIFESNAP_DEEPSEEK_CHAT_API_KEY",
            "LIFESNAP_CHAT_LLM_API_KEY",
            "DEEPSEEK_CHAT_API_KEY",
            "DEEPSEEK_API_KEY",
            "LIFESNAP_DEEPSEEK_API_KEY",
            "LIFESNAP_LLM_API_KEY",
        )
    return _env_first_optional_str(
        "LIFESNAP_CHAT_LLM_API_KEY",
        "LIFESNAP_LLM_API_KEY",
        "DEEPSEEK_API_KEY",
        "LIFESNAP_DEEPSEEK_API_KEY",
    )


def _default_llm_default_api_key() -> str | None:
    scoped_key = _env_first_optional_str("LIFESNAP_DEFAULT_AI_API_KEY", "LIFESNAP_LLM_DEFAULT_API_KEY")
    if scoped_key:
        return scoped_key
    if _deepseek_requested():
        return _env_first_optional_str(
            "DEEPSEEK_API_KEY",
            "LIFESNAP_DEEPSEEK_API_KEY",
            "LIFESNAP_LLM_API_KEY",
        )
    return _env_first_optional_str(
        "LIFESNAP_LLM_API_KEY",
        "DEEPSEEK_API_KEY",
        "LIFESNAP_DEEPSEEK_API_KEY",
    )


def _default_llm_model() -> str | None:
    configured = _env_first_optional_str("LIFESNAP_LLM_MODEL", "LIFESNAP_DEEPSEEK_MODEL")
    if configured:
        return configured
    if _deepseek_requested():
        return "deepseek-v4-flash"
    return None


def _default_llm_provider() -> str:
    provider = _env_optional_str("LIFESNAP_LLM_PROVIDER")
    if provider:
        return provider
    if _deepseek_requested():
        return "deepseek"
    return "openai_compatible"


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
    external_ocr_api_key: str | None = field(
        default_factory=lambda: _env_first_optional_str("LIFESNAP_IMAGE_BILL_API_KEY", "LIFESNAP_OCR_API_KEY")
    )
    external_ocr_provider: str = field(default_factory=lambda: os.getenv("LIFESNAP_OCR_PROVIDER", "external_http"))
    external_ocr_timeout_seconds: float = field(
        default_factory=lambda: _env_float("LIFESNAP_OCR_TIMEOUT_SECONDS", 15.0)
    )
    external_ai_parser_endpoint: str | None = field(
        default_factory=lambda: os.getenv("LIFESNAP_AI_PARSE_ENDPOINT")
    )
    external_ai_parser_api_key: str | None = field(
        default_factory=lambda: _env_first_optional_str("LIFESNAP_DEFAULT_AI_API_KEY", "LIFESNAP_AI_PARSE_API_KEY")
    )
    external_ai_parser_provider: str = field(
        default_factory=lambda: os.getenv("LIFESNAP_AI_PARSE_PROVIDER", "external_http")
    )
    external_ai_parser_timeout_seconds: float = field(
        default_factory=lambda: _env_float("LIFESNAP_AI_PARSE_TIMEOUT_SECONDS", 20.0)
    )
    llm_agent_base_url: str | None = field(default_factory=_default_llm_base_url)
    llm_agent_api_key: str | None = field(default_factory=_default_llm_api_key)
    llm_agent_chat_api_key: str | None = field(default_factory=_default_llm_chat_api_key)
    llm_agent_default_api_key: str | None = field(default_factory=_default_llm_default_api_key)
    llm_agent_model: str | None = field(default_factory=_default_llm_model)
    llm_agent_fine_tuned_model: str | None = field(
        default_factory=lambda: _env_optional_str("LIFESNAP_LLM_FINE_TUNED_MODEL")
    )
    llm_agent_fine_tuning_job_id: str | None = field(
        default_factory=lambda: _env_optional_str("LIFESNAP_LLM_FINE_TUNING_JOB_ID")
    )
    llm_agent_provider: str = field(default_factory=_default_llm_provider)
    llm_agent_timeout_seconds: float = field(
        default_factory=lambda: _env_float("LIFESNAP_LLM_TIMEOUT_SECONDS", 20.0)
    )
    llm_agent_temperature: float = field(
        default_factory=lambda: _env_float("LIFESNAP_LLM_TEMPERATURE", 0.0)
    )
    llm_agent_response_format: str = field(
        default_factory=lambda: os.getenv("LIFESNAP_LLM_RESPONSE_FORMAT", "json_object")
    )
    llm_agent_reasoning_effort: str | None = field(
        default_factory=lambda: _env_optional_str("LIFESNAP_LLM_REASONING_EFFORT")
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
        if not self.llm_agent_configured:
            return False
        if self.deepseek_llm_agent_enabled:
            return self.llm_agent_api_key_configured
        return True

    @property
    def llm_agent_api_key_configured(self) -> bool:
        return bool(self.llm_agent_api_key or self.llm_agent_chat_api_key or self.llm_agent_default_api_key)

    def llm_agent_api_key_for_kind(self, kind: str) -> str | None:
        if kind.casefold() == "chat_intent":
            return self.llm_agent_chat_api_key or self.llm_agent_api_key
        return self.llm_agent_default_api_key or self.llm_agent_api_key

    @property
    def llm_agent_configured(self) -> bool:
        return bool(self.llm_agent_base_url and self.llm_agent_runtime_model)

    @property
    def deepseek_llm_agent_enabled(self) -> bool:
        return self.llm_agent_provider.casefold() == "deepseek" or (
            (self.llm_agent_base_url or "").rstrip("/").casefold() == "https://api.deepseek.com"
        )

    @property
    def llm_agent_runtime_model(self) -> str | None:
        return self.llm_agent_fine_tuned_model or self.llm_agent_model

    @property
    def fine_tuned_llm_agent_enabled(self) -> bool:
        return bool(self.llm_agent_fine_tuned_model)


settings = Settings()
