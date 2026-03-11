"""Shared test fixtures for the API test suite."""
from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set required env vars before app modules are imported at collection time.
# setdefault means the real JWT_SECRET_KEY from the environment is preserved
# when running against a live service; the fallback only applies in CI/unit mode.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-ci-only")

# Stub out optional heavy dependencies that are not installed in the CI
# test environment so that importing app.main succeeds without them.
# setdefault is intentional: if the real packages are installed they are used
# as-is; the MagicMock stub only activates when they are absent.
for _mod in (
    "langchain_core",
    "langchain_core.messages",
    "langchain_core.output_parsers",
    "langchain_openai",
):
    sys.modules.setdefault(_mod, MagicMock())


@pytest.fixture(scope="session", autouse=True)
def _patch_external_connections():
    """Patch DB and Redis connections so tests run without live services.

    The TestClient is used at module level without a context manager, so the
    lifespan never runs and app.state is empty.  Inject lightweight async mocks
    directly onto app.state so that dependency-injection in every request
    succeeds without hitting a real database or Redis server.
    """
    from app.main import app  # imported here to respect sys.modules stubs above

    mock_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.incr.return_value = 1  # keeps rate-limit counter below threshold
    mock_email = MagicMock()
    mock_github = MagicMock()

    with (
        patch.object(app.state, "db_provider", mock_db, create=True),
        patch.object(app.state, "redis_provider", mock_redis, create=True),
        patch.object(app.state, "email_provider", mock_email, create=True),
        patch.object(app.state, "github_provider", mock_github, create=True),
    ):
        yield
