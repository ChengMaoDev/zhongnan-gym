from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from .chart import Chart
from .domain import Prediction, Sample, now


def label(text: str, name: str = "") -> QLabel:
    widget = QLabel(text)
    widget.setObjectName(name)
    return widget


class Panel(QWidget):
    day_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("panel")
        self.setFixedWidth(332)
        self.selected = now().date()
        self._today = self.selected
        self._earliest = self.selected
        self._following_today = True
        self._last_samples: tuple[Sample, ...] = ()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 5)
        layout.setSpacing(6)
        top = QHBoxLayout()
        top.addWidget(label("终南健身", "brand"))
        top.addStretch()
        top.addWidget(label("每分钟更新", "muted"))
        layout.addLayout(top)
        self.status = label("正在获取人数…", "status")
        layout.addWidget(self.status)
        count_row = QHBoxLayout()
        count_row.setSpacing(8)
        self.count = label("—", "count")
        count_row.addWidget(self.count)
        count_row.addWidget(label("人在场", "muted"), 0, Qt.AlignmentFlag.AlignBottom)
        count_row.addStretch()
        layout.addLayout(count_row)
        layout.addSpacing(2)
        dates = QHBoxLayout()
        self.previous = QToolButton()
        self.previous.setText("‹")
        self.previous.setAccessibleName("前一天")
        _ = self.previous.clicked.connect(self._previous)
        self.date = label("今天", "date")
        self.date.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next = QToolButton()
        self.next.setText("›")
        self.next.setAccessibleName("后一天")
        _ = self.next.clicked.connect(self._next)
        self.today_button = QToolButton()
        self.today_button.setText("今天")
        _ = self.today_button.clicked.connect(self._go_today)
        dates.addWidget(self.previous)
        dates.addWidget(self.date, 1)
        dates.addWidget(self.next)
        dates.addWidget(self.today_button)
        layout.addLayout(dates)
        self.chart = Chart()
        layout.addWidget(self.chart)
        self.summary = label("", "summary")
        layout.addWidget(self.summary)
        legend = QHBoxLayout()
        self.actual_legend = label("━ 实测人数", "actual")
        self.forecast_legend = label("┄ 今日预测", "forecast")
        legend.addWidget(self.actual_legend)
        legend.addWidget(self.forecast_legend)
        legend.addStretch()
        layout.addLayout(legend)
        self.model = label("记录 1 天后开始预测", "model")
        self.model.setWordWrap(True)
        layout.addWidget(self.model)
        layout.addSpacing(2)
        layout.addWidget(label("本机记录 · 30 天 · 北京时间", "muted"))

    def _previous(self) -> None:
        self._select(self.selected - timedelta(days=1))

    def _next(self) -> None:
        self._select(self.selected + timedelta(days=1))

    def _go_today(self) -> None:
        self._select(self._today)

    def _select(self, day: date) -> None:
        self.selected = max(self._earliest, min(self._today, day))
        self._following_today = self.selected == self._today
        self.day_changed.emit()

    def update_current(
        self, samples: tuple[Sample, ...], current: datetime, error: str
    ) -> None:
        self._last_samples = samples
        self._today = current.date()
        self._earliest = (current - timedelta(days=30)).date()
        if self._following_today:
            self.selected = self._today
        self.selected = max(self.selected, self._earliest)
        if samples:
            latest = samples[-1]
            self.count.setText(str(latest.count))
            stale = current.timestamp() - latest.timestamp > 180
            stamp = latest.time.strftime("%H:%M:%S")
            self.status.setText(
                f"上次更新 {stamp}" + (" · 等待恢复" if error or stale else "")
            )
        else:
            self.status.setText("等待首次采集" if error else "正在获取人数…")
        self.status.setToolTip(error)

    def update_day(
        self, samples: tuple[Sample, ...], prediction: Prediction | None
    ) -> None:
        is_today = self.selected == self._today
        self.date.setText(
            ("今天  " if is_today else "") + self.selected.strftime("%m 月 %d 日")
        )
        self.previous.setEnabled(self.selected > self._earliest)
        self.next.setEnabled(self.selected < self._today)
        self.today_button.setVisible(not is_today)
        points = prediction.points if prediction and is_today else ()
        self.chart.empty_message = (
            "这一天没有记录" if not is_today else "等待第一条人数记录"
        )
        self.chart.set_data(self.selected, samples, points)
        if samples:
            peak = max(samples, key=lambda sample: sample.count)
            mean = sum(s.count for s in samples) / len(samples)
            self.summary.setText(
                f"最高 {peak.count} 人 / {peak.time:%H:%M}    均值 {mean:.0f} 人"
            )
        else:
            self.summary.setText("暂无记录")
        if prediction is None:
            return
        if prediction.training_days < 1:
            self.model.setText("记录 1 天后开始预测")
        elif prediction.points:
            accuracy = (
                f" · 回测误差 {prediction.mae:.1f} 人"
                if prediction.mae is not None
                else " · 待回测"
            )
            self.model.setText(f"已学习 {prediction.training_days} 天{accuracy}")
        else:
            self.model.setText("剩余时段数据不足，继续采集")
