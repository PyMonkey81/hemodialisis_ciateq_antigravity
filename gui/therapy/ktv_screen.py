# gui/therapy/ktv_screen.py
from PySide6.QtWidgets import (
    QGridLayout, QWidget, QLabel, QPushButton,
    QVBoxLayout, QSizePolicy, QFrame, QComboBox, QListWidget
)
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtGui import QColor
import numpy as np
import pyqtgraph as pg
import logging
import csv
import os
from datetime import datetime
from shiboken6 import isValid
from core.state_manager import TreatmentPhase
from gui.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


def _safe_float(value, default=0.0):
    """Convierte a float evitando excepciones por valores nulos o inválidos."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class KTVScreen(QWidget):
    def __init__(self, parent=None, values_dict=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_values = values_dict if values_dict is not None else {}

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.themed_cards: list[QFrame] = []
        self.themed_labels: list[QLabel] = []
        self.themed_values: list[QLabel] = []

        self.ktv_records = []
        self.ktv_points = []      # (minutos_total, ktv)
        self.heit_points = []     # (minutos_total, heitmann)

        self._last_recorded_ktv = 0.0
        self._waiting_manual_result = False
        self._selected_frequency_index = 2
        self._manual_pending_row: int = -1
        self._last_calc_signature: str = ""

        self.setup_ui()
        self.init_plot()

        tm = ThemeManager.instance()
        tm.theme_changed.connect(self.apply_theme_styles)
        self.apply_theme_styles(tm.current_theme_name)

    def setup_background(self):
        tokens = ThemeManager.get_tokens()
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), QColor(tokens["bg_main"]))
        self.setPalette(p)

    def setup_ui(self):
        layout = QGridLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # ==================== FILA 0, COLUMNA 0: DATOS DEL PACIENTE ====================
        data_container = QFrame()
        self.themed_cards.append(data_container)
        data_layout = QGridLayout(data_container)
        data_layout.setSpacing(8)
        data_layout.setContentsMargins(16, 14, 16, 14)

        fields = ["Nombre de paciente:", "Edad:", "Altura:", "Peso:"]
        self.display_name = QLabel("N/A")
        self.display_age = QLabel("N/A")
        self.display_height = QLabel("N/A")
        self.display_weight = QLabel("N/A")

        for i, text in enumerate(fields):
            lbl = QLabel(text)
            self.themed_labels.append(lbl)
            data_layout.addWidget(lbl, i, 0)

        for i, widget in enumerate([self.display_name, self.display_age, self.display_height, self.display_weight]):
            self.themed_values.append(widget)
            widget.setAlignment(Qt.AlignCenter)
            data_layout.addWidget(widget, i, 1)

        # ==================== FILA 0, COLUMNA 1: BIOIMPEDANCIA + HEITMANN ====================
        data_container0 = QFrame()
        self.themed_cards.append(data_container0)
        dl0 = QGridLayout(data_container0)
        dl0.setSpacing(8)
        dl0.setContentsMargins(16, 14, 16, 14)

        label_bioz = QLabel("Bioimpedancia (Z):")
        self.themed_labels.append(label_bioz)
        dl0.addWidget(label_bioz, 0, 0)
        self.display_bioz = QLabel("--- Ω")
        self.display_bioz.setAlignment(Qt.AlignCenter)
        dl0.addWidget(self.display_bioz, 0, 1)

        label_volume_heitmann = QLabel("Volumen Heitmann (L):")
        self.themed_labels.append(label_volume_heitmann)
        dl0.addWidget(label_volume_heitmann, 1, 0)
        self.display_heitmann = QLabel("--- L")
        self.display_heitmann.setAlignment(Qt.AlignCenter)
        dl0.addWidget(self.display_heitmann, 1, 1)

        # ==================== FILA 1, COLUMNA 0: CONFIGURACIÓN ====================
        data_container1 = QFrame()
        self.themed_cards.append(data_container1)
        dl1 = QGridLayout(data_container1)
        dl1.setSpacing(10)
        dl1.setContentsMargins(16, 14, 16, 14)

        freq_label = QLabel("Frecuencia cálculo automático:")
        self.themed_labels.append(freq_label)

        self.lbl_freq_indicator = QLabel("● Deshabilitado")
        self.lbl_freq_indicator.setAlignment(Qt.AlignCenter)

        self.combo_freq = QComboBox()
        self.combo_freq.addItems(["15 minutos", "30 minutos", "Deshabilitado"])
        self.combo_freq.setCurrentIndex(2)
        self._selected_frequency_index = self.combo_freq.currentIndex()
        self.combo_freq.currentIndexChanged.connect(self._on_frequency_changed)

        self.btn_run_ktv = QPushButton("Iniciar Cálculo Kt/V Manual")
        self.btn_run_ktv.clicked.connect(self._on_run_ktv_now)

        self.lbl_next_schedule = QLabel("Próxima medición: No programado")
        self.themed_labels.append(self.lbl_next_schedule)

        dl1.addWidget(freq_label, 0, 0)
        dl1.addWidget(self.combo_freq, 0, 1)
        dl1.addWidget(self.lbl_freq_indicator, 0, 2)
        dl1.addWidget(self.btn_run_ktv, 0, 3)
        dl1.addWidget(self.lbl_next_schedule, 1, 0, 1, 4)

        # ==================== FILA 1, COLUMNA 1: RESULTADOS ====================
        data_container2 = QFrame()
        self.themed_cards.append(data_container2)
        dl2 = QGridLayout(data_container2)
        dl2.setSpacing(8)
        dl2.setContentsMargins(16, 14, 16, 14)

        self.results_list = QListWidget()
        dl2.addWidget(self.results_list, 0, 0)

        # ==================== FILA 2, COLUMNAS 0-1: GRÁFICA ====================
        self.plot_frame = QFrame()
        self.themed_cards.append(self.plot_frame)
        plot_layout = QGridLayout(self.plot_frame)
        plot_layout.setSpacing(0)
        plot_layout.setContentsMargins(10, 10, 10, 10)

        self.plot_widget = pg.PlotWidget()
        plot_layout.addWidget(self.plot_widget, 0, 0)

        # ==================== AÑADIR CARDS AL GRID PRINCIPAL ====================
        layout.addWidget(data_container, 0, 0)
        layout.addWidget(data_container0, 0, 1)
        layout.addWidget(data_container1, 1, 0)
        layout.addWidget(data_container2, 1, 1)
        layout.addWidget(self.plot_frame, 2, 0, 1, 2)

        layout.setRowStretch(0, 2)
        layout.setRowStretch(1, 2)
        layout.setRowStretch(2, 6)

        self.setLayout(layout)

    def init_plot(self):
        """Inicializa los parámetros de la gráfica pyqtgraph con dos ejes Y."""
        self.plot_widget.setBackground("#ffffff")
        self.plot_widget.setLabel('left', 'Kt/V', color='#0f172a', size="14pt")
        self.plot_widget.setLabel('bottom', 'Tiempo de terapia (min)', color='#0f172a', size="14pt")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.25)

        right_axis = self.plot_widget.plotItem.getAxis('right')
        right_axis.enableAutoSIPrefix(False)
        right_axis.setLabel('Heitmann (L)', color='#ff8800')

        self.curve_ktv = self.plot_widget.plot(
            [], [],
            pen=pg.mkPen('#0284c7', width=3),
            symbol='o', symbolSize=8, symbolBrush='#0284c7',
            name='Kt/V'
        )

        self.p2 = pg.ViewBox()
        self.plot_widget.scene().addItem(self.p2)
        self.plot_widget.plotItem.getAxis('right').linkToView(self.p2)
        self.p2.setXLink(self.plot_widget.plotItem)

        self.curve_heit = pg.PlotDataItem(
            [], [],
            pen=pg.mkPen('#f59e0b', width=3),
            symbol='o', symbolSize=8, symbolBrush='#f59e0b',
            name='Heitmann (L)'
        )
        self.p2.addItem(self.curve_heit)
        self.plot_widget.addLegend()

        def updateViews():
            self.p2.setGeometry(self.plot_widget.plotItem.vb.sceneBoundingRect())
            self.p2.linkedViewChanged(self.plot_widget.plotItem.vb, self.p2.XAxis)

        updateViews()
        self.plot_widget.plotItem.vb.sigResized.connect(updateViews)

    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        self.setup_background()
        self.setStyleSheet(f"KTVScreen {{ background-color: {tokens['bg_main']}; }}")

        card_qss = (
            f"QFrame {{ background: {tokens['bg_card']}; "
            f"border-radius: 14px; border: 2px solid {tokens['border_card']}; }}"
        )
        for c in self.themed_cards:
            c.setStyleSheet(card_qss)

        lbl_qss = f"color: {tokens['text_secondary']}; font-size: 20px; font-weight: bold; border: none; background: transparent;"
        for l in self.themed_labels:
            l.setStyleSheet(lbl_qss)

        val_qss = (
            f"color: {tokens['text_primary']}; background: {tokens['bg_input']}; "
            f"font-size: 20px; font-weight: bold; border: 2px solid {tokens['border_card']}; "
            f"border-radius: 8px; padding: 6px;"
        )
        for v in self.themed_values:
            v.setStyleSheet(val_qss)

        ind_qss = (
            f"color: {tokens['val_uf']}; background: {tokens['bg_card_alt']}; "
            f"font-size: 22px; font-weight: bold; border: 2px solid {tokens['primary']}; "
            f"border-radius: 8px; padding: 6px;"
        )
        self.display_bioz.setStyleSheet(ind_qss)
        self.display_heitmann.setStyleSheet(ind_qss)

        self.btn_run_ktv.setStyleSheet(f"""
            QPushButton {{
                background: {tokens['primary']};
                color: #ffffff;
                border: none;
                border-radius: 10px;
                font-size: 20px;
                font-weight: bold;
                padding: 10px 16px;
            }}
            QPushButton:hover {{ background: {tokens['primary_hover']}; }}
            QPushButton:pressed {{ background: {tokens['primary_pressed']}; }}
            QPushButton:disabled {{ background: {tokens['btn_disabled_bg']}; color: {tokens['btn_disabled_text']}; }}
        """)

        self.results_list.setStyleSheet(f"""
            QListWidget {{
                background: {tokens['bg_card_alt']};
                font-size: 18px;
                color: {tokens['text_primary']};
                border: 1.5px solid {tokens['border_card']};
                border-radius: 10px;
            }}
            QListWidget::item {{
                padding: 6px 10px;
            }}
        """)

        if hasattr(self, "plot_widget") and self.plot_widget:
            self.plot_widget.setBackground(tokens["plot_bg"])
            for axis_name in ("left", "bottom"):
                ax = self.plot_widget.plotItem.getAxis(axis_name)
                ax.setPen(pg.mkPen(tokens["plot_axis"]))
                ax.setTextPen(pg.mkPen(tokens["plot_axis"]))

        selected_text = self.combo_freq.currentText()
        _, color, badge = self._FREQ_MAP.get(selected_text, (0, "#94a3b8", "● Deshabilitado"))
        self.lbl_freq_indicator.setText(badge)
        self.lbl_freq_indicator.setStyleSheet(
            f"color: {color}; font-size: 18px; font-weight: bold; "
            f"background: {tokens['bg_card_alt']}; border: 1px solid {tokens['border_card']}; "
            f"border-radius: 8px; padding: 4px 10px;"
        )

    def update_state(self, phase: TreatmentPhase):
        btn = getattr(self, "btn_run_ktv", None)
        combo = getattr(self, "combo_freq", None)
        lbl_schedule = getattr(self, "lbl_next_schedule", None)

        if btn is None or combo is None or lbl_schedule is None:
            return
        if not isValid(btn) or not isValid(combo) or not isValid(lbl_schedule):
            return

        active = phase == TreatmentPhase.RUNNING
        btn.setEnabled(active)
        combo.setEnabled(phase in (TreatmentPhase.IDLE, TreatmentPhase.PAUSED, TreatmentPhase.RUNNING))

        if phase not in (TreatmentPhase.RUNNING, TreatmentPhase.PAUSED):
            lbl_schedule.setText("Próxima medición: No programado")

    def update_patient_data(self, new_values: dict):
        required_widgets = [
            getattr(self, "display_name", None),
            getattr(self, "display_age", None),
            getattr(self, "display_height", None),
            getattr(self, "display_weight", None),
            getattr(self, "display_bioz", None),
        ]
        if any(w is None or not isValid(w) for w in required_widgets):
            return

        self.current_values = new_values
        self.display_name.setText(str(new_values.get("patient_name", "N/A")))
        self.display_age.setText(str(new_values.get("patient_age", "N/A")))
        self.display_height.setText(str(new_values.get("patient_height_cm", "N/A")) + " cm")
        self.display_weight.setText(str(new_values.get("patient_pre_weight_kg", "N/A")) + " kg")
        self.display_bioz.setText(f"{new_values.get('bioz_resistance', 0.0):.2f} Ω")

    def update_values(self, ktv_data: dict):
        if getattr(self, "display_heitmann", None) is None or not isValid(self.display_heitmann):
            return

        heit_val = _safe_float(ktv_data.get("heitmann_value", 0.0), 0.0)
        ktv_val = _safe_float(ktv_data.get("ktv_acumulado", 0.0), 0.0)
        measurement_type = ktv_data.get("type", "Auto")
        minutes_total = _safe_float(ktv_data.get("therapy_minutes", 0.0), 0.0)
        is_calc_event = bool(ktv_data.get("calculation_event", False))
        event_signature = str(ktv_data.get("event_id", ""))

        self.display_heitmann.setText(f"{heit_val:.2f} L" if heit_val > 0 else "--- L")

        if not is_calc_event:
            return

        if event_signature and event_signature == self._last_calc_signature:
            return
        if event_signature:
            self._last_calc_signature = event_signature

        if isinstance(ktv_data, dict) and "calculation_event" in ktv_data:
            ktv_data["calculation_event"] = False

        x_val = max(0.0, minutes_total)
        self.ktv_points.append((x_val, float(ktv_val)))
        self.heit_points.append((x_val, float(heit_val)))

        total_therapy_minutes = self._get_total_therapy_minutes()
        x_max = max(1.0, total_therapy_minutes)

        x_ktv, y_ktv = zip(*self.ktv_points)
        self.curve_ktv.setData(list(x_ktv), list(y_ktv))
        max_ktv = max([0.0] + list(y_ktv))
        self.plot_widget.setXRange(0.0, x_max, padding=0)
        self.plot_widget.setYRange(0.0, max(0.5, max_ktv * 1.3), padding=0)

        x_h, y_h = zip(*self.heit_points)
        self.curve_heit.setData(list(x_h), list(y_h))
        max_heit = max([0.0] + list(y_h))
        self.p2.setYRange(0.0, max(1.0, max_heit * 1.3))

        record_entry = {
            "timestamp": QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss"),
            "heitmann_l": round(heit_val, 2),
            "ktv": round(ktv_val, 3),
            "type": measurement_type,
            "therapy_minutes": minutes_total,
        }
        self.ktv_records.append(record_entry)

        ts = QDateTime.currentDateTime().toString("dd/MM HH:mm")
        is_manual = (measurement_type == "Manual")
        prefix = "[MANUAL]" if is_manual else "[AUTO]"
        item_text = (
            f"{ts} {prefix}  Kt/V: {ktv_val:.3f} | "
            f"Heit: {heit_val:.1f} L | t: {minutes_total:.1f} min"
        )

        if is_manual and 0 <= self._manual_pending_row < self.results_list.count():
            self.results_list.item(self._manual_pending_row).setText(item_text)
            self._manual_pending_row = -1
        else:
            self.results_list.addItem(item_text)

        self.results_list.scrollToBottom()
        while self.results_list.count() > 60:
            self.results_list.takeItem(0)

    def _get_total_therapy_minutes(self) -> float:
        hours = float(self.current_values.get("heparineTherapyHours", 0) or 0)
        minutes = float(self.current_values.get("heparineTherapyMinutes", 0) or 0)
        total = (hours * 60.0) + minutes
        return total if total > 0 else 180.0

    def update_schedule_display(self, next_measurement_time_str: str):
        label = getattr(self, "lbl_next_schedule", None)
        if label is None or not isValid(label):
            return
        label.setText(f"Próxima medición: {next_measurement_time_str}")

    _FREQ_MAP = {
        "15 minutos":  (15,  "#22c55e", "● 15 min"),
        "30 minutos":  (30,  "#3b82f6", "● 30 min"),
        "Deshabilitado": (0, "#94a3b8", "● Deshabilitado"),
    }

    def _on_frequency_changed(self, index: int):
        self._selected_frequency_index = index
        selected_text = self.combo_freq.currentText()
        freq_min, color, badge = self._FREQ_MAP.get(selected_text, (0, "#94a3b8", "● Deshabilitado"))
        tokens = ThemeManager.get_tokens()

        lbl = getattr(self, "lbl_freq_indicator", None)
        if lbl and isValid(lbl):
            lbl.setText(badge)
            lbl.setStyleSheet(
                f"color: {color}; font-size: 18px; font-weight: bold; "
                f"background: {tokens['bg_card_alt']}; border: 1px solid {tokens['border_card']}; "
                f"border-radius: 8px; padding: 4px 10px;"
            )

        if hasattr(self.parent_window, 'ktv_controller') and self.parent_window.ktv_controller:
            self.parent_window.ktv_controller.set_automatic_frequency(freq_min)
            logger.info(f"Frecuencia de cálculo automático de Kt/V cambiada a {freq_min} minutos.")

    def _on_run_ktv_now(self):
        if hasattr(self.parent_window, 'ktv_controller') and self.parent_window.ktv_controller:
            self.parent_window.ktv_controller.start_manual_measurement()
            ts = QDateTime.currentDateTime().toString("dd/MM HH:mm")
            self._manual_pending_row = self.results_list.count()
            self.results_list.addItem(f"{ts} → [MANUAL] Cálculo iniciado, esperando resultado...")
            self.results_list.scrollToBottom()
        else:
            if hasattr(self.parent_window, 'show_error_message'):
                self.parent_window.show_error_message("Controlador Kt/V no disponible.")

    def save_final_report(self):
        if not hasattr(self, 'ktv_records') or not self.ktv_records:
            return None

        try:
            os.makedirs("logs/ktv_reports", exist_ok=True)
            filename = f"logs/ktv_reports/ktv_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            fieldnames = ["timestamp", "heitmann_l", "ktv", "type", "therapy_minutes"]

            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.ktv_records)

            logger.info(f"Reporte Kt/V final guardado: {filename}")
            return filename
        except Exception as e:
            logger.error(f"Error guardando reporte final: {e}")
            return None

    def reset_screen_data(self, preserve_frequency: bool = True):
        self.ktv_records.clear()
        self.ktv_points.clear()
        self.heit_points.clear()
        self.results_list.clear()
        self.curve_ktv.setData([], [])
        self.curve_heit.setData([], [])
        self.display_name.setText("N/A")
        self.display_age.setText("N/A")
        self.display_height.setText("N/A")
        self.display_weight.setText("N/A")
        self.display_bioz.setText("--- Ω")
        self.display_heitmann.setText("--- L")
        self.lbl_next_schedule.setText("Próxima medición: No programado")
        self._last_recorded_ktv = 0.0
        self._waiting_manual_result = False
        self._manual_pending_row = -1
        self._last_calc_signature = ""
        if preserve_frequency:
            self.combo_freq.blockSignals(True)
            self.combo_freq.setCurrentIndex(self._selected_frequency_index)
            self.combo_freq.blockSignals(False)
        else:
            self.combo_freq.setCurrentIndex(2)
            self._selected_frequency_index = 2
