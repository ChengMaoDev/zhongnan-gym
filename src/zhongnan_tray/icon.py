from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


def tray_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(
        QPen(QColor("#1886a1"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    )
    painter.drawLine(QPointF(16, 32), QPointF(48, 32))
    for x, height in ((10, 18), (20, 34), (44, 34), (54, 18)):
        painter.drawRoundedRect(QRectF(x - 2, 32 - height / 2, 4, height), 2, 2)
    painter.end()
    return QIcon(pixmap)
