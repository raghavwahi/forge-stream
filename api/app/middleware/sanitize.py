"""
Input sanitization utilities for common attack patterns.

These are standalone utility functions — not middleware.
Call them from the router/service layer for user-supplied string inputs.
"""
from __future__ import annotations

import re
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
    - Remove path separators (/ and \\)
    - Collapse directory-traversal sequences (..)
    - Allow only alphanumerics, hyphens, underscores, dots
    - Strip leading dots
    """
    # Remove directory separators and traversal sequences
    filename = filename.replace("/", "").replace("\\", "").replace("..", "")
    # Allow only safe characters
    filename = re.sub(r"[^\w\-.]", "", filename)
    # Remove leading dots (hidden file protection)
    filename = filename.lstrip(".")
    return filename or "unnamed"


def is_safe_url(url: str, allowed_hosts: frozenset[str]) -> bool:
    """
    Validate that a URL is safe for redirects (prevents open redirect attacks).

    Rules:
    - Relative URLs (no host) are always considered safe
    - Only http and https schemes are permitted
    - The URL's host must be in the provided allow-list
    """
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            # Relative URL — safe
            return True
        if parsed.scheme.lower() not in ("http", "https"):
            return False
        return parsed.netloc.lower() in allowed_hosts
    except Exception:
        return False
