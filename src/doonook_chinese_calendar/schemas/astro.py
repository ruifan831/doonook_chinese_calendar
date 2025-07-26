from pydantic import BaseModel
from typing import Optional
from datetime import date

class PeriodFortune(BaseModel):
    date: str = ""
    summary: Optional[str] = None
    money: str = ""
    career: str = ""
    love: str = ""
    health: Optional[str] = None
    job: Optional[str] = None

class YearFortune(BaseModel):
    date: str = ""
    summary: str = ""
    money: str = ""
    career: str = ""
    love: str = ""
    health: str = ""

class MonthFortune(BaseModel):
    date: str = ""
    summary: str = ""
    money: str = ""
    career: str = ""
    love: str = ""
    health: str = ""

class WeekFortune(BaseModel):
    money: str = ""
    career: str = ""
    health: str = ""
    love: str = ""
    job: str = ""
    date: str = ""

class DailyFortune(BaseModel):
    date: str = ""
    presummary: str = ""
    star: str = ""
    color: str = ""
    number: str = ""
    summary: str = ""
    money: str = ""
    career: str = ""
    love: str = ""
    health: str = ""

class AstroFortuneSchema(BaseModel):
    id: Optional[int] = None
    astroid: int
    astroname: str = ""
    date: date
    year: PeriodFortune = PeriodFortune()
    month: PeriodFortune = PeriodFortune()
    week: PeriodFortune = PeriodFortune()
    today: DailyFortune = DailyFortune()
    tomorrow: DailyFortune = DailyFortune()
    
    class Config:
        from_attributes = True


class JiSuFortuneSchema(BaseModel):
    astroid: int
    astroname: str = ""
    year: YearFortune = YearFortune()
    month: MonthFortune = MonthFortune()
    week: WeekFortune = WeekFortune()
    today: DailyFortune = DailyFortune()
    tomorrow: DailyFortune = DailyFortune()

    def check_year_fortune_empty(self):
        return not any([self.year.summary, self.year.career, self.year.money, self.year.love])
    
    def check_month_fortune_empty(self):
        return not any([self.month.summary, self.month.career, self.month.money, self.month.love, self.month.health])
    
    def check_week_fortune_empty(self):
        return not any([self.week.money, self.week.career, self.week.health, self.week.love, self.week.job])
            