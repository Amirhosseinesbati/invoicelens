import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_initial_migration_builds_schema(tmp_path):
    project_root = Path(__file__).resolve().parents[2]
    database = tmp_path / "fresh.db"
    environment = os.environ.copy()
    environment["INVOICELENS_DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "apps/api/alembic.ini",
            "upgrade",
            "head",
        ],
        cwd=project_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(database) as connection:
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert {
        "workspaces",
        "documents",
        "document_pages",
        "extraction_versions",
        "findings",
        "jobs",
        "alembic_version",
    } <= names
