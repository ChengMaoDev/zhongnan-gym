from __future__ import annotations

import json
import time
from sqlite3 import Error as sqlite_error
from typing import cast

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .domain import API_URL, INTERVAL, Sample, now
from .store import Store


def parse_response(payload: str) -> int:
    value: object = json.loads(payload)
    if not isinstance(value, dict):
        raise TypeError("接口返回格式异常")
    data = cast(dict[str, object], value)
    status = data.get("status")
    count = data.get("data")
    if type(status) is not int or status != 0:
        raise ValueError("接口未返回成功状态")
    if type(count) is not int or count < 0:
        raise ValueError("接口人数不是非负整数")
    return count


class Collector(QObject):
    changed = Signal()

    def __init__(self, store: Store) -> None:
        super().__init__()
        self.store = store
        self.error = ""
        self.collecting = False
        self._last_started = float("-inf")
        self._manager = QNetworkAccessManager(self)
        self._reply: QNetworkReply | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        _ = self._timer.timeout.connect(self.tick)
        self._deadline = QTimer(self)
        self._deadline.setSingleShot(True)
        _ = self._deadline.timeout.connect(self._abort)

    def start(self) -> None:
        self._timer.start()
        self.tick()

    def tick(self) -> None:
        if self.collecting or time.monotonic() - self._last_started < INTERVAL:
            return
        current = now()
        try:
            self.store.prune(current)
        except sqlite_error as error:
            self.error = f"清理记录失败：{error}"
            self._last_started = time.monotonic()
            self.changed.emit()
            return
        self._last_started = time.monotonic()
        self.collecting = True
        request = QNetworkRequest(QUrl(API_URL))
        request.setTransferTimeout(12000)
        request.setAttribute(
            QNetworkRequest.Attribute.CacheLoadControlAttribute,
            QNetworkRequest.CacheLoadControl.AlwaysNetwork,
        )
        self._reply = self._manager.get(request)
        _ = self._reply.finished.connect(self._finished)
        self._deadline.start(15000)

    def _abort(self) -> None:
        if self._reply is not None:
            self._reply.abort()

    def _finished(self) -> None:
        reply = self._reply
        if reply is None:
            return
        self._deadline.stop()
        self._reply = None
        self.collecting = False
        timestamp = int(now().timestamp())
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                raise ValueError(f"请求失败：{reply.errorString()}")
            status: object = reply.attribute(
                QNetworkRequest.Attribute.HttpStatusCodeAttribute
            )
            if status != 200:
                raise ValueError(f"HTTP {status}")
            payload = bytes(reply.readAll().data()).decode("utf-8")
            count = parse_response(payload)
            self.store.add(Sample(timestamp, count), payload)
            self.error = ""
        except (ValueError, TypeError, sqlite_error) as error:
            self.error = str(error)
            try:
                self.store.failure(timestamp, self.error)
            except sqlite_error as storage_error:
                self.error = f"{self.error}；记录失败：{storage_error}"
        finally:
            reply.deleteLater()
            self.changed.emit()

    def stop(self) -> None:
        self._timer.stop()
        self._deadline.stop()
        if self._reply is not None:
            _ = self._reply.finished.disconnect(self._finished)
            self._reply.abort()
            self._reply.deleteLater()
            self._reply = None
