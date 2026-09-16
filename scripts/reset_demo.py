"""Clears the database and reseeds, keeping the LLM cache (per PRD §7.1)."""
from pathlib import Path

from app.config import settings
from app.db import init_db
from scripts.seed import main as seed_main


def main() -> None:
    db_path = Path(settings.database_url.replace("sqlite:///", ""))
    if db_path.exists():
        db_path.unlink()
    for d in ("inbox", "outbox"):
        folder = settings.data_dir / d
        for f in folder.glob("*"):
            f.unlink()
    init_db()
    seed_main()
    print("Demo reset. LLM cache kept at", settings.llm_cache_dir)


if __name__ == "__main__":
    main()
