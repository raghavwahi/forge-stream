"""Tests for RequestValidationMiddleware and sanitization helpers."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.sanitize import is_safe_url, sanitize_filename, sanitize_string
from app.middleware.validation import _SECURITY_HEADERS, RequestValidationMiddleware

# ---------------------------------------------------------------------------
# Helpers – minimal app wired with the middleware under test
# ---------------------------------------------------------------------------


def _make_app(max_body_size_bytes: int = 10 * 1024 * 1024) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        RequestValidationMiddleware,
        max_body_size_bytes=max_body_size_bytes,
        allowed_content_types=frozenset(
            [
                "application/json",
                "application/x-www-form-urlencoded",
                "multipart/form-data",
            ]
        ),
    )

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    @app.post("/data")
    async def data():
        return {"ok": True}

    return app


client = TestClient(_make_app(), raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Security headers – present on every response
# ---------------------------------------------------------------------------


class TestSecurityHeaders:
    def test_headers_on_get(self):
        resp = client.get("/ping")
        for header in _SECURITY_HEADERS:
            assert header in resp.headers, f"Missing header: {header}"

    def test_x_frame_options_deny(self):
        resp = client.get("/ping")
        assert resp.headers["X-Frame-Options"] == "DENY"

    def test_headers_on_error_response(self):
        # 411 is returned before the handler runs, but headers must still be present
        resp = client.post("/data")
        for header in _SECURITY_HEADERS:
            assert header in resp.headers, f"Missing header on error response: {header}"


# ---------------------------------------------------------------------------
# Content-Length enforcement
# ---------------------------------------------------------------------------


class TestContentLength:
    def test_no_content_length_returns_411(self):
        import httpx

        # Use the raw transport to send a request without Content-Length
        transport = client._transport
        req = httpx.Request(
            "POST",
            "http://testserver/data",
            headers={"Content-Type": "application/json"},
            content=b'{"key": "value"}',
        )
        # Remove the Content-Length header that httpx adds automatically
        req.headers.pop("content-length", None)
        resp = transport.handle_request(req)
        resp.read()
        assert resp.status_code == 411
        assert "Content-Length" in resp.json()["detail"]

    def test_body_too_large_returns_413(self):
        small_client = TestClient(
            _make_app(max_body_size_bytes=10), raise_server_exceptions=False
        )
        resp = small_client.post(
            "/data",
            content=b"x" * 100,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 413
        assert "too large" in resp.json()["detail"].lower()

    def test_413_response_has_security_headers(self):
        small_client = TestClient(
            _make_app(max_body_size_bytes=10), raise_server_exceptions=False
        )
        resp = small_client.post(
            "/data",
            content=b"x" * 100,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 413
        for header in _SECURITY_HEADERS:
            assert header in resp.headers, f"Missing header on 413: {header}"

    def test_negative_content_length_returns_400(self):
        import httpx

        transport = client._transport  # reuse the in-process transport
        req = httpx.Request(
            "POST",
            "http://testserver/data",
            headers={"Content-Type": "application/json", "Content-Length": "-1"},
        )
        resp = transport.handle_request(req)
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Content-Type enforcement
# ---------------------------------------------------------------------------


class TestContentType:
    def test_unsupported_content_type_returns_415(self):
        resp = client.post(
            "/data",
            content=b"<root/>",
            headers={"Content-Type": "text/xml"},
        )
        assert resp.status_code == 415
        assert "Unsupported" in resp.json()["detail"]

    def test_415_response_has_security_headers(self):
        resp = client.post(
            "/data",
            content=b"<root/>",
            headers={"Content-Type": "text/xml"},
        )
        assert resp.status_code == 415
        for header in _SECURITY_HEADERS:
            assert header in resp.headers, f"Missing header on 415: {header}"

    def test_missing_content_type_with_body_returns_415(self):
        import httpx

        transport = client._transport
        body = b'{"key": "value"}'
        req = httpx.Request(
            "POST",
            "http://testserver/data",
            headers={"Content-Length": str(len(body))},
            content=body,
        )
        resp = transport.handle_request(req)
        assert resp.status_code == 415

    def test_valid_json_content_type_passes(self):
        resp = client.post(
            "/data",
            json={"key": "value"},
        )
        assert resp.status_code == 200

    def test_no_body_post_skips_content_type_check(self):
        # Content-Length: 0 means no body — Content-Type check should be skipped
        import httpx

        transport = client._transport
        req = httpx.Request(
            "POST",
            "http://testserver/data",
            headers={"Content-Length": "0"},
        )
        resp = transport.handle_request(req)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# sanitize_string
# ---------------------------------------------------------------------------


class TestSanitizeString:
    def test_removes_null_bytes(self):
        assert sanitize_string("hello\x00world") == "helloworld"

    def test_nfkc_normalization(self):
        # ﬁ (U+FB01 LATIN SMALL LIGATURE FI) should normalize to "fi"
        assert sanitize_string("\ufb01le") == "file"

    def test_truncation(self):
        assert sanitize_string("abcdef", max_length=3) == "abc"

    def test_non_string_raises(self):
        with pytest.raises(TypeError):
            sanitize_string(123)  # type: ignore[arg-type]

    def test_empty_string(self):
        assert sanitize_string("") == ""


# ---------------------------------------------------------------------------
# sanitize_filename
# ---------------------------------------------------------------------------


class TestSanitizeFilename:
    def test_traversal_sequences_stripped(self):
        assert sanitize_filename("../../etc/passwd") == "etc/passwd"

    def test_single_traversal(self):
        assert sanitize_filename("../secret.txt") == "secret.txt"

    def test_leading_slash_removed(self):
        assert sanitize_filename("/absolute/path") == "absolute/path"

    def test_backslash_normalized(self):
        assert sanitize_filename("..\\..\\etc\\passwd") == "etc/passwd"

    def test_null_bytes_stripped(self):
        result = sanitize_filename("file\x00name.txt")
        assert "\x00" not in result

    def test_normal_filename_unchanged(self):
        assert sanitize_filename("normal.txt") == "normal.txt"

    def test_empty_becomes_unnamed(self):
        assert sanitize_filename("") == "unnamed"

    def test_only_traversal_becomes_unnamed(self):
        assert sanitize_filename("../../..") == "unnamed"

    def test_dot_components_stripped(self):
        assert sanitize_filename("/./etc/./passwd") == "etc/passwd"


# ---------------------------------------------------------------------------
# is_safe_url
# ---------------------------------------------------------------------------


ALLOWED = frozenset({"app.example.com"})


class TestIsSafeUrl:
    def test_relative_url_safe(self):
        assert is_safe_url("/dashboard", ALLOWED) is True

    def test_relative_url_no_slash_safe(self):
        assert is_safe_url("dashboard", ALLOWED) is True

    def test_allowed_host_https_safe(self):
        assert is_safe_url("https://app.example.com/path", ALLOWED) is True

    def test_allowed_host_http_safe(self):
        assert is_safe_url("http://app.example.com/path", ALLOWED) is True

    def test_disallowed_host_unsafe(self):
        assert is_safe_url("https://evil.com/", ALLOWED) is False

    def test_javascript_scheme_unsafe(self):
        assert is_safe_url("javascript:alert(1)", ALLOWED) is False

    def test_data_scheme_unsafe(self):
        assert is_safe_url("data:text/html,<h1>hi</h1>", ALLOWED) is False

    def test_malformed_absolute_url_unsafe(self):
        # "http:evil.com" has scheme but no netloc
        assert is_safe_url("http:evil.com", ALLOWED) is False

    def test_case_insensitive_host(self):
        assert is_safe_url("https://APP.EXAMPLE.COM/path", ALLOWED) is True

    def test_host_with_port_allowed(self):
        allowed_with_port = frozenset({"app.example.com:443"})
        assert is_safe_url("https://app.example.com/path", allowed_with_port) is True

    def test_empty_url_safe(self):
        assert is_safe_url("", ALLOWED) is True

    def test_protocol_relative_url_disallowed_host(self):
        assert is_safe_url("//evil.com/path", ALLOWED) is False

    def test_protocol_relative_url_allowed_host(self):
        assert is_safe_url("//app.example.com/path", ALLOWED) is True
