from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np

from .domain import Estimate, Prediction, Sample, day_start
from .model import Profile, bin_samples, corrected, usable_days


@dataclass(frozen=True)
class Validation:
    alpha: float | None
    mae: float | None
    errors: tuple[float, ...]


def validate(samples: tuple[Sample, ...], days: tuple[date, ...]) -> Validation:
    if len(days) < 6:
        return Validation(None, None, ())
    candidates: list[Validation] = []
    for alpha in (None, 1.0, 10.0, 100.0):
        errors: list[float] = []
        for day in days[-3:]:
            previous = tuple(s for s in samples if s.time.date() < day)
            if not usable_days(previous):
                continue
            profile = Profile.fit(previous, alpha)
            today = tuple(s for s in samples if s.time.date() == day)
            for hour in (9, 12, 15, 18):
                issue = day_start(day) + timedelta(hours=hour)
                observed = tuple(s for s in today if s.timestamp <= issue.timestamp())
                future = tuple(
                    s
                    for s in today
                    if issue.timestamp() < s.timestamp <= issue.timestamp() + 6 * 3600
                    and profile.supported(s.time)
                )
                if not future:
                    continue
                estimates = corrected(
                    profile, tuple(s.time for s in future), observed, issue
                )
                errors.extend(
                    abs(float(predicted) - actual.count)
                    for predicted, actual in zip(estimates, future, strict=True)
                )
        if errors:
            candidates.append(
                Validation(alpha, sum(errors) / len(errors), tuple(errors))
            )
    if not candidates:
        return Validation(10.0, None, ())
    return min(
        candidates,
        key=lambda result: result.mae if result.mae is not None else float("inf"),
    )


class Forecaster:
    def __init__(self) -> None:
        self._cache_day: date | None = None
        self._profile: Profile | None = None
        self._validation = Validation(10.0, None, ())
        self._days = 0

    def predict(self, samples: tuple[Sample, ...], current: datetime) -> Prediction:
        eligible = tuple(s for s in samples if s.timestamp <= current.timestamp())
        binned = bin_samples(eligible)
        previous = tuple(s for s in binned if s.time.date() < current.date())
        days = usable_days(previous)
        if not days:
            return Prediction(int(current.timestamp()), (), "正在积累数据", len(days))
        if self._cache_day != current.date():
            self._validation = validate(previous, days)
            self._profile = Profile.fit(previous, self._validation.alpha)
            self._cache_day = current.date()
            self._days = len(days)
        profile = self._profile
        if profile is None:
            raise RuntimeError("预测模型未初始化")
        end = day_start(current.date()) + timedelta(days=1)
        stamp = (int(current.timestamp()) // 300 + 1) * 300
        times: list[datetime] = []
        while stamp < end.timestamp():
            time = datetime.fromtimestamp(stamp, current.tzinfo)
            if profile.supported(time):
                times.append(time)
            stamp += 300
        today = tuple(s for s in binned if s.time.date() == current.date())
        estimates = corrected(profile, tuple(times), today, current)
        spread = (
            float(np.quantile(self._validation.errors, 0.9))
            if self._validation.errors
            else None
        )
        points = tuple(
            Estimate(
                int(time.timestamp()),
                float(value),
                max(0.0, float(value) - spread) if spread is not None else None,
                float(value) + spread if spread is not None else None,
            )
            for time, value in zip(times, estimates, strict=True)
        )
        method = "时段均值" if self._validation.alpha is None else "周期回归"
        return Prediction(
            int(current.timestamp()), points, method, self._days, self._validation.mae
        )
