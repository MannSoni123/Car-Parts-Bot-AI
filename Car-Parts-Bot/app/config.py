
import os
from dotenv import load_dotenv
from dataclasses import dataclass, field

load_dotenv()


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else value


@dataclass
class AppConfig:
    # --- Core ---
    SECRET_KEY: str = _env("SECRET_KEY") or "unsafe-dev-secret"
    SQLALCHEMY_DATABASE_URI: str = _env("DATABASE_URL")  # REQUIRED

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "pool_size": 3,
        "max_overflow": 0,
        "connect_args": {"connect_timeout": 8},
    }

    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # --- Redis ---
    REDIS_URL: str | None = _env("REDIS_URL")
    # config.py
    UPLOAD_ROOT = os.getenv(
        "UPLOAD_ROOT"# local
    )
    MAX_REFERENCE_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

    ALLOWED_REFERENCE_EXTENSIONS = {"pdf", "txt", "docx"}
    # --- External APIs ---
    OPENAI_API_KEY: str | None = _env("OPENAI_API_KEY")
    OPENAI_MODEL: str = _env("OPENAI_MODEL", "gpt-4o-mini")

    META_VERIFY_TOKEN: str | None = _env("META_VERIFY_TOKEN")
    META_ACCESS_TOKEN: str | None = _env("META_ACCESS_TOKEN")
    META_PHONE_NUMBER_ID: str | None = _env("META_PHONE_NUMBER_ID")
    META_BUSINESS_ID: str | None = _env("META_BUSINESS_ID")

    CHASSIS_API_BASE_URL: str | None = _env("CHASSIS_API_BASE_URL")
    CHASSIS_API_KEY: str | None = _env("CHASSIS_API_KEY")

    ADMIN_TOKEN: str = _env("ADMIN_TOKEN", "admin-token")

    SALES_AGENTS: list[str] = field(default_factory=list)

    def __post_init__(self):
        agents = _env("SALES_AGENTS")
        self.SALES_AGENTS = [a.strip() for a in agents.split(",")] if agents else []
