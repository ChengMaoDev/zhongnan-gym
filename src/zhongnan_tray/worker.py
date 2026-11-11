from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import QThread, Signal

from .domain import Sample
from .forecast import Forecaster

LOG = logging.getLogger(__name__)


class ModelWorker(QThread):
    ready = Signal(object)
    failed = Signal(str)

    def __init__(
        self, forecaster: Forecaster, samples: tuple[Sample, ...], current: datetime
    ) -> None:
        super().__init__()
        self.forecaster = forecaster
        self.samples = samples
        self.current = current

    def run(self) -> None:
        try:
            prediction = self.forecaster.predict(self.samples, self.current)
            self.ready.emit(prediction)
        except Exception:
            LOG.exception("模型计算失败")
            self.failed.emit("模型计算失败")
