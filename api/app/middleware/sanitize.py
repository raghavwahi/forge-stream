"""
Input sanitization utilities for common attack patterns.

These are standalone utility functions — not middleware.
Call them from the router/service layer for user-supplied string inputs.
"""
from __future__ import annotations

import unicodedata
from urllib.parse import urlparse


def sanitize_string(value: str, max_length: int = 10_000) -> str:
    """
    Basic string sanitization:
    - Reject non-string input with TypeError
    - Remove null bytes (can cause path traversal / injection issues)
    - Normalize to NFKC unicode form
    - Truncate to max_length characters
    """
    if not isinstance(value, str):
        raise TypeError(f"Expected str, got {type(value).__name__}")
    # Strip null bytes
    value = value.replace("\x00", "")
    # Normalize unicode
    value = unicodedata.normalize("NFKC", value)
    # Truncate
    return value[:max_length]


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal attacks:
    - Strip null bytes
    - Normalize backslashes to forward slashes
    - Split on path separators, drop empty parts and directory-traversal
      components (``..`` and ``.``)
    - Rejoin remaining parts with forward slashes

    Examples:
        ``../../etc/passwd``  →  ``etc/passwd``
        ``../secret.txt``     →  ``secret.txt``
        ``/absolute/path``    →  ``absolute/path``
        ``/./etc/./passwd``   →  ``etc/passwd``
        ``normal.txt``        →  ``normal.txt``
    """
    # Strip null bytes
    filename = filename.replace("\x00", "")
    # Normalize backslashes to forward slashes
    filename = filename.replace("\\", "/")
    # Split, discard traversal components (.. and .) and empty segments
    parts = [p for p in filename.split("/") if p and p not in ("..", ".")]
    return "/".join(parts) or "unnamed"


def is_safe_url(url: str, allowed_hosts: frozenset[str]) -> bool:
    """
    Validate that a URL is safe for redirects (prevents open redirect attacks).

    Rules:
    - Relative URLs are only considered safe when they have **no scheme**
      and **no host** (both ``scheme`` and ``netloc`` are empty).
    - For absolute or scheme-relative URLs:
      - Only ``http`` and ``https`` schemes are permitted (when a scheme is
        present).
      - The URL's hostname must be non-empty and in the provided allow-list.
      - Comparison is case-insensitive; port info in ``allowed_hosts`` entries
        is stripped before comparison.
    """
    try:
        parsed = urlparse(url)
        scheme = (parsed.scheme or "").lower()
        netloc = parsed.netloc or ""

        # Strictly relative URL (no scheme, no host) — safe
        if not scheme and not netloc:
            return True

        # If a scheme is present it must be http or https
        if scheme and scheme not in ("http", "https"):
            return False

        # Require a resolvable hostname present in the allow-list.
        # parsed.hostname strips port and userinfo; it returns None for malformed URLs.
        hostname = parsed.hostname
        if not hostname:
            # Covers malformed absolute URLs like "http:evil.com" or scheme-only strings
            return False

        # Normalize allowed_hosts: strip optional port, casefold for comparison
        normalized_allowed = {h.split(":", 1)[0].casefold() for h in allowed_hosts}
        return hostname.casefold() in normalized_allowed
    except Exception:
        return False
