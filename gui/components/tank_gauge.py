# gui/components/tank_gauge.py
"""
Módulo para el widget de indicador visual tipo tanque modernizado y compatible con temas.
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QLinearGradient, QPainterPath
import logging
from gui.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class TankGauge(QWidget):
    """
    Widget que visualiza un valor numérico como el nivel de un tanque moderno
    con escala lateral, gradiente de llenado y badge digital inferior.
    """

    def __init__(self, titulo, min_val, max_val, unidad, color_liquido="#1640f9", parent=None):
        super().__init__(parent)
        self.titulo = titulo
        self.min_val = min_val
        self.max_val = max_val
        self.unidad = unidad
        self.color_liquido = QColor(color_liquido)
        self.val = min_val
        self.setMinimumSize(100, 200)

        tm = ThemeManager.instance()
        tm.theme_changed.connect(lambda _t: self.update())

    def setValue(self, valor):
        try:
            self.val = float(valor) if valor is not None else self.min_val
        except (TypeError, ValueError):
            self.val = self.min_val
        self.update()

    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 150:
            return

        tokens = ThemeManager.get_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. Tarjeta contenedora exterior con margen sutil
        card_rect = QRectF(6.0, 4.0, float(w - 12), float(h - 8))
        painter.setPen(QPen(QColor(tokens["border_card"]), 2))
        painter.setBrush(QColor(tokens["bg_card"]))
        painter.drawRoundedRect(card_rect, 14.0, 14.0)

        # 2. Título superior
        painter.setPen(QColor(tokens["text_primary"]))
        painter.setFont(QFont("Segoe UI", 18, QFont.Bold))
        painter.drawText(QRectF(0, 10, w, 34), Qt.AlignCenter, self.titulo.upper())

        # 3. Geometría del tanque
        margin_x = 42
        margin_top = 48
        margin_bottom = 86
        tank_x = float(margin_x)
        tank_y = float(margin_top)
        tank_w = float(w - (margin_x * 2))
        tank_h = float(h - margin_top - margin_bottom)

        if tank_h <= 10 or tank_w <= 10:
            painter.end()
            return

        tank_rect = QRectF(tank_x, tank_y, tank_w, tank_h)

        # 4. Fondo del tanque (vacío)
        painter.setPen(QPen(QColor(tokens["gauge_tank_border"]), 3))
        painter.setBrush(QColor(tokens["gauge_tank_bg"]))
        painter.drawRoundedRect(tank_rect, 12.0, 12.0)

        # 5. Marcas de graduación (ticks) en el borde izquierdo
        painter.setPen(QPen(QColor(tokens["text_muted"]), 1.5))
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        num_ticks = 5
        for i in range(num_ticks + 1):
            frac = i / num_ticks
            ty = tank_y + tank_h - (frac * tank_h)
            tick_len = 8 if i % 2 == 0 else 5
            painter.drawLine(int(tank_x - tick_len - 3), int(ty), int(tank_x - 3), int(ty))

        # 6. Nivel de líquido con gradiente y recorte redondeado
        rango = self.max_val - self.min_val
        if rango == 0:
            rango = 1.0
        val_safe = max(self.min_val, min(self.max_val, self.val))
        pct = (val_safe - self.min_val) / rango
        fill_h = tank_h * pct

        if fill_h > 2.0:
            clip_path = QPainterPath()
            clip_path.addRoundedRect(tank_rect.adjusted(2, 2, -2, -2), 10.0, 10.0)
            painter.save()
            painter.setClipPath(clip_path)

            y_pos = (tank_y + tank_h) - fill_h
            fill_rect = QRectF(tank_x, y_pos, tank_w, fill_h)

            grad = QLinearGradient(tank_x, y_pos, tank_x + tank_w, y_pos + fill_h)
            grad.setColorAt(0.0, self.color_liquido.lighter(125))
            grad.setColorAt(0.5, self.color_liquido)
            grad.setColorAt(1.0, self.color_liquido.darker(125))

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawRect(fill_rect)

            # Línea brillante de menisco superior
            painter.setPen(QPen(self.color_liquido.lighter(160), 2.5))
            painter.drawLine(int(tank_x), int(y_pos), int(tank_x + tank_w), int(y_pos))
            painter.restore()

        # 7. Badge digital inferior para el valor y unidad
        badge_rect = QRectF(12.0, float(h - 78), float(w - 24), 66.0)
        painter.setPen(QPen(QColor(tokens["border_card"]), 1.5))
        painter.setBrush(QColor(tokens["bg_card_alt"]))
        painter.drawRoundedRect(badge_rect, 10.0, 10.0)

        painter.setPen(QColor(tokens["text_primary"]))
        painter.setFont(QFont("Consolas", 21, QFont.Bold))
        painter.drawText(QRectF(12.0, float(h - 76), float(w - 24), 38.0), Qt.AlignCenter, f"{self.val:.1f}")

        painter.setPen(QColor(tokens["text_muted"]))
        painter.setFont(QFont("Segoe UI", 13, QFont.Bold))
        painter.drawText(QRectF(12.0, float(h - 40), float(w - 24), 24.0), Qt.AlignCenter, self.unidad)

        painter.end()

    def sizeHint(self):
        return QSize(192, 451)
