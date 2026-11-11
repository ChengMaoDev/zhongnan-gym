from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from math import exp, pi

import numpy as np
from numpy.typing import NDArray

from .domain import Sample

Array = NDArray[np.float64]


def features(times: tuple[datetime, ...]) -> Array:
    rows: list[list[float]] = []
    for time in times:
        angle = (time.hour * 60 + time.minute) * 2 * pi / 1440
        row: list[float] = [1.0]
        for harmonic in range(1, 7):
            row.extend(
                [float(np.sin(harmonic * angle)), float(np.cos(harmonic * angle))]
            )
        row.extend(float(time.weekday() == day) for day in range(7))
        weekend = float(time.weekday() >= 5)
        for harmonic in range(1, 3):
            row.extend(
                [
                    weekend * float(np.sin(harmonic * angle)),
                    weekend * float(np.cos(harmonic * angle)),
                ]
            )
        for weekday in range(7):
            for harmonic in range(1, 3):
                row.extend(
                    [
                        float(time.weekday() == weekday)
                        * float(np.sin(harmonic * angle)),
                        float(time.weekday() == weekday)
                        * float(np.cos(harmonic * angle)),
                    ]
                )
        rows.append(row)
    return np.asarray(rows, dtype=np.float64).reshape((-1, 52))


def bin_samples(samples: tuple[Sample, ...]) -> tuple[Sample, ...]:
    bins: dict[int, list[Sample]] = defaultdict(list)
    for sample in samples:
        bins[sample.timestamp // 300 * 300].append(sample)
    return tuple(
        Sample(
            max(sample.timestamp for sample in values),
            round(sum(sample.count for sample in values) / len(values)),
        )
        for _, values in sorted(bins.items())
    )


def usable_days(samples: tuple[Sample, ...]) -> tuple[date, ...]:
    days: dict[date, list[int]] = defaultdict(list)
    for sample in samples:
        days[sample.time.date()].append(sample.timestamp)
    return tuple(
        day
        for day, stamps in sorted(days.items())
        if len(stamps) >= 48 and max(stamps) - min(stamps) >= 6 * 3600
    )


@dataclass(frozen=True)
class Profile:
    coefficients: Array | None
    supported_slots: frozenset[int]
    means: tuple[tuple[float, ...], ...]

    @classmethod
    def fit(cls, samples: tuple[Sample, ...], alpha: float | None) -> Profile:
        days: dict[int, set[date]] = defaultdict(set)
        nearby: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for sample in samples:
            time = sample.time
            slot = (time.hour * 60 + time.minute) // 5
            for target in range(max(0, slot - 3), min(288, slot + 4)):
                days[target].add(time.date())
                nearby[target].append((time.weekday(), sample.count))
        supported = frozenset(days)
        means: list[tuple[float, ...]] = []
        for weekday in range(7):
            values: list[float] = []
            for slot in range(288):
                pool = nearby[slot]
                matching = [count for day, count in pool if day == weekday]
                counts = (
                    matching if len(matching) >= 4 else [count for _, count in pool]
                )
                values.append(sum(counts) / len(counts) if counts else 0.0)
            means.append(tuple(values))
        if alpha is None:
            return cls(None, supported, tuple(means))
        design = features(tuple(sample.time for sample in samples))
        targets = np.asarray([sample.count for sample in samples], dtype=np.float64)
        newest = max(sample.timestamp for sample in samples)
        weights = np.sqrt(
            np.asarray(
                [exp(-(newest - sample.timestamp) / (10 * 86400)) for sample in samples]
            )
        )
        weighted = design * weights[:, None]
        penalty = np.eye(design.shape[1]) * alpha
        penalty[0, 0] = 0.001
        coefficients: Array = np.linalg.solve(
            weighted.T @ weighted + penalty, weighted.T @ (targets * weights)
        )
        return cls(coefficients, supported, tuple(means))

    def predict(self, times: tuple[datetime, ...]) -> Array:
        if self.coefficients is not None:
            return np.maximum(features(times) @ self.coefficients, 0.0)
        return np.asarray(
            [
                self.means[time.weekday()][(time.hour * 60 + time.minute) // 5]
                for time in times
            ],
            dtype=np.float64,
        )

    def supported(self, time: datetime) -> bool:
        return (time.hour * 60 + time.minute) // 5 in self.supported_slots


def corrected(
    profile: Profile,
    times: tuple[datetime, ...],
    today: tuple[Sample, ...],
    issued: datetime,
) -> Array:
    recent = tuple(s for s in today if 0 <= issued.timestamp() - s.timestamp <= 1800)
    correction = 0.0
    if recent:
        expected = profile.predict(tuple(s.time for s in recent))
        residuals = np.asarray([s.count for s in recent]) - expected
        correction = float(np.median(residuals))
    result = profile.predict(times)
    decay = np.asarray(
        [exp(-max(0.0, time.timestamp() - issued.timestamp()) / 5400) for time in times]
    )
    return np.maximum(0.0, result + correction * decay)
