# gui/therapy/nibp_history_screen.py
"""
Pantallas de historial de mediciones de presión arterial (NIBP) para una sesión de terapia.
Referencia visual: Dialog+ / Dialog iQ, IFU 38910440ES, apartado 11.2.4.

Se separa en dos pantallas que comparten la misma instancia de NibpPressureHistory:
  1. NibpHistoryScreen (Tomas):
     - Tabla con la medición más reciente arriba.
     - Columnas: Tiempo (HH:MM), Sistólica, Diastólica, MAP, Frecuencia, SpO2.
     - Sin hora: "—". Sin colorear tomas fuera de rango todavía.
     - Botones: "Gráfica" (abre la pantalla de gráfica) y "Cerrar" (regresa al baumanómetro).
  2. NibpChartScreen (Gráfica):
     - Dos gráficas apiladas con fondos claros.
     - Superior: Sistólica y Diastólica en rojo.
     - Inferior: Frecuencia en azul.
     - Eje X: hora local de taken_at con marcas HH:MM (incluye tomas antes de iniciar RUNNING).
     - Ventana temporal de terapia para no estirar una sola serie corta a todo el ancho.
     - Botones: "Tomas" (regresa a la tabla) y "Cerrar" (regresa al baumanómetro).
"""

from datetime import datetime
import logging
import math
from typing import Optional, List, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

import pyqtgraph as pg
import numpy as np

from core.nibp_pressure_history import NibpPressureHistory, NibpPressureMeasurement
from gui.theme_manager import ThemeManager

logger = logging.getLogger(__name__)

_RED_BP = "#dc2626"
_BLUE_HR = "#2563eb"
_AXIS_LEFT_WIDTH = 96


def format_taken_at_hhmm(taken_at) -> str:
    """Formatea taken_at como HH:MM en hora local, o '—' si no tiene hora."""
    if taken_at is None:
        return "—"
    if hasattr(taken_at, "strftime"):
        try:
            return taken_at.strftime("%H:%M")
        except Exception:
            return "—"
    if isinstance(taken_at, (int, float)):
        try:
            return datetime.fromtimestamp(float(taken_at)).strftime("%H:%M")
        except Exception:
            return "—"
    if isinstance(taken_at, str):
        text = taken_at.strip()
        if not text:
            return "—"
        if len(text) >= 5 and text[2] == ":":
            return text[:5]
        try:
            dt = datetime.fromisoformat(text)
            return dt.strftime("%H:%M")
        except Exception:
            return text
    return "—"


def extract_timestamp_seconds(taken_at) -> Optional[float]:
    """Convierte taken_at (datetime, timestamp o 'HH:MM') a segundos epoch locales."""
    if taken_at is None:
        return None
    if hasattr(taken_at, "timestamp"):
        try:
            return float(taken_at.timestamp())
        except Exception:
            return None
    if isinstance(taken_at, (int, float)):
        try:
            val = float(taken_at)
            if math.isfinite(val):
                return val
        except Exception:
            return None
    if isinstance(taken_at, str):
        text = taken_at.strip()
        if not text:
            return None
        try:
            return float(datetime.fromisoformat(text).timestamp())
        except Exception:
            pass
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                parsed = datetime.strptime(text, fmt)
                now = datetime.now()
                combined = now.replace(
                    hour=parsed.hour,
                    minute=parsed.minute,
                    second=parsed.second if fmt == "%H:%M:%S" else 0,
                    microsecond=0,
                )
                return float(combined.timestamp())
            except Exception:
                continue
    return None


def _floor_to_clock_step(ts_seconds: float, step_minutes: int = 15) -> float:
    """Redondea hacia abajo un timestamp epoch al múltiplo de step_minutes en hora local."""
    dt = datetime.fromtimestamp(ts_seconds)
    floored_min = (dt.minute // step_minutes) * step_minutes
    floored_dt = dt.replace(minute=floored_min, second=0, microsecond=0)
    return float(floored_dt.timestamp())


class ClockTimeAxisItem(pg.AxisItem):
    """Eje X en hora local con marcas HH:MM."""

    def __init__(self, orientation="bottom", **kwargs):
        super().__init__(orientation=orientation, **kwargs)
        self.enableAutoSIPrefix(False)

    def tickValues(self, minVal: float, maxVal: float, size: float) -> List[Tuple[float, List[float]]]:
        if not (math.isfinite(minVal) and math.isfinite(maxVal)) or maxVal <= minVal:
            return []

        span_s = maxVal - minVal
        span_min = span_s / 60.0

        if span_min <= 60:
            major_step_min = 10
            minor_step_min = 5
        elif span_min <= 150:
            major_step_min = 15
            minor_step_min = 5
        elif span_min <= 300:
            major_step_min = 30
            minor_step_min = 15
        else:
            major_step_min = 60
            minor_step_min = 30

        major_step_s = major_step_min * 60.0
        minor_step_s = minor_step_min * 60.0
        edge_pad = span_s * 0.025

        start_major = _floor_to_clock_step(minVal, major_step_min)
        while start_major < minVal + edge_pad:
            start_major += major_step_s

        major_ticks: List[float] = []
        t = start_major
        max_ticks = 24
        while t <= maxVal - edge_pad and len(major_ticks) < max_ticks:
            major_ticks.append(t)
            t += major_step_s

        if not major_ticks:
            major_ticks = [minVal + span_s * 0.5]

        start_minor = _floor_to_clock_step(minVal, minor_step_min)
        while start_minor < minVal + edge_pad:
            start_minor += minor_step_s

        major_set = {round(v) for v in major_ticks}
        minor_ticks: List[float] = []
        t = start_minor
        while t <= maxVal - edge_pad and len(minor_ticks) < 60:
            if round(t) not in major_set:
                minor_ticks.append(t)
            t += minor_step_s

        return [
            (major_step_s, major_ticks),
            (minor_step_s, minor_ticks),
        ]

    def tickStrings(self, values, scale, spacing) -> List[str]:
        labels: List[str] = []
        for v in values:
            try:
                labels.append(datetime.fromtimestamp(float(v)).strftime("%H:%M"))
            except Exception:
                labels.append("")
        return labels


class NibpHistoryScreen(QWidget):
    """
    Pantalla de Tomas de presión arterial (tabla con la más reciente arriba).
    Comparte la instancia de NibpPressureHistory con NibpChartScreen.
    """

    graph_requested = Signal()
    close_requested = Signal()

    COLUMNS = [
        "Tiempo (HH:MM)",
        "Sistólica",
        "Diastólica",
        "MAP",
        "Frecuencia",
        "SpO2",
    ]

    def __init__(self, parent=None, history: Optional[NibpPressureHistory] = None):
        super().__init__(parent if isinstance(parent, QWidget) else None)
        self.parent_window = parent
        self.history = history if history is not None else NibpPressureHistory()
        self.programmed_therapy_minutes = 240

        self.setObjectName("NibpHistoryScreen")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.setup_background()
        self.setup_ui()
        self.update_from_history()
        try:
            ThemeManager.instance().theme_changed.connect(self._on_theme_changed)
        except Exception:
            pass

    def setup_background(self):
        """Fondo claro como el resto de la interfaz."""
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), QColor("#f8fafc"))
        self.setPalette(p)

    def setup_ui(self):
        """Construye la pantalla de Tomas: encabezado con botones Gráfica y Cerrar, tabla y pie."""
        main_layout = QVBoxLayout(self)
        dpi = max(self.logicalDpiX() / 96.0, 1.0)
        margen = int(16 * dpi)
        main_layout.setContentsMargins(margen, margen, margen, margen)
        main_layout.setSpacing(12)

        # ─── ENCABEZADO ───────────────────────────────────────────────
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        self.lbl_title = QLabel("Tomas de Presión Arterial")
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()

        self.btn_graph = QPushButton("Gráfica")
        self.btn_graph.clicked.connect(self.on_graph_clicked)
        header_layout.addWidget(self.btn_graph)

        self.btn_close = QPushButton("Cerrar")
        self.btn_close.clicked.connect(self.on_close_clicked)
        header_layout.addWidget(self.btn_close)

        main_layout.addLayout(header_layout)

        # ─── CONTENEDOR DE TABLA ──────────────────────────────────────
        self.card_frame = QFrame()
        self.card_frame.setObjectName("card")
        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(10)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setMinimumHeight(44)

        card_layout.addWidget(self.table, stretch=1)
        main_layout.addWidget(self.card_frame, stretch=1)

        # ─── PIE DE PÁGINA ────────────────────────────────────────────
        footer_layout = QHBoxLayout()
        self.lbl_count = QLabel("Total: 0 mediciones")
        footer_layout.addWidget(self.lbl_count)
        footer_layout.addStretch()
        main_layout.addLayout(footer_layout)

        self._apply_theme_styles()

    def _on_theme_changed(self, _theme_name: str):
        self.setup_background()
        self._apply_theme_styles()

    def _apply_theme_styles(self):
        bg_primary = "#f8fafc"
        bg_card = "#ffffff"
        bg_alt = "#f1f5f9"
        text_primary = "#0f172a"
        border = "#cbd5e1"
        accent = "#2563eb"
        accent_soft = "#dbeafe"
        btn_primary_bg = "#06298a"

        self.setStyleSheet(f"""
            QWidget#NibpHistoryScreen {{ background-color: {bg_primary}; }}
            QFrame#card {{
                background-color: {bg_card};
                border: 1px solid {border};
                border-radius: 12px;
            }}
        """)

        self.lbl_title.setStyleSheet(
            f"font-size: 28px; font-weight: bold; color: {text_primary}; background: transparent;"
        )
        self.btn_graph.setStyleSheet(f"""
            QPushButton {{
                background-color: {btn_primary_bg};
                color: #ffffff;
                font-size: 20px;
                font-weight: bold;
                padding: 10px 24px;
                border-radius: 8px;
                border: 1px solid {border};
            }}
            QPushButton:hover {{ background-color: {accent}; color: #ffffff; }}
        """)
        self.btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: #64748b;
                color: #ffffff;
                font-size: 20px;
                font-weight: bold;
                padding: 10px 24px;
                border-radius: 8px;
                border: 1px solid {border};
            }}
            QPushButton:hover {{ background-color: {accent}; color: #ffffff; }}
        """)
        self.lbl_count.setStyleSheet(
            f"font-size: 16px; color: {text_primary}; background: transparent;"
        )

        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {bg_card};
                gridline-color: {border};
                border: 1px solid {border};
                border-radius: 8px;
                color: {text_primary};
                font-size: 18px;
            }}
            QTableWidget::item {{
                padding: 6px;
                background-color: {bg_card};
                color: {text_primary};
            }}
            QTableWidget::item:selected {{
                background-color: {accent_soft};
                color: {text_primary};
            }}
            QHeaderView {{
                background-color: {bg_alt};
                border: none;
            }}
            QHeaderView::section {{
                background-color: {bg_alt};
                color: {text_primary};
                padding: 8px;
                border: none;
                border-bottom: 2px solid {border};
                font-size: 18px;
                font-weight: bold;
            }}
            QTableCornerButton::section {{
                background-color: {bg_alt};
                border: none;
            }}
        """)

    def update_from_history(self):
        """Actualiza la tabla desde el historial sin borrarlo. La más reciente arriba."""
        measurements = self.history.get_all_measurements()
        ordered = list(reversed(measurements))
        self.table.setRowCount(len(ordered))

        for row_idx, measurement in enumerate(ordered):
            time_str = format_taken_at_hhmm(getattr(measurement, "taken_at", None))
            spo2_str = str(measurement.spo2) if measurement.spo2 is not None else "—"

            row_values = [
                time_str,
                str(measurement.sys),
                str(measurement.dia),
                str(measurement.map_mmhg),
                str(measurement.hr),
                spo2_str,
            ]

            for col_idx, val_str in enumerate(row_values):
                item = QTableWidgetItem(val_str)
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_idx, col_idx, item)

        self.lbl_count.setText(f"Total: {len(measurements)} mediciones")

    def set_programmed_duration(self, hours: int, minutes: int):
        """Conserva la duración programada de terapia."""
        self.programmed_therapy_minutes = hours * 60 + minutes

    def on_graph_clicked(self):
        """Abre la pantalla de Gráfica."""
        self.graph_requested.emit()
        if self.parent_window and hasattr(self.parent_window, "show_nibp_chart_screen"):
            self.parent_window.show_nibp_chart_screen()

    def on_close_clicked(self):
        """Vuelve a la pantalla del baumanómetro."""
        self.close_requested.emit()
        if self.parent_window and hasattr(self.parent_window, "show_nibp_screen"):
            self.parent_window.show_nibp_screen()


class NibpChartScreen(QWidget):
    """
    Pantalla de Gráfica de presión arterial:
      - Dos gráficas apiladas con fondos claros.
      - Arriba: Sistólica y Diastólica en rojo.
      - Abajo: Frecuencia en azul.
      - Eje X: hora local de taken_at con marcas HH:MM (incluye tomas antes de iniciar).
      - Ventana horaria proporcional a la terapia para no estirar una serie corta a todo el ancho.
    """

    tomas_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent=None, history: Optional[NibpPressureHistory] = None):
        super().__init__(parent if isinstance(parent, QWidget) else None)
        self.parent_window = parent
        self.history = history if history is not None else NibpPressureHistory()
        self.programmed_therapy_minutes = 240

        self.setObjectName("NibpChartScreen")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.setup_background()
        self.setup_ui()
        self.update_from_history()
        try:
            ThemeManager.instance().theme_changed.connect(self._on_theme_changed)
        except Exception:
            pass

    def setup_background(self):
        """Fondo claro como el resto de la interfaz."""
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), QColor("#f8fafc"))
        self.setPalette(p)

    def setup_ui(self):
        """Construye encabezado (botones Tomas y Cerrar) y dos gráficas apiladas."""
        main_layout = QVBoxLayout(self)
        dpi = max(self.logicalDpiX() / 96.0, 1.0)
        margen = int(16 * dpi)
        main_layout.setContentsMargins(margen, margen, margen, margen)
        main_layout.setSpacing(12)

        # ─── ENCABEZADO ───────────────────────────────────────────────
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        self.lbl_title = QLabel("Gráfica de Presión Arterial")
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()

        self.btn_tomas = QPushButton("Tomas")
        self.btn_tomas.clicked.connect(self.on_tomas_clicked)
        header_layout.addWidget(self.btn_tomas)

        self.btn_close = QPushButton("Cerrar")
        self.btn_close.clicked.connect(self.on_close_clicked)
        header_layout.addWidget(self.btn_close)

        main_layout.addLayout(header_layout)

        # ─── TARJETA CON DOS GRÁFICAS APILADAS ────────────────────────
        self.charts_card = QFrame()
        self.charts_card.setObjectName("card")
        charts_layout = QVBoxLayout(self.charts_card)
        charts_layout.setContentsMargins(16, 14, 16, 14)
        charts_layout.setSpacing(10)

        # 1. Gráfica superior: Sistólica y Diastólica en rojo
        self.axis_bottom_bp = ClockTimeAxisItem(orientation="bottom")
        self.plot_bp = pg.PlotWidget(axisItems={"bottom": self.axis_bottom_bp})
        self.plot_bp.hideButtons()
        self.plot_bp.setMouseEnabled(x=False, y=False)
        self.plot_bp.setMenuEnabled(False)
        self.plot_bp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.plot_item_bp = self.plot_bp.plotItem
        self.plot_item_bp.showGrid(x=True, y=True, alpha=0.25)
        self.plot_item_bp.hideAxis("top")
        self.plot_item_bp.hideAxis("right")

        left_bp = self.plot_item_bp.getAxis("left")
        left_bp.enableAutoSIPrefix(False)
        left_bp.setStyle(tickTextOffset=7)
        left_bp.setWidth(_AXIS_LEFT_WIDTH)
        self.axis_bottom_bp.setStyle(tickTextOffset=5, autoExpandTextSpace=True)
        self.axis_bottom_bp.setHeight(34)

        self.plot_item_bp.vb.enableAutoRange(False)
        self.plot_item_bp.vb.setYRange(40, 200, padding=0)

        self.curve_sys = self.plot_bp.plot(
            [], [],
            pen=pg.mkPen(_RED_BP, width=2.5),
            symbol="o",
            symbolSize=8,
            symbolBrush=_RED_BP,
            symbolPen=pg.mkPen(_RED_BP),
            name="Sistólica",
        )
        self.curve_dia = self.plot_bp.plot(
            [], [],
            pen=pg.mkPen(_RED_BP, width=2.5),
            symbol="o",
            symbolSize=8,
            symbolBrush=_RED_BP,
            symbolPen=pg.mkPen(_RED_BP),
            name="Diastólica",
        )

        self.legend_bp = pg.LegendItem(offset=(10, 8))
        self.legend_bp.setParentItem(self.plot_item_bp.vb)
        self.legend_bp.addItem(self.curve_sys, "Sistólica (mmHg)")
        self.legend_bp.addItem(self.curve_dia, "Diastólica (mmHg)")

        # 2. Gráfica inferior: Frecuencia en azul
        self.axis_bottom_hr = ClockTimeAxisItem(orientation="bottom")
        self.plot_hr = pg.PlotWidget(axisItems={"bottom": self.axis_bottom_hr})
        self.plot_hr.hideButtons()
        self.plot_hr.setMouseEnabled(x=False, y=False)
        self.plot_hr.setMenuEnabled(False)
        self.plot_hr.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.plot_item_hr = self.plot_hr.plotItem
        self.plot_item_hr.showGrid(x=True, y=True, alpha=0.25)
        self.plot_item_hr.hideAxis("top")
        self.plot_item_hr.hideAxis("right")

        left_hr = self.plot_item_hr.getAxis("left")
        left_hr.enableAutoSIPrefix(False)
        left_hr.setStyle(tickTextOffset=7)
        left_hr.setWidth(_AXIS_LEFT_WIDTH)
        self.axis_bottom_hr.setStyle(tickTextOffset=5, autoExpandTextSpace=True)
        self.axis_bottom_hr.setHeight(34)

        self.plot_item_hr.vb.enableAutoRange(False)
        self.plot_item_hr.vb.setYRange(40, 160, padding=0)

        self.curve_hr = self.plot_hr.plot(
            [], [],
            pen=pg.mkPen(_BLUE_HR, width=2.5),
            symbol="o",
            symbolSize=8,
            symbolBrush=_BLUE_HR,
            symbolPen=pg.mkPen(_BLUE_HR),
            name="Frecuencia",
        )

        self.legend_hr = pg.LegendItem(offset=(10, 8))
        self.legend_hr.setParentItem(self.plot_item_hr.vb)
        self.legend_hr.addItem(self.curve_hr, "Frecuencia (lpm)")

        self.lbl_x_axis = QLabel("Hora (HH:MM)")
        self.lbl_x_axis.setAlignment(Qt.AlignCenter)

        charts_layout.addWidget(self.plot_bp, stretch=3)
        charts_layout.addWidget(self.plot_hr, stretch=2)
        charts_layout.addWidget(self.lbl_x_axis, stretch=0)

        main_layout.addWidget(self.charts_card, stretch=1)

        # ─── PIE DE PÁGINA ────────────────────────────────────────────
        footer_layout = QHBoxLayout()
        self.lbl_count = QLabel("Total: 0 mediciones")
        footer_layout.addWidget(self.lbl_count)
        footer_layout.addStretch()
        main_layout.addLayout(footer_layout)

        self._apply_theme_styles()

    def _on_theme_changed(self, _theme_name: str):
        self.setup_background()
        self._apply_theme_styles()

    def _apply_theme_styles(self):
        # Fondos siempre claros, como el resto de la interfaz clínica
        bg_primary = "#f8fafc"
        bg_card = "#ffffff"
        bg_alt = "#f8fafc"
        text_primary = "#0f172a"
        text_secondary = "#475569"
        border = "#cbd5e1"
        accent = "#2563eb"
        btn_primary_bg = "#06298a"

        self.setStyleSheet(f"""
            QWidget#NibpChartScreen {{ background-color: {bg_primary}; }}
            QFrame#card {{
                background-color: {bg_card};
                border: 1px solid {border};
                border-radius: 12px;
            }}
        """)

        self.lbl_title.setStyleSheet(
            f"font-size: 28px; font-weight: bold; color: {text_primary}; background: transparent;"
        )
        self.btn_tomas.setStyleSheet(f"""
            QPushButton {{
                background-color: {btn_primary_bg};
                color: #ffffff;
                font-size: 20px;
                font-weight: bold;
                padding: 10px 24px;
                border-radius: 8px;
                border: 1px solid {border};
            }}
            QPushButton:hover {{ background-color: {accent}; color: #ffffff; }}
        """)
        self.btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: #64748b;
                color: #ffffff;
                font-size: 20px;
                font-weight: bold;
                padding: 10px 24px;
                border-radius: 8px;
                border: 1px solid {border};
            }}
            QPushButton:hover {{ background-color: {accent}; color: #ffffff; }}
        """)

        for plot_widget, plot_item, y_label in (
            (self.plot_bp, self.plot_item_bp, "mmHg"),
            (self.plot_hr, self.plot_item_hr, "lpm"),
        ):
            plot_widget.setBackground(bg_card)
            plot_item.vb.setBackgroundColor(bg_card)
            plot_item.setLabel("left", y_label, color=text_primary)

            left_axis = plot_item.getAxis("left")
            left_axis.setPen(pg.mkPen(text_secondary))
            left_axis.setTextPen(pg.mkPen(text_primary))

            bottom_axis = plot_item.getAxis("bottom")
            bottom_axis.setPen(pg.mkPen(text_secondary))
            bottom_axis.setTextPen(pg.mkPen(text_primary))

            plot_item.vb.setBorder(pg.mkPen(border, width=1))

        c_bg = QColor(bg_alt)
        for legend in (self.legend_bp, self.legend_hr):
            legend.setBrush(pg.mkBrush(c_bg.red(), c_bg.green(), c_bg.blue(), 235))
            legend.setPen(pg.mkPen(border))

        self.lbl_x_axis.setStyleSheet(
            f"font-size: 14px; color: {text_primary}; font-weight: 600; background: transparent;"
        )
        self.lbl_count.setStyleSheet(
            f"font-size: 16px; color: {text_primary}; background: transparent;"
        )

    def _compute_time_window(self, x_timestamps: List[float]) -> Tuple[float, float]:
        """
        Calcula el rango [x_start, x_end] del eje X en segundos epoch.
        Usa una ventana de duración de terapia (mínimo 2 horas, 4 horas por defecto)
        anclada a la primera toma para no estirar una sola serie corta a todo el ancho.
        """
        therapy_min = self.programmed_therapy_minutes if self.programmed_therapy_minutes > 0 else 240
        window_s = float(max(therapy_min, 120) * 60)

        if x_timestamps:
            first_ts = min(x_timestamps)
            last_ts = max(x_timestamps)
            x_start = _floor_to_clock_step(first_ts - 300.0, step_minutes=15)
            x_end = max(x_start + window_s, last_ts + 600.0)
        else:
            now_ts = float(datetime.now().timestamp())
            x_start = _floor_to_clock_step(now_ts, step_minutes=15)
            x_end = x_start + window_s

        return x_start, x_end

    def update_from_history(self):
        """
        Actualiza las dos gráficas apiladas desde el historial sin borrarlo.
        Incluye todas las tomas que tienen taken_at (incluyendo las de antes de RUNNING).
        """
        all_measurements = self.history.get_all_measurements()

        valid_points: List[Tuple[float, NibpPressureMeasurement]] = []
        for m in all_measurements:
            ts = extract_timestamp_seconds(getattr(m, "taken_at", None))
            if ts is not None:
                valid_points.append((ts, m))

        valid_points.sort(key=lambda pair: pair[0])

        if valid_points:
            x_list = [pair[0] for pair in valid_points]
            x_data = np.array(x_list, dtype=float)
            sys_data = np.array([pair[1].sys for pair in valid_points], dtype=float)
            dia_data = np.array([pair[1].dia for pair in valid_points], dtype=float)
            hr_data = np.array([pair[1].hr for pair in valid_points], dtype=float)

            self.curve_sys.setData(x_data, sys_data)
            self.curve_dia.setData(x_data, dia_data)
            self.curve_hr.setData(x_data, hr_data)

            bp_min = min(40.0, float(np.min(dia_data)) - 10.0)
            bp_max = max(200.0, float(np.max(sys_data)) + 10.0)
            hr_min = min(40.0, float(np.min(hr_data)) - 10.0)
            hr_max = max(160.0, float(np.max(hr_data)) + 10.0)
        else:
            x_list = []
            self.curve_sys.clear()
            self.curve_dia.clear()
            self.curve_hr.clear()
            bp_min, bp_max = 40.0, 200.0
            hr_min, hr_max = 40.0, 160.0

        x_start, x_end = self._compute_time_window(x_list)

        self.plot_item_bp.vb.enableAutoRange(False)
        self.plot_item_bp.vb.setXRange(x_start, x_end, padding=0)
        self.plot_item_bp.vb.setYRange(bp_min, bp_max, padding=0)

        self.plot_item_hr.vb.enableAutoRange(False)
        self.plot_item_hr.vb.setXRange(x_start, x_end, padding=0)
        self.plot_item_hr.vb.setYRange(hr_min, hr_max, padding=0)

        self.lbl_count.setText(f"Total: {len(all_measurements)} mediciones")

    def set_programmed_duration(self, hours: int, minutes: int):
        """Establece la duración programada de la terapia para la ventana temporal del eje X."""
        self.programmed_therapy_minutes = hours * 60 + minutes

    def on_tomas_clicked(self):
        """Regresa a la pantalla de Tomas."""
        self.tomas_requested.emit()
        if self.parent_window and hasattr(self.parent_window, "show_nibp_history_screen"):
            self.parent_window.show_nibp_history_screen()

    def on_close_clicked(self):
        """Vuelve a la pantalla del baumanómetro."""
        self.close_requested.emit()
        if self.parent_window and hasattr(self.parent_window, "show_nibp_screen"):
            self.parent_window.show_nibp_screen()


NibpGraphScreen = NibpChartScreen
NibpTomasScreen = NibpHistoryScreen
