# Catchline

AI sourcing co-pilot for a frozen-seafood RFx. Full spec in [PRD.md](PRD.md); build rules in [CLAUDE.md](CLAUDE.md).

## Setup

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set ANTHROPIC_API_KEY (or another LiteLLM-supported provider)
```

## Run

```bash
python scripts/seed.py       # seeds the 5 demo suppliers
uvicorn app.main:app --reload
```

Open http://localhost:8000.

## Reset

```bash
python scripts/reset_demo.py   # clears the DB and reseeds; keeps the LLM cache
```

## Test

```bash
pytest -m "not llm"    # fast tests, no live model calls
pytest -m llm          # tests that call the live model (needs ANTHROPIC_API_KEY)
```

## Score extraction

```bash
python scripts/score_extraction.py   # compares extraction output with data/seed/.../05_answer_key
```

## Status

Day 1 AM foundations: repo scaffold, config, `app/llm.py` (LiteLLM wrapper with
retries/fallback/cache/tool loop), DB models (§8), app shell (sidebar + topbar,
built from `design/ux.html`'s tokens) and navigation, seed/reset scripts.

Remaining build steps follow PRD §13: ingestion + extraction + normaliser (Day 1
PM), rules/auditor/eligibility + review queue + comparison grid (Day 2 AM),
co-pilot and analyst agents (Day 2 PM), co-pilot UI and send flow (Day 3 AM),
hardening against the §11 eval (Day 3 PM).
