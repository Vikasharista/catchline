# Catchline

AI sourcing co-pilot for a frozen-seafood RFx. Full spec in [PRD.md](PRD.md); build rules in [CLAUDE.md](CLAUDE.md).

## Setup

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set ANTHROPIC_API_KEY; GEMINI_API_KEY is optional but recommended
                        # as an automatic fallback if the Anthropic key runs out of credit
```

## Run

```bash
uvicorn app.main:app --reload
```

Open http://localhost:8000 — you'll land on the RFQ list. Click "+ New RFQ"
(or type what you need and "Start with chat") to create one; it seeds itself
automatically, so `scripts/seed.py` is no longer a required step.

## Reset

```bash
python -m scripts.reset_demo   # clears the DB and reseeds a demo RFx; keeps the LLM cache
```

Run scripts with `-m` (not `python scripts/reset_demo.py` directly) so `app`
resolves on the path — running the file directly only puts `scripts/` on
`sys.path`, not the repo root.

## Test

```bash
pytest -m "not llm"    # fast tests, no live model calls
pytest -m llm          # tests that call the live model (needs ANTHROPIC_API_KEY)
```

## Score extraction

```bash
python -m scripts.score_extraction   # compares extraction output with data/seed/.../05_answer_key
```

## Status

Day 1 AM foundations: repo scaffold, config, `app/llm.py` (LiteLLM wrapper with
retries/fallback/cache/tool loop), DB models (§8), app shell (sidebar + topbar,
built from `design/ux.html`'s tokens) and navigation, seed/reset scripts.

Remaining build steps follow PRD §13: ingestion + extraction + normaliser (Day 1
PM), rules/auditor/eligibility + review queue + comparison grid (Day 2 AM),
co-pilot and analyst agents (Day 2 PM), co-pilot UI and send flow (Day 3 AM),
hardening against the §11 eval (Day 3 PM).
