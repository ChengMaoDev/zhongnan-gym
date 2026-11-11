import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from zhongnan_tray.domain import RETENTION, ZONE, Estimate, Prediction, Sample
from zhongnan_tray.store import Store


def test_retention_covers_samples_errors_and_saved_predictions(tmp_path: Path) -> None:
    current = datetime(2026, 11, 11, 13, tzinfo=ZONE)
    cutoff = int((current - RETENTION).timestamp())
    store = Store(tmp_path / "history.sqlite3")
    for stamp in (cutoff - 1, cutoff, int(current.timestamp())):
        store.add(Sample(stamp, 12), '{"data":12,"status":0}')
        store.failure(stamp, "断网")
        store.save_prediction(
            Prediction(stamp, (Estimate(stamp + 300, 15),), "test", 3)
        )
    store.prune(current)
    assert tuple(s.timestamp for s in store.history(current)) == (
        cutoff,
        int(current.timestamp()),
    )
    store.close()
    with sqlite3.connect(tmp_path / "history.sqlite3") as db:
        assert db.execute(
            "SELECT min(timestamp),count(*) FROM attempts"
        ).fetchone() == (cutoff, 2)
        assert db.execute(
            "SELECT min(issued_at),count(*) FROM predictions"
        ).fetchone() == (cutoff, 2)


def test_beijing_midnight_and_restart_preserve_raw_records(tmp_path: Path) -> None:
    midnight = datetime(2026, 11, 11, tzinfo=ZONE)
    path = tmp_path / "history.sqlite3"
    store = Store(path)
    before = Sample(int(midnight.timestamp()) - 1, 0)
    after = Sample(int(midnight.timestamp()), 81)
    store.add(before, '{"data":0,"status":0}')
    store.add(after, '{"data":81,"status":0}')
    store.close()
    store = Store(path)
    assert store.day(midnight.date(), midnight + timedelta(minutes=1)) == (after,)
    assert store.day((midnight - timedelta(days=1)).date(), midnight) == (before,)
    store.close()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT payload FROM samples WHERE count=0").fetchone() == (
            '{"data":0,"status":0}',
        )
