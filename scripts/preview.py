"""Render the real tray menu with isolated synthetic data for visual checks."""

from __future__ import annotations

import os
from datetime import timedelta
from math import exp, sin
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMenu, QWidgetAction

from zhongnan_tray.domain import Sample, day_start, now
from zhongnan_tray.forecast import Forecaster
from zhongnan_tray.panel import Panel
from zhongnan_tray.theme import stylesheet, theme


def main() -> None:
    app = QApplication([])
    current = now().replace(hour=16, minute=20, second=0, microsecond=0)
    samples: list[Sample] = []
    for offset in range(8, -1, -1):
        start = day_start(current.date()) - timedelta(days=offset)
        for minute in range(7 * 60, 23 * 60):
            timestamp = int((start + timedelta(minutes=minute)).timestamp())
            if timestamp > current.timestamp():
                break
            hour = minute / 60
            count = max(
                0,
                round(
                    15
                    + 50 * exp(-(((hour - 12) / 2) ** 2))
                    + 125 * exp(-(((hour - 19) / 2) ** 2))
                    + 3 * sin(minute * 0.07)
                ),
            )
            samples.append(Sample(timestamp, count))
    prediction = Forecaster().predict(tuple(samples), current)
    menu = QMenu()
    panel = Panel()
    action = QWidgetAction(menu)
    action.setDefaultWidget(panel)
    menu.addAction(action)
    menu.addSeparator()
    _ = menu.addAction("复制 MCP 地址")
    _ = menu.addAction("退出终南健身")
    panel.update_current(tuple(samples), current, "")
    panel.status.setText("界面测试 · 示例数据")
    panel.update_day(
        tuple(s for s in samples if s.time.date() == current.date()), prediction
    )
    directory = Path(__file__).resolve().parent.parent / "build"
    directory.mkdir(exist_ok=True)
    for mode in ("light", "dark"):
        palette = QPalette()
        palette.setColor(
            QPalette.ColorRole.Window,
            QColor("#1d2630" if mode == "dark" else "#ffffff"),
        )
        app.setPalette(palette)
        menu.setStyleSheet(stylesheet())
        t = theme()
        panel.actual_legend.setStyleSheet(f"color:{t.actual}")
        panel.forecast_legend.setStyleSheet(f"color:{t.forecast}")
        menu.popup(QPoint(0, 0))
        app.processEvents()
        if not menu.grab().save(str(directory / f"preview-{mode}.png")):
            raise RuntimeError("无法保存预览")
    menu.close()


if __name__ == "__main__":
    main()
