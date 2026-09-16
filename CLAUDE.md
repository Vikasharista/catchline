# CLAUDE.md: Catchline

Read PRD.md first. It is the spec. Build in the order given in its §13.

## Hard rules

- **The AI must really run.** Never hardcode demo answers or reference numbers (6.91M, 8.93, 48k, …) anywhere in app/.
- **The LLM never produces a number that is displayed.** All maths lives in app/normalize/ and the analyst tools.
- **Never pass data/seed/05_answer_key/ to any prompt or tool.** It is only for tests and scripts/score_extraction.py.
- **The co-pilot has no tool that writes to the draft.** Drafts change only through copilot/apply.py, after a buyer action.
- The risk classification (money/eligibility) is decided by code, never by the model.
- Uncertain values stay null or flagged. Never guess them.
- All LLM calls go through app/llm.py (LiteLLM, model name from env).

## UI

- design/ux.html is the visual source of truth (app shell: sidebar nav + topbar, and design tokens). Reuse its tokens and components; don't invent new styles. It does not include per-screen mockups — those are built from the PRD's functional requirements (§7.2–7.10) using the same tokens.
- If the HTML and the PRD disagree on behaviour, follow the PRD.

## Commands

- `uvicorn app.main:app --reload`: run the app
- `python scripts/seed.py`: seed the demo data
- `python scripts/reset_demo.py`: reset the demo
- `pytest -m "not llm"`: run fast tests
- `pytest -m llm`: run tests that call the live model
- `python scripts/score_extraction.py`: score extraction against the answer key

## Definition of done

See PRD §13. In short:

- the full flow works on the deployed URL;
- the extraction eval has 0 silently wrong values;
- the §11 questions pass.
