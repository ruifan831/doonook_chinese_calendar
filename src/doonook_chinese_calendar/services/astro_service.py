import logging
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models.astro import AstroFortune
from datetime import date
from typing import Any, List, Optional
from ..core.config import settings
from ..schemas.astro import AstroFortuneSchema
import traceback

logger = logging.getLogger(__name__)


class AstroService:
    def __init__(self):
        self._setup_mappings()
        self.api_url = "https://api.jisuapi.com/astro/fortune"
        self.api_key = settings.JISU_API_KEY
    
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
            api_data = await self._fetch_api_data(astroid, today)
            
            if api_data:
                # Add required fields before creating the schema
                api_data["astroid"] = astroid  # Ensure astroid is a string
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
                    logging.error(f"Data causing error: {api_data}")
                    logging.error(traceback.format_exc())
                    raise ValueError(f"Schema validation error: {str(validation_error)}")
            
            return None
        except Exception as e:
            error_msg = f"Error getting fortune for astroid {astroid}"
            logging.error(error_msg)
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
            logging.error(error_msg)
            logging.error(traceback.format_exc())
            db.rollback()  # Roll back the transaction on error
            raise ValueError(error_msg) from e
    
    async def _fetch_api_data(self, astroid: int, date: date) -> dict:
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
                # Add astroname from our mapping
                result["astroname"] = self.astro.get(astroid, "Unknown")
                
                return result
        except Exception as e:
            error_msg = f"Error fetching astrology data for astroid {astroid} on date {date}"
            logging.error(error_msg)
            logging.error(traceback.format_exc())
            raise ValueError(error_msg) from e
            
            