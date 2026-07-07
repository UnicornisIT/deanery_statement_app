from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


class LoadingOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._message = "Загрузка..."
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.hide()

        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._tick)

    def start(self, message: str) -> None:
        self._message = message
        if self.parentWidget():
            self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()
        self._timer.start()
        self.update()

    def stop(self) -> None:
        self._timer.stop()
        self.hide()

    def _tick(self) -> None:
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.fillRect(self.rect(), QColor(2, 6, 23, 176))

        center = self.rect().center()
        radius = 28
        segment_count = 12
        for index in range(segment_count):
            alpha = int(55 + (200 * index / segment_count))
            color = QColor(248, 250, 252, alpha)
            pen = QPen(color, 4, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(pen)
            painter.save()
            painter.translate(center)
            painter.rotate(self._angle + index * (360 / segment_count))
            painter.drawLine(0, -radius, 0, -radius + 10)
            painter.restore()

        painter.setPen(QColor(248, 250, 252))
        font = QFont("Segoe UI", 11)
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        painter.drawText(
            0,
            center.y() + radius + 28,
            self.width(),
            28,
            Qt.AlignHCenter | Qt.AlignVCenter,
            self._message,
        )
