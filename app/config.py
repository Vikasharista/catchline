from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_model: str = "anthropic/claude-sonnet-4-5"
    llm_fallback: str | None = None
    llm_temperature: float = 0.0

    # Credit-wastage guardrails (app/llm.py, app/rate_limit.py). Budget is
    # enforced *before* a call is attempted — once today's spend estimate
    # hits this, no further LLM call goes out at all, not even a retry.
    llm_daily_budget_usd: float = 3.0
    llm_chat_max_tokens: int = 1200
    llm_chat_rate_limit_count: int = 15
    llm_chat_rate_limit_window_s: int = 600

    database_url: str = "sqlite:///./data/db.sqlite3"
    data_dir: Path = Path("./data")
    llm_cache_dir: Path = Path("./data/cache")

    default_incoterm_place: str = "Boulogne"

    # Read by litellm directly from the environment; declared here only so
    # pydantic-settings doesn't reject it as an unknown .env key.
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    groq_api_key: str | None = None

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.llm_cache_dir.mkdir(parents=True, exist_ok=True)
(settings.data_dir / "inbox").mkdir(parents=True, exist_ok=True)
(settings.data_dir / "outbox").mkdir(parents=True, exist_ok=True)
