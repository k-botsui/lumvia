from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.local_network import is_lan_origin
from app.local_paths import CONFIG_FILE, STATE_ROOT


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=CONFIG_FILE, extra="ignore")
    database_url: str
    secret_key: str
    app_url: str = "http://127.0.0.1:3000"
    environment: str = "development"
    local_network: bool = False
    storage_backend: str = "local"
    storage_root: Path = STATE_ROOT / "storage"
    reference_preview_root: Path = STATE_ROOT / "reference-previews"
    support_github_repository: str = Field(
        default="k-botsui/lumvia",
        pattern=r"^$|^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$",
    )
    support_gateway_url: str = ""
    support_operator_delivery: bool = False
    broker_url: str = "amqp://guest:guest@127.0.0.1:5679//"
    redis_url: str = "redis://127.0.0.1:6381/0"
    max_upload_bytes: int = 256 * 1024 * 1024
    max_library_bytes: int = 10 * 1024 * 1024 * 1024
    max_duration_ms: int = 3600000
    max_concurrent_jobs: int = 20
    max_reference_items: int = 2000
    max_managed_items: int = 500
    max_cells: int = 2000
    max_cells_per_media: int = 100
    max_clip_ms: int = 300000
    max_analysis_runs: int = 10
    processing_timeout_seconds: int = 900
    session_hours: int = 24 * 7
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    s3_endpoint: str | None = None
    s3_bucket: str = "lumvia"
    s3_region: str = "us-east-1"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_allowed_domains: str = ""

    @model_validator(mode="after")
    def secure_configuration(self):
        if self.environment not in {"development", "production", "test"}:
            raise ValueError("Unsupported environment")
        if self.support_gateway_url:
            gateway = urlsplit(self.support_gateway_url)
            if (
                gateway.scheme != "https"
                or not gateway.hostname
                or gateway.username
                or gateway.password
                or gateway.query
                or gateway.fragment
                or gateway.path not in {"", "/"}
            ):
                raise ValueError("Support gateway must be a fixed HTTPS origin")
        if len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must contain at least 32 characters")
        if not self.database_url.startswith("postgresql"):
            raise ValueError("PostgreSQL is required")
        if self.environment == "production" and not self.app_url.startswith("https://"):
            raise ValueError("Production requires an HTTPS APP_URL")
        if self.storage_backend not in {"local", "s3"}:
            raise ValueError("Unsupported storage backend")
        parts = urlsplit(self.app_url)
        if (
            parts.scheme not in {"http", "https"}
            or not (
                parts.hostname in {"127.0.0.1", "localhost", "::1"}
                or (self.local_network and self.environment == "production" and is_lan_origin(self.app_url))
            )
            or parts.username
            or parts.password
        ):
            raise ValueError("Lumvia requires loopback, or an explicitly enabled private Wi-Fi HTTPS origin")
        if (
            self.storage_backend != "local"
            or self.oidc_issuer
            or self.oidc_client_id
            or self.oidc_client_secret
        ):
            raise ValueError("Lumvia is local only: cloud storage and external account login are disabled")
        for value, service in [
            (self.database_url, "postgres"),
            (self.broker_url, "rabbitmq"),
            (self.redis_url, "redis"),
        ]:
            if urlsplit(value).hostname not in {"127.0.0.1", "localhost", "::1", service}:
                raise ValueError(
                    "Lumvia is local only: databases and queues must stay on this computer or the private container network"
                )
        durable, disposable = self.storage_root.resolve(), self.reference_preview_root.resolve()
        if durable == disposable or durable in disposable.parents or disposable in durable.parents:
            raise ValueError("Temporary previews must stay separate from durable storage")
        return self


settings = Settings()
