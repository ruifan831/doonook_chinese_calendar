from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr, model_validator
from sqlalchemy.engine import URL


class CalendarSettings(BaseSettings):
    TIMEZONE: str = "Asia/Shanghai"
    LANGUAGE: str = "zh_CN"
    # Used only by the separate huangli date service, never astrology.
    JISU_API_KEY: str = ""
    QWEN_BASE_URL: str = ""
    QWEN_LAN_API_KEY: SecretStr = SecretStr("")
    QWEN_MODEL: str = ""
    QWEN_TIMEOUT_SECONDS: float = Field(default=120, gt=0, le=600)
    # HTTP requests must not wait for local model inference. CLI prefetch still generates.
    ASTRO_GENERATE_ON_REQUEST: bool = False
    # Optional override; empty uses the ephemeris distributed inside the package.
    ASTRO_EPHEMERIS_PATH: str = ""

    # Database settings
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "chinese_calendar"
    # Same topology variables as doonook_common; POSTGRES_HOST stays local.
    DOONOOK_NODE_ROLE: Literal["primary", "replica"] = "primary"
    REMOTE_WRITER_HOST: str | None = None

    @model_validator(mode="after")
    def require_remote_writer(self):
        if self.DOONOOK_NODE_ROLE == "replica" and not (
            self.REMOTE_WRITER_HOST and self.REMOTE_WRITER_HOST.strip()
        ):
            raise ValueError("replica 节点必须配置 REMOTE_WRITER_HOST")
        return self

    @property
    def WRITER_DATABASE_URL(self) -> URL:
        host = (
            self.REMOTE_WRITER_HOST
            if self.DOONOOK_NODE_ROLE == "replica"
            else self.POSTGRES_HOST
        )
        return URL.create(
            "postgresql",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=host,
            port=int(self.POSTGRES_PORT),
            database=self.POSTGRES_DB,
        )

    @property
    def DATABASE_URL(self) -> str:
        # Backwards compatibility, including migrations: always target writer.
        return self.WRITER_DATABASE_URL.render_as_string(hide_password=False)

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )


settings = CalendarSettings()
