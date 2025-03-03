from sqlalchemy import Boolean, Column, Integer, String, Date, JSON
from ..core.database import Base


class DailyCalendar(Base):
    __tablename__ = "daily_calendars"

    id = Column(Integer, primary_key=True, index=True)
    # 极速 field
    year = Column(String)
    month = Column(String)
    day = Column(String)
    yangli = Column(String)
    nongli = Column(String)
    star = Column(String)   # 星座
    taishen = Column(String)  # 胎神
    wuxing = Column(String)  # 五行
    chong = Column(String)  # 冲
    sha = Column(String)  # 煞
    shengxiao = Column(String)  # 生肖
    jiri = Column(String)  # 吉日
    zhiri = Column(String)  # 值日天神
    xiongshen = Column(String)  # 凶神
    jishenyiqu = Column(String)  # 吉神宜趋
    caishen = Column(String)  # 财神
    xishen = Column(String)  # 喜神
    fushen = Column(String)  # 福神
    suici = Column(String)  # 岁次
    yi = Column(String)  # 宜
    ji = Column(String)  # 忌
    eweek = Column(String)  # 英文星期
    emonth = Column(String)  # 英文月份
    week = Column(String)  # 星期

    # Self calendar field
    date = Column(Date, unique=True, index=True)
    year_ganzhi = Column(String)
    month_ganzhi = Column(String)
    day_ganzhi = Column(String)
    lunar_year = Column(String)
    lunar_month = Column(String)
    lunar_day = Column(String)
    lunar_date = Column(String)
    solar_term = Column(String) # 节气
    is_leap_month = Column(Boolean) # 是否闰月
