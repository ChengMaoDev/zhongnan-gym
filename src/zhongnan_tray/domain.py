from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Asia/Shanghai")
API_URL = "https://www.forzadata.cn/api/fitnessCenter/8840/actualNumber"
RETENTION = timedelta(days=30)
INTERVAL = 60


def now() -> datetime:
    return datetime.now(ZONE)


@dataclass(frozen=True)
class Sample:
    timestamp: int
    count: int

    @property
    def time(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp, ZONE)


@dataclass(frozen=True)
class Estimate:
    timestamp: int
    count: float
    lower: float | None = None
    upper: float | None = None


@dataclass(frozen=True)
class Prediction:
    issued_at: int
    points: tuple[Estimate, ...]
    method: str
    training_days: int
    mae: float | None = None


def day_start(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time(), ZONE)
