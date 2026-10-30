"""Server-only configuration, independent from Vite's public environment."""

from pathlib import Path
import os

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HANJANG_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    cors_origins: list[AnyHttpUrl] = Field(
        default_factory=lambda: [
            AnyHttpUrl("http://localhost:5173"),
            AnyHttpUrl("http://127.0.0.1:5173"),
        ]
    )
    upload_root: Path = PROJECT_ROOT / "uploads" / "originals"
    photo_model_path: Path = PROJECT_ROOT / "artifacts" / "models" / "rembg" / "u2netp.onnx"
    photo_timeout_seconds: float = Field(default=90, gt=0, le=120)
    photo_max_side: int = Field(default=1600, ge=256, le=4096)
    analysis_python: Path = PROJECT_ROOT / '.venv-analysis' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    analysis_model_path: Path = PROJECT_ROOT / 'artifacts/models/analysis/ViT-B-32.pt'
    analysis_timeout_seconds: float = Field(default=120, gt=0, le=300)
    analysis_idle_seconds: float = Field(default=300, gt=0, le=3600)
    copy_provider: Literal['mock', 'openai'] = 'mock'
    copy_model: str = 'gpt-5.4-mini-2026-03-17'
    copy_allow_paid: bool = False
    copy_max_requests: int = Field(default=6, ge=0, le=6)
    copy_budget_usd: float = Field(default=.1, ge=0, le=.1, allow_inf_nan=False)
    copy_max_retries: int = Field(default=1, ge=0, le=1)
    openai_api_key: SecretStr | None = Field(default=None, validation_alias='OPENAI_API_KEY')
    copy_budget_path: Path = PROJECT_ROOT / 'artifacts/copy-usage/ledger.json'
    # Exact unprefixed name agreed with B. Optional until the real adapter exists.
    ranking_model_path: Path | None = Field(default=None, validation_alias="RANKING_MODEL_PATH")

    @field_validator("ranking_model_path", mode="before")
    @classmethod
    def resolve_ranking_model(cls, value):
        if value is None or value == "":
            return None
        path = Path(value).expanduser()
        return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()

    @field_validator("cors_origins")
    @classmethod
    def require_origins(cls, origins: list[AnyHttpUrl]) -> list[AnyHttpUrl]:
        for origin in origins:
            if (
                origin.path not in (None, "/")
                or origin.query
                or origin.fragment
                or origin.username
                or origin.password
            ):
                raise ValueError("CORS entries must be origins without paths or credentials")
        return origins

    @property
    def allowed_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.cors_origins]
