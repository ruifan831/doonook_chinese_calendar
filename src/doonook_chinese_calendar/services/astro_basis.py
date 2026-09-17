"""Offline ephemeris + versioned editorial rules for generic Sun-sign fortunes.

Positions are astronomical calculations. Scores are explicitly our entertainment
rules, not scientific predictions or personalized natal-chart transits.
"""

from calendar import monthrange
from datetime import date, datetime, time, timedelta
from functools import lru_cache
import hashlib
from itertools import combinations
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from skyfield.api import load, load_file
from skyfield.framelib import ecliptic_frame

RULE_VERSION = "solar-whole-sign-v1"
SIGNS = (
    "白羊座",
    "金牛座",
    "双子座",
    "巨蟹座",
    "狮子座",
    "处女座",
    "天秤座",
    "天蝎座",
    "射手座",
    "摩羯座",
    "水瓶座",
    "双鱼座",
)
BODIES = {
    "sun": ("太阳", "sun"),
    "moon": ("月亮", "moon"),
    "mercury": ("水星", "mercury"),
    "venus": ("金星", "venus"),
    "mars": ("火星", "mars barycenter"),
    "jupiter": ("木星", "jupiter barycenter"),
    "saturn": ("土星", "saturn barycenter"),
}
# Product-defined orbs, not an astronomical measurement uncertainty.
ASPECTS = (
    ("conjunction", "合相", 0, 8, 0),
    ("sextile", "六合", 60, 4, 0.6),
    ("square", "刑相", 90, 6, -1),
    ("trine", "拱相", 120, 6, 1),
    ("opposition", "冲相", 180, 8, -1),
)
DOMAINS = {
    "love": ({"moon", "venus"}, {5, 7}),
    "career": ({"sun", "mercury", "mars", "saturn"}, {6, 10}),
    "money": ({"venus", "jupiter", "saturn"}, {2, 8}),
    "health": ({"sun", "moon", "mars"}, {1, 6, 12}),
}
HOUSE_IMPACT = {
    "sun": 0.2,
    "moon": 0.1,
    "mercury": 0.2,
    "venus": 0.35,
    "mars": -0.2,
    "jupiter": 0.35,
    "saturn": -0.35,
}


class EphemerisError(Exception):
    """Missing/invalid local ephemeris or unsupported dates; never use random fallback."""


def angular_distance(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def find_aspect(a: float, b: float):
    separation = angular_distance(a, b)
    for name, label, angle, allowance, effect in ASPECTS:
        orb = abs(separation - angle)
        if orb <= allowance:
            return dict(
                name=name,
                label=label,
                angle=angle,
                orb=orb,
                allowance=allowance,
                effect=effect,
            )
    return None


def period_ranges(target: date):
    tomorrow = target + timedelta(days=1)
    monday = target - timedelta(days=target.weekday())
    return {
        "today": (target, target),
        "tomorrow": (tomorrow, tomorrow),
        "week": (monday, monday + timedelta(days=6)),
        "month": (
            target.replace(day=1),
            target.replace(day=monthrange(target.year, target.month)[1]),
        ),
        "year": (date(target.year, 1, 1), date(target.year, 12, 31)),
    }


@lru_cache(maxsize=2)
def _kernel(path: str):
    file = (
        Path(path).expanduser()
        if path.strip()
        else Path(__file__).resolve().parents[1] / "data" / "de440s.bsp"
    )
    if not file.is_file():
        raise EphemerisError("本地星历未配置")
    try:
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        ephemeris = load_file(str(file))  # Never downloads data.
        timescale = load.timescale(builtin=True)  # Never fetches leap-second data.
        return ephemeris, timescale, digest
    except Exception:
        raise EphemerisError("本地星历不可用") from None


@lru_cache(maxsize=8)
def _year_positions(path: str, year: int, timezone: str):
    ephemeris, timescale, _ = _kernel(path)
    start, end = date(year, 1, 1), date(year, 12, 31)
    dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    moments = [datetime.combine(day, time(12), ZoneInfo(timezone)) for day in dates]
    t = timescale.from_datetimes(moments)
    observer = ephemeris["earth"].at(t)
    series = {}
    for body, (_, key) in BODIES.items():
        _, longitude, _ = (
            observer.observe(ephemeris[key]).apparent().frame_latlon(ecliptic_frame)
        )
        series[body] = longitude.degrees % 360
    return {
        day: {body: float(values[i]) for body, values in series.items()}
        for i, day in enumerate(dates)
    }


def daily_rules(positions: dict, astroid: int):
    """Noon snapshot: transit-to-transit aspects + solar whole-sign placements."""
    if astroid not in range(1, 13):
        raise ValueError("astroid must be between 1 and 12")
    houses = {
        body: (int(lon // 30) - (astroid - 1)) % 12 + 1
        for body, lon in positions.items()
    }
    factors = {domain: [] for domain in DOMAINS}
    for one, two in combinations(BODIES, 2):
        aspect = find_aspect(positions[one], positions[two])
        if not aspect:
            continue
        effect = aspect["effect"]
        if aspect["name"] == "conjunction":
            # Conjunction is not uniformly "good": pair-specific editorial rule.
            effect = (
                -0.6
                if {one, two} & {"mars", "saturn"}
                else 0.6 if {one, two} & {"venus", "jupiter"} else 0
            )
        strength = 1 - aspect["orb"] / aspect["allowance"]
        for domain, (relevant, _) in DOMAINS.items():
            if not {one, two} & relevant:
                continue
            factors[domain].append(
                {
                    "id": f"aspect:{one}:{two}:{aspect['name']}",
                    "kind": "aspect",
                    "label": f"{BODIES[one][0]}与{BODIES[two][0]}呈{aspect['label']}",
                    "orb_degrees": round(aspect["orb"], 4),
                    "contribution": effect * strength,
                }
            )
    for domain, (relevant, active_houses) in DOMAINS.items():
        for body in sorted(relevant):
            if houses[body] in active_houses:
                factors[domain].append(
                    {
                        "id": f"house:{body}:{houses[body]}",
                        "kind": "solar_house",
                        "label": f"{BODIES[body][0]}位于{SIGNS[int(positions[body] // 30)]}，太阳整宫第{houses[body]}宫",
                        "contribution": HOUSE_IMPACT[body],
                    }
                )
    return factors


def build_basis(
    astroid: int, target: date, path: str, timezone="Asia/Shanghai"
) -> dict:
    if not 1900 <= target.year <= 2099:
        raise EphemerisError("星历支持的请求年份为1900至2099")
    try:
        _, _, digest = _kernel(path)
        ranges = period_ranges(target)
        days = sorted(
            {
                start + timedelta(days=i)
                for start, end in ranges.values()
                for i in range((end - start).days + 1)
            }
        )
        positions = {
            day: _year_positions(path, day.year, timezone)[day] for day in days
        }
        rules = {day: daily_rules(positions[day], astroid) for day in days}
        output = {}
        for period, (start, end) in ranges.items():
            samples = [start + timedelta(days=i) for i in range((end - start).days + 1)]
            categories = {}
            for domain in DOMAINS:
                grouped = {}
                daily_totals = []
                for day in samples:
                    day_factors = rules[day][domain]
                    daily_totals.append(
                        max(-2, min(2, sum(f["contribution"] for f in day_factors)))
                    )
                    for f in day_factors:
                        key = f["id"]
                        if key not in grouped:
                            grouped[key] = dict(
                                f, observed_days=0, total=0, sample_date=day.isoformat()
                            )
                        group = grouped[key]
                        group["observed_days"] += 1
                        group["total"] += f["contribution"]
                        if abs(f["contribution"]) > abs(group["contribution"]):
                            group.update(f, sample_date=day.isoformat())
                raw = 3 + sum(daily_totals) / len(samples)
                evidence = []
                for group in grouped.values():
                    group["mean_contribution"] = round(
                        group.pop("total") / len(samples), 4
                    )
                    group.pop("contribution")
                    evidence.append(group)
                evidence.sort(key=lambda f: (-abs(f["mean_contribution"]), f["id"]))
                categories[domain] = {
                    "score": max(1, min(5, math.floor(raw + 0.5))),
                    "raw_score": round(raw, 4),
                    "factors": evidence,
                }
            output[period] = {
                "rule_version": RULE_VERSION,
                "ephemeris": "JPL SPK",
                "ephemeris_sha256": digest,
                "zodiac": "tropical",
                "frame": "geocentric apparent; true ecliptic/equinox of date",
                "scope": "generic Sun-sign; not a natal chart",
                "astroid": astroid,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "sampling": f"daily 12:00 {timezone}; snapshots, not exact aspect events",
                "sample_count": len(samples),
                "categories": categories,
            }
            if period in {"today", "tomorrow"}:
                output[period]["positions"] = {
                    body: {
                        "longitude": round(lon, 6),
                        "sign": SIGNS[int(lon // 30)],
                        "solar_house": (int(lon // 30) - astroid + 1) % 12 + 1,
                    }
                    for body, lon in positions[start].items()
                }
        return output
    except EphemerisError:
        raise
    except Exception:
        raise EphemerisError("星历计算失败") from None


def prompt_basis(basis: dict) -> dict:
    """Small evidence digest; full deterministic provenance stays in the DB."""
    return {
        period: {
            "range": f"{item['start']}至{item['end']}",
            "sample_count": item["sample_count"],
            **{
                domain: {
                    "score": category["score"],
                    "factors": [
                        {
                            key: factor[key]
                            for key in ("label", "sample_date", "observed_days")
                        }
                        for factor in category["factors"][:2]
                    ],
                }
                for domain, category in item["categories"].items()
            },
        }
        for period, item in basis.items()
    }
