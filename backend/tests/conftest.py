import os

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_mvp.db"
os.environ["USE_MOCK_WECHAT"] = "true"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ADMIN_TOKEN"] = "test-admin-token"

from app.main import app  # noqa: E402
from app.db import Base, engine  # noqa: E402


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c

