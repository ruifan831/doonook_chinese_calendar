from datetime import datetime
from sqlalchemy import select
import sxtwl
import httpx
from sqlalchemy.orm import Session
from chinese_calendar.utils import get_holidays,get_holiday_detail
from ..schemas.calendar import DoonookDailyCalendarInfo, JiSuDailyCalendarInfo,DailyCalendarInfoSchema
from ..core.config import settings
from ..models.calendar import DailyCalendar
import logging
import traceback

class ChineseCalendarService:
    def __init__(self):
        self._setup_mappings()
        self.api_url = "https://api.jisuapi.com/huangli/date"
        self.api_key = settings.JISU_API_KEY

    def _setup_mappings(self):
        self.Gan = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
        self.Zhi = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
        self.ShX = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]
        self.jqmc = ["冬至", "小寒", "大寒", "立春", "雨水", "惊蛰", "春分", "清明", "谷雨", "立夏",
                     "小满", "芒种", "夏至", "小暑", "大暑", "立秋", "处暑", "白露", "秋分", "寒露",
                     "霜降", "立冬", "小雪", "大雪"]
        self.ymc = ["正", "二", "三", "四", "五", "六", "七", "八", "九", "十","十一", "十二"]
        self.rmc = ["初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十",
                    "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
                    "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九", "三十"]
        self.festival_mapping = {
            "New Year's Day": "元旦",
            "Spring Festival": "春节",
            "Tomb-sweeping Day": "清明节",
            "Labour Day": "劳动节",
            "Dragon Boat Festival": "端午节",
            "National Day": "国庆节",
            "Mid-autumn Festival": "中秋节",
        }

    async def get_daily_calendar(self, date: datetime, db: Session) -> DailyCalendarInfoSchema:
        try:
            # Check database first
            select_query = select(DailyCalendar).where(DailyCalendar.date == date.date())
            db_calendar = db.execute(select_query).scalar_one_or_none()
            if db_calendar:
                logging.info(f"Found calendar in database for date: {date}")
                return self._format_calendar_response(db_calendar)

            # Calculate basic calendar info
            logging.info(f"Calculating calendar info for date: {date}")
            base_info = self._calculate_calendar_info(date)
            
            # Fetch additional info from API
            logging.info(f"Fetching API data for date: {date}")
            api_info = await self._fetch_api_data(date)
            
            # Combine and save to database
            combined_info = DailyCalendarInfoSchema(**base_info.model_dump(),**api_info.model_dump())
            logging.info(f"Combined calendar info for date: {date}")
            self._save_to_database(db,combined_info)
            
            return combined_info
            
        except Exception as e:
            error_msg = f"Error getting daily calendar for date: {date}"
            logging.error(error_msg)
            logging.error(traceback.format_exc())
            raise ValueError(error_msg) from e

    async def _fetch_api_data(self, date: datetime) -> JiSuDailyCalendarInfo:
        async with httpx.AsyncClient() as client:
            # https://api.jisuapi.com/huangli/date?appkey=yourappkey&year=2015&month=10&day=27
            params = {
                "appkey": self.api_key,
                "year": date.year,
                "month": date.month,
                "day": date.day
            }
            response = await client.get(self.api_url, params=params)
            data = response.json()
            logging.info(f"API response: {data}")
            
            if data["status"] != 0:
                raise ValueError(f"API Error: {data['msg']}")
                
            result = data["result"]
            return JiSuDailyCalendarInfo(**result)

    def _save_to_database(self, db: Session, info: DailyCalendarInfoSchema):
        calendar_entry = DailyCalendar(**info.model_dump())
        db.add(calendar_entry)
        db.commit()

    def _calculate_calendar_info(self, date: datetime) -> DoonookDailyCalendarInfo:
        try:
            day = sxtwl.fromSolar(date.year, date.month, date.day)
            
            # Get lunar date components
            lunar_month = day.getLunarMonth()
            lunar_day = day.getLunarDay()
            lunar_year = day.getLunarYear()
            is_leap_month = day.isLunarLeap()
            
            # Get solar terms
            jq = day.getJieQi()
            logging.info(f"Jie Qi: {jq}")
            solar_term = self.jqmc[jq] if jq <= 24 and jq >= 0 else None
            
            # Get heavenly stems and earthly branches for year, month, day
            year_gz = day.getYearGZ()
            month_gz = day.getMonthGZ()
            day_gz = day.getDayGZ()
            result = {
                "date": date.strftime("%Y-%m-%d"),
                "lunar_year": lunar_year,
                "lunar_month": self.ymc[lunar_month - 1],
                "lunar_day": self.rmc[lunar_day - 1],
                "is_leap_month": is_leap_month,
                "lunar_date": f"{'闰' if is_leap_month else ''}{self.ymc[lunar_month - 1]}月{self.rmc[lunar_day - 1]}",
                "solar_term": solar_term,
                "year_ganzhi": f"{self.Gan[year_gz.tg]}{self.Zhi[year_gz.dz]}",
                "month_ganzhi": f"{self.Gan[month_gz.tg]}{self.Zhi[month_gz.dz]}",
                "day_ganzhi": f"{self.Gan[day_gz.tg]}{self.Zhi[day_gz.dz]}",
            }
            return DoonookDailyCalendarInfo(**result)
            
        except Exception as e:
            error_msg = f"Error converting date to lunar calendar: {date}"
            raise ValueError(error_msg) from e


    def _get_suitable_activities(self, heavenly_stem: int, earthly_branch: int) -> list:
        # This would contain your logic for determining suitable activities
        # based on the heavenly stem and earthly branch
        return ["祭祀", "开市", "出行"]  # Example activities

    def _get_unsuitable_activities(self, heavenly_stem: int, earthly_branch: int) -> list:
        # This would contain your logic for determining unsuitable activities
        return ["动土", "安葬"]  # Example activities

    def _format_calendar_response(self, db_calendar: DailyCalendarInfoSchema) -> dict:
        # Implement the logic to format the database response into the desired format
        # This is a placeholder and should be replaced with the actual implementation
        return DailyCalendarInfoSchema.model_validate(db_calendar)

    def convert_to_lunar(self, date: datetime) -> dict:
        return self._calculate_calendar_info(date)
    
    def get_holidays(self, start_date: datetime, end_date: datetime) -> list:
        return self._get_holidays(start_date, end_date)
    
    def _get_holidays(self, start_date: datetime, end_date: datetime) -> list:
        holidays = get_holidays(start_date, end_date, True)
        holiday_details = [(holiday,get_holiday_detail(holiday)[1]) for holiday in holidays]
        holiday_list = [
            {
                "date": holiday[0],
                "name": self._get_holiday_name(holiday[1]),
            }
            for holiday in holiday_details
        ]
        return holiday_list
    
    def _get_holiday_name(self, holiday: str) -> str:
        return self.festival_mapping.get(holiday, '')
