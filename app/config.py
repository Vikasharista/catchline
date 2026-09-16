from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_model: str = "anthropic/claude-sonnet-4-5"
    llm_fallback: str | None = None
    llm_temperature: float = 0.0

    database_url: str = "sqlite:///./data/db.sqlite3"
    data_dir: Path = Path("./data")
    llm_cache_dir: Path = Path("./data/cache")

    default_incoterm_place: str = "Boulogne"

    class Config:
        env_file = ".env"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.llm_cache_dir.mkdir(parents=True, exist_ok=True)
(settings.data_dir / "inbox").mkdir(parents=True, exist_ok=True)
(settings.data_dir / "outbox").mkdir(parents=True, exist_ok=True)
