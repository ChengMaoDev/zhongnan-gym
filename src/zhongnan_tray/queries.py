from __future__ import annotations

import sqlite3
import threading
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import cast

from .domain import RETENTION, ZONE, Prediction, Sample, day_start, now
from .model import bin_samples, usable_days
from .records import Segment, expand, read_segments
from .schemas import (
    CurrentState,
    DailySummary,
    ForecastPoint,
    ForecastResult,
    HistoryResult,
    ModelStatus,
    Period,
    QuietResult,
    QuietWindow,
    SummaryResult,
    WeekdayStatus,
)


class SharedState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._prediction: Prediction | None = None
        self._error: str | None = None

    def update(self, prediction: Prediction | None, error: str | None = None) -> None:
        with self._lock:
            self._prediction, self._error = prediction, error

    def get(self) -> tuple[Prediction | None, str | None]:
        with self._lock:
            return self._prediction, self._error


def local_time(timestamp: int) -> datetime:
    return datetime.fromtimestamp(timestamp, ZONE)


class Queries:
    def __init__(self, path: Path, state: SharedState) -> None:
        self.path, self.state = path, state

    def _segments(self, start: datetime, end: datetime) -> tuple[Segment, ...]:
        current = now()
        with closing(sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)) as db:
            return read_segments(
                db,
                int(max(start, current - RETENTION).timestamp()),
                int(min(end, current).timestamp()),
            )

    def current(self) -> CurrentState:
        with closing(sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)) as db:
            last = cast(
                tuple[int, int] | None,
                db.execute(
                    "SELECT observed_until,count FROM samples ORDER BY observed_until DESC LIMIT 1"
                ).fetchone(),
            )
            failure = cast(
                tuple[int, str] | None,
                db.execute(
                    "SELECT timestamp,error FROM attempts ORDER BY timestamp DESC LIMIT 1"
                ).fetchone(),
            )
        error = failure[1] if failure and (not last or failure[0] > last[0]) else None
        return CurrentState(
            count=last[1] if last else None,
            updated_at=local_time(last[0]) if last else None,
            stale=not last or now().timestamp() - last[0] > 180 or error is not None,
            error=error,
        )

    def history(self, day: date, offset: int, limit: int) -> HistoryResult:
        segments = self._segments(
            day_start(day), day_start(day) + timedelta(days=1) - timedelta(seconds=1)
        )
        items = [
            Period(start=local_time(s.start), end=local_time(s.end), count=s.count)
            for s in segments[offset : offset + limit]
        ]
        more = offset + limit < len(segments)
        return HistoryResult(
            day=day.isoformat(),
            items=items,
            total_count=len(segments),
            next_offset=offset + limit if more else None,
            has_more=more,
        )

    def summaries(self, days: int) -> SummaryResult:
        current = now()
        summaries: list[DailySummary] = []
        for offset in range(days):
            day = current.date() - timedelta(days=offset)
            segments = self._segments(
                day_start(day),
                day_start(day) + timedelta(days=1) - timedelta(seconds=1),
            )
            samples = expand(segments)
            peak = max(samples, key=lambda s: s.count) if samples else None
            summaries.append(
                DailySummary(
                    day=day.isoformat(),
                    weekday=day.weekday(),
                    peak=peak.count if peak else None,
                    peak_at=peak.time if peak else None,
                    minimum=min((s.count for s in samples), default=None),
                    mean=sum(s.count for s in samples) / len(samples)
                    if samples
                    else None,
                    observed_minutes=len({s.timestamp // 60 for s in samples}),
                    segments=len(segments),
                )
            )
        return SummaryResult(items=summaries)

    def forecast(self) -> ForecastResult:
        prediction, error = self.state.get()
        if prediction is None:
            return ForecastResult(
                issued_at=None,
                status=error or "正在准备模型",
                method=None,
                training_days=0,
                validation_mae=None,
                items=[],
            )
        current = now()
        stale = current.timestamp() - prediction.issued_at > 180
        items = (
            []
            if stale or error
            else [
                ForecastPoint(
                    time=local_time(p.timestamp),
                    count=p.count,
                    lower=p.lower,
                    upper=p.upper,
                )
                for p in prediction.points
                if p.timestamp > current.timestamp()
                and local_time(p.timestamp).date() == current.date()
            ]
        )
        status = error or (
            "预测已过期，等待应用更新"
            if stale
            else (
                "可用"
                if items
                else (
                    "记录1个有效训练日后开始预测"
                    if not prediction.training_days
                    else "剩余时段无历史覆盖"
                )
            )
        )
        return ForecastResult(
            issued_at=local_time(prediction.issued_at),
            status=status,
            method=prediction.method,
            training_days=prediction.training_days,
            validation_mae=prediction.mae,
            items=items,
        )

    def model(self) -> ModelStatus:
        prediction, error = self.state.get()
        current = now()
        samples: tuple[Sample, ...] = expand(
            self._segments(
                current - RETENTION, day_start(current.date()) - timedelta(seconds=1)
            )
        )
        days = usable_days(bin_samples(samples))
        weekdays = [
            WeekdayStatus(
                weekday=day,
                name="周" + "一二三四五六日"[day],
                training_days=sum(d.weekday() == day for d in days),
            )
            for day in range(7)
        ]
        return ModelStatus(
            method=prediction.method if prediction else None,
            training_days=len(days),
            weekdays=weekdays,
            validation_mae=prediction.mae if prediction else None,
            error=error,
        )

    def quiet(self, minutes: int, limit: int) -> QuietResult:
        forecast = self.forecast()
        length = minutes // 5
        windows: list[QuietWindow] = []
        points = forecast.items
        for index in range(len(points) - length + 1):
            group = points[index : index + length]
            if (group[-1].time - group[0].time).total_seconds() != (length - 1) * 300:
                continue
            windows.append(
                QuietWindow(
                    start=group[0].time,
                    end=group[-1].time + timedelta(minutes=5),
                    predicted_mean=sum(p.count for p in group) / length,
                    predicted_peak=max(p.count for p in group),
                )
            )
        selected: list[QuietWindow] = []
        for window in sorted(windows, key=lambda w: w.predicted_mean):
            if all(
                window.end <= other.start or window.start >= other.end
                for other in selected
            ):
                selected.append(window)
            if len(selected) == limit:
                break
        return QuietResult(status=forecast.status, windows=selected)
