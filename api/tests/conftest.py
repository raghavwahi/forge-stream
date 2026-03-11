"""Pytest configuration: set minimum environment variables for testing.

These defaults allow the application to be imported without a real database or
external services. Individual tests override dependencies as needed.
"""

from __future__ import annotations

import os

# Set required environment variables before any app module is imported.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-only")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("REDIS_HOST", "localhost")
