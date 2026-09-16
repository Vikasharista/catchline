# Fabricated dataset - RFQ-2026-FROZ-017 (multi-species frozen fish)

All companies, people, prices, FX rates and certificates are fictional, made for a product demo.

Buyer: Nordcap Seafood Processing SAS, Boulogne-sur-Mer (processor). 30 lines x 5 suppliers, 85 quoted cells.
Comparison basis: EUR/kg NET weight, DAP Boulogne.

| Folder | What |
|---|---|
| 01_buyer_rfx | The RFQ (PDF) and the response template the suppliers were asked to use (xlsx) |
| 02_supplier_replies | 5 replies, none in the template: Excel (NOK, own layout), PDF (USD/lb, glazed weight, footnote discount), Word (prices in paragraphs, per carton), angled phone photo (CIF, per 10 kg carton, coffee stain), one-paragraph email ("same as last year") |
| 03_attachments | Food-safety certificates (S4's has expired - contradicts its questionnaire) |
| 04_buyer_reference_data | FX rates, freight adders to DAP, last year's contract prices, award rules |
| 05_answer_key | Ground truth for every quote cell (native -> EUR/kg net DAP) and supplier qualification. Use it to score extraction; never feed it to the app. |

Ugly edges built in: partial coverage (8 to 27 of 30 lines), NOK and USD, USD per lb, 20% glaze on gross weight,
per-block / per-carton / per-master-carton units, 4 different Incoterms, decimal commas, French and Norwegian labels,
illegible cell (S4 line L28), "same as last year" references, conditional discounts (2% volume rebate, 3% early-PO),
phosphates on raw shrimp, expired certificate, a supplier who never answered the questionnaire.
