from datetime import datetime

from pydantic import BaseModel


class CurrentState(BaseModel):
    count: int | None
    updated_at: datetime | None
    stale: bool
    error: str | None
    timezone: str = "Asia/Shanghai"
    polling_seconds: int = 60


class Period(BaseModel):
    start: datetime
    end: datetime
    count: int


class HistoryResult(BaseModel):
    day: str
    items: list[Period]
    total_count: int
    next_offset: int | None
    has_more: bool


class DailySummary(BaseModel):
    day: str
    weekday: int
    peak: int | None
    peak_at: datetime | None
    minimum: int | None
    mean: float | None
    observed_minutes: int
    segments: int


class SummaryResult(BaseModel):
    items: list[DailySummary]
    timezone: str = "Asia/Shanghai"


class ForecastPoint(BaseModel):
    time: datetime
    count: float
    lower: float | None
    upper: float | None


class ForecastResult(BaseModel):
    issued_at: datetime | None
    status: str
    method: str | None
    training_days: int
    validation_mae: float | None
    items: list[ForecastPoint]
    interval_minutes: int = 5
    error_band: str = "历史滚动回测绝对误差的90%分位范围，非校准置信区间"


class WeekdayStatus(BaseModel):
    weekday: int
    name: str
    training_days: int


class ModelStatus(BaseModel):
    method: str | None
    training_days: int
    minimum_training_days: int = 1
    weekdays: list[WeekdayStatus]
    factors: list[str] = [
        "日内周期",
        "周一至周日",
        "工作日与周末",
        "星期与日内周期交互",
        "近期权重",
        "今日实时偏差",
    ]
    validation_mae: float | None
    error: str | None


class QuietWindow(BaseModel):
    start: datetime
    end: datetime
    predicted_mean: float
    predicted_peak: float


class QuietResult(BaseModel):
    status: str
    windows: list[QuietWindow]
    based_on: str = "今日后续预测；未覆盖的时段不推荐"
