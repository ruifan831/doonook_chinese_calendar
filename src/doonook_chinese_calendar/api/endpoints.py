from ..schemas.calendar import DailyCalendarInfoSchema
from ..core.database import get_db
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from ..services.calendar_service import ChineseCalendarService
from typing import Optional

router = APIRouter()
calendar_service = ChineseCalendarService()

@router.get("/daily",response_model=DailyCalendarInfoSchema)
async def get_daily_calendar(date: Optional[str] = None, db: Session = Depends(get_db)):
    try:
        if date:
            query_date = datetime.strptime(date, "%Y-%m-%d")
        else:
            query_date = datetime.now()
            
        return await calendar_service.get_daily_calendar(query_date,db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/convert-to-lunar")
async def convert_to_lunar(date: Optional[str] = None):
    try:
        if date:
            query_date = datetime.strptime(date, "%Y-%m-%d")
        else:
            query_date = datetime.now()
            
        return calendar_service.convert_to_lunar(query_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
