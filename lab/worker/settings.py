"""Worker configuration (env-driven)."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class WorkerSettings(BaseSettings):
    redis_host: str = "localhost"
    redis_port: int = 6379
    order_queue: str = "orders:confirm"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "shop"
    db_user: str
    db_password: SecretStr
    db_pool_size: int = 2
    max_retries: int = 3
    backoff_base_s: float = 1.0
    connect_attempts: int = 10

    model_config = SettingsConfigDict(extra="ignore")

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.db_user,
            password=self.db_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )

    @property
    def dead_queue(self) -> str:
        return f"{self.order_queue}:dead"


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
