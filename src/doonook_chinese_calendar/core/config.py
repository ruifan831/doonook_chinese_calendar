from pydantic_settings import BaseSettings

class CalendarSettings(BaseSettings):
    TIMEZONE: str = "Asia/Shanghai"
    LANGUAGE: str = "zh_CN"
    JISU_API_KEY: str
    
    # Database settings
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "chinese_calendar"
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore"  # This will ignore extra fields from other settings 


settings = CalendarSettings()
