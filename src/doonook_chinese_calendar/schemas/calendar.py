from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import datetime, date

class DoonookDailyCalendarInfo(BaseModel):
    date: str
    lunar_year: int
    lunar_month: str
    lunar_day: str
    is_leap_month: bool
    lunar_date: str
    solar_term: Optional[str]
    year_ganzhi: str
    month_ganzhi: str
    day_ganzhi: str

    class Config:
        json_schema_extra = {
            "example": {
                "date": "2024-03-20",
                "lunar_year": 2024,
                "lunar_month": "二",
                "lunar_day": "初十",
                "is_leap_month": False,
                "lunar_date": "二月初十",
                "solar_term": "春分",
                "year_ganzhi": "甲辰",
                "month_ganzhi": "丙卯",
                "day_ganzhi": "壬午",
            }
        }

class JiSuDailyCalendarInfo(BaseModel):
    year: str
    month: str
    day: str
    yangli: str
    nongli: str
    star: str   # 星座
    taishen: str  # 胎神
    wuxing: str  # 五行
    chong: str  # 冲
    sha: str  # 煞
    shengxiao: str  # 生肖
    jiri: Optional[str]  # 吉日
    zhiri: Optional[str]  # 值日天神
    xiongshen: Optional[str]  # 凶神
    jishenyiqu: Optional[str]  # 吉神宜趋
    caishen: Optional[str]  # 财神
    xishen: Optional[str]  # 喜神
    fushen: Optional[str]  # 福神
    suici: List[str]  # 岁次
    yi: List[str]  # 宜
    ji: List[str]  # 忌
    eweek: str  # 英文星期
    emonth: str  # 英文月份
    week: str  # 星期

class DailyCalendarInfoSchema(DoonookDailyCalendarInfo,JiSuDailyCalendarInfo):
    id: Optional[int] = None
    date: str
    yi: List[str]
    ji: List[str]
    suici: List[str]

    @field_validator('yi', 'ji', 'suici', mode='before')
    @classmethod
    def parse_postgres_array(cls, value):
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            # Remove the curly braces and split by comma
            cleaned = value.strip('{}')
            if not cleaned:
                return []
            return [item.strip() for item in cleaned.split(',')]
        return value

    @field_validator('date', mode='before')
    @classmethod
    def parse_date(cls, value):
        if isinstance(value, date):
            return value.strftime("%Y-%m-%d")
        return value

    class Config:
        from_attributes = True
