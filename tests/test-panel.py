from datetime import timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu, QWidgetAction

from zhongnan_tray.domain import Estimate, Prediction, Sample, now
from zhongnan_tray.panel import Panel
from zhongnan_tray.theme import stylesheet


def test_history_navigation_and_forecast_visibility(app: QApplication) -> None:
    current = now()
    panel = Panel()
    menu = QMenu()
    menu.setStyleSheet(stylesheet())
    action = QWidgetAction(menu)
    action.setDefaultWidget(panel)
    menu.addAction(action)
    sample = Sample(int(current.timestamp()), 81)
    prediction = Prediction(
        sample.timestamp, (Estimate(sample.timestamp + 300, 90, 70, 110),), "test", 3
    )
    panel.update_current((sample,), current, "")
    panel.update_day((sample,), prediction)
    menu.show()
    app.processEvents()
    assert panel.chart.estimates
    QTest.mouseClick(panel.previous, Qt.MouseButton.LeftButton)
    panel.update_day((), prediction)
    assert panel.selected == current.date() - timedelta(days=1)
    assert panel.chart.estimates == ()
    assert panel.summary.text() == "暂无记录"
    QTest.mouseClick(panel.today_button, Qt.MouseButton.LeftButton)
    panel.update_day((sample,), prediction)
    assert panel.selected == current.date()
    assert len(panel.chart.estimates) == 1
    snapshot = panel.grab().toImage()
    assert not snapshot.isNull()
    assert snapshot.width() == 332
    assert snapshot.height() < 450
    assert isinstance(snapshot, QImage)
    QTest.keyClick(menu, Qt.Key.Key_Escape)
    assert not menu.isVisible()
    menu.close()


def test_midnight_rolls_today_and_never_displays_zero_for_missing_data(
    app: QApplication,
) -> None:
    del app
    panel = Panel()
    current = now()
    sample = Sample(int(current.timestamp()), 81)
    panel.update_current((sample,), current, "")
    panel.update_current((sample,), current + timedelta(days=1), "断网")
    panel.update_day((), None)
    assert panel.selected == (current + timedelta(days=1)).date()
    assert panel.count.text() == "81"
    assert "等待恢复" in panel.status.text()
