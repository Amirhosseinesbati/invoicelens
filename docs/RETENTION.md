# Workspace retention maintenance

The CLI `python -m invoicelens.retention` deletes old document records and their local source/export files in **one named workspace**. Page previews are generated from the source on request and are not stored separately; extracted page text and evidence are database rows. LangGraph checkpoints are deleted by exact `workspace:document-id` thread. Users, vendor master records, and other workspaces remain intact. The tool selects a document only when its last recorded activity (upload/update, extraction, review, job event, approval, or export) is before the specified UTC date. Purchase orders still referenced by retained match proposals are held back.

The command is read-only by default. `--apply` requires `--offline-confirmed`, which is an **operator assertion**: the CLI cannot prove that no other API or worker process is running. Stop every API/worker replica and prevent new uploads before applying a plan. The command also refuses a workspace with a job marked `processing`. Back up the matching database and storage volume first, agree the cutoff and any legal holds, and inspect every selected document ID and storage key in the dry-run output.

For a Compose installation, leave `db` running but stop `api`, then run the same command once to preview and once to apply:

```bash
docker compose stop api
docker compose run --rm --no-deps api python -m invoicelens.retention --workspace customer-slug --before 2026-01-01
docker compose run --rm --no-deps api python -m invoicelens.retention --workspace customer-slug --before 2026-01-01 --apply --offline-confirmed
docker compose up -d api
```

`--before 2026-01-01` means activity must be strictly earlier than 2026-01-01 00:00 UTC. Inspect the JSON output for `document_ids`, `storage_keys`, `blocked_purchase_order_ids`, and `processing_job_count`. No file is removed by the preview command. Apply writes a journal under the configured storage volume's sibling `retention-journals` directory before deleting database rows. It then deletes exact checkpoint threads and exact workspace file paths. It never recursively deletes a workspace folder. The journal records identifiers and storage keys, not source content, and must be protected and rotated under the customer's metadata retention policy.

If apply is interrupted, keep the API stopped and resume the **same** journal instead of starting a fresh deletion:

```bash
docker compose run --rm --no-deps api python -m invoicelens.retention --workspace customer-slug --resume-journal /app/data/retention-journals/JOURNAL.json --apply --offline-confirmed
```

The journal's workspace, database fingerprint, and storage root must match the current configuration. Database, checkpoint, and file phases are idempotent. A schema change that adds an unreviewed workspace or document table blocks the command until the deletion inventory is updated and tested. Check the journal's `state: complete`, document absence in the workbench, and absence of the selected source/export files before restarting service.

This is an **offline operator maintenance control**, not a self-service deletion endpoint. It does not erase encrypted backups, application or proxy logs, provider-side content, optional LangSmith traces, the generated synthetic corpus, or user/vendor master data. Configure and verify deletion/redaction schedules for those stores separately; keep source text and secrets out of logs and tracing by default. No purge of customer data has been run as part of repository verification. The automated retention test uses only disposable isolated SQLite, storage, and checkpoint fixtures on D:.
