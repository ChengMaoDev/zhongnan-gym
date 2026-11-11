from datetime import datetime, timedelta

from zhongnan_tray.domain import ZONE, Sample, day_start
from zhongnan_tray.model import Profile


def test_each_weekday_learns_its_own_level_and_weekends() -> None:
    start = datetime(2026, 10, 12, tzinfo=ZONE)
    samples: list[Sample] = []
    for day in range(21):
        date = start + timedelta(days=day)
        level = 30 + date.weekday() * 10 + (80 if date.weekday() >= 5 else 0)
        for minute in range(7 * 60, 23 * 60, 5):
            samples.append(
                Sample(
                    int(
                        (day_start(date.date()) + timedelta(minutes=minute)).timestamp()
                    ),
                    level,
                )
            )
    model = Profile.fit(tuple(samples), 1.0)
    targets = tuple(start + timedelta(days=21 + day, hours=12) for day in range(7))
    values = model.predict(targets)
    assert values[3] > values[0] + 20
    assert values[5] > values[0] + 100
    assert values[6] > values[5] + 5
