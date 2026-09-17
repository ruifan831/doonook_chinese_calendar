"""Manual LAN test: real model, isolated database, no business DB access.

Default: temporary SQLite. Optional TEST_CALENDAR_DATABASE_URL must point to
an empty, disposable localhost PostgreSQL database named qwen_contract_test.
"""

import asyncio
from datetime import date
import importlib
import json
import os
from pathlib import Path
import tempfile
import time

# Never import package database settings from a deployment .env.
os.environ.update(
    POSTGRES_USER="test",
    POSTGRES_PASSWORD="test",
    POSTGRES_HOST="127.0.0.1",
    POSTGRES_PORT="1",
    POSTGRES_DB="unused",
    DOONOOK_NODE_ROLE="primary",
)

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from doonook_chinese_calendar.core.config import CalendarSettings
from doonook_chinese_calendar.models.astro import AstroFortune
from doonook_chinese_calendar.services.astro_service import AstroService


async def main():
    settings = CalendarSettings(_env_file=os.environ.get("TEST_QWEN_ENV_FILE", ".env"))
    service = AstroService(settings)
    with tempfile.TemporaryDirectory(prefix="qwen-fortune-smoke-") as directory:
        url = os.environ.get("TEST_CALENDAR_DATABASE_URL")
        if url:
            parsed = make_url(url)
            if (
                parsed.get_backend_name() != "postgresql"
                or parsed.host not in {"127.0.0.1", "localhost"}
                or parsed.database != "qwen_contract_test"
            ):
                raise ValueError(
                    "Use a disposable localhost qwen_contract_test database"
                )
        else:
            url = "sqlite:///" + str(Path(directory) / "test.sqlite")
        engine = create_engine(url)
        try:
            if inspect(engine).get_table_names():
                raise ValueError(
                    "Refusing to use a database containing existing tables"
                )
            if engine.dialect.name == "postgresql":
                migration = importlib.import_module(
                    "doonook_chinese_calendar.migrations.versions.75c3add9cb65_initial_migration"
                )
                with engine.begin() as connection:
                    with Operations.context(MigrationContext.configure(connection)):
                        migration.upgrade()
                print(
                    "PASS original PostgreSQL migration applied to isolated database",
                    flush=True,
                )
            else:
                AstroFortune.__table__.create(engine)
            with Session(engine) as db:
                started = time.monotonic()
                result = await service.get_daily_fortune(1, date(2026, 9, 17), db)
                elapsed = time.monotonic() - started
            # New session reads committed state. Disable model connectivity to
            # prove the second query genuinely uses the persisted cache.
            offline = AstroService(
                settings.model_copy(update={"QWEN_BASE_URL": "http://127.0.0.1:1/v1"})
            )
            with Session(engine) as db:
                started = time.monotonic()
                cached = await offline.get_daily_fortune(1, date(2026, 9, 17), db)
                cached_elapsed = time.monotonic() - started
                assert result == cached
                assert db.scalar(select(func.count()).select_from(AstroFortune)) == 1
                row = db.get(AstroFortune, result.id)
                for period in ("year", "month", "week", "today", "tomorrow"):
                    saved = getattr(row, period)
                    assert isinstance(saved, dict)
                    for field in (
                        "date",
                        "summary",
                        "money",
                        "career",
                        "love",
                        "health",
                    ):
                        assert isinstance(saved[field], str) and saved[field].strip(), (
                            period,
                            field,
                        )
                assert row.date == date(2026, 9, 17)
                assert row.astroid == 1 and row.astroname == "白羊座"
                columns = {
                    c["name"]: str(c["type"])
                    for c in inspect(engine).get_columns("astro_fortunes")
                }
                print("PASS database columns:", json.dumps(columns), flush=True)
        finally:
            engine.dispose()
    output = Path.home() / ".config/qwen-lan/sample-fortune.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2)
    )
    print(f"PASS Qwen generation + persistence: {elapsed:.2f}s")
    print(
        f"PASS new-session cache hit with Qwen offline: {cached_elapsed:.4f}s; one row"
    )
    print(f"Sample: {output}")
    print(result.today.summary)


if __name__ == "__main__":
    asyncio.run(main())
