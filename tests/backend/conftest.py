import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_temp_root = Path(__file__).resolve().parents[2] / "tmp"
try:
    _test_root = Path(tempfile.mkdtemp(prefix="invoicelens-backend-", dir=_temp_root))
    os.environ["TMP"] = str(_temp_root)
    os.environ["TEMP"] = str(_temp_root)
    tempfile.tempdir = str(_temp_root)
except PermissionError:
    _test_root = Path(tempfile.mkdtemp(prefix="invoicelens-backend-"))
os.environ["INVOICELENS_MODE"] = "DEMO"
os.environ["INVOICELENS_DATABASE_URL"] = (
    f"sqlite:///{(_test_root / 'test.db').as_posix()}"
)
os.environ["INVOICELENS_STORAGE_ROOT"] = str(_test_root / "uploads")
os.environ["INVOICELENS_CHECKPOINT_PATH"] = str(_test_root / "checkpoints.sqlite")
os.environ["INVOICELENS_AUTO_WORKER"] = "false"

from invoicelens.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def operator_headers(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "operator@example.com", "password": "DemoPass123!"},
    )
    assert response.status_code == 200, response.text
    return {}
