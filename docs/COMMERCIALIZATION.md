# Commercialization guide

## Buyer and offer

The first buyer is a distributor or accounts-payable team that receives many supplier invoices and purchase orders and currently rekeys document data. Offer a customer-installed pilot that captures documents, exposes evidence and exceptions, and exports a reviewed accounting dataset. Price installation and customization to the customer's document layouts, export schema, security constraints, and operating volume; do not use the synthetic demo to claim savings or measured accuracy on customer data.

## Onboarding sequence

1. Agree on data residency, retention, users/roles, expected volumes, and a sample of permitted customer documents.
2. Deploy a separate installation for the customer with PostgreSQL, scoped file storage, HTTPS, strong secrets, backup and monitoring arrangements.
3. Configure the model provider ID, credentials, cost limit, OCR capability, currency policy, and supported locale/date formats. Keep credentials server-side.
4. Map customer vendor and PO identifiers and the target CSV/XLSX/JSON columns. Review an explicit set of ambiguous and cross-currency cases.
5. Run a held-out customer sample, inspect false positives/negatives and source evidence with an operator, and accept or adjust the rollout criteria.
6. Train operators on corrections, revalidation, approval, and export; rehearse restore and recovery before live use.

## Reusable modules

The document ingestion/validation boundary, typed extraction schema, evidence viewer, PO matching, approval/version guard, and export adapters can be reused in adjacent document products. Customer-specific templates and mappings belong in configuration or scoped adapters; the core arithmetic and approval rules stay shared.

## Operating costs

Estimate monthly costs with customer parameters rather than a fixed promise:

`monthly cost = hosting + storage_GB × storage_rate + OCR_pages × OCR_page_rate + model_input_tokens × input_rate + model_output_tokens × output_rate + support_hours × support_rate`.

Track native and scanned page counts separately. Model, OCR, storage, and hosting prices can change, so confirm current provider quotes before a commercial proposal. The local DEMO has no paid model/OCR call requirement.

## Supported boundary and limitations

v1 exports approved data as CSV, XLSX, and schema-versioned JSON. Direct accounting API posting is not in scope. Customer-specific tax rules, exchange-rate sourcing, invoice authority, and compliance certification require separate work. A deterministic synthetic score is only a development signal, not real-customer accuracy.

The direct PDF/OCR/generator license review and sources are in [DEPENDENCIES.md](DEPENDENCIES.md). The runtime uses pypdfium2 rather than AGPL/commercial PyMuPDF. Before redistribution, inspect the exact installed wheel, npm tree, Docker image packages, and any font/image assets, then retain all required notices. A complete transitive license audit remains a release gate; no third-party commercial rights are claimed here.
