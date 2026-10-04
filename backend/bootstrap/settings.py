"""B.O.S. Platform Settings v1.0

Environment-driven settings for one B.O.S. deployment.
Every value has a safe default so a new operator can start with zero configuration.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


def _sql_url(url: str) -> str:
    """Hosted Postgres URLs (postgres://, postgresql://) use the installed psycopg 3 driver."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def _default_data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data"


@dataclass
class PlatformSettings:
    """Resolved runtime settings for the platform process."""

    environment: str = "development"
    data_dir: Path = field(default_factory=_default_data_dir)
    database_url: str = ""
    memory_database_url: str = ""
    memory_database_schema: str = ""
    secret_key: str = ""
    public_base_url: str = ""
    cors_origins: List[str] = field(default_factory=list)

    ai_provider: str = "auto"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"

    autopilot_interval_minutes: int = 60
    autopilot_scheduler_enabled: bool = True
    frontend_dist: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2] / "frontend" / "dist")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @classmethod
    def from_env(cls) -> "PlatformSettings":
        data_dir = Path(os.getenv("BOS_DATA_DIR") or _default_data_dir())
        data_dir.mkdir(parents=True, exist_ok=True)
        origins = [o.strip() for o in os.getenv("BOS_CORS_ORIGINS", "").split(",") if o.strip()]
        frontend_dist = os.getenv("BOS_FRONTEND_DIST")
        settings = cls(
            environment=os.getenv("ENVIRONMENT", "development"),
            data_dir=data_dir,
            database_url=_sql_url(os.getenv("DATABASE_URL") or f"sqlite:///{data_dir / 'bos.db'}"),
            memory_database_url=_sql_url(os.getenv("MEMORY_DATABASE_URL") or f"sqlite:///{data_dir / 'memory.db'}"),
            memory_database_schema=os.getenv("MEMORY_DATABASE_SCHEMA", ""),
            secret_key=os.getenv("BOS_SECRET_KEY", ""),
            public_base_url=os.getenv("PUBLIC_BASE_URL", "").rstrip("/"),
            cors_origins=origins,
            ai_provider=os.getenv("BOS_AI_PROVIDER", "auto").lower(),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            anthropic_model=os.getenv("BOS_CLAUDE_MODEL", "claude-opus-5-5"),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            gemini_model=os.getenv("BOS_GEMINI_MODEL", "gemini-3.5-flash-lite"),
            autopilot_interval_minutes=max(5, _int("BOS_AUTOPILOT_INTERVAL_MINUTES", 60)),
            autopilot_scheduler_enabled=_bool("BOS_AUTOPILOT_SCHEDULER", True),
        )
        if not os.getenv("MEMORY_DATABASE_URL") and not settings.database_url.startswith("sqlite"):
            # One hosted database is enough: memory lives in its own schema, never in business tables.
            settings.memory_database_url = settings.database_url
            settings.memory_database_schema = settings.memory_database_schema or "bos_memory"
        if frontend_dist:
            settings.frontend_dist = Path(frontend_dist)
        if not settings.secret_key:
            settings.secret_key = _load_or_create_secret(data_dir)
        return settings


def _load_or_create_secret(data_dir: Path) -> str:
    """Persist a generated signing key so sessions survive restarts without manual setup."""
    import secrets

    key_file = data_dir / ".secret_key"
    if key_file.exists():
        return key_file.read_text().strip()
    key = secrets.token_urlsafe(48)
    key_file.write_text(key)
    try:
        key_file.chmod(0o600)
    except OSError:
        pass
    return key
