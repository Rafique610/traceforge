"""Toy settings: every value comes from an environment variable listed in compose.yaml."""

import os
from dataclasses import dataclass


def env(key, default):
    return os.environ.get(key, default)


@dataclass
class Settings:
    redis_host: str
    redis_port: int
    db_pool_size: int
    tax_rate: float
    discount_cap: float


def settings():
    return Settings(
        redis_host=env("REDIS_HOST", "localhost"),
        redis_port=int(env("REDIS_PORT", "6379")),
        db_pool_size=int(env("DB_POOL_SIZE", "5")),
        tax_rate=float(env("TAX_RATE", "0.17")),
        discount_cap=float(env("DISCOUNT_CAP", "0.5")),
    )
