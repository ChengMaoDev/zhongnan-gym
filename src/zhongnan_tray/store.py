from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import cast

from .domain import RETENTION, Prediction, Sample, day_start
from .records import expand, migrate, read_segments


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._db = sqlite3.connect(path)
        _ = self._db.execute("PRAGMA journal_mode=WAL")
        _ = self._db.execute("PRAGMA auto_vacuum=INCREMENTAL")
        _ = self._db.executescript("""
            CREATE TABLE IF NOT EXISTS samples (
                timestamp INTEGER PRIMARY KEY, count INTEGER NOT NULL CHECK(count>=0),
                payload TEXT NOT NULL, observed_until INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attempts (
                timestamp INTEGER PRIMARY KEY, error TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS predictions (
                issued_at INTEGER NOT NULL, target_at INTEGER NOT NULL,
                count REAL NOT NULL, lower REAL, upper REAL,
                method TEXT NOT NULL, training_days INTEGER NOT NULL, mae REAL,
                PRIMARY KEY (issued_at, target_at)
            );
        """)
        self._db.commit()
        migrate(self._db)

    def add(self, sample: Sample, payload: str) -> None:
        with self._db:
            last = cast(
                tuple[int, int, int] | None,
                self._db.execute(
                    "SELECT timestamp,observed_until,count FROM samples ORDER BY timestamp DESC LIMIT 1"
                ).fetchone(),
            )
            failed = cast(
                tuple[int],
                self._db.execute(
                    "SELECT count(*) FROM attempts WHERE timestamp>? AND timestamp<=?",
                    (last[1] if last else 0, sample.timestamp),
                ).fetchone(),
            )[0]
            if (
                last
                and last[2] == sample.count
                and 0 <= sample.timestamp - last[1] <= 90
                and not failed
            ):
                _ = self._db.execute(
                    "UPDATE samples SET observed_until=? WHERE timestamp=?",
                    (sample.timestamp, last[0]),
                )
            else:
                _ = self._db.execute(
                    "INSERT OR REPLACE INTO samples(timestamp,count,payload,observed_until) VALUES (?,?,?,?)",
                    (sample.timestamp, sample.count, payload, sample.timestamp),
                )

    def failure(self, timestamp: int, error: str) -> None:
        with self._db:
            _ = self._db.execute(
                "INSERT OR REPLACE INTO attempts VALUES (?, ?)", (timestamp, error)
            )

    def prune(self, current: datetime) -> None:
        cutoff = int((current - RETENTION).timestamp())
        with self._db:
            _ = self._db.execute(
                "DELETE FROM samples WHERE observed_until < ?", (cutoff,)
            )
            _ = self._db.execute(
                "UPDATE samples SET timestamp=? WHERE timestamp<? AND observed_until>=?",
                (cutoff, cutoff, cutoff),
            )
            for table, column in (
                ("attempts", "timestamp"),
                ("predictions", "issued_at"),
            ):
                _ = self._db.execute(
                    f"DELETE FROM {table} WHERE {column} < ?", (cutoff,)
                )
        _ = self._db.execute("PRAGMA incremental_vacuum(64)")

    def history(self, current: datetime) -> tuple[Sample, ...]:
        return expand(
            read_segments(
                self._db,
                int((current - RETENTION).timestamp()),
                int(current.timestamp()),
            )
        )

    def day(self, day: date, current: datetime) -> tuple[Sample, ...]:
        start = max(day_start(day), current - RETENTION)
        end = min(day_start(day) + timedelta(days=1), current + timedelta(seconds=1))
        return expand(
            read_segments(self._db, int(start.timestamp()), int(end.timestamp()) - 1)
        )

    def save_prediction(self, prediction: Prediction) -> None:
        with self._db:
            self._db.executemany(
                "INSERT OR REPLACE INTO predictions VALUES (?,?,?,?,?,?,?,?)",
                [
                    (
                        prediction.issued_at,
                        point.timestamp,
                        point.count,
                        point.lower,
                        point.upper,
                        prediction.method,
                        prediction.training_days,
                        prediction.mae,
                    )
                    for point in prediction.points
                ],
            )

    def last_forecast_issue(self) -> int:
        row = cast(
            tuple[int | None],
            self._db.execute("SELECT max(issued_at) FROM predictions").fetchone(),
        )
        return row[0] or 0

    def close(self) -> None:
        self._db.close()
