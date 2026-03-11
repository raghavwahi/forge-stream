from fastapi import APIRouter, Depends, status

from app.dependencies import get_auth_service, get_current_user
from app.models.auth import (
    AuthResponse,
    GitHubAuthURLResponse,
    LoginRequest,
    MessageResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from app.models.user import UserInDB
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup(
    data: SignupRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return await service.signup(data)


@router.post("/login", response_model=AuthResponse)
async def login(
    data: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return await service.login(data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    data: RefreshTokenRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return await service.refresh_tokens(data.refresh_token)


@router.post("/password-reset/request", response_model=MessageResponse)
async def request_password_reset(
    data: PasswordResetRequest,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    await service.request_password_reset(data.email)
    return MessageResponse(
        message="If the email exists, a reset link has been sent."
    )


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def confirm_password_reset(
    data: PasswordResetConfirm,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    await service.confirm_password_reset(data.token, data.new_password)
    return MessageResponse(message="Password has been reset successfully.")


@router.post("/logout", response_model=MessageResponse)
async def logout(
    data: RefreshTokenRequest,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    await service.logout(data.refresh_token)
    return MessageResponse(message="Logged out successfully.")


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: UserInDB = Depends(get_current_user),
) -> UserResponse:
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        avatar_url=current_user.avatar_url,
        provider=current_user.provider,
        is_verified=current_user.is_verified,
        created_at=str(current_user.created_at),
        updated_at=str(current_user.updated_at),
    )


@router.get("/github", response_model=GitHubAuthURLResponse)
async def github_auth_url(
    service: AuthService = Depends(get_auth_service),
) -> GitHubAuthURLResponse:
    return await service.get_github_auth_url()


@router.get("/github/callback", response_model=AuthResponse)
async def github_callback(
    code: str,
    state: str,
    service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return await service.handle_github_callback(code, state)
