import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import JWTError

from app.config import Settings
from app.models.auth import (
    AuthResponse,
    GitHubAuthURLResponse,
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from app.providers.base import BaseCacheProvider, BaseEmailProvider
from app.providers.github import GitHubOAuthProvider
from app.repositories.oauth_account import OAuthAccountRepository
from app.repositories.password_reset import PasswordResetRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.security.jwt import JWTManager
from app.security.password import PasswordManager

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: RefreshTokenRepository,
        reset_repo: PasswordResetRepository,
        oauth_repo: OAuthAccountRepository,
        jwt_manager: JWTManager,
        password_manager: PasswordManager,
        email_provider: BaseEmailProvider,
        github_provider: GitHubOAuthProvider,
        cache_provider: BaseCacheProvider,
        settings: Settings,
    ) -> None:
        self._user_repo = user_repo
        self._token_repo = token_repo
        self._reset_repo = reset_repo
        self._oauth_repo = oauth_repo
        self._jwt = jwt_manager
        self._pwd = password_manager
        self._email = email_provider
        self._github = github_provider
        self._cache = cache_provider
        self._settings = settings

    async def signup(self, data: SignupRequest) -> AuthResponse:
        existing = await self._user_repo.find_by_email(data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to complete signup",
            )

        password_hash = self._pwd.hash(data.password)
        user = await self._user_repo.create(
            email=data.email,
            name=data.name,
            password_hash=password_hash,
        )
        tokens = await self._create_token_pair(str(user["id"]))
        return self._build_auth_response(user, tokens)

    async def login(self, data: LoginRequest) -> AuthResponse:
        user = await self._user_repo.find_by_email(data.email)
        if not user or not user.get("password_hash"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        if not self._pwd.verify(data.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        if not user["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account disabled",
            )

        if self._pwd.needs_rehash(user["password_hash"]):
            new_hash = self._pwd.hash(data.password)
            await self._user_repo.update_password(
                str(user["id"]), new_hash
            )

        tokens = await self._create_token_pair(str(user["id"]))
        return self._build_auth_response(user, tokens)

    async def refresh_tokens(self, raw_refresh_token: str) -> TokenResponse:
        try:
            payload = self._jwt.decode_token(raw_refresh_token)
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        if payload.type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        token_hash = self._hash_token(raw_refresh_token)
        stored = await self._token_repo.find_by_token_hash(token_hash)

        if not stored:
            if payload.family_id:
                await self._token_repo.revoke_family(payload.family_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token reuse detected",
            )

        user = await self._user_repo.find_by_id(payload.sub)
        if not user or not user["is_active"]:
            await self._token_repo.revoke(str(stored["id"]))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        await self._token_repo.revoke(str(stored["id"]))
        return await self._create_token_pair(
            payload.sub, family_id=payload.family_id
        )

    async def request_password_reset(self, email: str) -> None:
        user = await self._user_repo.find_by_email(email)
        if not user:
            return

        raw_token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        await self._reset_repo.revoke_all_for_user(str(user["id"]))
        await self._reset_repo.create(
            str(user["id"]), token_hash, expires_at
        )

        reset_url = (
            f"{self._settings.frontend_url}/reset-password?token={raw_token}"
        )
        try:
            await self._email.send_email(
                to=email,
                subject="ForgeStream Password Reset",
                html_body=(
                    f"<p>Click <a href='{reset_url}'>here</a> to reset "
                    f"your password. This link expires in 1 hour.</p>"
                ),
            )
        except Exception:
            logger.exception("Failed to send password reset email")

    async def confirm_password_reset(
        self, token: str, new_password: str
    ) -> None:
        token_hash = self._hash_token(token)
        stored = await self._reset_repo.find_valid_by_hash(token_hash)

        if not stored:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token",
            )

        password_hash = self._pwd.hash(new_password)
        await self._user_repo.update_password(
            str(stored["user_id"]), password_hash
        )
        await self._reset_repo.mark_used(str(stored["id"]))
        await self._token_repo.revoke_all_for_user(str(stored["user_id"]))

    async def logout(self, raw_refresh_token: str) -> None:
        try:
            self._jwt.decode_token(raw_refresh_token)
        except JWTError:
            return

        token_hash = self._hash_token(raw_refresh_token)
        stored = await self._token_repo.find_by_token_hash(token_hash)
        if stored:
            await self._token_repo.revoke(str(stored["id"]))

    async def get_github_auth_url(self) -> GitHubAuthURLResponse:
        state = secrets.token_urlsafe(32)
        await self._cache.set(
            f"oauth_state:{state}", "1", expire_seconds=600
        )
        url = self._github.get_authorization_url(state)
        return GitHubAuthURLResponse(authorization_url=url, state=state)

    async def handle_github_callback(
        self, code: str, state: str
    ) -> AuthResponse:
        stored_state = await self._cache.get(f"oauth_state:{state}")
        if not stored_state:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OAuth state",
            )
        await self._cache.delete(f"oauth_state:{state}")
        token_data = await self._github.exchange_code_for_token(code)
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to obtain access token from GitHub",
            )

        gh_user = await self._github.get_user_info(access_token)
        gh_id = str(gh_user["id"])
        email = gh_user.get("email") or f"{gh_id}@github.noemail"
        name = gh_user.get("name") or gh_user.get("login", "GitHub User")
        avatar_url = gh_user.get("avatar_url")

        existing_oauth = await self._oauth_repo.find_by_provider_id(
            "github", gh_id
        )

        if existing_oauth:
            user = await self._user_repo.find_by_id(
                str(existing_oauth["user_id"])
            )
        else:
            user = await self._user_repo.find_by_email(email)
            if not user:
                user = await self._user_repo.create_oauth_user(
                    email=email,
                    name=name,
                    provider="github",
                    avatar_url=avatar_url,
                )
            await self._oauth_repo.create(
                user_id=str(user["id"]),
                provider="github",
                provider_account_id=gh_id,
                access_token=access_token,
            )

        tokens = await self._create_token_pair(str(user["id"]))
        return self._build_auth_response(user, tokens)

    async def _create_token_pair(
        self, user_id: str, family_id: str | None = None
    ) -> TokenResponse:
        access_token = self._jwt.create_access_token(user_id)
        refresh_token, fid, expires_at = self._jwt.create_refresh_token(
            user_id, family_id
        )
        token_hash = self._hash_token(refresh_token)

        await self._token_repo.create(user_id, token_hash, fid, expires_at)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=self._settings.jwt.access_token_expire_minutes * 60,
        )

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def _build_auth_response(
        user: dict, tokens: TokenResponse
    ) -> AuthResponse:
        return AuthResponse(
            user=UserResponse(
                id=str(user["id"]),
                email=user["email"],
                name=user["name"],
                avatar_url=user.get("avatar_url"),
                provider=user["provider"],
                is_verified=user["is_verified"],
                created_at=str(user["created_at"]),
                updated_at=str(user["updated_at"]),
            ),
            tokens=tokens,
        )
