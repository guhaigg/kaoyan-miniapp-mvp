import os

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_mvp.db"
os.environ["USE_MOCK_WECHAT"] = "true"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ADMIN_TOKEN"] = "test-admin-token"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"
os.environ["ENABLE_NOTIFICATION_WORKER"] = "false"
os.environ["NOTIFICATION_BATCH_WINDOW_SECONDS"] = "0"

from app.main import app  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.dependencies import reset_runtime_state_for_tests  # noqa: E402
from app.services.notifications import notification_engine  # noqa: E402


@pytest.fixture(autouse=True)
def setup_db():
    reset_runtime_state_for_tests()
    notification_engine.reset_for_tests()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
