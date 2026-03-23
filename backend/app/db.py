from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine_kwargs = {
    "future": True,
    "pool_pre_ping": True,
}
if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    if settings.database_url in {"sqlite://", "sqlite:///:memory:"}:
        engine_kwargs["poolclass"] = StaticPool
        engine_kwargs["pool_pre_ping"] = False
engine = create_engine(settings.database_url, **engine_kwargs)
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
    _ensure_adjustment_opportunity_search_schema()


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


def _ensure_adjustment_opportunity_search_schema() -> None:
    inspector = inspect(engine)
    if "adjustment_opportunities" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("adjustment_opportunities")}
    additive_columns = {
        "has_history": "INTEGER NOT NULL DEFAULT 0",
        "is_long_track": "INTEGER NOT NULL DEFAULT 0",
        "reference_link_count": "INTEGER NOT NULL DEFAULT 0",
        "min_score_required": "INTEGER",
    }
    missing = {name: ddl for name, ddl in additive_columns.items() if name not in existing_columns}

    with engine.begin() as conn:
        for column_name, ddl in missing.items():
            conn.execute(text(f"ALTER TABLE adjustment_opportunities ADD COLUMN {column_name} {ddl}"))

    inspector = inspect(engine)
    existing_indexes = {index["name"] for index in inspector.get_indexes("adjustment_opportunities")}
    index_statements = {
        "ix_adjustment_opportunities_broad_filters": """
            CREATE INDEX ix_adjustment_opportunities_broad_filters
            ON adjustment_opportunities (school_tier, has_history, is_long_track, min_score_required)
        """,
        "ix_adjustment_opportunities_reference_links": """
            CREATE INDEX ix_adjustment_opportunities_reference_links
            ON adjustment_opportunities (school_tier, reference_link_count)
        """,
    }
    missing_indexes = {name: ddl for name, ddl in index_statements.items() if name not in existing_indexes}
    if not missing_indexes:
        return

    with engine.begin() as conn:
        for ddl in missing_indexes.values():
            conn.execute(text(" ".join(ddl.split())))
