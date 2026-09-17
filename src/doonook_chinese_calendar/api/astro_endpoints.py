import logging
from datetime import date as Date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db_writer
from ..schemas.astro import AstroFortuneSchema
from ..services.astro_service import AstroService
from ..services.qwen_fortune import FortuneGenerationError

logger = logging.getLogger(__name__)
router = APIRouter()
astro_service = AstroService()


@router.get("/astro/{astroid}", response_model=AstroFortuneSchema)
async def get_daily_fortune(
    astroid: Annotated[int, Path(ge=1, le=12)],
    date: Date | None = None,
    db: Session = Depends(get_db_writer),
):
    """GET may create a cached fortune: query, lock and save on the writer.

    Uses the host's node-role/REMOTE_WRITER_HOST settings with a synchronous
    session. Replica nodes keep POSTGRES_HOST pointing to their local standby.
    """
    target = date or datetime.now(ZoneInfo(settings.TIMEZONE)).date()
    try:
        return await astro_service.get_daily_fortune(astroid, target, db)
    except FortuneGenerationError as exc:
        raise HTTPException(
            503, detail=str(exc), headers={"Retry-After": "10"}
        ) from None
    except ValueError:
        raise HTTPException(400, detail="无法获取星座运势") from None
    except Exception:
        logger.error("Unable to load fortune for sign %s on %s", astroid, target)
        raise HTTPException(500, detail="无法获取星座运势") from None
