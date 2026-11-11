"""Settings from environment variables (or the gitignored .env file).

DB_HOST, DB_PORT, DB_NAME, DB_USER and DB_PASSWORD are required; nothing is
hard-coded, so no credential can end up in Git.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    db_host: str
    db_port: int = 5432
    db_name: str
    db_user: str
    db_password: str
    db_pool_min: int = 1
    db_pool_max: int = 10


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  (values come from the environment)
