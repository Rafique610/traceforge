"""App settings. The only place that reads environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRACEFORGE_", env_file=ROOT_ENV, extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "traceforge"
    db_user: str = "traceforge"
    db_password: SecretStr = SecretStr("")

    # LLM gateway: any OpenAI-compatible provider
    llm_provider: Literal["ollama", "openrouter", "mistral", "groq", "beatapi", "axforge"] = (
        "ollama"
    )
    llm_model: str = "qwen2.5-coder:7b"
    # Hard guard against paid use: only allowlisted providers, openrouter ids must end ':free'.
    llm_free_only: bool = True
    llm_free_allowlist: frozenset[str] = frozenset({"ollama", "openrouter", "beatapi", "axforge"})
    llm_max_output_tokens: int = 4096  # reasoning models spend part of this on hidden reasoning
    llm_reasoning_effort: Literal["low", "high", "max"] | None = (
        None  # axforge only; None = provider default
    )
    llm_allow_ollama_cloud: bool = False  # cloud-tagged Ollama models are billed per token
    ollama_base_url: str = "http://localhost:11434/v1"
    openrouter_api_key: SecretStr = SecretStr("")
    mistral_api_key: SecretStr = SecretStr("")
    groq_api_key: SecretStr = SecretStr("")
    # BeatAPI free-only profile (only glm-5.3-flash-free; see agent/beatapi.py). The key may be
    # set as TRACEFORGE_BEATAPI_API_KEY or plain BEATAPI_API_KEY.
    beatapi_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("TRACEFORGE_BEATAPI_API_KEY", "BEATAPI_API_KEY"),
    )
    # AxForge (only glm-5.3-flash; see agent/axforge.py). key env: AXFORGE_API_KEY
    axforge_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("TRACEFORGE_AXFORGE_API_KEY", "AXFORGE_API_KEY"),
    )
    llm_cache_dir: Path = Path(".cache/llm")
    llm_call_log: Path = Path("runs/llm_calls.jsonl")
    llm_max_rps: float = 1.0
    llm_max_prompt_chars: int = 400_000
    manifest: str | None = None  # dataset manifest for GET /evaluation/report
    runs_dir: Path = Path("runs")  # saved experiment runs (TRACEFORGE_RUNS_DIR)
    # Scratch space for live end-to-end evidence runs; git-ignored under .cache by default.
    e2e_scratch_dir: Path = Field(
        default=Path(__file__).resolve().parents[2] / ".cache" / "e2e",
        validation_alias=AliasChoices("TRACEFORGE_E2E_SCRATCH_DIR", "TF_E2E_SCRATCH"),
    )
    showcase_mode: bool = False  # read-only public showcase: non-GET requests get 403
    agent_context_budget_chars: int = 12000  # D20 placeholder until the P0-S06 measured limit
    # model id -> (USD per 1M input tokens, USD per 1M output tokens), list-price equivalent
    llm_prices: dict[str, tuple[float, float]] = {}

    # GitHub intake: read-only token optional; empty allowlist means every URL is refused.
    # Entries are "owner" or "owner/repo".
    github_token: SecretStr | None = None
    github_allowed_owners: list[str] = []
    github_api_base: str = "https://api.github.com"
    github_timeout_s: float = 10.0

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
