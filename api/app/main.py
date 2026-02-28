import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.middleware.rate_limit import RateLimitMiddleware
from app.providers.database import DatabaseProvider
from app.providers.email import SMTPEmailProvider
from app.providers.github import GitHubOAuthProvider
from app.providers.redis import RedisProvider
from app.routers.auth import router as auth_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    db = DatabaseProvider(
        settings.db.dsn,
        settings.db.min_pool_size,
        settings.db.max_pool_size,
    )
    redis = RedisProvider(
        settings.redis.host, settings.redis.port, settings.redis.db
    )
    email = SMTPEmailProvider(
        host=settings.smtp.host,
        port=settings.smtp.port,
        username=settings.smtp.username,
        password=settings.smtp.password,
        from_email=settings.smtp.from_email,
        use_tls=settings.smtp.use_tls,
    )
    github = GitHubOAuthProvider(
        client_id=settings.github.client_id,
        client_secret=settings.github.client_secret,
        redirect_uri=settings.github.redirect_uri,
    )

    await db.connect()
    await redis.connect()
    logger.info("Database and Redis connected")

    app.state.db_provider = db
    app.state.redis_provider = redis
    app.state.email_provider = email
    app.state.github_provider = github

    yield

    await db.disconnect()
    await redis.disconnect()
    logger.info("Database and Redis disconnected")


app = FastAPI(title="ForgeStream API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware)

app.include_router(auth_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
