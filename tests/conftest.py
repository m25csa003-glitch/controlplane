import os

import pytest

API_KEYS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "CP_API_KEY", "CP_JUDGE_PROVIDER")


@pytest.fixture(autouse=True)
def no_api_calls(monkeypatch, request):
    """Tests never spend money.

    Once .env holds a real key, every test that reaches tier 2 starts making
    live judge calls - slow, billable, and non-deterministic. Keys are stripped
    for the whole suite; a test that genuinely needs the API asks for it with
    @pytest.mark.live and is skipped when no key is configured."""
    if request.node.get_closest_marker("live"):
        if not any(os.getenv(k) for k in API_KEYS[:3]):
            pytest.skip("no API key configured")
        return
    for key in API_KEYS:
        monkeypatch.delenv(key, raising=False)


def pytest_configure(config):
    config.addinivalue_line("markers", "live: hits a real provider API; needs a key")
