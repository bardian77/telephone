"""Settings, loaded from environment variables and the project's .env file.

The .env file is the one at the project root (see telephone/paths.py), whatever the current
directory is, and a relative data dir is anchored on the root too.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .paths import project_root
from .providers.defaults import DEFAULT_CAPTIONER, DEFAULT_GENERATOR


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8", extra="ignore")

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

    @field_validator("telephone_data_dir", mode="after")
    @classmethod
    def _anchor_on_root(cls, v: Path) -> Path:
        return v if v.is_absolute() else project_root() / v

    # defaults (model ids come from telephone/providers/defaults.py)
    default_captioner: str = DEFAULT_CAPTIONER
    default_generator: str = DEFAULT_GENERATOR
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
    def figures_dir(self) -> Path:
        return self.telephone_data_dir / "figures"

    @property
    def fixtures_dir(self) -> Path:
        return self.telephone_data_dir / "fixtures"

    @property
    def originals_dir(self) -> Path:
        return self.telephone_data_dir / "originals"

    @property
    def private_dir(self) -> Path:
        """Photographs that are processed on request but never exported or served."""
        return self.originals_dir / "private"


@lru_cache
def get_settings() -> Settings:
    env_file = project_root() / ".env"
    return Settings(_env_file=env_file if env_file.exists() else None)
