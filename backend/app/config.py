"""Server-only configuration, independent from Vite's public environment."""

from pathlib import Path

from pydantic import AnyHttpUrl, Field, field_validator
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
