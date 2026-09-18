"""Generate and validate fortune text without changing the public API schema."""

import asyncio
from datetime import date, timedelta
import json
from typing import Annotated
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError

from ..core.config import CalendarSettings
from ..schemas.astro import AstroFortuneSchema
from .astro_basis import EphemerisError, build_basis, prompt_basis

Text = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=300),
]


class FortuneGenerationError(Exception):
    """A retryable provider failure; never contains credentials or model output."""


class GeneratedPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: Text
    money: Text
    career: Text
    love: Text
    health: Text


class GeneratedDay(GeneratedPeriod):
    presummary: Text
    star: Text
    color: Text
    number: Text


class GeneratedFortune(BaseModel):
    model_config = ConfigDict(extra="forbid")
    year: GeneratedPeriod
    month: GeneratedPeriod
    week: GeneratedPeriod
    today: GeneratedDay
    tomorrow: GeneratedDay


def parse_generated_fortune(content: str) -> GeneratedFortune:
    """Handle only observed MLX framing; never extract arbitrary JSON snippets."""
    content = content.strip().removesuffix("</think>").rstrip()
    try:
        return GeneratedFortune.model_validate_json(content)
    except ValidationError:
        # MLX can return a complete JSON draft, then </think>, then the final
        # JSON. raw_decode respects marker literals inside JSON strings. Both
        # objects must independently satisfy the schema; all other tails fail.
        draft, end = json.JSONDecoder().raw_decode(content)
        remainder = content[end:].strip()
        if not remainder.startswith("</think>"):
            raise ValueError("Unexpected trailing content") from None
        GeneratedFortune.model_validate(draft)
        return GeneratedFortune.model_validate_json(
            remainder[len("</think>") :].strip()
        )


class QwenFortuneGenerator:
    def __init__(self, settings: CalendarSettings):
        self.settings = settings
        self.basis = None

    async def generate(
        self, astroid: int, name: str, target: date
    ) -> AstroFortuneSchema:
        base = self.settings.QWEN_BASE_URL.rstrip("/")
        url = urlsplit(base)
        key = self.settings.QWEN_LAN_API_KEY.get_secret_value()
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or not key
            or not self.settings.QWEN_MODEL.strip()
        ):
            raise FortuneGenerationError("星座运势生成服务尚未配置")

        try:
            self.basis = await asyncio.to_thread(
                build_basis,
                astroid,
                target,
                self.settings.ASTRO_EPHEMERIS_PATH,
                self.settings.TIMEZONE,
            )
        except EphemerisError:
            raise FortuneGenerationError("本地星历不可用，无法生成运势") from None

        tomorrow = target + timedelta(days=1)
        monday = target - timedelta(days=target.weekday())
        dates = {
            "today": target.isoformat(),
            "tomorrow": tomorrow.isoformat(),
            "week": f"{monday.isoformat()}至{(monday + timedelta(days=6)).isoformat()}",
            "month": target.strftime("%Y-%m"),
            "year": str(target.year),
        }
        prompt = (
            f"为{name}生成简体中文娱乐星座运势。日期范围："
            + json.dumps(dates, ensure_ascii=False)
            + "。以下是代码计算的占星规则依据（分数为1至5，3为中性，不是概率）："
            + json.dumps(
                prompt_basis(self.basis), ensure_ascii=False, separators=(",", ":")
            )
            + "。只能依据对应时期的评分和因素给建议；低分偏谨慎，高分偏主动，无因素时用中性建议。"
            "这些是当地每日中午的采样，不是整期持续相位；不要把某天因素说成整月整年都有。"
            "不用向用户复述星体、相位、度数、宫位或分数，转成简短日常建议，不添加其他天象。"
            "star/color/number是兼容旧界面的娱乐装饰，不属于天文事实。"
            "各时期内容应有区别：日运聚焦当天行动，周运关注安排与沟通，"
            "月运关注阶段计划，年运关注长期习惯与方向。"
            "summary写100至150个汉字，用3至5句话说明整体节奏、重点和行动建议。"
            "money/career/love/health各写60至100个汉字，用2至4句话，"
            "包含一个可能遇到的日常场景、一条具体可执行建议及需要留意的事项。"
            "场景须用条件或可能性表达，不把用户经历当作已知事实。"
            "避免空泛套话、重复凑字和不同维度复用同一段话；不要为了丰富内容编造天象。"
            "presummary保持15至30个汉字的一句话提示；star/color/number只填简短值。"
            "只输出一个JSON对象，顶层必须有year、month、week、today、tomorrow。"
            "year/month/week各有summary、money、career、love、health五个非空字符串。"
            "today/tomorrow除了上述五个字段，还要有presummary（一句提示）、"
            "star（贵人星座）、color（幸运颜色）、number（幸运数字字符串）。"
            "不要添加date、id或其他字段，不要Markdown，不要解释。"
            "\n输出必须符合以下JSON Schema："
            + json.dumps(GeneratedFortune.model_json_schema(), ensure_ascii=False)
        )
        payload = {
            "model": self.settings.QWEN_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "你撰写温和、实用的娱乐星座文案。"
                    "不声称真实预测，不编造天象依据，不承诺收益、疾病诊断或命定事件。"
                    "健康仅提供日常作息建议，财务仅提供理性预算建议。严格遵守JSON字段要求。",
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "reasoning_effort": "none",
            "temperature": 0.3,
            "max_tokens": 6500,
        }
        try:
            # This backend's MLX package lacks xgrammar: validate plain JSON here
            # rather than relying on unsupported response_format/json_schema.
            async with asyncio.timeout(self.settings.QWEN_TIMEOUT_SECONDS):
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(
                        self.settings.QWEN_TIMEOUT_SECONDS, connect=5
                    ),
                    trust_env=False,
                ) as client:
                    response = await client.post(
                        base + "/chat/completions",
                        json=payload,
                        headers={"Authorization": "Bearer " + key},
                    )
                    response.raise_for_status()
                    choice = response.json()["choices"][0]
                    if choice.get("finish_reason") != "stop":
                        raise ValueError("Incomplete generation")
                    content = choice["message"]["content"]
                    if not isinstance(content, str) or len(content) > 20000:
                        raise ValueError("Invalid content")
                    generated = parse_generated_fortune(content)
        except (
            httpx.HTTPError,
            TimeoutError,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
            ValidationError,
        ):
            raise FortuneGenerationError("星座运势生成暂不可用，请稍后重试") from None

        data = generated.model_dump()
        for period, text in dates.items():
            data[period]["date"] = text
        data["week"]["job"] = data["week"]["career"]
        # Dates, sign and name are supplied by our code, never trusted to the LLM.
        return AstroFortuneSchema(astroid=astroid, astroname=name, date=target, **data)
