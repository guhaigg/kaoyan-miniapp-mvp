import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["USE_MOCK_WECHAT"] = "true"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ADMIN_TOKEN"] = "test-admin-token"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"
os.environ["ENABLE_NOTIFICATION_WORKER"] = "false"
os.environ["ENABLE_CRAWL_WORKER"] = "false"
os.environ["NOTIFICATION_BATCH_WINDOW_SECONDS"] = "0"

from app.main import app  # noqa: E402
from app import models  # noqa: E402,F401
from app.db import Base, engine, init_db  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.dependencies import reset_runtime_state_for_tests  # noqa: E402
from app.services.notifications import notification_engine  # noqa: E402


@pytest.fixture(autouse=True)
def setup_db():
    get_settings.cache_clear()
    reset_runtime_state_for_tests()
    notification_engine.reset_for_tests()
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
