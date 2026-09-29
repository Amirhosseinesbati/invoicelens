"""Generate the local synthetic documents, then ingest through the real API seed path.

This wrapper never reads evaluator ground truth. It passes only the public
manifest to ``invoicelens.seed`` so demo processing uses normal ingestion.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=("fast", "full"), default="fast")
    parser.add_argument("--manifest", type=Path, help="Use an existing public manifest")
    parser.add_argument("--regenerate", action="store_true", help="Regenerate deterministic source documents")
    parser.add_argument("--generate-only", action="store_true", help="Skip backend ingestion")
    args = parser.parse_args()
    output = ROOT / "generated" / ("invoicelens-fast" if args.preset == "fast" else "invoicelens")
    manifest = (args.manifest or output / "manifest.json").resolve()
    if not args.manifest:
        valid = False
        if manifest.exists():
            metadata = json.loads(manifest.read_text(encoding="utf-8"))
            valid = bool(metadata.get("documents")) and all(
                (manifest.parent / item["path"]).is_file() for item in metadata["documents"]
            )
        if args.regenerate or not valid:
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "generate_dataset.py"), "--preset", args.preset, "--output", str(output)],
                check=True,
                cwd=ROOT,
            )
    if not manifest.is_file():
        parser.error(f"Manifest not found: {manifest}")
    if args.generate_only:
        print(f"Generated public manifest: {manifest}")
        return
    environment = os.environ.copy()
    source_path = str(ROOT / "apps" / "api" / "src")
    environment["PYTHONPATH"] = source_path + (os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
    subprocess.run(
        [sys.executable, "-m", "invoicelens.seed", "--manifest", str(manifest)],
        check=True,
        cwd=ROOT,
        env=environment,
    )


if __name__ == "__main__":
    main()
