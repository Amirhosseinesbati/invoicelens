"""Run the full offline DEMO workflow in an isolated DB, then score its outputs.

The generator's answer file is opened only by the final evaluator process,
after ingestion and prediction export have finished.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evals" / "results"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "generated" / "invoicelens" / "manifest.json",
    )
    parser.add_argument(
        "--api-python",
        type=Path,
        default=ROOT
        / "apps"
        / "api"
        / ".venv"
        / ("Scripts/python.exe" if os.name == "nt" else "bin/python"),
    )
    parser.add_argument(
        "--database", type=Path, default=RESULTS / "invoicelens-eval.db"
    )
    parser.add_argument(
        "--skip-processing",
        action="store_true",
        help="Score an already processed evaluation database",
    )
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="Queue all sources without processing; use process_queued.py in bounded batches",
    )
    args = parser.parse_args()
    if args.skip_processing and args.seed_only:
        parser.error("--skip-processing and --seed-only cannot be combined")
    manifest = args.manifest.resolve()
    database = args.database.resolve()
    # Preserve virtual-environment launcher symlinks: resolving them to the base
    # interpreter drops the environment's installed site-packages on POSIX.
    api_python = args.api_python.absolute()
    if not manifest.is_file():
        parser.error(
            f"Public manifest missing: {manifest}; run the full generator first"
        )
    if not api_python.is_file():
        parser.error(
            f"API Python missing: {api_python}; install backend dependencies first"
        )
    entries = json.loads(manifest.read_text(encoding="utf-8"))["documents"]
    RESULTS.mkdir(parents=True, exist_ok=True)
    temporary_root = RESULTS / "tmp"
    temporary_root.mkdir(exist_ok=True)
    environment = os.environ.copy()
    environment.update(
        {
            "INVOICELENS_MODE": "DEMO",
            "INVOICELENS_DATABASE_URL": f"sqlite:///{database.as_posix()}",
            "INVOICELENS_STORAGE_ROOT": str(RESULTS / "storage"),
            "INVOICELENS_CHECKPOINT_PATH": str(RESULTS / "graph-checkpoints.sqlite"),
            "INVOICELENS_SECRET_KEY": "isolated-evaluation-demo-only-secret",
            "INVOICELENS_AUTO_WORKER": "false",
            "TEMP": str(temporary_root),
            "TMP": str(temporary_root),
            "TMPDIR": str(temporary_root),
            "PYTHONPATH": str(ROOT / "apps" / "api" / "src")
            + (
                os.pathsep + environment["PYTHONPATH"]
                if environment.get("PYTHONPATH")
                else ""
            ),
        }
    )
    if not args.skip_processing:
        action = "Queueing" if args.seed_only else "Processing"
        print(
            f"{action} {len(entries)} public source documents with isolated DEMO database",
            flush=True,
        )
        subprocess.run(
            [
                str(api_python),
                "-m",
                "invoicelens.seed",
                "--manifest",
                str(manifest),
                "--reset",
                "--process-first",
                "0" if args.seed_only else str(len(entries)),
            ],
            cwd=ROOT,
            env=environment,
            check=True,
        )
    if args.seed_only:
        print(
            f"Queued {len(entries)} synthetic sources; process them in bounded batches before scoring",
            flush=True,
        )
        return
    prediction_file = RESULTS / "demo_predictions.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "evals" / "export_demo_predictions.py"),
            "--manifest",
            str(manifest),
            "--database",
            str(database),
            "--output",
            str(prediction_file),
        ],
        cwd=ROOT,
        env=environment,
        check=True,
    )
    # The prediction export is complete. Only this final command opens private truth.
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "evals" / "runner.py"),
            "--predictions",
            str(prediction_file),
        ],
        cwd=ROOT,
        env=environment,
        check=True,
    )


if __name__ == "__main__":
    main()
