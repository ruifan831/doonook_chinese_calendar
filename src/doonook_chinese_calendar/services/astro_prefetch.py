"""Sequential, resumable prefetch. Never run inference inside an HTTP request."""

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable
from zoneinfo import ZoneInfo

from ..core.config import settings
from ..core import database
from .astro_service import AstroService


@dataclass
class PrefetchResult:
    ready: int = 0
    failed: list[tuple[date, int]] = field(default_factory=list)


async def prefetch(
    start: date,
    days: int = 7,
    signs: tuple[int, ...] = tuple(range(1, 13)),
    *,
    session_factory=None,
    service=None,
    report: Callable[[str], None] = print,
) -> PrefetchResult:
    if not 1 <= days <= 31 or not signs or any(s not in range(1, 13) for s in signs):
        raise ValueError("days must be 1..31 and signs must be 1..12")
    dates = [start + timedelta(days=n) for n in range(days)]
    service = service or AstroService()
    session_factory = session_factory or database.WriterSessionLocal
    result = PrefetchResult()
    # Complete all signs for today before spending time on future dates.
    for target in dates:
        for sign in dict.fromkeys(signs):
            try:
                with session_factory() as db:
                    await service.get_daily_fortune(sign, target, db)
                result.ready += 1
                report(f"ready: {target} sign={sign}")
            except Exception:
                # Do not expose provider URLs, credentials or connection strings.
                # Cancellation/KeyboardInterrupt are deliberately not caught.
                result.failed.append((target, sign))
                report(f"failed: {target} sign={sign}; retry on next run")
    report(f"complete: ready={result.ready} failed={len(result.failed)}")
    return result


async def maintain(days: int, interval: int, report: Callable[[str], None] = print):
    """One process, one batch at a time; recompute local date after every sleep."""
    while True:
        start = datetime.now(ZoneInfo(settings.TIMEZONE)).date()
        try:
            await prefetch(start, days, report=report)
        except Exception:
            report("batch failed; retry on next run")
        await asyncio.sleep(interval)
