# InvoiceLens product scope

InvoiceLens is an independent portfolio project for **Harbor Industrial**, a fictional B2B equipment distributor. It is a self-hostable document operations pilot. The value proposition is faster review of invoice and purchase-order data with source evidence and explicit exceptions. It does not provide audit certification or promise recovered revenue.

## Users and decisions

- **Operator:** uploads documents, compares source pages with extracted values, corrects fields, resolves findings, and requests approval.
- **Admin:** manages installation configuration and users and can approve and export a version.
- **Viewer:** inspects documents and workload without altering financial records.

The workbench treats a document as a versioned record. Source files, extraction output, corrections, validation findings, review decisions, and approval are separate facts. Approval is bound to one exact version. A later edit requires fresh validation and approval before export.

## v1 journey

1. Upload PDF, PNG, or JPEG files in a batch. See per-file states and page progress. A duplicate source is identified within its workspace.
2. Extract native text or OCR page content, classify invoice, credit note, or purchase order, and produce typed fields with page evidence when available.
3. Normalize dates and amounts, validate line and header arithmetic, and compare invoices with candidate purchase orders. Uncertain matches remain proposals for human review.
4. Review the source and data side by side; inspect discrepancies and formula breakdowns; correct values with an audit trail.
5. Approve the current version and download CSV, XLSX, or structured JSON. Repeated export requests for the same approved version and format resolve to the same export record.

## Modes

**DEMO** uses clearly labeled synthetic documents and local adapters. It sends no messages or payments and makes no paid model calls. **CONNECTED** uses the configured live model adapter and the same review and export workflow. A live adapter error is surfaced as an error; it is never presented as a successful demo result.

The only required live integration in v1 is the downloadable accounting-ready export. Direct posting to an accounting provider is a later customer-specific extension.

## Release boundary

This repository is a commercial pilot starting point. Customer deployment still requires sample-layout evaluation, credentials, backup/restore rehearsal, access and retention configuration, operator training, and a live model smoke test within an approved spending limit. Actual completed checks and limits are recorded in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) and [HANDOVER.md](HANDOVER.md).
