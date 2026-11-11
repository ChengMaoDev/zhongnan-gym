from datetime import datetime, timedelta
from math import exp

from zhongnan_tray.domain import ZONE, Sample, day_start
from zhongnan_tray.forecast import Forecaster
from zhongnan_tray.model import bin_samples


def history(days: int, current: datetime) -> tuple[Sample, ...]:
    samples: list[Sample] = []
    for offset in range(days, 0, -1):
        day = day_start(current.date()) - timedelta(days=offset)
        for minute in range(7 * 60, 23 * 60, 5):
            hour = minute / 60
            count = round(
                12
                + 50 * exp(-(((hour - 12) / 2) ** 2))
                + 110 * exp(-(((hour - 19) / 2) ** 2))
            )
            samples.append(
                Sample(int((day + timedelta(minutes=minute)).timestamp()), count)
            )
    return tuple(samples)


def test_cold_start_does_not_invent_forecasts() -> None:
    current = datetime(2026, 11, 11, 12, tzinfo=ZONE)
    result = Forecaster().predict((), current)
    assert result.points == ()
    assert result.training_days == 0


def test_one_training_day_is_enough_to_start_predicting() -> None:
    current = datetime(2026, 11, 11, 12, tzinfo=ZONE)
    result = Forecaster().predict(history(1, current), current)
    assert result.training_days == 1
    assert result.points
    assert result.mae is None


def test_sparse_days_do_not_count_as_training_days() -> None:
    current = datetime(2026, 11, 11, 12, tzinfo=ZONE)
    samples = tuple(
        Sample(int((current - timedelta(days=day)).timestamp()), 30)
        for day in range(1, 9)
    )
    assert Forecaster().predict(samples, current).points == ()


def test_forecasts_are_future_only_supported_and_nonnegative() -> None:
    current = datetime(2026, 11, 11, 12, tzinfo=ZONE)
    result = Forecaster().predict(history(3, current), current)
    assert len(result.points) > 100
    assert result.mae is None
    assert all(point.count >= 0 for point in result.points)
    assert all(
        current.timestamp()
        < point.timestamp
        < day_start(current.date()).timestamp() + 86400
        for point in result.points
    )
    assert result.points[-1].timestamp <= int(
        current.replace(hour=23, minute=10).timestamp()
    )


def test_future_data_is_excluded_and_current_observations_update_prediction() -> None:
    current = datetime(2026, 11, 11, 12, tzinfo=ZONE)
    samples = history(3, current)
    expected = Forecaster().predict(samples, current)
    poisoned = (
        *samples,
        Sample(int((current + timedelta(hours=1)).timestamp()), 100000),
    )
    assert Forecaster().predict(poisoned, current) == expected
    observed = tuple(
        Sample(int((current - timedelta(minutes=minute)).timestamp()), 120)
        for minute in range(0, 25, 5)
    )
    updated = Forecaster().predict((*samples, *observed), current)
    assert updated.points[0].count > expected.points[0].count + 30


def test_walk_forward_selects_model_and_reports_real_held_out_error() -> None:
    current = datetime(2026, 11, 11, 12, tzinfo=ZONE)
    result = Forecaster().predict(history(8, current), current)
    assert result.training_days == 8
    assert result.mae is not None and result.mae < 15
    assert all(
        point.lower is not None and point.upper is not None for point in result.points
    )


def test_binned_timestamp_never_precedes_its_last_observation() -> None:
    binned = bin_samples((Sample(600, 10), Sample(840, 30)))
    assert binned == (Sample(840, 20),)
