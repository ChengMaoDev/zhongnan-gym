from zhongnan_tray.domain import Sample
from zhongnan_tray.trace import smooth


def test_smoothing_reduces_points_and_keeps_latest_value_without_changing_records() -> (
    None
):
    samples = tuple(Sample(600 + index * 60, 10 + index) for index in range(60))
    traces = smooth(samples)
    assert sum(len(trace) for trace in traces) < 30
    assert traces[-1][-1] == (samples[-1].timestamp, float(samples[-1].count))
    assert len(samples) == 60


def test_smoothing_never_connects_across_missing_minutes() -> None:
    samples = (Sample(600, 10), Sample(660, 20), Sample(840, 30), Sample(900, 40))
    traces = smooth(samples)
    assert len(traces) == 2
    assert traces[0][-1][0] <= 660
    assert traces[1][0][0] >= 840
