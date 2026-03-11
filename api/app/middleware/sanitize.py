"""Sanitization utilities for strings, filenames, and URLs."""

from __future__ import annotations

import unicodedata
import urllib.parse


def sanitize_string(value: str, max_length: int | None = None) -> str:
    """Sanitize an arbitrary string.

    * Removes embedded null bytes.
    * Normalises Unicode to NFKC (converts ligatures, compatibility chars, etc.).
    * Optionally truncates to *max_length* characters.
    """
    if value == "":
        return value

    cleaned = value.replace("\x00", "")
    cleaned = unicodedata.normalize("NFKC", cleaned)

    if max_length is not None and max_length >= 0:
        cleaned = cleaned[:max_length]

    return cleaned


def sanitize_filename(value: str, max_length: int | None = None) -> str:
    """Sanitize a filename to mitigate path traversal and null-byte injection.

    * Strips null bytes.
    * Removes path traversal components (``..`` and ``.``).
    * Strips leading slashes so the result is always a relative path.
    * Optionally truncates to *max_length* characters.
    """
    if value == "":
        return value

    cleaned = value.replace("\x00", "")

    parts = []
    for segment in cleaned.replace("\\", "/").split("/"):
        if segment in ("", ".", ".."):
            continue
        parts.append(segment)

    safe = "/".join(parts)
    safe = safe.lstrip("/")

    if max_length is not None and max_length >= 0:
        safe = safe[:max_length]

    return safe


def is_safe_url(url: str, allowed_hosts: frozenset[str] | set[str]) -> bool:
    """Return ``True`` if *url* is safe to redirect to.

    Rules:
    * Empty URLs are treated as safe (no redirect).
    * Relative URLs (no scheme and no netloc) are treated as safe to avoid
      open redirects to external sites.
    * Absolute URLs must use HTTP or HTTPS and have a netloc present in
      *allowed_hosts*.
    * Non-HTTP(S) schemes (e.g. ``data:``) are rejected.
    """
    if url == "":
        return True

    parsed = urllib.parse.urlparse(url)

    if not parsed.scheme and not parsed.netloc:
        return True

    if parsed.scheme not in {"http", "https"}:
        return False

    return parsed.netloc in allowed_hosts
