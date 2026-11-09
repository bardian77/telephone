"""Settings, loaded from environment variables and an optional .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # provider keys (all optional; a missing key disables that provider)
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    cloudflare_account_id: str | None = None
    cloudflare_api_token: str | None = None
    replicate_api_token: str | None = None
    openai_api_key: str | None = None

    # money
    telephone_spend_cap_usd: float = Field(
        15.0,
        description="Hard stop on lifetime API spend for this project, in USD. Counted from the "
        "ledger's append-only spend log, so it survives restarts and new processes.",
    )
    gemini_free_tier: bool = Field(
        False,
        description="Set GEMINI_FREE_TIER=1 only if your Gemini key really is on the free tier. "
        "Then Gemini calls are costed at 0 and only the list price is recorded. By default "
        "Gemini is billed at list price, which is the honest assumption.",
    )

    # paths
    telephone_data_dir: Path = Path("data")

    # defaults
    default_captioner: str = "anthropic"
    default_caption_model: str = "claude-sonnet-5-5"
    default_generator: str = "gemini"
    default_generation_model: str = "gemini-2.5-flash-image"
    default_generations: int = 12
    default_seed: int = 7

    # live API
    telephone_live: bool = False
    telephone_live_daily_cap_usd: float = 1.0
    telephone_live_rpm_per_ip: int = 2

    @property
    def runs_dir(self) -> Path:
        return self.telephone_data_dir / "runs"

    @property
    def cache_dir(self) -> Path:
        return self.telephone_data_dir / "cache"

    @property
    def ledger_path(self) -> Path:
        return self.telephone_data_dir / "ledger.sqlite"

    @property
    def results_dir(self) -> Path:
        return self.telephone_data_dir / "results"

    @property
    def originals_dir(self) -> Path:
        return self.telephone_data_dir / "originals"


@lru_cache
def get_settings() -> Settings:
    return Settings()
