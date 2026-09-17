"""The calendar package shares the host's topology env, not its local reader."""

from contextlib import contextmanager
from datetime import date
import os
import subprocess
import sys
from unittest.mock import AsyncMock

from click.testing import CliRunner
import pytest
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from doonook_chinese_calendar.api import astro_endpoints, endpoints
from doonook_chinese_calendar.cli import cli
from doonook_chinese_calendar.core import database
from doonook_chinese_calendar.core.config import CalendarSettings
from doonook_chinese_calendar.services.astro_service import AstroService


@pytest.mark.parametrize(
    "role,expected", [("primary", "local.invalid"), ("replica", "writer.invalid")]
)
def test_writer_uses_host_topology_without_changing_local_host(role, expected):
    config = CalendarSettings(
        _env_file=None,
        DOONOOK_NODE_ROLE=role,
        POSTGRES_HOST="local.invalid",
        REMOTE_WRITER_HOST="writer.invalid",
        POSTGRES_USER="test",
        POSTGRES_PASSWORD="p@ss:/?#%",
        POSTGRES_PORT="5433",
    )
    assert config.POSTGRES_HOST == "local.invalid"
    assert config.WRITER_DATABASE_URL.host == expected
    assert config.WRITER_DATABASE_URL.port == 5433
    # Legacy CLI/migration URL must use the same writer, including escaping.
    parsed = make_url(config.DATABASE_URL)
    assert parsed.host == expected
    assert parsed.password == "p@ss:/?#%"


@pytest.mark.parametrize("host", [None, "", "   "])
def test_replica_without_writer_fails_without_disclosing_credentials(host):
    with pytest.raises(ValidationError) as exc:
        CalendarSettings(
            _env_file=None,
            DOONOOK_NODE_ROLE="replica",
            REMOTE_WRITER_HOST=host,
            POSTGRES_PASSWORD="private-test-password",
        )
    assert "REMOTE_WRITER_HOST" in str(exc.value)
    assert "private-test-password" not in str(exc.value)


def test_both_cache_routes_explicitly_depend_on_writer():
    for router, path in [
        (astro_endpoints.router, "/astro/{astroid}"),
        (endpoints.router, "/daily"),
    ]:
        route = next(route for route in router.routes if route.path == path)
        assert route.dependant.dependencies[0].call is database.get_db_writer


def test_writer_dependency_closes_session_on_error(monkeypatch):
    class Session:
        closed = False

        def close(self):
            self.closed = True

    session = Session()
    monkeypatch.setattr(database, "WriterSessionLocal", lambda: session)
    dependency = database.get_db_writer()
    assert next(dependency) is session
    with pytest.raises(RuntimeError):
        dependency.throw(RuntimeError("request cancelled"))
    assert session.closed


def test_warm_astro_uses_writer_session(monkeypatch):
    session = object()
    closed = []

    @contextmanager
    def writer():
        try:
            yield session
        finally:
            closed.append(True)

    fake = AsyncMock()
    monkeypatch.setattr(database, "WriterSessionLocal", writer)
    monkeypatch.setattr(AstroService, "get_daily_fortune", fake)
    result = CliRunner().invoke(
        cli, ["warm-astro", "--date", "2026-09-17", "--sign", "1"]
    )
    assert result.exit_code == 0, result.output
    fake.assert_awaited_once_with(1, date(2026, 9, 17), session)
    assert closed == [True]


def test_shared_dotenv_initializes_writer_in_separate_process(monkeypatch, tmp_path):
    # Launch just like the host: cwd contains the shared .env; no overrides.
    for name in ("DOONOOK_NODE_ROLE", "REMOTE_WRITER_HOST", "POSTGRES_HOST"):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env").write_text(
        "DOONOOK_NODE_ROLE=replica\nPOSTGRES_HOST=local.invalid\n"
        "REMOTE_WRITER_HOST=writer.invalid\nREAD_REPLICA_DSN=postgresql://unused/reader\n"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from doonook_chinese_calendar.core.database import writer_engine; "
            "assert writer_engine.url.host == 'writer.invalid'; print('PASS writer')",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, "Writer initialization failed"
    assert "PASS writer" in result.stdout


def test_replica_route_persists_on_primary_not_local_host(tmp_path):
    url = os.environ.get("TEST_CALENDAR_DATABASE_URL")
    if not url:
        pytest.skip("requires isolated PostgreSQL")
    target = make_url(url)
    assert (
        target.host in {"127.0.0.1", "localhost"} and target.database == "calendar_test"
    )
    environment = os.environ.copy()
    environment.update(
        DOONOOK_NODE_ROLE="replica",
        POSTGRES_HOST="192.0.2.1",
        REMOTE_WRITER_HOST=target.host,
        POSTGRES_PORT=str(target.port),
        POSTGRES_USER=target.username,
        POSTGRES_PASSWORD=target.password,
        POSTGRES_DB=target.database,
    )
    # A fresh interpreter exercises module-level engine creation and the actual
    # route dependency. The local-reader address is deliberately unreachable.
    script = """
from datetime import date
from unittest.mock import AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from doonook_chinese_calendar.api.astro_endpoints import router
from doonook_chinese_calendar.core.database import writer_engine, WriterSessionLocal
from doonook_chinese_calendar.models.astro import AstroFortune
from doonook_chinese_calendar.schemas.astro import AstroFortuneSchema
from doonook_chinese_calendar.services.qwen_fortune import QwenFortuneGenerator
assert writer_engine.url.host in {"127.0.0.1", "localhost"}
AstroFortune.__table__.create(writer_engine)
try:
    QwenFortuneGenerator.generate = AsyncMock(return_value=AstroFortuneSchema(
        astroid=1, astroname="白羊座", date=date(2026,9,17)))
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get("/astro/1?date=2026-09-17")
        assert response.status_code == 200
        assert response.json()["id"] is not None
        assert client.get("/astro/1?date=2026-09-17").json() == response.json()
    QwenFortuneGenerator.generate.assert_awaited_once()
    with WriterSessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(AstroFortune)) == 1
    print("PASS replica route persisted and cached on primary")
finally:
    AstroFortune.__table__.drop(writer_engine)
    writer_engine.dispose()
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, "Isolated primary routing integration failed"
    assert "PASS replica route" in result.stdout


def test_migration_default_uses_writer_with_encoded_password(monkeypatch):
    import importlib

    module = importlib.import_module("doonook_chinese_calendar.cli")
    config = CalendarSettings(
        _env_file=None,
        DOONOOK_NODE_ROLE="replica",
        REMOTE_WRITER_HOST="writer.invalid",
        POSTGRES_HOST="local.invalid",
        POSTGRES_PASSWORD="p@ss%word",
    )
    calls = []

    def upgrade(alembic_config, revision):
        url = make_url(alembic_config.get_main_option("sqlalchemy.url"))
        assert url.host == "writer.invalid" and url.password == "p@ss%word"
        calls.append(revision)

    monkeypatch.setattr(module, "settings", config)
    monkeypatch.setattr(module.command, "upgrade", upgrade)
    result = CliRunner().invoke(cli, ["migrate"])
    assert result.exit_code == 0, result.output
    assert calls == ["head"]
    assert "p@ss" not in result.output
