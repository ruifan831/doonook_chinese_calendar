from pydantic import BaseModel
from typing import Optional
from datetime import date

class PeriodFortune(BaseModel):
    date: str
    summary: Optional[str] = None
    money: str
    career: str
    love: str
    health: Optional[str] = None
    job: Optional[str] = None

class DailyFortune(BaseModel):
    date: str
    presummary: str
    star: str
    color: str
    number: str
    summary: str
    money: str
    career: str
    love: str
    health: str

class AstroFortuneSchema(BaseModel):
    id:Optional[int] = None
    astroid:int
    astroname:str
    date:date
    year: PeriodFortune
    month: PeriodFortune
    week: PeriodFortune
    today: DailyFortune
    tomorrow: DailyFortune
    class Config:
        from_attributes = True