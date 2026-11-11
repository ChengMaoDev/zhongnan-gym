from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import cast

from .domain import Sample


@dataclass(frozen=True)
class Segment:
    start: int
    end: int
    count: int


def read_segments(db: sqlite3.Connection, start: int, end: int) -> tuple[Segment, ...]:
    rows = cast(
        list[tuple[int, int, int]],
        db.execute(
            "SELECT timestamp,observed_until,count FROM samples "
            "WHERE observed_until>=? AND timestamp<=? ORDER BY timestamp",
            (start, end),
        ).fetchall(),
    )
    return tuple(
        Segment(max(begin, start), min(until, end), count)
        for begin, until, count in rows
    )


def expand(segments: tuple[Segment, ...]) -> tuple[Sample, ...]:
    result: list[Sample] = []
    for segment in segments:
        result.extend(
            Sample(stamp, segment.count)
            for stamp in range(segment.start, segment.end + 1, 60)
        )
        if not result or result[-1].timestamp != segment.end:
            result.append(Sample(segment.end, segment.count))
    return tuple(result)


def migrate(db: sqlite3.Connection) -> None:
    columns = cast(
        list[tuple[int, str, str, int, str | None, int]],
        db.execute("PRAGMA table_info(samples)").fetchall(),
    )
    if "observed_until" in {row[1] for row in columns}:
        return
    with db:
        _ = db.execute(
            "ALTER TABLE samples ADD COLUMN observed_until INTEGER NOT NULL DEFAULT 0"
        )
        _ = db.execute("UPDATE samples SET observed_until=timestamp")
        rows = cast(
            list[tuple[int, int]],
            db.execute(
                "SELECT timestamp,count FROM samples ORDER BY timestamp"
            ).fetchall(),
        )
        start, last, previous = 0, 0, -1
        for timestamp, count in rows:
            if count == previous and 0 <= timestamp - last <= 90:
                _ = db.execute(
                    "UPDATE samples SET observed_until=? WHERE timestamp=?",
                    (timestamp, start),
                )
                _ = db.execute("DELETE FROM samples WHERE timestamp=?", (timestamp,))
            else:
                start, previous = timestamp, count
            last = timestamp
