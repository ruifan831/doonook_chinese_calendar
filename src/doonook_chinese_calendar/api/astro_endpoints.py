import logging
from ..schemas.astro import AstroFortuneSchema
from ..core.database import get_db
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import date
from ..services.astro_service import AstroService
from typing import List

# Set up logger
logger = logging.getLogger(__name__)

router = APIRouter()
astro_service = AstroService()

@router.get("/astro/{astroid}", response_model=AstroFortuneSchema)
async def get_daily_fortune(astroid: int, date: date = date.today(), db: Session = Depends(get_db)):
    try:
        fortune = await astro_service.get_daily_fortune(astroid, date, db)
        if not fortune:
            raise HTTPException(status_code=404, detail="Fortune not found for today")
        return fortune
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 