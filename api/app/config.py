from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    host: str = "localhost"
    port: int = 5432
    user: str = "forge"
    password: str = "forge"
    name: str = "forgestream"
    min_pool_size: int = 5
    max_pool_size: int = 20

    @property
    def dsn(self) -> str:
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )

    model_config = SettingsConfigDict(env_prefix="DB_")


class RedisSettings(BaseSettings):
    host: str = "localhost"
    port: int = 6379
    db: int = 0

    model_config = SettingsConfigDict(env_prefix="REDIS_")


class JWTSettings(BaseSettings):
    secret_key: str = Field(..., description="Must be set via JWT_SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    model_config = SettingsConfigDict(env_prefix="JWT_")


class SMTPSettings(BaseSettings):
    host: str = "localhost"
    port: int = 1025
    username: str = ""
    password: str = ""
    from_email: str = "noreply@forgestream.dev"
    use_tls: bool = False

    model_config = SettingsConfigDict(env_prefix="SMTP_")


class GitHubOAuthSettings(BaseSettings):
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://localhost:3000/api/auth/callback/github"

    model_config = SettingsConfigDict(env_prefix="GITHUB_")


class Settings(BaseSettings):
    env: str = "development"
    log_level: str = "info"
    frontend_url: str = "http://localhost:3000"
    jwt_secret_key: str = Field(
        ..., description="Must be set via JWT_SECRET_KEY"
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    smtp: SMTPSettings = Field(default_factory=SMTPSettings)
    github: GitHubOAuthSettings = Field(default_factory=GitHubOAuthSettings)

    @property
    def cors_origins(self) -> list[str]:
        return [self.frontend_url]

    @property
    def jwt(self) -> JWTSettings:
        return JWTSettings(
            secret_key=self.jwt_secret_key,
            algorithm=self.jwt_algorithm,
            access_token_expire_minutes=self.jwt_access_token_expire_minutes,
            refresh_token_expire_days=self.jwt_refresh_token_expire_days,
        )


def get_settings() -> Settings:
    return Settings()
