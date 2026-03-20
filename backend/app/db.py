from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_portal_subscription_schema()


def _ensure_portal_subscription_schema() -> None:
    inspector = inspect(engine)
    if "portal_user_subscriptions" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("portal_user_subscriptions")}
    additive_columns = {
        "display_label": "VARCHAR(255)",
        "source_record_id": "VARCHAR(64)",
        "source_item_kind": "VARCHAR(32)",
        "source_title": "VARCHAR(255)",
        "source_url": "VARCHAR(1024)",
        "target_school_name": "VARCHAR(255)",
        "target_school_name_normalized": "VARCHAR(255)",
        "target_department_name": "VARCHAR(255)",
        "target_department_name_normalized": "VARCHAR(255)",
        "target_major_code": "VARCHAR(32)",
        "target_major_name": "VARCHAR(255)",
        "target_major_name_normalized": "VARCHAR(255)",
    }

    missing = {name: ddl for name, ddl in additive_columns.items() if name not in existing_columns}
    if not missing:
        return

    with engine.begin() as conn:
        for column_name, ddl in missing.items():
            conn.execute(text(f"ALTER TABLE portal_user_subscriptions ADD COLUMN {column_name} {ddl}"))
