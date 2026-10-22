# gui/components/conductivity_bar.py
"""
Módulo para el widget de barra indicadora de conductividad modernizado y compatible con temas.
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QPen
from gui.theme_manager import ThemeManager


class ConductivityBar(QWidget):
    """
    Widget de barra indicadora vertical para mostrar la conductividad con
    segmentos iluminados por zonas y badge digital inferior.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(100, 200)

        self.min_value = 8.5
        self.max_value = 16.0
        self.value = 14.0

        # === ZONAS BASE ===
        self.base_colors = [
            "#9e0142", "#d53e4f", "#f46d43", "#fdae61",
            "#10b981", "#3288bd", "#dc2626"
        ]

        # === DIVIDIR CADA ZONA EN 3 BARRAS ===
        self.colors = []
        for color in self.base_colors:
            c = QColor(color)
            self.colors.append(c.darker(115))
            self.colors.append(c)
            self.colors.append(c.lighter(115))

        self.n_steps = len(self.colors)
        self._bar_solid_percent = 0.82
        self._padding = 18

        tm = ThemeManager.instance()
        tm.theme_changed.connect(lambda _t: self.update())

    def setValue(self, value):
        try:
            v = float(value)
            if 0.0 <= v <= 20.0:
                if abs(v - self.value) > 0.01:
                    self.value = v
                    self.update()
        except Exception:
            pass

    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 180:
            return

        tokens = ThemeManager.get_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. Tarjeta contenedora exterior (homologada con TankGauge)
        card_rect = QRectF(6.0, 4.0, float(w - 12), float(h - 8))
        painter.setPen(QPen(QColor(tokens["border_card"]), 2))
        painter.setBrush(QColor(tokens["bg_card"]))
        painter.drawRoundedRect(card_rect, 14.0, 14.0)

        # 2. Título superior
        painter.setPen(QColor(tokens["text_primary"]))
        painter.setFont(QFont("Segoe UI", 18, QFont.Bold))
        painter.drawText(QRectF(0, 10, w, 34), Qt.AlignCenter, "COND.")

        # 3. Área de barras
        bar_x = 34
        bar_y = 48
        bar_width = w - 68
        bar_height = h - 134

        if bar_height <= 10 or bar_width <= 10:
            painter.end()
            return

        step_size = bar_height / self.n_steps
        bar_height_step = max(2.0, step_size * self._bar_solid_percent)

        range_total = self.max_value - self.min_value
        if range_total == 0:
            range_total = 1.0

        pc = max(0.0, min(1.0, (self.value - self.min_value) / range_total))
        steps_to_draw = max(0, min(self.n_steps, int(pc * self.n_steps)))

        inactive_bg = QColor(tokens["gauge_tank_bg"])
        inactive_bg.setAlpha(90 if not tokens.get("is_dark") else 150)

        is_mono = bool(tokens.get("monochrome", False))
        for i in range(self.n_steps):
            y_pos = bar_y + bar_height - ((i + 1) * step_size) + (step_size * (1 - self._bar_solid_percent) / 2)
            rh_w = max(1, int(bar_width))
            rh_h = max(1, int(bar_height_step))

            if i < steps_to_draw:
                if is_mono:
                    gray_val = int(210 - (i / max(1, self.n_steps - 1)) * 140)
                    color = QColor(gray_val, gray_val, gray_val)
                    painter.setBrush(color)
                    painter.setPen(QPen(color.darker(120), 1.5))
                else:
                    color = QColor(self.colors[i])
                    painter.setBrush(color)
                    painter.setPen(QPen(color.darker(140), 1.5))
            else:
                painter.setBrush(inactive_bg)
                painter.setPen(QPen(QColor(tokens["border_card"]), 1))

            painter.drawRoundedRect(int(bar_x), int(y_pos), rh_w, rh_h, 5, 5)

        # 4. Badge digital inferior
        badge_rect = QRectF(12.0, float(h - 78), float(w - 24), 66.0)
        painter.setPen(QPen(QColor(tokens["border_card"]), 1.5))
        painter.setBrush(QColor(tokens["bg_card_alt"]))
        painter.drawRoundedRect(badge_rect, 10.0, 10.0)

        painter.setPen(QColor(tokens["text_primary"]))
        painter.setFont(QFont("Consolas", 21, QFont.Bold))
        painter.drawText(QRectF(12.0, float(h - 76), float(w - 24), 38.0), Qt.AlignCenter, f"{self.value:.2f}")

        painter.setPen(QColor(tokens["text_muted"]))
        painter.setFont(QFont("Segoe UI", 13, QFont.Bold))
        painter.drawText(QRectF(12.0, float(h - 40), float(w - 24), 24.0), Qt.AlignCenter, "mS/cm")

        painter.end()

    def sizeHint(self):
        return QSize(120, 452)
