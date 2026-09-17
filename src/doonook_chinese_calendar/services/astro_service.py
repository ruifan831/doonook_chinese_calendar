import asyncio
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from ..models.astro import AstroFortune
from datetime import date
from typing import Optional
from ..core.config import CalendarSettings, settings
from .qwen_fortune import FortuneGenerationError, QwenFortuneGenerator
from ..schemas.astro import AstroFortuneSchema


class AstroService:
    def __init__(self, config: Optional[CalendarSettings] = None):
        self.config = config or settings
        self._setup_mappings()

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
            12: "双鱼座",
        }

    async def get_daily_fortune(
        self, astroid: int, date_param: date, db: Session
    ) -> AstroFortuneSchema:
        """Reuse persisted fortunes; generate only on a cache miss.

        This method owns its transaction and must receive a writer DB session.
        PostgreSQL transaction locks serialize the same sign/date across workers.
        """
        if astroid not in self.astro:
            raise ValueError("astroid must be between 1 and 12")
        query = (
            select(AstroFortune)
            .where(AstroFortune.astroid == astroid, AstroFortune.date == date_param)
            .order_by(AstroFortune.id)
            .limit(1)
        )
        try:
            cached = db.execute(query).scalar_one_or_none()
            if cached:
                return AstroFortuneSchema.model_validate(cached)

            if db.get_bind().dialect.name == "postgresql":
                lock_key = date_param.toordinal() * 16 + astroid
                try:
                    async with asyncio.timeout(self.config.QWEN_TIMEOUT_SECONDS):
                        while not db.execute(
                            text("SELECT pg_try_advisory_xact_lock(:namespace, :key)"),
                            {"namespace": 20260917, "key": lock_key},
                        ).scalar():
                            await asyncio.sleep(0.1)
                except TimeoutError:
                    raise FortuneGenerationError(
                        "星座运势正在生成，请稍后重试"
                    ) from None
                cached = db.execute(query).scalar_one_or_none()
                if cached:
                    return AstroFortuneSchema.model_validate(cached)

            generator = QwenFortuneGenerator(self.config)
            generated = await generator.generate(
                astroid, self.astro[astroid], date_param
            )
            if generated is None:
                raise FortuneGenerationError("星座运势生成暂不可用，请稍后重试")
            payload = generated.model_dump()
            payload.update(
                astroid=astroid, astroname=self.astro[astroid], date=date_param
            )
            validated = AstroFortuneSchema.model_validate(payload)
            record = validated.model_dump(exclude={"id"})
            if generator.basis is not None:
                for period, evidence in generator.basis.items():
                    record[period]["_basis"] = evidence
            saved = await self.create_fortune(astroid, record, db)
            return AstroFortuneSchema.model_validate(saved)
        finally:
            # Covers provider failures and client cancellation, releasing the
            # advisory transaction lock without persisting partial model output.
            db.rollback()

    async def create_fortune(
        self, astroid: int, fortune_data: dict, db: Session
    ) -> AstroFortune:
        """Create a new fortune for an astrology sign"""
        try:
            fortune = AstroFortune(**fortune_data)
            db.add(fortune)
            db.commit()
            db.refresh(fortune)
            return fortune
        except Exception as e:
            error_msg = f"Error saving astrology data for astroid {astroid} to database"
            db.rollback()  # Roll back the transaction on error
            raise ValueError(error_msg) from e
