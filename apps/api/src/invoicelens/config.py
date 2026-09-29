from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INVOICELENS_", env_file=".env", extra="ignore")

    mode: str = "DEMO"
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'invoicelens.db').as_posix()}"
    storage_root: Path = PROJECT_ROOT / "data" / "uploads"
    checkpoint_path: Path = PROJECT_ROOT / "data" / "graph-checkpoints.sqlite"
    secret_key: str = "demo-only-change-before-connected-mode"
    cookie_secure: bool = False
    allowed_origin: str = "http://localhost:5173"
    max_upload_mb: int = 20
    openai_model: str = ""
    openai_api_key: str = ""
    openai_max_output_tokens: int = 2048
    ocr_language: str = "eng"
    date_order: str = "MDY"
    decimal_separator: str = "."
    worker_poll_seconds: float = 1.0
    job_lease_seconds: int = 120
    auto_worker: bool = True

    def validate_runtime(self) -> None:
        if self.mode not in {"DEMO", "CONNECTED"}:
            raise ValueError("INVOICELENS_MODE must be DEMO or CONNECTED")
        if self.mode == "CONNECTED" and (
            len(self.secret_key) < 32 or self.secret_key == "demo-only-change-before-connected-mode"
        ):
            raise ValueError(
                "Set INVOICELENS_SECRET_KEY to a unique value of at least 32 characters in CONNECTED mode"
            )
        if self.openai_max_output_tokens < 256 or self.openai_max_output_tokens > 8192:
            raise ValueError("INVOICELENS_OPENAI_MAX_OUTPUT_TOKENS must be between 256 and 8192")
        if self.date_order not in {"MDY", "DMY", "NONE"}:
            raise ValueError("INVOICELENS_DATE_ORDER must be MDY, DMY, or NONE")
        if self.decimal_separator not in {".", ","}:
            raise ValueError("INVOICELENS_DECIMAL_SEPARATOR must be . or ,")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_runtime()
    return settings
