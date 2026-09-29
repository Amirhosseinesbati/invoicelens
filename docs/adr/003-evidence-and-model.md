# ADR 003 — Evidence before confidence

Status: accepted.

The extractor keeps page text or OCR output and source coordinates separately from normalized values. Only coordinates returned by a real page extraction are shown as a bounding box. A vision-derived fact without coordinates can point to a page, but cannot invent a span. Quality indicators combine parse success, evidence presence, and deterministic rule violations; a model's self-reported confidence is not treated as calibrated accuracy. DEMO and CONNECTED adapters obey the same schema and error contract.
