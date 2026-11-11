from __future__ import annotations

import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from sqlite3 import Error as StorageError

from PySide6.QtCore import QLockFile, QObject, QStandardPaths, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidgetAction

from .collector import Collector
from .domain import Prediction, now
from .forecast import Forecaster
from .icon import tray_icon
from .panel import Panel
from .queries import Queries, SharedState
from .server import URL, LocalServer
from .store import Store
from .theme import stylesheet, theme
from .toggle import Toggle
from .updater import Updater
from .worker import ModelWorker

LOG = logging.getLogger(__name__)


class Application(QObject):
    def __init__(self, app: QApplication, directory: Path) -> None:
        super().__init__()
        self.app = app
        self.directory = directory
        self.store = Store(directory / "history.sqlite3")
        self.store.prune(now())
        self.collector = Collector(self.store)
        self.shared = SharedState()
        self.server = LocalServer(Queries(self.store.path, self.shared))
        self.server.start()
        self.forecaster = Forecaster()
        self.prediction: Prediction | None = None
        self.worker: ModelWorker | None = None
        self.last_issue = self.store.last_forecast_issue()
        self.panel = Panel()
        self.menu = QMenu()
        self.toggle = Toggle()
        _ = self.menu.aboutToHide.connect(self.menu_hidden)
        self.menu.setStyleSheet(stylesheet())
        widget_action = QWidgetAction(self.menu)
        widget_action.setDefaultWidget(self.panel)
        self.menu.addAction(widget_action)
        self.menu.addSeparator()
        self.updater = Updater(app, directory)
        self.menu.addAction(self.updater.action)
        self.mcp_action = self.menu.addAction("复制 MCP 地址")
        _ = self.mcp_action.triggered.connect(self.copy_mcp_url)
        quit_action = self.menu.addAction("退出终南健身")
        _ = quit_action.triggered.connect(app.quit)
        self.tray = QSystemTrayIcon(tray_icon(), self)
        self.tray.setToolTip("终南健身 · 正在获取人数")
        _ = self.tray.activated.connect(self.activate)
        _ = self.panel.day_changed.connect(self.refresh_day)
        _ = self.collector.changed.connect(self.refresh)
        _ = app.aboutToQuit.connect(self.shutdown)
        self.clock = QTimer(self)
        self.clock.setInterval(60000)
        _ = self.clock.timeout.connect(self.refresh)
        self.clock.start()
        self.tray.show()
        self.refresh()
        QTimer.singleShot(0, self.collector.start)

    def activate(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason not in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.Context,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            return
        if not self.toggle.should_open(self.menu.isVisible(), time.monotonic()):
            self.menu.close()
            self.toggle.hidden(False, time.monotonic())
            return
        self.refresh()
        self.menu.setStyleSheet(stylesheet())
        t = theme()
        self.panel.actual_legend.setStyleSheet(f"color:{t.actual}")
        self.panel.forecast_legend.setStyleSheet(f"color:{t.forecast}")
        self.mcp_action.setEnabled(self.server.ready)
        self.mcp_action.setText(
            "复制 MCP 地址" if self.server.ready else "MCP 连接暂不可用"
        )
        self.menu.popup(QCursor.pos())

    def menu_hidden(self) -> None:
        self.toggle.hidden(
            self.tray.geometry().contains(QCursor.pos()), time.monotonic()
        )

    def refresh(self) -> None:
        current = now()
        try:
            samples = self.store.history(current)
            self.panel.update_current(samples, current, self.collector.error)
            self.refresh_day()
            if samples:
                self.tray.setToolTip(f"终南健身 · {samples[-1].count} 人在场")
            if self.worker is None:
                self.worker = ModelWorker(self.forecaster, samples, current)
                _ = self.worker.ready.connect(self.on_prediction)
                _ = self.worker.failed.connect(self.on_model_error)
                _ = self.worker.finished.connect(self.worker_finished)
                self.worker.start()
        except StorageError:
            LOG.exception("读取本地记录失败")
            self.panel.status.setText("读取记录失败，检查数据文件夹权限")

    def refresh_day(self) -> None:
        self.panel.update_day(
            self.store.day(self.panel.selected, now()), self.prediction
        )

    def on_prediction(self, value: object) -> None:
        if not isinstance(value, Prediction):
            raise TypeError("模型返回格式异常")
        self.prediction = value
        self.shared.update(value)
        if value.points and value.issued_at - self.last_issue >= 900:
            try:
                self.store.save_prediction(value)
                self.last_issue = value.issued_at
            except StorageError:
                LOG.exception("保存预测失败")
                self.panel.status.setText("保存预测失败，检查可用磁盘空间")
        self.refresh_day()

    def on_model_error(self, error: str) -> None:
        LOG.error("模型计算失败：%s", error)
        self.shared.update(self.prediction, error)
        self.panel.model.setText("预测暂不可用，下次采集后重试")

    def worker_finished(self) -> None:
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None

    def copy_mcp_url(self) -> None:
        self.app.clipboard().setText(URL)

    def shutdown(self) -> None:
        self.clock.stop()
        self.collector.stop()
        self.updater.stop()
        self.server.stop()
        if self.worker is not None:
            _ = self.worker.wait()
        self.tray.hide()
        self.store.close()


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
        from .health import smoke_test

        return smoke_test(Path(sys.argv[2]))
    app = QApplication(sys.argv)
    app.setApplicationName("ZhongnanGym")
    app.setApplicationDisplayName("终南健身")
    app.setOrganizationName("ZhongnanGym")
    app.setQuitOnLastWindowClosed(False)
    directory = Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation
        )
    )
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        directory / "app.log", maxBytes=100_000, backupCount=1, encoding="utf-8"
    )
    logging.basicConfig(handlers=[handler], level=logging.INFO)
    lock = QLockFile(str(directory / "app.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        return 0
    if not QSystemTrayIcon.isSystemTrayAvailable():
        LOG.error("系统托盘不可用")
        return 1
    try:
        controller = Application(app, directory)
        result = app.exec()
        del controller
        return result
    except Exception:
        LOG.exception("启动失败")
        return 1
    finally:
        lock.unlock()


if __name__ == "__main__":
    raise SystemExit(main())
