import os
from dataclasses import dataclass

from pydantic_settings import BaseSettings, SettingsConfigDict

LOG_X = os.environ.get("LOG_X", "")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_")
    log_level: str = "info"


@dataclass
class Cfg:
    redis_host: str
    pool: int


def get_cfg():
    return Cfg(redis_host=os.getenv("REDIS_HOST", "x"), pool=int(os.environ["DB_POOL"]))
