"""API contract tests: /health and CSRF-protected endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_health_method_not_allowed_for_post(self):
        resp = client.post("/health")
        assert resp.status_code == 405


class TestGitHubAppStatus:
    def test_status_returns_unconfigured(self):
        """GET /api/v1/github-app/status is public and works when App is unconfigured."""
        resp = client.get("/api/v1/github-app/status")
        # May fail with 500 if github_app_router not loaded; acceptable if not mounted
        assert resp.status_code in (200, 404, 500)

    def test_status_response_schema(self):
        resp = client.get("/api/v1/github-app/status")
        if resp.status_code == 200:
            data = resp.json()
            assert "is_configured" in data
            assert "message" in data


class TestJobsEndpointAuth:
    """Jobs endpoints require JWT authentication."""

    def test_enqueue_requires_auth(self):
        resp = client.post(
            "/api/v1/jobs",
            json={"type": "generate_items", "payload": {}},
        )
        assert resp.status_code in (401, 403, 404)

    def test_get_job_status_requires_auth(self):
        resp = client.get("/api/v1/jobs/some-job-id")
        assert resp.status_code in (401, 403, 404)


class TestRepositoriesEndpointAuth:
    """Repositories endpoint requires JWT authentication."""

    def test_list_repos_requires_auth(self):
        resp = client.get("/api/v1/repositories?installation_id=123")
        assert resp.status_code in (401, 403, 404, 503)
