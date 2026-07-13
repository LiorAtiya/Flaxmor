"""Shared test fixtures.

- `client`: a TestClient over a freshly-built app with a known test configuration.
  TestClient runs the lifespan (so app.state.http_client exists), and `respx`
  intercepts the outgoing httpx calls to the fake OpenAI upstream.
- Settings are cached (lru_cache), so every fixture clears the cache before
  and after to keep tests isolated.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app

TEST_API_KEY: str = "sk-test-key"
TEST_UPSTREAM_URL: str = "https://fake-openai.test/v1"


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """App client configured against the fake upstream, API key present."""
    monkeypatch.setenv("OPENAI_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("OPENAI_BASE_URL", TEST_UPSTREAM_URL)
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


@pytest.fixture()
def client_without_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """App client with NO API key configured — for readiness tests."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()
