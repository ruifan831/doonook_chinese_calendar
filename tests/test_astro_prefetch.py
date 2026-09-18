import asyncio
from contextlib import contextmanager
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from click.testing import CliRunner
import pytest

from doonook_chinese_calendar.cli import cli
from doonook_chinese_calendar.services import astro_prefetch as jobs


@pytest.mark.asyncio
async def test_date_first_order_failure_isolation_and_session_cleanup():
    sessions = []
    closed = []

    @contextmanager
    def session():
        item = object()
        sessions.append(item)
        try:
            yield item
        finally:
            closed.append(item)

    fake = AsyncMock(
        side_effect=[RuntimeError("secret must not be logged"), None, None, None]
    )
    messages = []
    result = await jobs.prefetch(
        date(2026, 12, 31),
        2,
        (1, 2, 1),
        session_factory=session,
        service=SimpleNamespace(get_daily_fortune=fake),
        report=messages.append,
    )
    assert [(c.args[0], c.args[1]) for c in fake.await_args_list] == [
        (1, date(2026, 12, 31)),
        (2, date(2026, 12, 31)),
        (1, date(2027, 1, 1)),
        (2, date(2027, 1, 1)),
    ]
    assert result.ready == 3 and result.failed == [(date(2026, 12, 31), 1)]
    assert len(sessions) == 4 and sessions == closed
    assert "secret" not in " ".join(messages)


@pytest.mark.asyncio
async def test_cancellation_stops_batch_and_closes_session():
    closed = []

    @contextmanager
    def session():
        try:
            yield object()
        finally:
            closed.append(True)

    fake = AsyncMock(side_effect=asyncio.CancelledError)
    with pytest.raises(asyncio.CancelledError):
        await jobs.prefetch(
            date(2026, 9, 17),
            service=SimpleNamespace(get_daily_fortune=fake),
            session_factory=session,
        )
    assert closed == [True]
    assert fake.await_count == 1


@pytest.mark.asyncio
async def test_maintenance_recomputes_date_and_retries_after_failed_batch(monkeypatch):
    dates = iter([datetime(2026, 12, 31), datetime(2027, 1, 1)])

    class Clock:
        @staticmethod
        def now(tz):
            assert str(tz) == "Asia/Shanghai"
            return next(dates)

    fake = AsyncMock(
        side_effect=[RuntimeError("offline"), jobs.PrefetchResult(ready=84)]
    )
    sleep = AsyncMock(side_effect=[None, asyncio.CancelledError])
    monkeypatch.setattr(jobs, "datetime", Clock)
    monkeypatch.setattr(jobs, "prefetch", fake)
    monkeypatch.setattr(jobs.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        await jobs.maintain(7, 3600, report=lambda _: None)
    assert [c.args[0] for c in fake.await_args_list] == [
        date(2026, 12, 31),
        date(2027, 1, 1),
    ]
    assert all(c.args == (3600,) for c in sleep.await_args_list)


def test_cli_partial_failure_is_nonzero_and_range_is_forwarded(monkeypatch):
    fake = AsyncMock(
        return_value=jobs.PrefetchResult(ready=1, failed=[(date(2026, 9, 17), 2)])
    )
    monkeypatch.setattr(jobs, "prefetch", fake)
    result = CliRunner().invoke(
        cli,
        [
            "warm-astro",
            "--date",
            "2026-09-17",
            "--days",
            "7",
            "--sign",
            "1",
            "--sign",
            "2",
        ],
    )
    assert result.exit_code == 1
    assert "1 条未完成" in result.output
    assert fake.await_args.args == (date(2026, 9, 17), 7, (1, 2))
    assert CliRunner().invoke(cli, ["warm-astro", "--days", "0"]).exit_code == 2
    assert CliRunner().invoke(cli, ["maintain-astro", "--interval", "0"]).exit_code == 2


def test_cli_default_date_uses_configured_timezone(monkeypatch):
    fake = AsyncMock(return_value=jobs.PrefetchResult(ready=12))
    monkeypatch.setattr(jobs, "prefetch", fake)
    result = CliRunner().invoke(cli, ["warm-astro"])
    assert result.exit_code == 0
    assert fake.await_args.args[1:] == (1, tuple(range(1, 13)))
