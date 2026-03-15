from contextlib import asynccontextmanager
import logging
import time
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request

from .config import get_settings
from .db import init_db
from .routers import admin, auth, content, health, jobs, schools, search


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
request_logger = logging.getLogger("uvicorn.error")
cors_allow_origins = settings.cors_allow_origins_list()
allow_all_origins = cors_allow_origins == ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    started_at = time.perf_counter()
    request_id = request.headers.get("X-Request-Id", "").strip() or str(uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    response.headers["X-Request-Id"] = request_id
    request_logger.info(
        "method=%s path=%s status=%s request_id=%s elapsed_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        request_id,
        elapsed_ms,
    )
    return response


app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(schools.router, prefix=settings.api_prefix)
app.include_router(search.router, prefix=settings.api_prefix)
app.include_router(jobs.router, prefix=settings.api_prefix)
app.include_router(content.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
