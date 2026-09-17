import asyncio
from datetime import date, datetime
import json
import os
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from doonook_chinese_calendar.api import astro_endpoints
from doonook_chinese_calendar.core.config import CalendarSettings
from doonook_chinese_calendar.core.database import get_db
from doonook_chinese_calendar.models.astro import AstroFortune
from doonook_chinese_calendar.schemas.astro import AstroFortuneSchema
from doonook_chinese_calendar.services.astro_service import AstroService
from doonook_chinese_calendar.services import qwen_fortune
from doonook_chinese_calendar.services.qwen_fortune import (
    FortuneGenerationError,
    QwenFortuneGenerator,
)


@pytest.fixture(autouse=True)
def deterministic_basis(monkeypatch):
    def calculate(astroid, target, path, timezone):
        return {
            period: {
                "start": target.isoformat(),
                "end": target.isoformat(),
                "sample_count": 1,
                "rule_version": "test-rule",
                "categories": {
                    domain: {
                        "score": 2,
                        "factors": [
                            {
                                "label": "测试刑相",
                                "sample_date": target.isoformat(),
                                "observed_days": 1,
                            }
                        ],
                    }
                    for domain in ("love", "career", "money", "health")
                },
            }
            for period in ("today", "tomorrow", "week", "month", "year")
        }

    monkeypatch.setattr(qwen_fortune, "build_basis", calculate)


@pytest.fixture
def config():
    return CalendarSettings(_env_file=None)


@pytest.fixture
def generated():
    period = {
        key: "保持耐心，循序渐进地处理日常事务。"
        for key in ("summary", "money", "career", "love", "health")
    }
    day = dict(
        period, presummary="适当放慢节奏。", star="天秤座", color="蓝色", number="6"
    )
    return {
        "year": dict(period),
        "month": dict(period),
        "week": dict(period),
        "today": dict(day),
        "tomorrow": dict(day),
    }


def mock_http(monkeypatch, response=None, error=None, handler=None):
    original = httpx.AsyncClient

    def handle(request):
        if error:
            raise error
        return handler(request) if handler else response

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handle)),
    )


@pytest.mark.asyncio
async def test_request_and_server_owned_dates(monkeypatch, config, generated):
    def handle(request):
        assert str(request.url) == "http://qwen.invalid/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["reasoning_effort"] == "none"
        assert "response_format" not in body
        assert "双鱼座" in body["messages"][1]["content"]
        assert "测试刑相" in body["messages"][1]["content"]
        assert '"score":2' in body["messages"][1]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(generated)},
                    }
                ]
            },
        )

    mock_http(monkeypatch, handler=handle)
    result = await QwenFortuneGenerator(config).generate(
        12, "双鱼座", date(2026, 12, 31)
    )
    assert result.astroid == 12 and result.astroname == "双鱼座"
    assert result.today.date == "2026-12-31"
    assert result.tomorrow.date == "2027-01-01"
    assert result.year.date == "2026" and result.month.date == "2026-12"
    assert result.week.date == "2026-12-28至2027-01-03"
    assert result.week.summary == generated["week"]["summary"]
    assert result.date == date(2026, 12, 31)


@pytest.mark.asyncio
async def test_terminal_thinking_marker_is_normalized(monkeypatch, config, generated):
    generated["today"]["summary"] = "正文中的</think>不应被替换"
    mock_http(
        monkeypatch,
        httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(generated) + "\n</think>\n"},
                    }
                ]
            },
        ),
    )
    result = await QwenFortuneGenerator(config).generate(1, "白羊座", date(2026, 9, 17))
    assert result.today.summary == generated["today"]["summary"]


@pytest.mark.asyncio
async def test_marker_does_not_bypass_validation(monkeypatch, config):
    mock_http(
        monkeypatch,
        httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"today":{}}\n</think>'},
                    }
                ]
            },
        ),
    )
    with pytest.raises(FortuneGenerationError):
        await QwenFortuneGenerator(config).generate(1, "白羊座", date(2026, 9, 17))


@pytest.mark.parametrize(
    "case", ["empty", "missing", "extra", "wrong_type", "fenced", "truncated"]
)
@pytest.mark.asyncio
async def test_reject_invalid_output(monkeypatch, config, generated, case):
    if case == "empty":
        generated["today"]["summary"] = " "
    if case == "missing":
        del generated["year"]
    if case == "extra":
        generated["astroid"] = 9
    if case == "wrong_type":
        generated["today"]["number"] = 6
    content = json.dumps(generated)
    if case == "fenced":
        content = "```json\n" + content + "\n```"
    mock_http(
        monkeypatch,
        httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length" if case == "truncated" else "stop",
                        "message": {"content": content},
                    }
                ]
            },
        ),
    )
    with pytest.raises(FortuneGenerationError):
        await QwenFortuneGenerator(config).generate(1, "白羊座", date(2026, 9, 17))


@pytest.mark.parametrize("status", [401, 429, 500, 502, 503])
@pytest.mark.asyncio
async def test_provider_errors_are_sanitized(monkeypatch, config, status):
    mock_http(monkeypatch, httpx.Response(status, text="secret provider body"))
    with pytest.raises(FortuneGenerationError) as exc:
        await QwenFortuneGenerator(config).generate(1, "白羊座", date(2026, 9, 17))
    assert "secret" not in str(exc.value) and "test-key" not in str(exc.value)


@pytest.mark.asyncio
async def test_timeout(monkeypatch, config):
    mock_http(monkeypatch, error=httpx.ReadTimeout("secret"))
    with pytest.raises(FortuneGenerationError):
        await QwenFortuneGenerator(config).generate(1, "白羊座", date(2026, 9, 17))


@pytest.mark.parametrize("field", ["QWEN_BASE_URL", "QWEN_LAN_API_KEY", "QWEN_MODEL"])
@pytest.mark.asyncio
async def test_unconfigured_qwen_does_not_call_network(monkeypatch, config, field):
    config = config.model_copy(
        update={field: CalendarSettings.model_fields[field].default}
    )
    request = AsyncMock()
    monkeypatch.setattr(httpx.AsyncClient, "post", request)
    with pytest.raises(FortuneGenerationError):
        await QwenFortuneGenerator(config).generate(1, "白羊座", date(2026, 9, 17))
    request.assert_not_awaited()


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    AstroFortune.__table__.create(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.mark.asyncio
async def test_cache_and_existing_contract(monkeypatch, config, generated, db):
    fake = AsyncMock(
        return_value=AstroFortuneSchema(
            astroid=1, astroname="白羊座", date=date(2026, 9, 17), **generated
        )
    )
    monkeypatch.setattr(QwenFortuneGenerator, "generate", fake)
    service = AstroService(config)
    one = await service.get_daily_fortune(1, date(2026, 9, 17), db)
    two = await service.get_daily_fortune(1, date(2026, 9, 17), db)
    assert one == two and one.id is not None
    assert fake.await_count == 1
    assert set(one.model_dump()) == {
        "id",
        "astroid",
        "astroname",
        "date",
        "today",
        "tomorrow",
        "week",
        "month",
        "year",
    }
    assert db.scalar(select(func.count()).select_from(AstroFortune)) == 1
    # Existing records remain available even when Qwen is offline.
    fake.side_effect = FortuneGenerationError("offline")
    assert await service.get_daily_fortune(1, date(2026, 9, 17), db) == one


@pytest.mark.asyncio
async def test_qwen_json_to_database_without_losing_fields(
    monkeypatch, config, generated, db
):
    mock_http(
        monkeypatch,
        httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(generated)},
                    }
                ]
            },
        ),
    )
    result = await AstroService(config).get_daily_fortune(1, date(2026, 9, 17), db)
    row = db.get(AstroFortune, result.id)
    for period in ("year", "month", "week", "today", "tomorrow"):
        persisted = getattr(row, period)
        for key, value in generated[period].items():
            assert persisted[key] == value
    assert row.today["_basis"]["rule_version"] == "test-rule"
    assert "_basis" not in result.today.model_dump()
    assert row.date == date(2026, 9, 17)
    assert row.tomorrow["date"] == "2026-09-18"
    assert row.week["job"] == row.week["career"]


@pytest.mark.asyncio
async def test_invalid_qwen_json_never_reaches_database(monkeypatch, config, db):
    mock_http(
        monkeypatch,
        httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"content": '{"today": {}}'}}
                ]
            },
        ),
    )
    with pytest.raises(FortuneGenerationError):
        await AstroService(config).get_daily_fortune(1, date(2026, 9, 17), db)
    assert db.scalar(select(func.count()).select_from(AstroFortune)) == 0


@pytest.mark.parametrize(
    "failure", [FortuneGenerationError("offline"), asyncio.CancelledError()]
)
@pytest.mark.asyncio
async def test_failure_or_cancel_leaves_no_row(monkeypatch, config, db, failure):
    monkeypatch.setattr(
        QwenFortuneGenerator, "generate", AsyncMock(side_effect=failure)
    )
    with pytest.raises(type(failure)):
        await AstroService(config).get_daily_fortune(1, date(2026, 9, 17), db)
    assert not db.in_transaction()
    assert db.scalar(select(func.count()).select_from(AstroFortune)) == 0


def test_route_validation_503_and_timezone(monkeypatch, db):
    app = FastAPI()
    app.include_router(astro_endpoints.router, prefix="/calendar")
    app.dependency_overrides[get_db] = lambda: db
    fake = AsyncMock(side_effect=FortuneGenerationError("暂不可用"))
    monkeypatch.setattr(astro_endpoints.astro_service, "get_daily_fortune", fake)

    class Clock:
        @staticmethod
        def now(tz):
            assert str(tz) == "Asia/Shanghai"
            return datetime(2027, 1, 1, tzinfo=tz)

    monkeypatch.setattr(astro_endpoints, "datetime", Clock)
    with TestClient(app) as client:
        for path in [
            "/calendar/astro/0",
            "/calendar/astro/13",
            "/calendar/astro/1?date=no",
        ]:
            assert client.get(path).status_code == 422
        assert fake.await_count == 0
        response = client.get("/calendar/astro/1")
        assert response.status_code == 503 and response.headers["Retry-After"] == "10"
        assert fake.await_args.args[1] == date(2027, 1, 1)


def test_http_response_keeps_client_contract(monkeypatch, db, generated):
    app = FastAPI()
    app.include_router(astro_endpoints.router, prefix="/calendar")
    app.dependency_overrides[get_db] = lambda: db
    fake = AsyncMock(
        return_value=AstroFortuneSchema(
            astroid=1, astroname="白羊座", date=date(2026, 9, 17), **generated
        )
    )
    monkeypatch.setattr(QwenFortuneGenerator, "generate", fake)
    with TestClient(app) as client:
        response = client.get("/calendar/astro/1?date=2026-09-17")
        assert response.status_code == 200
        data = response.json()
        assert data["astroid"] == 1 and data["date"] == "2026-09-17"
        assert "data" not in data
        for period in ("today", "tomorrow", "week", "month", "year"):
            for name in ("date", "money", "career", "love"):
                assert isinstance(data[period][name], str)


@pytest.mark.asyncio
async def test_stale_provider_setting_cannot_enable_third_party(
    monkeypatch, generated, db
):
    monkeypatch.setenv("ASTRO_PROVIDER", "jisu")
    config = CalendarSettings(_env_file=None)
    qwen = AsyncMock(
        return_value=AstroFortuneSchema(
            astroid=1, astroname="白羊座", date=date(2026, 9, 17), **generated
        )
    )
    monkeypatch.setattr(QwenFortuneGenerator, "generate", qwen)
    result = await AstroService(config).get_daily_fortune(1, date(2026, 9, 17), db)
    assert result.astroname == "白羊座"
    qwen.assert_awaited_once()
    assert not hasattr(config, "ASTRO_PROVIDER")
    assert not hasattr(AstroService, "_fetch_api_data")
    assert not hasattr(AstroService, "get_fortune_by_type")


def test_dotenv_loads_model_config_without_exports(monkeypatch, tmp_path):
    for name in ("QWEN_BASE_URL", "QWEN_LAN_API_KEY", "QWEN_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "QWEN_BASE_URL=http://dotenv.invalid/v1\n"
        'QWEN_LAN_API_KEY="dotenv-test-key"\n'
        "QWEN_MODEL=dotenv-test-model\n",
        encoding="utf-8",
    )
    loaded = CalendarSettings()
    assert loaded.QWEN_BASE_URL == "http://dotenv.invalid/v1"
    assert loaded.QWEN_MODEL == "dotenv-test-model"
    assert loaded.QWEN_LAN_API_KEY.get_secret_value() == "dotenv-test-key"
    assert "dotenv-test-key" not in repr(loaded)


@pytest.mark.asyncio
async def test_postgres_concurrent_single_generation(monkeypatch, config, generated):
    url = os.environ.get("TEST_CALENDAR_DATABASE_URL")
    if not url:
        pytest.skip("requires isolated PostgreSQL")
    engine = create_engine(url)
    AstroFortune.__table__.create(engine, checkfirst=True)
    calls = 0

    async def generate(*args):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.2)
        return AstroFortuneSchema(
            astroid=1, astroname="白羊座", date=date(2026, 9, 17), **generated
        )

    monkeypatch.setattr(QwenFortuneGenerator, "generate", generate)

    async def fetch():
        with Session(engine) as session:
            return await AstroService(config).get_daily_fortune(
                1, date(2026, 9, 17), session
            )

    try:
        values = await asyncio.gather(*(fetch() for _ in range(6)))
        assert calls == 1 and len({v.id for v in values}) == 1
    finally:
        AstroFortune.__table__.drop(engine)
        engine.dispose()


@pytest.mark.asyncio
async def test_missing_ephemeris_never_calls_model_or_saves(monkeypatch, config, db):
    from doonook_chinese_calendar.services.astro_basis import EphemerisError

    def missing(*args):
        raise EphemerisError("missing")

    monkeypatch.setattr(qwen_fortune, "build_basis", missing)
    request = AsyncMock()
    monkeypatch.setattr(httpx.AsyncClient, "post", request)
    with pytest.raises(FortuneGenerationError):
        await AstroService(config).get_daily_fortune(1, date(2026, 9, 17), db)
    request.assert_not_awaited()
    assert db.scalar(select(func.count()).select_from(AstroFortune)) == 0


def test_mlx_draft_marker_final_uses_final_json(generated):
    import copy

    draft = copy.deepcopy(generated)
    draft["today"]["summary"] = "草稿文案"
    generated["today"]["summary"] = "最终文案包含字符串</think>"
    content = json.dumps(draft) + "\n</think>\n" + json.dumps(generated)
    parsed = qwen_fortune.parse_generated_fortune(content)
    assert parsed.today.summary == generated["today"]["summary"]


@pytest.mark.parametrize(
    "case", ["no_marker", "bad_draft", "bad_final", "extra_tail", "extra_marker"]
)
def test_protocol_parser_does_not_accept_arbitrary_json_fragments(generated, case):
    valid = json.dumps(generated)
    content = valid + "</think>" + valid
    if case == "no_marker":
        content = valid + valid
    if case == "bad_draft":
        content = "{}" + "</think>" + valid
    if case == "bad_final":
        content = valid + "</think>" + "{}"
    if case == "extra_tail":
        content += "extra explanation"
    if case == "extra_marker":
        content = valid + "</think></think>" + valid
    with pytest.raises(ValueError):
        qwen_fortune.parse_generated_fortune(content)
