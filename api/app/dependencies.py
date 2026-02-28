from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.config import Settings, get_settings
from app.models.user import UserInDB
from app.providers.database import DatabaseProvider
from app.providers.email import SMTPEmailProvider
from app.providers.github import GitHubOAuthProvider
from app.providers.redis import RedisProvider
from app.repositories.oauth_account import OAuthAccountRepository
from app.repositories.password_reset import PasswordResetRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.security.jwt import JWTManager
from app.security.password import PasswordManager
from app.services.auth import AuthService

bearer_scheme = HTTPBearer()


@lru_cache
def get_cached_settings() -> Settings:
    return get_settings()


def get_db_provider(request: Request) -> DatabaseProvider:
    return request.app.state.db_provider


def get_redis_provider(request: Request) -> RedisProvider:
    return request.app.state.redis_provider


def get_email_provider(request: Request) -> SMTPEmailProvider:
    return request.app.state.email_provider


def get_github_provider(request: Request) -> GitHubOAuthProvider:
    return request.app.state.github_provider


def get_user_repository(
    db: DatabaseProvider = Depends(get_db_provider),
) -> UserRepository:
    return UserRepository(db)


def get_refresh_token_repository(
    db: DatabaseProvider = Depends(get_db_provider),
) -> RefreshTokenRepository:
    return RefreshTokenRepository(db)


def get_password_reset_repository(
    db: DatabaseProvider = Depends(get_db_provider),
) -> PasswordResetRepository:
    return PasswordResetRepository(db)


def get_oauth_account_repository(
    db: DatabaseProvider = Depends(get_db_provider),
) -> OAuthAccountRepository:
    return OAuthAccountRepository(db)


def get_jwt_manager(
    settings: Settings = Depends(get_cached_settings),
) -> JWTManager:
    return JWTManager(
        secret_key=settings.jwt.secret_key,
        algorithm=settings.jwt.algorithm,
        access_expire_minutes=settings.jwt.access_token_expire_minutes,
        refresh_expire_days=settings.jwt.refresh_token_expire_days,
    )


def get_password_manager() -> PasswordManager:
    return PasswordManager()


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    token_repo: RefreshTokenRepository = Depends(
        get_refresh_token_repository
    ),
    reset_repo: PasswordResetRepository = Depends(
        get_password_reset_repository
    ),
    oauth_repo: OAuthAccountRepository = Depends(
        get_oauth_account_repository
    ),
    jwt_manager: JWTManager = Depends(get_jwt_manager),
    password_manager: PasswordManager = Depends(get_password_manager),
    email_provider: SMTPEmailProvider = Depends(get_email_provider),
    github_provider: GitHubOAuthProvider = Depends(get_github_provider),
    cache_provider: RedisProvider = Depends(get_redis_provider),
    settings: Settings = Depends(get_cached_settings),
) -> AuthService:
    return AuthService(
        user_repo=user_repo,
        token_repo=token_repo,
        reset_repo=reset_repo,
        oauth_repo=oauth_repo,
        jwt_manager=jwt_manager,
        password_manager=password_manager,
        email_provider=email_provider,
        github_provider=github_provider,
        cache_provider=cache_provider,
        settings=settings,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    jwt_manager: JWTManager = Depends(get_jwt_manager),
    user_repo: UserRepository = Depends(get_user_repository),
) -> UserInDB:
    token = credentials.credentials
    try:
        payload = jwt_manager.decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if payload.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user = await user_repo.find_by_id(payload.sub)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
        )

    return UserInDB(**user)
