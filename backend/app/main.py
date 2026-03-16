from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import init_db
from .routers import admin, auth, content, health, schools, search
from .routers import console


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db()
    redis_client = None
    try:
        import redis

        redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        redis_client.ping()
    except Exception:
        redis_client = None
    app.state.redis = redis_client
    yield
    if redis_client is not None:
        redis_client.close()


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
cors_allow_origins = settings.cors_allow_origins_list()
allow_all_origins = cors_allow_origins == ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent / "static"), name="static")

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(schools.router, prefix=settings.api_prefix)
app.include_router(search.router, prefix=settings.api_prefix)
app.include_router(content.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(console.router)
