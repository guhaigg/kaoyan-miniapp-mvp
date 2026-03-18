import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import init_db
from .routers import admin, auth, content, crawl, health, monitoring, notifications, schools, search, site_sections, subscriptions
from .routers import console
from .services.crawler import crawl_engine
from .services.notifications import notification_engine


async def _notification_worker_loop():
    settings = get_settings()
    sleep_seconds = max(0.2, float(settings.notification_poll_interval_seconds))
    while True:
        try:
            processed = await asyncio.to_thread(notification_engine.process_batch)
        except Exception:
            processed = 0

        if processed <= 0:
            await asyncio.sleep(sleep_seconds)
        else:
            await asyncio.sleep(0.05)


async def _crawl_worker_loop():
    settings = get_settings()
    sleep_seconds = max(0.2, float(settings.crawl_poll_interval_seconds))
    while True:
        try:
            processed = await asyncio.to_thread(crawl_engine.process_job_batch)
        except Exception:
            processed = 0

        if processed <= 0:
            await asyncio.sleep(sleep_seconds)
        else:
            await asyncio.sleep(0.05)


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
    notification_task = None
    crawl_task = None
    if settings.enable_notification_worker:
        notification_task = asyncio.create_task(_notification_worker_loop())
    if settings.enable_crawl_worker:
        crawl_task = asyncio.create_task(_crawl_worker_loop())
    app.state.notification_task = notification_task
    app.state.crawl_task = crawl_task
    yield
    if crawl_task is not None:
        crawl_task.cancel()
        with suppress(asyncio.CancelledError):
            await crawl_task
    if notification_task is not None:
        notification_task.cancel()
        with suppress(asyncio.CancelledError):
            await notification_task
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
app.include_router(crawl.router, prefix=settings.api_prefix)
app.include_router(site_sections.router, prefix=settings.api_prefix)
app.include_router(monitoring.router, prefix=settings.api_prefix)
app.include_router(subscriptions.router, prefix=settings.api_prefix)
app.include_router(notifications.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(console.router)
