import logging
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models.astro import AstroFortune
from datetime import date
from typing import Any, List, Optional
from ..core.config import settings
from ..schemas.astro import AstroFortuneSchema, JiSuFortuneSchema
import traceback

logger = logging.getLogger(__name__)


class AstroService:
    def __init__(self):
        self._setup_mappings()
        self.api_url = "https://api.jisuapi.com/astro/fortune"
        self.api_key = settings.JISU_API_KEY
        self.juhe_api_key = settings.JUHE_API_KEY
    
    def _setup_mappings(self) -> None:
        self.astro = {
            1: "白羊座",
            2: "金牛座",
            3: "双子座",
            4: "巨蟹座",
            5: "狮子座",
            6: "处女座",
            7: "天秤座",
            8: "天蝎座",
            9: "射手座",
            10: "摩羯座",
            11: "水瓶座",
            12: "双鱼座"
        }
        
    
    async def get_daily_fortune(self, astroid: int, date_param: date, db: Session) -> AstroFortuneSchema:
        """Get daily fortune for an astrology sign"""
        try:  
            # Check if we have fortune in database
            today = date_param
            select_query = select(AstroFortune).where(
                AstroFortune.astroid == astroid,
                AstroFortune.date == today
            )
            db_fortune = db.execute(select_query).scalar()
            
            if db_fortune:
                logger.debug(f"Found fortune in database for astroid {astroid} on {today}")
                return AstroFortuneSchema.model_validate(db_fortune)
            
            # Fetch from API if not in database
            logger.debug(f"Fetching fortune from API for astroid {astroid}")
            api_data: JiSuFortuneSchema = await self._fetch_api_data(astroid, today)
            
            if api_data:
                # Add required fields before creating the schema
                api_data.astroid = astroid  # Ensure astroid is a string
                api_data= api_data.model_dump()
                api_data["date"] = today  # Add the date field
                
                # Create database record
                await self.create_fortune(astroid, api_data, db)
                
                try:
                    # Create schema from validated data
                    fortune_schema = AstroFortuneSchema.model_validate(api_data)
                    return fortune_schema
                except Exception as validation_error:
                    # Log detailed validation error
                    logging.error(f"Schema validation error: {str(validation_error)}")
                    raise ValueError(f"Schema validation error: {str(validation_error)}")
            
            return None
        except Exception as e:
            error_msg = f"Error getting fortune for astroid {astroid}"
            logging.error(traceback.format_exc())
            raise ValueError(error_msg) from e

    async def create_fortune(self, astroid: int, fortune_data: dict, db: Session) -> AstroFortune:
        """Create a new fortune for an astrology sign"""
        try:
            fortune = AstroFortune(
                **fortune_data
            )
            db.add(fortune)
            db.commit()
            db.refresh(fortune)
            return fortune
        except Exception as e:
            error_msg = f"Error saving astrology data for astroid {astroid} to database"
            db.rollback()  # Roll back the transaction on error
            raise ValueError(error_msg) from e
    
    async def _fetch_api_data(self, astroid: int, date: date) -> JiSuFortuneSchema:
        """Fetch fortune data from API"""
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "appkey": self.api_key, 
                    "astroid": astroid,
                    "date": date.strftime("%Y-%m-%d")
                }
                response = await client.get(self.api_url, params=params)
                data = response.json()
                
                if data["status"] != 0:
                    raise ValueError(f"API Error: {data['msg']}")
                
                result = data["result"]
                jisu_fortune = JiSuFortuneSchema.model_validate(result)
                if jisu_fortune.check_year_fortune_empty():
                    year_data = await self.get_fortune_by_type(astroid, "year")
                    jisu_fortune.year.career = "".join(year_data.get("career", []))
                    jisu_fortune.year.money = "".join(year_data.get("finance", []))
                    jisu_fortune.year.love = "".join(year_data.get("love", []))
                    jisu_fortune.year.health = "".join(year_data.get("health", []))
                if jisu_fortune.check_month_fortune_empty():
                    month_data = await self.get_fortune_by_type(astroid, "month")
                    jisu_fortune.month.summary = month_data.get("all", "")
                    jisu_fortune.month.health = month_data.get("health", "")
                    jisu_fortune.month.love = month_data.get("love", "")
                    jisu_fortune.month.money = month_data.get("money", "")
                    jisu_fortune.month.career = month_data.get("work", "")
                if jisu_fortune.check_week_fortune_empty():
                    week_data = await self.get_fortune_by_type(astroid, "week")
                    jisu_fortune.week.health = week_data.get("health", "")
                    jisu_fortune.week.career = week_data.get("work", "")
                    jisu_fortune.week.love = week_data.get("love", "")
                    jisu_fortune.week.money = week_data.get("money", "")
                
                # Add astroname from our mapping
                jisu_fortune.astroname = self.astro.get(astroid, "Unknown")
                
                return jisu_fortune
        except Exception as e:
            error_msg = f"Error fetching astrology data for astroid {astroid} on date {date}"
            logging.error(error_msg)
            raise ValueError(error_msg) from e


    async def get_fortune_by_type(self, astroid: int, period: str):
        async with httpx.AsyncClient() as client:
            apiUrl = 'http://web.juhe.cn/constellation/getAll'
            requestParams = {
                'key': self.juhe_api_key,
                'consName': self.astro.get(astroid, "狮子座"),
                'type': period,
            }
            response = await client.get(apiUrl, params=requestParams)
            data = response.json()
            return data
            