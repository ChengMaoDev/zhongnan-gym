from __future__ import annotations

from datetime import date, datetime
from math import ceil

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from .domain import ZONE, Estimate, Sample
from .theme import theme
from .trace import smooth


def line_path(
    points: tuple[tuple[int, QPointF], ...], max_gap: int | None
) -> QPainterPath:
    path = QPainterPath()
    previous: int | None = None
    for timestamp, point in points:
        if previous is None or (max_gap is not None and timestamp - previous > max_gap):
            path.moveTo(point)
        else:
            path.lineTo(point)
        previous = timestamp
    return path


class Chart(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(308, 172)
        self.samples: tuple[Sample, ...] = ()
        self.estimates: tuple[Estimate, ...] = ()
        self.day: date = datetime.now(ZONE).date()
        self.empty_message = "开始记录后，这里会出现今天的曲线"
        self.setMouseTracking(True)

    def set_data(
        self, day: date, samples: tuple[Sample, ...], estimates: tuple[Estimate, ...]
    ) -> None:
        self.day, self.samples, self.estimates = day, samples, estimates
        self.update()

    def _point(self, stamp: int, value: float, area: QRectF, maximum: float) -> QPointF:
        time = datetime.fromtimestamp(stamp, ZONE)
        minutes = time.hour * 60 + time.minute + time.second / 60
        return QPointF(
            area.left() + minutes / 1440 * area.width(),
            area.bottom() - value / maximum * area.height(),
        )

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        t = theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(28, 15, self.width() - 48, 126)
        counts = [float(s.count) for s in self.samples]
        counts.extend(p.upper or p.count for p in self.estimates)
        maximum = max(20, ceil(max(counts, default=20) / 20) * 20)
        painter.setFont(QFont(self.font().family(), 9))
        painter.setPen(QColor(t.muted))
        for fraction in (0.0, 0.5, 1.0):
            y = area.bottom() - area.height() * fraction
            painter.setPen(QPen(QColor(t.line), 0.7))
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            painter.setPen(QColor(t.muted))
            painter.drawText(
                QRectF(0, y - 8, 23, 16),
                Qt.AlignmentFlag.AlignRight,
                str(round(maximum * fraction)),
            )
        for hour in (0, 6, 12, 18, 24):
            x = area.left() + hour / 24 * area.width()
            painter.drawText(
                QRectF(x - 18, area.bottom() + 8, 36, 18),
                Qt.AlignmentFlag.AlignCenter,
                f"{hour:02d}:00",
            )
        if not self.samples and not self.estimates:
            painter.drawText(area, Qt.AlignmentFlag.AlignCenter, self.empty_message)
            painter.end()
            return
        self._band(painter, area, maximum)
        traces = [(points, t.actual, False) for points in smooth(self.samples)]
        traces.append(
            (tuple((p.timestamp, p.count) for p in self.estimates), t.forecast, True)
        )
        for points, color, dashed in traces:
            painter.setPen(
                QPen(
                    QColor(color),
                    2.1,
                    Qt.PenStyle.DashLine if dashed else Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            projected = tuple(
                (stamp, self._point(stamp, value, area, maximum))
                for stamp, value in points
            )
            path = line_path(projected, 300 if dashed else None)
            if len(projected) == 1:
                painter.drawEllipse(projected[0][1], 1.3, 1.3)
            painter.drawPath(path)
        if self.samples:
            latest = self.samples[-1]
            point = self._point(latest.timestamp, latest.count, area, maximum)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(t.actual))
            painter.drawEllipse(point, 3.5, 3.5)
        painter.end()

    def _band(self, painter: QPainter, area: QRectF, maximum: float) -> None:
        group: list[Estimate] = []
        for estimate in (*self.estimates, Estimate(0, 0)):
            if group and (
                estimate.timestamp - group[-1].timestamp > 300 or not estimate.timestamp
            ):
                path = QPainterPath()
                for index, point in enumerate(group):
                    location = self._point(
                        point.timestamp, point.upper or point.count, area, maximum
                    )
                    path.moveTo(location) if index == 0 else path.lineTo(location)
                for point in reversed(group):
                    path.lineTo(
                        self._point(point.timestamp, point.lower or 0, area, maximum)
                    )
                path.closeSubpath()
                color = QColor(theme().forecast)
                color.setAlpha(24)
                painter.fillPath(path, color)
                group = []
            if estimate.lower is not None and estimate.upper is not None:
                group.append(estimate)
