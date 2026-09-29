import pytest
from invoicelens.config import Settings


def test_connected_requires_real_session_secret():
    for secret in ("", "short", "demo-only-change-before-connected-mode"):
        with pytest.raises(ValueError, match="INVOICELENS_SECRET_KEY"):
            Settings(mode="CONNECTED", secret_key=secret).validate_runtime()
    Settings(mode="CONNECTED", secret_key="a" * 32).validate_runtime()


def test_model_output_bound():
    with pytest.raises(ValueError, match="OPENAI_MAX_OUTPUT_TOKENS"):
        Settings(openai_max_output_tokens=100).validate_runtime()
    Settings(openai_max_output_tokens=2048).validate_runtime()
