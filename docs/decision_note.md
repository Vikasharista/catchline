# Decision Note: What I Built, What I Left Out

Aerchain take-home · Vikash Kumar · Multi-species frozen fish RFx, 5 suppliers × 30 lines, ~€6.9M annual spend

## The problem as I framed it

Reading the quotes is the easy part. Making them comparable is where money is lost. In seafood, $3.74/lb of 20%-glazed shrimp is actually more expensive than €8.76/kg of net-weight shrimp. A buyer who extracts the numbers perfectly but ignores glaze or freight terms still makes the wrong award. So I built the product around one rule: every price becomes EUR per kg of net weight, delivered to Boulogne, and every step of that conversion is visible.

## Key decisions and why

- The model reads, Python calculates. The model extracts, matches lines and reasons. All FX, unit, glaze and freight maths is deterministic code, so a buyer never has to trust arithmetic done by a language model.
- Uncertain values are not guessed. The stained cell on the photo is shown as "Illegible, ask the supplier", not filled with a plausible number. With €7M at stake, a visible gap is better than a silent error.
- Three states, not two: a supplier is eligible, not eligible, or unknown. Baltic Blue never sent a questionnaire, which is different from failing it. Excluding them costs about €48k, and the buyer should see that trade-off.
- Conditional terms are shown, not applied. The 3% discount in a footnote and the 2% volume rebate sit next to the price. They affect rankings only when the buyer accepts the condition.
- The analyst uses both fixed tools and generated code. Fixed tools give reliable answers to common questions (split award, quality filter, FX what-if). A read-only pandas sandbox covers the rest, and the tool calls or code are always shown.
- Extraction is scored against an answer key inside the app. I created ground truth for all 85 price cells. The target is zero silent errors, not full automation.
- Swappable model, stubbed email. LiteLLM keeps the model a config setting. Email is a folder, as the brief allowed. Everything with AI in it is real.

## Deliberately left out

- Real email/SMTP, supplier portal, authentication and user roles: this is plumbing, not the hard problem.
- Import duty and trade-agreement tariffs (EVFTA, GSP) and live FX feeds: I used fixed reference tables, which the buyer can edit.
- Negotiation rounds, e-auctions and supplier follow-up automation. The system drafts an "ask supplier" email but does not send it.
- Multi-currency hedging, payment-term NPV and capacity-constrained optimisation: the split-award tool handles simple caps only (for example, max 60% per supplier per species).
- Spec-level quality scoring (grade, fillet defects, yield). The questionnaire is checked against rules, not scored.

## Where I think the more interesting problem is

Comparability should be designed into the RFx, not fixed after the replies arrive. Most of the mess came from things the buyer could have fixed up front: net or gross weight, glaze cap, delivery term, pack-size basis. A co-pilot that insists on these at drafting time, and replies to non-compliant quotes within minutes ("you quoted per lb on glazed weight; please confirm net €/kg"), removes a whole category of errors. The second insight: qualification decided the award more than price did. After the quality filter, black tiger shrimp had no eligible supplier at all. That signal matters more than a 2% price difference, and it points to a supplier-development problem, not just an RFx tool.

## What I would measure

| Metric | Target |
| :-- | :-- |
| Share of price cells extracted with no human edit, and silent-error rate | >85% auto, 0 silent errors |
| Time from last reply received to award decision | 4 days → under half a day |
| Share of analyst answers the buyer used in an award memo | Trust indicator: more than 60% |
