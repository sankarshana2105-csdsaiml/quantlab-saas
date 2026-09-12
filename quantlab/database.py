import os
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from .db_models import Base


DEFAULT_DATABASE_URL = "sqlite:///database/quantlab.db"


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


def database_url() -> str:
    return normalize_database_url(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))


def create_database(url: str | None = None, *, initialize: bool = False) -> tuple[Engine, sessionmaker]:
    resolved = normalize_database_url(url) if url else database_url()
    parsed = make_url(resolved)
    options: dict[str, object] = {"pool_pre_ping": True}
    if parsed.drivername.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        if parsed.database in (None, "", ":memory:"):
            options["poolclass"] = StaticPool
        else:
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(resolved, **options)
    if parsed.drivername.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    if initialize:
        Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)
