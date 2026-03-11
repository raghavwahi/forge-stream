from pydantic import BaseModel


class InstallationInfo(BaseModel):
    id: int
    account_login: str
    account_type: str  # "User" | "Organization"
    html_url: str
    app_id: int


class InstallationTokenResponse(BaseModel):
    token: str
    expires_at: str  # ISO8601 datetime string


class GitHubAppStatusResponse(BaseModel):
    is_configured: bool
    app_id: str | None = None
    message: str
