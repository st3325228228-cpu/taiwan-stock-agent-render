"""Environment-backed configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    """Runtime settings with safe local defaults."""

    database_path: str = "data/agent.db"
    llm_model: str = "gpt-5-mini"
    use_llm: bool = True
    news_limit: int = 8
    provider: str = "yfinance"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_path=os.getenv("STOCK_AGENT_DB", "data/agent.db"),
            llm_model=os.getenv("LLM_MODEL", "gpt-5-mini"),
            use_llm=_as_bool(os.getenv("USE_LLM"), True),
            news_limit=max(1, int(os.getenv("NEWS_LIMIT", "8"))),
            provider=os.getenv("STOCK_DATA_PROVIDER", "yfinance").lower(),
        )
