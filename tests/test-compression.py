import sqlite3
from datetime import timedelta
from pathlib import Path

from zhongnan_tray.domain import Sample, now
from zhongnan_tray.store import Store


def test_constant_count_is_one_record_and_reopens_without_losing_duration(
    tmp_path: Path,
) -> None:
    current = now()
    start = int((current - timedelta(hours=1)).timestamp())
    path = tmp_path / "count.sqlite3"
    store = Store(path)
    for minute in range(60):
        store.add(Sample(start + minute * 60, 81), '{"data":81,"status":0}')
    store.close()
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT count(*),max(observed_until) FROM samples"
        ).fetchone() == (1, start + 59 * 60)
    store = Store(path)
    history = store.history(current)
    assert len(history) == 60
    assert history[-1].count == 81
    store.close()


def test_unchanged_count_after_a_gap_is_not_joined(tmp_path: Path) -> None:
    current = now()
    start = int(current.timestamp()) - 3600
    store = Store(tmp_path / "gap.sqlite3")
    store.add(Sample(start, 30), "{}")
    store.add(Sample(start + 60, 30), "{}")
    store.failure(start + 120, "断网")
    store.add(Sample(start + 180, 30), "{}")
    assert tuple(s.timestamp for s in store.history(current)) == (
        start,
        start + 60,
        start + 180,
    )
    store.close()


def test_retention_clips_long_constant_segment_instead_of_losing_it(
    tmp_path: Path,
) -> None:
    current = now()
    cutoff = int((current - timedelta(days=30)).timestamp())
    store = Store(tmp_path / "long.sqlite3")
    for second in range(-120, 181, 60):
        store.add(Sample(cutoff + second, 30), "{}")
    store.prune(current)
    assert store.history(current) == tuple(
        Sample(cutoff + second, 30) for second in range(0, 181, 60)
    )
    store.close()


def test_existing_minute_database_is_migrated_without_losing_observations(
    tmp_path: Path,
) -> None:
    path = tmp_path / "old.sqlite3"
    start = int(now().timestamp()) - 300
    with sqlite3.connect(path) as db:
        _ = db.execute(
            "CREATE TABLE samples(timestamp INTEGER PRIMARY KEY,count INTEGER,payload TEXT)"
        )
        _ = db.executemany(
            "INSERT INTO samples VALUES(?,?,?)",
            [(start + minute * 60, 81, "{}") for minute in range(3)],
        )
    store = Store(path)
    assert len(store.history(now())) == 3
    store.close()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM samples").fetchone() == (1,)
