"""Unit tests for sanitize utility functions."""
from __future__ import annotations

from app.middleware.sanitize import is_safe_url, sanitize_filename, sanitize_string


class TestSanitizeString:
    def test_removes_null_bytes(self):
        assert "\x00" not in sanitize_string("hel\x00lo")

    def test_nfkc_normalization(self):
        # ﬁ (U+FB01 LATIN SMALL LIGATURE FI) should become "fi"
        result = sanitize_string("\ufb01le")
        assert result == "file"

    def test_truncates_at_max_length(self):
        long_str = "a" * 20_000
        result = sanitize_string(long_str, max_length=100)
        assert len(result) == 100

    def test_empty_string_passthrough(self):
        assert sanitize_string("") == ""

    def test_normal_string_unchanged(self):
        s = "Hello, World!"
        assert sanitize_string(s) == s


class TestSanitizeFilename:
    def test_strips_path_traversal(self):
        result = sanitize_filename("../../etc/passwd")
        assert ".." not in result
        assert "etc/passwd" in result or "etcpasswd" in result

    def test_strips_leading_slash(self):
        result = sanitize_filename("/etc/passwd")
        assert not result.startswith("/")

    def test_strips_null_bytes(self):
        result = sanitize_filename("file\x00.txt")
        assert "\x00" not in result

    def test_normal_filename_unchanged(self):
        result = sanitize_filename("document.pdf")
        assert "document" in result

    def test_empty_string(self):
        assert sanitize_filename("") == ""


class TestIsSafeUrl:
    def test_allows_trusted_host(self):
        allowed = frozenset({"example.com"})
        assert is_safe_url("https://example.com/path", allowed) is True

    def test_blocks_untrusted_host(self):
        allowed = frozenset({"example.com"})
        assert is_safe_url("https://evil.com/path", allowed) is False

    def test_relative_url_allowed_for_empty_netloc(self):
        allowed = frozenset({"example.com"})
        # Relative paths have no netloc — treated as safe (no open redirect)
        assert is_safe_url("/relative/path", allowed) is True

    def test_blocks_data_url(self):
        allowed = frozenset({"example.com"})
        assert is_safe_url("data:text/html,<h1>XSS</h1>", allowed) is False

    def test_empty_url(self):
        allowed = frozenset({"example.com"})
        assert is_safe_url("", allowed) is True
