from sqlalchemy import Column, Integer, String, Date, JSON
from ..database import Base


class AstroFortune(Base):
    __tablename__ = "astro_fortunes"

    id = Column(Integer, primary_key=True, index=True)
    astroid = Column(Integer, index=True)
    astroname = Column(String)
    date = Column(Date, index=True)
    
    # Store nested JSON data for period fortunes
    year = Column(JSON,default=dict)      # 年运势
    month = Column(JSON,default=dict)     # 月运势
    week = Column(JSON,default=dict)      # 周运势
    today = Column(JSON,default=dict)     # 今日运势
    tomorrow = Column(JSON,default=dict)  # 明日运势