"""Shop API configuration. All env access in the service goes through here."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "shop"
    db_user: str
    db_password: SecretStr
    db_pool_size: int = 5
    redis_host: str = "localhost"
    redis_port: int = 6379
    order_queue: str = "orders:confirm"

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
