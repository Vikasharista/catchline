# PRD: Catchline, an AI Sourcing Co-pilot for Frozen Seafood RFx

**Owner:** Vikash Kumar · **Build agent:** Claude Code · **Status:** Ready to build · **Timeline:** 3 days
**Context:** Aerchain Principal PM take-home, "Kill the Quote Spreadsheet"

**For Claude Code:** read this whole file before writing code. Build in the order given in §13. The UX source of truth is design/ux.html (supplied by Vikash). Match its layout, copy and styling; where it disagrees with this PRD on *behaviour*, this PRD wins. Where the HTML has no screen for something here, reuse its components and tokens.

**Non-negotiable rule from the brief:** the plumbing (email, auth) can be stubbed, but **the AI must really run**. Extraction and reasoning go through a real LLM every time. **Never hardcode demo answers**, not even in fallbacks.

---

## 1. TL;DR

A buyer at a fish processor drafts an RFx by chatting with a co-pilot. The co-pilot only *proposes* changes; the buyer approves each one and signs off each section. The RFx goes out to 5 suppliers, whose replies come back as Excel, PDF, Word, a phone photo and an email.

Agents then:

- read every reply;
- Python converts every price to **EUR per kg of net weight, delivered to Boulogne (DAP)**;
- anything uncertain goes to a review queue;
- the buyer asks questions in plain English until they reach an award they can defend.

Every number traces back to its source, and nothing uncertain is guessed.

## 2. Problem and goals

Buyers spend about 3 days retyping quotes and another day on each "what if" question. In seafood, quotes are hard to compare:

- currencies differ (EUR, USD, NOK);
- units differ (per kg, per lb, per 7.5 kg block, per 10 kg carton);
- glaze (ice coating) inflates the weight;
- delivery terms (Incoterms) differ;
- certificates decide who is even eligible.

| Goal | Measure (for the demo) |
| :-- | :-- |
| Build a comparable table without retyping | All 85 quoted cells extracted; **0 silently wrong values** against the answer key |
| Earn trust with €7M at stake | Every cell has source text, location and each conversion step; uncertain cells are flagged, never guessed |
| Keep the buyer in control of the RFx | No AI edit reaches the draft without a click; sending is blocked until every section is signed off |
| Answer questions in plain language | The 10 script questions in §11 are answered correctly, without hardcoding |

**Non-goals:**

- real SMTP;
- login and user roles;
- a supplier portal;
- negotiation rounds or e-auctions;
- live FX feeds;
- import duty;
- optimisation beyond simple caps;
- mobile layout;
- editing the RFx after it has been sent;
- a second approver.

## 3. Users

- **Claire, category buyer** (primary): experienced and non-technical. She owns the RFx and the award.
- **VP Procurement** (reads the output): receives the award memo and export. Has no login.

## 4. Tech stack

| Area | Choice |
| :-- | :-- |
| Backend | Python 3.11, **FastAPI**, Uvicorn, Pydantic v2 |
| Frontend | **Vikash's HTML** (design/ux.html), split into Jinja2 templates plus vanilla JS modules (or Alpine.js/htmx if the HTML already uses them). No React. |
| Real-time updates | Server-Sent Events (SSE) for agent progress and chat streaming |
| Storage | SQLite (SQLModel) with files on local disk under data/ |
| LLM | **LiteLLM** behind app/llm.py. The model name comes from env vars. Default LLM_MODEL=anthropic/claude-sonnet-4-5 (or the latest available); LLM_FALLBACK is optional. Temperature is 0. |
| Documents | openpyxl, pdfplumber + pypdfium2 (page images), python-docx, Python email library, Pillow |
| Analysis | pandas; Plotly (JSON sent to plotly.js in the browser) |
| Output files | reportlab for the RFQ PDF and award memo PDF; openpyxl for Excel exports |
| Tests | pytest |
| Deploy | Dockerfile, deployed to **Render** (or Railway), with a persistent disk for data/. .env.example included. |

## 5. Repo layout

```
catchline/
  app/
    main.py              # FastAPI app, routes, SSE
    config.py            # env settings
    llm.py               # LiteLLM wrapper: complete(), tool loop, JSON schema, images, retries, cache
    db.py, models.py     # SQLModel tables (§8)
    schemas/             # Pydantic: RfxDraft, ChangeProposal, ExtractedQuote, ...
    copilot/             # agent.py, tools.py, apply.py (JSON patch), checks.py (section rules), prompts.py
    ingest/              # router.py, xlsx.py, pdf.py, docx.py, image.py, eml.py
    extract/             # agent.py (pass A items, pass B line matching), prompts.py
    normalize/           # convert.py (FX, unit, glaze, freight), reference.py
    validate/            # rules.py, auditor.py (LLM), eligibility.py
    analyst/             # agent.py, tools.py (fixed tools), sandbox.py (read-only pandas)
    exports/             # rfq_pdf.py, template_xlsx.py, award_xlsx.py, memo.py
    channel/             # outbox.py, inbox.py (stubbed email)
  web/
    templates/           # built from design/ux.html
    static/              # css (tokens copied from the HTML), js
  design/ux.html         # SUPPLIED BY VIKASH
  data/seed/             # aerchain_fish_rfx_dataset (unzipped)
  scripts/seed.py, scripts/score_extraction.py, scripts/reset_demo.py
  tests/
  Dockerfile, .env.example, README.md, CLAUDE.md
```

## 6. Demo data (already provided)

Unzip aerchain_fish_rfx_dataset.zip into data/seed/.

| Folder | Contents |
| :-- | :-- |
| 01_buyer_rfx/ | Reference RFQ (PDF) and response template (xlsx). Used to seed a "completed draft" so the demo can skip drafting if needed. |
| 02_supplier_replies/ | S1 Fjordline: xlsx, NOK, FCA Ålesund, own layout, decimal commas, per-block pollock · S2 Pacific Rim: PDF, USD per lb, glazed (gross) weight with 20% glaze, CFR Le Havre, 3% early-PO discount in a footnote, questionnaire on page 2 · S3 Atlantico: docx, EUR, DAP, prices written in paragraphs, some per 6×2 kg carton · S4 Oceanis: angled jpg, EUR, CIF Rotterdam, shrimp per 10 kg master carton, **coffee stain over line L28**, 27 of 30 lines · S5 Baltic Blue: eml, EXW Gdynia plus ~€0.18 freight, "rest same as last year", no questionnaire |
| 03_attachments/ | Food-safety certificates. **S4's expired on 2026-08-31.** |
| 04_buyer_reference_data/ | fx_rates_2026-09-10.csv (USD 1.17, NOK 11.70 per EUR) · freight_adders_to_DAP_Boulogne.csv (FCA Ålesund 0.35, CFR Le Havre 0.12, CIF Rotterdam 0.22, DAP 0) · last_year_contract_prices.xlsx · award_rules.md |
| 05_answer_key/ | ground_truth_quotes.csv, ground_truth_supplier_qualification.csv. **Only for scoring and tests. Never pass these to any LLM prompt or tool.** |

Line and supplier master data comes from the RFx itself: 30 lines, L01–L30, with species, form, grade and annual volume.

## 7. Functional requirements

### 7.1 App shell (all screens)

- **Left navigation:** Draft · Inbox · Review · Compare · Ask · Award. Each step shows as done / current / locked.
- **Top bar:**
  - RFx ID;
  - an "Agents: N working" pill (from SSE);
  - ⌘K "Ask anything", which opens the Ask screen with the question filled in.
- **Activity drawer:** a time-ordered feed of agent and user actions (from audit_log). Each entry links to the item it touched.
- **Reset demo button** (settings menu): runs scripts/reset_demo.py, which clears the database, reseeds, and keeps the LLM cache.

### 7.2 RFx co-pilot, with the buyer in control (Draft screen)

**What it covers:** Scope · Line items · Questionnaire · Terms · **Custom sections** (any title the buyer asks for). The co-pilot drafts **only from the buyer's chat**. It may add ideas from its own domain knowledge, but these are labelled suggested.

**RfxDraft schema** (Pydantic, stored as JSON with a version number):

- **scope:**
  - title, category, buyer_site, contract_start, contract_end;
  - incoterm, incoterm_place, currency;
  - weight_basis (net | gross), response_deadline, award_date.
- **lines[]:**
  - line_id, species, form, grade, spec_notes, unit (kg);
  - annual_volume_kg, custom_fields{}.
- **questionnaire[]:**
  - q_id, group (certifications | quality | traceability | commercial);
  - text, answer_type (yes_no | text | date | file);
  - pass_rule (optional, structured, e.g. {"type": "date_after", "ref": "award_date"}).
- **terms:**
  - payment_terms, glaze_cap_pct, quote_validity_days, partial_quotes_allowed;
  - eval_weights {price, quality, commercial};
  - award_rules[] (e.g. {"type": "max_share_per_supplier_per_species", "value": 0.6}, {"type": "require_valid_cert", "schemes": ["BRCGS", "IFS"]}, {"type": "ban_additive", "codes": ["E450", "E451", "E452"], "applies_to": "raw shrimp"}).
- **custom_sections[]:**
  - key, title, body_md, requires_supplier_response (bool).
- **suppliers[]:** name, email (5 seeded suppliers; the co-pilot can suggest the list, and the buyer confirms it).

**Agent tools.** None of these write to the draft.

| Tool | Purpose |
| :-- | :-- |
| read_draft() | Returns the current draft JSON, each section's status, pending proposals, and the last 20 rejected proposals |
| propose_change(section, op: add\|update\|remove, target, value, reason, origin: from_you\|suggested, risk: money_or_eligibility\|normal) | Suggests an edit to an existing section |
| propose_section(title, body_md, requires_supplier_response, reason, origin) | Suggests a new custom section |
| ask(question, options[], allow_free_text) | Asks the buyer a question |

**The loop:**

1. **Buyer sends a chat message.** The agent runs a tool loop (max 6 steps) and streams its text reply over SSE.
2. **Each proposal becomes a change_proposal row** with status pending, shown inline in the draft as a tracked change: before is struck through, after is highlighted.
   - The card shows an **origin badge** ("From you" / "Suggested"), the reason, and **Accept / Edit / Reject** buttons.
3. **Accept or Edit:**
   - copilot/apply.py turns the proposal into a JSON patch and applies it to a copy of the draft.
   - The copy is validated against the RfxDraft schema.
   - On success: save it as version N+1 and write to audit_log.
   - On validation failure: do not change the draft; send the error back to the agent in the next turn, and show "Couldn't apply: {reason}" on the card.
4. **Reject:** set status rejected and store it. The system prompt tells the agent **not to propose it again** unless the buyer brings it up.
5. **Accept all (shown):**
   - Applies only visible pending proposals with risk = normal.
   - Skips money_or_eligibility proposals and says "2 changes need individual review".
   - risk is set by **code, not the model**. It is money_or_eligibility if the target is:
     - lines[*].annual_volume_kg
     - scope.weight_basis, scope.incoterm*, scope.currency
     - terms.glaze_cap_pct, terms.eval_weights, terms.award_rules
     - questionnaire[*].pass_rule
     - or a line is added or removed.
6. **Section sign-off:**
   - Each section has drafting | signed_off | reopened.
   - The [Sign off] button runs copilot/checks.py. It is disabled while any check fails, and its tooltip lists the failures.
   - While signed off, a new proposal that targets the section gets status held and shows a banner: "{Section} is signed off. Reopen to apply?" with [Reopen] [Dismiss].
   - Reopening sets reopened, releases held proposals back to pending, and requires signing off again.
7. **Version history:** every applied change is a version. Restoring version K:
   - sets the draft to version K as a new version (N+1);
   - reopens every section whose content differs;
   - is logged.
8. **Send:**
   - Enabled only when all sections are signed_off and there are 0 pending proposals.
   - Opens the **pre-send preview**: RFQ PDF, response template xlsx, and a sign-off summary (who and when).
   - Confirm → channel/outbox.py writes one .eml per supplier to data/outbox/, and the RFx becomes sent (read-only).

**Section checks (code):**

| Section | Must be true before sign-off |
| :-- | :-- |
| Scope | incoterm and place, currency, weight_basis, contract dates, response_deadline, award_date are set; deadline is before award date |
| Lines | ≥1 line; each has species, form, grade, unit and volume > 0; line_ids are unique |
| Questionnaire | ≥1 question; every pass_rule references an existing field or date |
| Terms | eval_weights add up to 100; if any line is glazed (shrimp or squid), glaze_cap_pct is set; payment_terms is set |
| Custom section | title and body are not empty |

**System prompt rules for the co-pilot (put these in prompts.py):**

- Never invent volumes, prices or dates. Ask instead.
- Ask before assuming anything in the money or eligibility list.
- Label your own ideas as suggested.
- Keep replies short and in plain language.
- Do not repeat rejected proposals.
- You cannot edit the draft yourself; say "I've suggested N changes".

**Acceptance criteria:**

- Given an empty draft, when the buyer says *"Annual frozen raw-material contract, delivered Boulogne, add salmon HOG 3–4 kg 60 t"*: the co-pilot proposes the scope fields and 1 line (origin from_you), asks about weight basis with [Net] [Gross] chips, and **the draft is unchanged** until the buyer clicks Accept.
- Given *"add squid rings"* with no volume: the co-pilot asks for the volume and proposes no line with a made-up number.
- Given the buyer says *"add a section on packaging requirements"*: a propose_section card appears, and after it's accepted a new tab "Packaging requirements" exists with status drafting.
- Given Scope is signed off, when a proposal targets scope.currency: its status is held, and the banner appears.
- Given 3 pending proposals, one of which changes annual_volume_kg: "Accept all" applies 2 and leaves the volume change pending.
- Given Terms eval weights of 60/25/5: Sign off is disabled with the tooltip "Evaluation weights add up to 90%, not 100%".
- Given an unsigned section: Send is disabled with the reason shown.
- **Demo shortcut:** a "Load reference RFx" button seeds the full 30-line draft from data/seed (all sections drafting), so the demo can show sign-off without dictating 30 lines. The chat still works on top of it.

### 7.3 Channel (stubbed)

- **Outbox:** writes .eml files.
- **Inbox:** "Simulate replies arriving" copies the 5 files from 02_supplier_replies (and certificates from 03_attachments) into data/inbox/. They arrive one by one, about 1.5 seconds apart, with an SSE event for each.
- Replies can also be **uploaded** by drag and drop, so interviewers can try their own file live.
- Each file is linked to a supplier by the sender email or filename. If neither matches, the buyer picks the supplier.

### 7.4 Ingestion and extraction (Inbox screen)

**Router:** turns each file into an IngestedDoc made of chunks: {kind: text|table|image, content, locator}.

| Format | How it's read | Locator |
| :-- | :-- | :-- |
| xlsx | Cell grid with A1 references, all sheets, values as displayed (keep decimal commas) | cell (e.g. Tilbud!D8) |
| pdf | Text per page (pdfplumber) plus a PNG of each page (pypdfium2, 150 dpi) | page, bbox if available |
| docx | Paragraphs and tables, in order | paragraph or table index |
| jpg/png | Image sent as is to a vision model; EXIF rotation fixed | image, plus row region if the model returns one |
| eml | Headers and body text; attachments sent back through the router | message, attachment name |

**Extraction agent** (real LLM, structured output). Runs once per document:

- **Pass A: items.** Returns ExtractedItem[], where each item has:
  - raw_text (exact source quote) and locator;
  - product_desc, price (number or null), currency, price_unit (e.g. per_lb, per_kg, per_block, per_carton, per_master_carton), pack_size_kg (number or null), weight_basis (net | gross | unknown), glaze_pct, incoterm, incoterm_place;
  - conditions[] (discounts, rebates, surcharges, with scope and condition);
  - references_prior (e.g. "same as last year");
  - legibility (clear | partial | illegible) and confidence (0 to 1).
  - Document-level fields as well: supplier name, currency, incoterm, validity, payment terms, glaze statement, and questionnaire answers {q_id, answer, raw_text, locator}.
- **Pass B: line matching.** Matches items to RFx lines (species × form × grade), with match_reason and match_confidence. Unmatched items are kept and shown.

**Rules:**

- The model **reads numbers exactly as written** and never converts them.
- If a value can't be read, return price: null, legibility: illegible.
- A document that sets a default (e.g. "all prices CFR Le Havre in USD", "shrimp 20% glaze on gross weight") is applied to every item it covers, and the item notes where that came from.
- Pydantic validates the output; retry once on failure, then mark the document needs_attention.
- Cache by sha256(file) + prompt_version + model. The "Re-run live" button ignores the cache.

**UI:**

- Supplier cards with a step list (Opened → Found prices → Matched lines → Converted → Checked);
- a coverage bar;
- counts of confirmed values and values that need the buyer;
- a document preview with extracted locations highlighted (image/page boxes where available).
- **Summary strip:** "85 prices read · X confirmed automatically · Y need you · 0 guessed".
- **Accuracy card** (demo mode): scripts/score_extraction.py compares results with the answer key and shows exact / flagged / silently wrong.

### 7.5 Normaliser (Python only)

For each matched item, normalize/convert.py returns eur_kg_net_dap and a steps[] list, each step with a label, operation and value:

1. **Unit to per kg:** per_lb → ÷ 0.45359237 · per_block / per_carton / per_master_carton → ÷ pack_size_kg (if pack_size is missing → flag unit_unknown, no value).
2. **FX:** ÷ units_per_EUR from the reference CSV.
3. **Glaze:** if weight_basis is gross and glaze_pct > 0 → ÷ (1 − glaze_pct). If the basis is unknown for a glazed species → flag glaze_basis_unknown (value computed on net, amber).
4. **Freight to DAP Boulogne:** + the adder from the freight table. Use the supplier-stated freight if given (S5 ~0.18, marked supplier_stated_approx). An unknown incoterm → flag.
5. **"Same as last year":** take the price from last_year_contract_prices.xlsx (already DAP, net), with status inferred and source "2025-26 contract". If the supplier also says "freight extra", flag freight_ambiguous (no adder applied; the buyer decides).
6. **Conditions** (discounts and rebates) are **not applied**. They are stored for the analyst.

**Acceptance:** unit tests reproduce eur_per_kg_net_dap for **every** row of ground_truth_quotes.csv within ±0.01 when given the answer key's native fields. Worked example: S2 L18 $3.74/lb → ÷0.45359 = 8.245 → ÷1.17 = 7.047 → ÷0.80 = 8.809 → +0.12 = **8.93**.

### 7.6 Validator and eligibility

**Rule flags** (validate/rules.py), each with a severity (red | amber | info):

| Flag | Condition | Severity |
| :-- | :-- | :-- |
| illegible | Item marked illegible | red |
| unit_unknown, glaze_basis_unknown, freight_ambiguous | From the normaliser | amber |
| inferred_prior | Price taken from last year's contract | amber |
| glaze_adjusted, fx_converted, unit_converted, freight_assumed | Conversion applied | info |
| peer_outlier | More than 25% from the median of other suppliers on that line | amber |
| ly_outlier | More than 20% from last year's price | amber |
| low_confidence | Confidence below 0.8 | amber |
| not_quoted | Line missing from a supplier's reply (**not** a zero price) | info |
| unmatched_item | Item that didn't match any line | info |

**LLM auditor** (validate/auditor.py): one call per supplier, given its questionnaire answers, certificate extraction, and document notes. It returns contradictions with evidence from both sides. For example: S4 questionnaire says "BRCGS valid" vs the certificate's valid_until 2026-08-31, which is before the award date.

**Eligibility** (validate/eligibility.py, deterministic, applies the RFx award rules):

- A supplier is eligible, not_eligible, conditional (eligible except for some lines, e.g. S2 raw shrimp because of E451), or unknown (no questionnaire or certificate, e.g. S5).
- Each status comes with reasons and evidence links.
- **Expected results:** S1 eligible · S2 conditional (blocked on L17–L19 and L22–L24) · S3 eligible · S4 not eligible (expired certificate) · S5 unknown.

### 7.7 Review queue (Review screen)

- One item at a time, holding every red and amber flag plus auditor contradictions.
- Each item shows the source crop or snippet, the extracted value, the conversion trail, and why it was flagged.
- **Actions:**
  - **Accept:** status confirmed.
  - **Edit value:** requires a reason; status edited.
  - **Ask supplier:** drafts an email to the outbox with the LLM, shown for approval before it's saved; status ask_supplier.
  - **Exclude line for this supplier.**
  - For eligibility items: **Override**, which requires a reason.
- Keyboard shortcuts: A / E / S / X. The screen shows progress ("3 of 7").
- **Everything is written to audit_log.**

### 7.8 Comparison (Compare screen)

- **Grid:** lines × suppliers in €/kg net DAP, grouped by species.
  - The cheapest eligible value in each row is marked.
  - Cell states: confirmed / auto / edited / inferred / flagged / illegible / not quoted.
- **Column headers:** eligibility badge, certificate expiry, coverage (e.g. 27/30).
- **Clicking a cell** opens a popover with raw_text, document and locator (plus a jump to the preview), the steps, confidence, flags and conditions.
- **Assumptions panel** (editable): FX rates, freight adders, award date. Editing re-runs the normaliser (not the LLM) and logs the change.
- **Filters:** species, "eligible only", "hide inferred".

### 7.9 Analyst agent (Ask screen)

**Data given to the agent:** a read-only DataFrame quotes, with columns:

- line_id, species, form, grade, volume_kg;
- supplier_id, supplier_name, eur_kg_net_dap, status, flags, conditions;
- eligibility, line_blocked, native_price, native_unit, currency, incoterm.

Plus the suppliers, questionnaire and last_year tables, and the current assumptions.

**Fixed tools** (tried first):

| Tool | Returns |
| :-- | :-- |
| coverage() | Lines quoted per supplier; lines with fewer than N quotes |
| uncertain_items() | Everything not confirmed, grouped by reason |
| explain_cell(supplier, line) | Source, steps, flags |
| cheapest_per_line(filter) | Filter can be eligible_only, exclude/include suppliers, species. Returns the award table, total spend (volume × price), winners by supplier, and uncovered lines. |
| split_award(max_share_per_supplier_per_species, filter) | Greedy fill: cheapest first, respecting the cap. Reports species where the cap **can't** be met. |
| what_if(fx=…, freight=…, include_supplier=…, apply_conditions=[…]) | Reruns the normaliser and award on a copy and returns the difference against the baseline |
| price_spread() | Per line: min, max, spread % |
| compare_last_year(supplier?) | Comparison only on lines that have history |
| make_chart(spec) | Plotly JSON |
| export_award(…) | Builds the xlsx |
| draft_memo(…) | Builds the memo |

**Sandbox** (analyst/sandbox.py), for anything the tools don't cover. The model writes a pandas expression or short snippet, which runs with:

- only pd, np and read-only copies of the tables;
- no imports, dunder access, file or network access;
- a 5-second timeout;
- a result capped at 500 rows.

**Answer card:**

- headline;
- body text;
- optional table and chart;
- a **trust note** (e.g. "Relies on 5 inferred values and 0 unconfirmed values");
- a **"How I got this"** section listing each tool call and its arguments, or the code, plus the rows used;
- actions: Add to award / Export / Show chart.

**Analyst system prompt rules:**

- Use tools for every number.
- Never state a number that didn't come from a tool result.
- Never guess illegible or flagged values; name them.
- Say "not in this RFx" for anything unknown.
- Mention which suppliers or lines were excluded, and why.

### 7.10 Award and export (Award screen)

- **Award memo** (the LLM writes the text from tool results only):
  - recommendation;
  - total spend;
  - change against last year on lines that have history;
  - award table by species;
  - risks (lines with no eligible supplier, unknown suppliers, expired certificates, unconfirmed values);
  - assumptions;
  - number of logged decisions.
- **Exports:**
  - award.xlsx with tabs Award, Comparison, Assumptions, Open flags, Eligibility, Audit log;
  - memo.pdf.

## 8. Data model (SQLite)

| Table | Key fields |
| :-- | :-- |
| rfx | id, status (drafting / sent / closed), current_version, created_at |
| rfx_version | rfx_id, version, draft_json, created_at, created_by, cause (proposal_id / restore / seed) |
| section_state | rfx_id, section_key, status, signed_by, signed_at, last_check_json |
| change_proposal | id, rfx_id, chat_turn_id, section_key, op, target, before_json, after_json, reason, origin, risk, status (pending / accepted / edited / rejected / held / failed), error, decided_at |
| copilot_question | id, rfx_id, chat_turn_id, question, options_json, answer, answered_at |
| chat_turn | id, thread (copilot / analyst), role, content, tool_calls_json, created_at |
| supplier | id, name, country, email |
| document | id, supplier_id, filename, kind, sha256, path, received_at, status |
| extracted_item | id, document_id, fields_json, raw_text, locator_json, confidence, legibility, matched_line_id, match_reason, match_confidence |
| normalized_quote | id, item_id, supplier_id, line_id, eur_kg_net_dap, steps_json, status (auto / confirmed / edited / inferred / illegible / excluded / ask_supplier) |
| flag | id, entity_type, entity_id, code, severity, message, evidence_json, resolved |
| qa_answer | supplier_id, q_id, answer, raw_text, locator_json, result (pass / fail / unknown) |
| certificate | supplier_id, scheme, grade, valid_until, document_id |
| eligibility | supplier_id, status, blocked_lines_json, reasons_json, overridden_by, override_reason |
| assumption | key, value_json, updated_at |
| audit_log | id, ts, actor (buyer / agent:copilot / agent:extractor / agent:analyst / system), action, entity, before_json, after_json, reason |

## 9. API (FastAPI)

| Method and path | Purpose |
| :-- | :-- |
| POST /api/rfx · POST /api/rfx/{id}/seed-reference | Create an RFx; load the reference draft |
| GET /api/rfx/{id} | Draft, section states, pending proposals |
| POST /api/rfx/{id}/copilot/messages (SSE response) | Chat with the co-pilot |
| POST /api/proposals/{id}/accept, /edit (body: value), /reject | Decide on one proposal |
| POST /api/rfx/{id}/proposals/accept-visible (body: ids) | Accept all shown |
| POST /api/rfx/{id}/questions/{qid}/answer | Answer a co-pilot question |
| POST /api/rfx/{id}/sections/{key}/signoff, /reopen | Section sign-off |
| GET /api/rfx/{id}/versions · POST /api/rfx/{id}/versions/{v}/restore | Version history |
| GET /api/rfx/{id}/preview/rfq.pdf, /template.xlsx · POST /api/rfx/{id}/send | Pre-send preview and send |
| POST /api/inbox/simulate · POST /api/inbox/upload · GET /api/events (SSE) | Stubbed inbox and live events |
| POST /api/documents/{id}/extract?live=true | (Re-)run extraction |
| GET /api/review · POST /api/review/{flag_id}/resolve | Review queue |
| GET /api/comparison · PUT /api/assumptions | Comparison grid and assumptions |
| POST /api/analyst/messages (SSE response) | Ask screen |
| GET /api/award/export.xlsx, /memo.pdf | Award exports |
| GET /api/audit · POST /api/admin/reset | Audit log; demo reset |

**SSE event types:**

- agent_status
- token
- proposal_created
- question_created
- doc_received
- extract_step
- flag_created
- answer_card
- error

## 10. Non-functional requirements

- **Latency:** co-pilot's first token under 3 seconds; cached extraction of a document under 1 second; live extraction of all 5 documents under 90 seconds; analyst answer under 15 seconds.
- **Reliability:**
  - LLM calls retry with backoff, then fall back to LLM_FALLBACK;
  - every agent failure shows a friendly error card with Retry;
  - the app never shows a half-applied draft.
- **Security:** API keys only in env; the sandbox is locked down as in §7.9; uploads limited to 20 MB and to the file types xlsx, pdf, docx, jpg, png, eml.
- **Accessibility:** follow the HTML's tokens; WCAG AA contrast; status is never shown by colour alone.
- **Observability:** every LLM call is logged with model, tokens, latency and prompt_version (in the DB or a jsonl file).

## 11. Evaluation: questions the demo must pass without hardcoding

Reference answers are for **checking the output only**, never for prompts or code. Put them in tests/test_analyst_e2e.py, marked @pytest.mark.llm.

| # | Question | Expected result |
| :-- | :-- | :-- |
| 1 | Who didn't quote everything? Which lines have fewer than 3 quotes? | Lines quoted: S1 16, S2 15, S3 19, S4 27, S5 8. Fewer than 3 quotes: L23–L28, L30. |
| 2 | Show me everything you weren't sure about. | L28 S4 illegible; S5 inferred lines and freight ambiguity; S2 glaze adjustments; S1 2% rebate and S2 3% discount as conditions; S4 certificate contradiction |
| 3 | Why is Pacific Rim vannamei 21/25 €8.93 when they quoted $3.74? | The conversion trail from §7.5 |
| 4 | Cheapest per line, only suppliers who cleared the quality questionnaire | ≈ €6.91M; S1 13 lines, S2 9, S3 6; L23–L24 uncovered |
| 5 | Cost of keeping Baltic Blue out? | ≈ €6.86M if included, so ≈ €48k/yr |
| 6 | Max 60% of any species per supplier | Split shown; cap can't be met for salmon (S1 only) or hake (S3 only) |
| 7 | Chart price spread; where to negotiate? | Top: L17 ~17%, L09 ~11%, L23 ~10% |
| 8 | EUR/USD 1.10? | L14–L16 move to S1; L20, L26, L30 move to S3; L21, L25, L29 stay with S2 |
| 9 | Is the 3% early-PO discount worth it? | Eligible shrimp L20–L21 ≈ €17k/yr; requires a PO by 30 Sep; 30% advance payment |
| 10 | Draft the award memo and export it | Memo and xlsx with assumptions and open flags |
| T1 | Oceanis hake fillet price? | Refuses to give a number; offers the crop and an ask-supplier draft |
| T2 | Cheapest for king crab? | "Not in this RFx" |
| T3 | Cheapest per line, ignore quality | ≈ €7.02M, with a warning about Oceanis (4 winning lines) and Baltic Blue (5) |

**Extraction eval** (scripts/score_extraction.py): all 85 cells.

- **Pass bar:** 0 silently wrong values (off by more than 1% and not flagged), with S4 L28 flagged as illegible.
- **Target:** at least 90% exact.

## 12. Risks

| Risk | Mitigation |
| :-- | :-- |
| Vision misreads a digit on the photo | Confidence score, peer/last-year outlier flags, image crop shown in review |
| Pass B matches an item to the wrong line | match_reason shown; low match confidence goes to review |
| Co-pilot proposes a malformed patch | Schema validation before applying; error sent back to the agent |
| Sandbox code is wrong | Fixed tools tried first; code shown; result shape checked; one retry |
| Live-demo API outage | Cache, fallback model, pre-recorded video |

## 13. Build order (3 days) and definition of done

1. **Day 1 AM: foundations.**
   - Repo scaffold, config, llm.py (with a tool loop, JSON-schema output and images), DB models, seed script.
   - Split design/ux.html into templates and static tokens; app shell and navigation.
   - Deploy a hello-world to Render.
2. **Day 1 PM: extraction and conversion.**
   - Ingestion router for all 5 formats; extraction passes A and B; cache.
   - Normaliser, plus **unit tests against the answer key**.
   - Scoring script.
3. **Day 2 AM: checks and comparison.**
   - Rules, auditor, eligibility.
   - Review queue; comparison grid and popover; assumptions panel.
4. **Day 2 PM: agents.**
   - Analyst agent (tools, sandbox, answer cards, charts, exports).
   - Co-pilot backend: schema, tools, proposals, apply, checks, risk classifier, versions. Plus tests for every acceptance criterion in §7.2.
5. **Day 3 AM: co-pilot UI and flow.**
   - Co-pilot UI: tracked-change cards, sign-off and lock, held banner, custom sections, version restore, pre-send preview, send.
   - Stubbed inbox simulation with SSE; activity drawer; reset demo.
6. **Day 3 PM: hardening.**
   - Error and empty states; run the §11 eval; fix what fails; write the README.

**Definition of done:**

- The flow Draft → Send → Inbox → Review → Compare → Ask → Award works end to end on the deployed URL.
- pytest passes, except tests marked llm, which must pass on a manual run.
- Extraction eval meets the pass bar.
- No hardcoded answers: grep for the reference numbers finds nothing in app/.
- README explains how to set up, set env vars, run, reset, and score.

**Cut order if late:**

1. version restore;
2. "accept all";
3. document preview highlights;
4. charts (tables are enough);
5. LLM auditor (keep the rule-based certificate expiry check).

**Never cut:**

- real extraction;
- the normaliser trail;
- the review queue;
- the co-pilot's propose → approve → sign-off gate;
- analyst tools with "How I got this".

## 14. Decisions log

| Decision | Choice |
| :-- | :-- |
| Comparison basis | EUR/kg net weight, DAP Boulogne |
| Who calculates | Python only; the LLM never produces displayed numbers |
| Co-pilot edits | Proposes only; buyer accepts, edits or rejects; section sign-off locks the section |
| Co-pilot inputs | Buyer chat only (no uploads, templates or supplier directory in this version) |
| Co-pilot's own ideas | Allowed, labelled "Suggested", never pre-accepted |
| Accept all | Skips money and eligibility changes |
| Second approver | No |
| Restoring a version | Reopens the affected sections |
| After sending | RFx is read-only |
| Eligibility | 4 states: eligible / conditional / not eligible / unknown |
| Conditional discounts | Shown, applied only on request |
| Frontend | FastAPI + Vikash's HTML; deploy on Render |
| LLM | Swappable through LiteLLM |
