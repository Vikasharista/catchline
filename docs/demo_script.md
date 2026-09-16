# Demo Script: Buyer Q&A Walkthrough

Recorded walkthrough (~8–9 min) + live-demo prep · Reference answers come from the dataset answer key (05_answer_key)

Kept here as the source for the §11 eval questions and the live-demo checklist. Not used in prompts or code — for tests and manual verification only.

## Recording structure

| Time | Segment | What to show |
| :-- | :-- | :-- |
| 0:00–0:45 | The pain | Five replies side by side: Excel (NOK), PDF on letterhead (USD/lb), Word paragraphs, angled photo, one-line email. "This is 4 days of retyping." |
| 0:45–2:00 | Co-pilot drafts the RFx | Buyer: "Annual frozen raw material contract, 30 lines, salmon to squid, delivered Boulogne." The co-pilot asks: net or gross weight? max glaze? certificate required? It generates the PDF and template, then Send (stubbed). |
| 2:00–3:15 | Extraction + review queue | Run extraction on all 5 replies. Show the accuracy card from the answer key, then go through the review queue: stained cell, "same as last year", glaze, expired certificate. |
| 3:15–8:00 | Buyer asks questions | Questions 1–9 below. Open "How I got this" at least twice. |
| 8:00–8:45 | Award + export | Question 10: draft the VP memo and export the Excel file with the assumptions tab. |

## The questions, in order

Each question tests something specific. The "Reference answer" is what the system should produce with the fabricated data. It is **not hardcoded**; it is here so you can check the output live.

| # | Buyer asks | Why it matters | Reference answer / expected behaviour |
| :-- | :-- | :-- | :-- |
| 1 | Who didn't quote everything, and which lines have fewer than 3 quotes? | Coverage before price | Lines quoted: Fjordline 16, Pacific Rim 15, Atlantico 19, Oceanis 27, Baltic Blue 8 (of 30). Fewer than 3 quotes: L23–L24 black tiger, L25–L26 tuna, L27–L28 hake, L30 squid rings. |
| 2 | Show me everything you weren't sure about. | Honesty about uncertainty | Oceanis L28 hake fillet illegible (not guessed). 5 Baltic Blue lines inferred from "same as last year", freight unclear. Pacific Rim glaze adjustment. 2 conditional discounts. Oceanis certificate contradiction. |
| 3 | Why is Pacific Rim's vannamei 21/25 €8.93 when they quoted $3.74? | Tracing a number to its source | $3.74/lb ÷ 0.4536 = $8.25/kg → ÷1.17 = €7.05 → ÷0.80 glaze = €8.81 → +€0.12 freight = **€8.93/kg net DAP**. Shows the PDF snippet and footnote. Ignoring glaze would have shown €7.17, falsely the cheapest. |
| 4 | What if we split it, cheapest per line, but only among suppliers who cleared the quality questionnaire? | The VP question from the brief | Eligible: Fjordline, Atlantico. Pacific Rim is eligible except raw shrimp (phosphates). Oceanis is excluded (certificate expired 31 Aug). Baltic Blue is unknown (no questionnaire). Result ≈ **€6.91M**; Fjordline 13 lines, Pacific Rim 9, Atlantico 6. **Black tiger L23–L24 has no eligible supplier** and is flagged. |
| 5 | What does it cost us to keep Baltic Blue out until they send their certificate? | Price of a policy choice | If Baltic Blue were eligible, total ≈ €6.86M, so waiting costs ≈ **€48k/yr** (mostly salmon). Suggests a follow-up email. |
| 6 | Apply our rule: max 60% of any species with one supplier. Show the split. | Constrained award | split_award tool with a cap. Cod, haddock, pollock, vannamei, tuna and squid are split across 2 eligible suppliers, with the extra cost compared with Q4. **The cap cannot be met for salmon (only Fjordline is eligible) or hake (only Atlantico)**, so the system flags this instead of forcing a split. |
| 7 | Chart the price spread per line: where is it worth negotiating? | A chart that supports a decision | Bar/range chart. Widest spreads: L17 vannamei 16/20 (~17%), L09 cod fillet (~11%), L23 black tiger (~10%). |
| 8 | If EUR/USD drops to 1.10, does the award change? | What-if on assumptions | Pacific Rim prices rise ~6%. Among eligible suppliers, pollock L14–L16 moves to Fjordline; cooked shrimp L20, tuna saku L26 and squid rings L30 move to Atlantico. L21, L25 and L29 stay with Pacific Rim. |
| 9 | Is Pacific Rim's 3% early-PO discount worth it? | Conditional terms | Applies to shrimp only; among eligible lines that means cooked L20–L21 ≈ **€17k/yr**, but it requires a PO by 30 Sep (the award date). Mentions the 30% advance payment. |
| 10 | Draft the award recommendation for my VP and export it. | The final output | A one-page memo: award by line, total, savings, risks (black tiger gap, Baltic Blue pending, Oceanis certificate), plus an Excel export with an assumptions tab and open flags. |

## Trap questions (for the live demo)

The interviewers will drive the live session. These questions check that the system refuses to guess:

| Buyer asks | Correct behaviour |
| :-- | :-- |
| "What's Oceanis' price for hake fillet?" | Illegible on the photo. No number given; offers the crop and a draft question to the supplier. |
| "Who's cheapest for king crab?" | Not in this RFx; no invented supplier or price. |
| "Just give me the cheapest per line, ignore quality." | Answers (≈ €7.02M across all 30 lines) but warns that 4 winning lines come from Oceanis, whose certificate has expired, and 5 from Baltic Blue, which has no questionnaire. |
| "Average salmon price across suppliers?" | Computes it and notes that 4 Baltic Blue salmon values are inferred from last year, not quoted. |
| "Is Fjordline cheaper than last year?" | Only cod H&G and haddock H&G have Fjordline history; says the comparison covers only those lines. |

## Live-demo checklist

- Warm the cache: run extraction once before the call, and keep "re-run live" ready to show it isn't faked.
- Have the fallback model configured in secrets. Keep the recorded video open in a tab.
- "Reset demo" button: restores the untouched dataset and clears overrides.
- Be ready to explain: why EUR/kg net DAP, why "unknown" differs from "fail", why conditional discounts aren't applied by default.
