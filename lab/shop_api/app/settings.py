"""Shop API configuration. All env access in the service goes through here."""

from decimal import Decimal
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
    # pricing rules (see app/quote.py)
    tax_rate: Decimal = Decimal("0.17")
    shipping_fee: Decimal = Decimal("4.99")
    free_shipping_over: Decimal = Decimal("50.00")
    max_discount_pct: int = 30
    coupon_codes: str = "WELCOME10=10,BULK20=20,STAFF50=50"
    coupons_valid_until: str = "2099-12-31"
    low_stock_level: int = 3

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
