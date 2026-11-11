from __future__ import annotations

from .domain import Sample


def smooth(samples: tuple[Sample, ...]) -> tuple[tuple[tuple[int, float], ...], ...]:
    """Three-minute display averages, split at missing observations."""
    traces: list[tuple[tuple[int, float], ...]] = []
    points: list[tuple[int, float]] = []
    bucket: list[Sample] = []
    previous = 0

    def flush_bucket() -> None:
        if bucket:
            points.append(
                (
                    round(sum(s.timestamp for s in bucket) / len(bucket)),
                    sum(s.count for s in bucket) / len(bucket),
                )
            )
            bucket.clear()

    for sample in samples:
        if previous and sample.timestamp - previous > 90:
            flush_bucket()
            traces.append(tuple(points))
            points = []
        if bucket and sample.timestamp // 180 != bucket[0].timestamp // 180:
            flush_bucket()
        bucket.append(sample)
        previous = sample.timestamp
    flush_bucket()
    if points:
        if samples[-1].timestamp != points[-1][0]:
            points.append((samples[-1].timestamp, float(samples[-1].count)))
        traces.append(tuple(points))
    return tuple(traces)
