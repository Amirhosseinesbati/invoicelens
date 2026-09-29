"""Process one bounded batch from a previously seeded DEMO evaluation database.

Run each batch in a fresh capped container to release OCR temporary layers before
the next batch. This script uses only the public queued documents, not evaluator
truth, and exits nonzero if any selected job fails.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evals" / "results"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 40:
        parser.error("--limit must be between 1 and 40")
    database = args.database.absolute()
    if not database.is_file():
        parser.error(f"Seeded evaluation database missing: {database}")
    os.environ.update(
        {
            "INVOICELENS_MODE": "DEMO",
            "INVOICELENS_DATABASE_URL": f"sqlite:///{database.as_posix()}",
            "INVOICELENS_STORAGE_ROOT": str(RESULTS / "storage"),
            "INVOICELENS_CHECKPOINT_PATH": str(RESULTS / "graph-checkpoints.sqlite"),
            "INVOICELENS_SECRET_KEY": "isolated-evaluation-demo-only-secret",
            "INVOICELENS_AUTO_WORKER": "false",
            "TEMP": str(RESULTS / "tmp"),
            "TMP": str(RESULTS / "tmp"),
            "TMPDIR": str(RESULTS / "tmp"),
        }
    )
    sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

    from invoicelens.db import SessionLocal
    from invoicelens.models import Job
    from invoicelens.workflow import run_job
    from sqlalchemy import func, select

    with SessionLocal() as db:
        job_ids = db.scalars(
            select(Job.id)
            .where(Job.status == "queued")
            .order_by(Job.created_at, Job.id)
            .limit(args.limit)
        ).all()
    for job_id in job_ids:
        run_job(job_id)
    with SessionLocal() as db:
        statuses = dict(
            db.execute(
                select(Job.status, func.count(Job.id)).group_by(Job.status)
            ).all()
        )
        selected_failed = (
            db.scalar(
                select(func.count(Job.id)).where(
                    Job.id.in_(job_ids), Job.status != "complete"
                )
            )
            or 0
        )
    print(
        json.dumps(
            {
                "batch": len(job_ids),
                "statuses": statuses,
                "selected_incomplete": selected_failed,
            }
        )
    )
    if selected_failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
