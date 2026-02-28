"""Tests for api/scripts/init_admin.py (unit-level, no live DB)."""

from __future__ import annotations

import string
from unittest.mock import MagicMock, patch

from scripts.init_admin import _generate_password, _hash_password, init_admin

# ── Password generation ────────────────────────────────────────────

def test_generate_password_length():
    pwd = _generate_password(32)
    assert len(pwd) == 32


def test_generate_password_default_length():
    pwd = _generate_password()
    assert len(pwd) == 24


def test_generate_password_characters():
    allowed = set(string.ascii_letters + string.digits + string.punctuation)
    pwd = _generate_password(100)
    assert all(ch in allowed for ch in pwd)


# ── Password hashing ──────────────────────────────────────────────

def test_hash_password_format():
    h = _hash_password("secret")
    parts = h.split("$")
    assert len(parts) == 2
    salt, digest = parts
    assert len(salt) == 32       # 16 bytes → 32 hex chars
    assert len(digest) == 64     # SHA-256 → 64 hex chars


def test_hash_password_determinism():
    """Two calls with the same input produce different hashes (random salt)."""
    h1 = _hash_password("same")
    h2 = _hash_password("same")
    assert h1 != h2


# ── init_admin (mocked DB) ───────────────────────────────────────

@patch("scripts.init_admin.psycopg2")
def test_init_admin_creates_new_user(mock_pg):
    """When no admin row exists, an INSERT should be executed."""
    mock_conn = MagicMock()
    mock_pg.connect.return_value = mock_conn
    mock_cur = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    # No existing admin
    mock_cur.fetchone.return_value = None

    password = init_admin("postgresql://fake", "admin@test.local")

    assert len(password) == 24
    # The INSERT call should have been made
    calls = mock_cur.execute.call_args_list
    assert any("INSERT" in str(c) for c in calls)


@patch("scripts.init_admin.psycopg2")
def test_init_admin_rotates_existing_user(mock_pg):
    """When an admin row exists, an UPDATE should be executed."""
    mock_conn = MagicMock()
    mock_pg.connect.return_value = mock_conn
    mock_cur = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    # Existing admin
    mock_cur.fetchone.return_value = ("some-uuid",)

    password = init_admin("postgresql://fake", "admin@test.local")

    assert len(password) == 24
    calls = mock_cur.execute.call_args_list
    assert any("UPDATE" in str(c) for c in calls)
