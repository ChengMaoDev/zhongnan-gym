from __future__ import annotations

import hashlib
import logging
import threading
from pathlib import Path
from typing import cast

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication

from .download import Update, download, latest
from .install import install_update
from .release import VERSION

LOG = logging.getLogger(__name__)


class Events(QObject):
    status = Signal(str)
    ready = Signal(object)
    failed = Signal(str)
    finished = Signal()


class UpdateThread(threading.Thread):
    def __init__(self, directory: Path, events: Events) -> None:
        super().__init__(name="gym-updater", daemon=True)
        self.directory, self.events = directory, events
        self.cancelled = threading.Event()
        self._progress = -1

    def run(self) -> None:
        try:
            update = latest()
            if update is None:
                self.events.ready.emit(None)
            else:
                path = download(
                    update, self.directory, self.cancelled.is_set, self.progress
                )
                self.events.ready.emit((update, path))
        except (OSError, ValueError, RuntimeError) as error:
            LOG.exception("检查或下载更新失败")
            self.events.failed.emit(str(error))
        finally:
            self.events.finished.emit()

    def progress(self, percent: int) -> None:
        if percent // 10 != self._progress // 10:
            self._progress = percent
            self.events.status.emit(f"正在下载更新 {percent}%")


class Updater(QObject):
    def __init__(self, app: QApplication, directory: Path) -> None:
        super().__init__()
        self.app, self.directory = app, directory / "updates"
        self.events = Events()
        self.worker: UpdateThread | None = None
        self.pending: tuple[Update, Path] | None = None
        self.action = QAction(f"v{VERSION} · 检查更新", self)
        _ = self.action.triggered.connect(self.clicked)
        _ = self.events.status.connect(self.action.setText)
        _ = self.events.ready.connect(self.ready)
        _ = self.events.failed.connect(self.failed)
        _ = self.events.finished.connect(self.finished)
        self.timer = QTimer(self)
        self.timer.setInterval(6 * 3600 * 1000)
        _ = self.timer.timeout.connect(self.check)
        self.timer.start()
        QTimer.singleShot(6000, self.check)

    def check(self) -> None:
        if self.worker is not None:
            return
        self.action.setText("正在检查更新…")
        self.action.setEnabled(False)
        self.worker = UpdateThread(self.directory, self.events)
        self.worker.start()

    def ready(self, value: object) -> None:
        self.action.setEnabled(True)
        if value is None:
            self.pending = None
            self.action.setText(f"v{VERSION} · 已是最新，点击检查")
            return
        if not isinstance(value, tuple):
            raise TypeError("更新结果格式异常")
        update, path = cast(tuple[Update, Path], value)
        self.pending = update, path
        self.action.setText(f"安装 v{update.version} 并重启")

    def failed(self, message: str) -> None:
        self.action.setEnabled(True)
        self.action.setText("检查更新失败，点击重试")
        self.action.setToolTip(message)

    def finished(self) -> None:
        self.worker = None

    def clicked(self) -> None:
        if self.pending is None:
            self.check()
            return
        update, path = self.pending
        try:
            with path.open("rb") as source:
                if hashlib.file_digest(source, "sha256").hexdigest() != update.digest:
                    raise ValueError("下载包已改变，请重新检查更新")
            install_update(path, self.directory)
            self.app.quit()
        except (OSError, ValueError, RuntimeError) as error:
            LOG.exception("安装更新失败")
            self.failed(str(error))
            self.pending = None

    def stop(self) -> None:
        self.timer.stop()
        if self.worker is not None:
            self.worker.cancelled.set()
