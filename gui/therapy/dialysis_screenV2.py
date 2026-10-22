# gui/therapy/dialysis_screenV2.py

"""
Pantalla principal de monitorización y control de la terapia de diálisis,
modernizada visualmente y compatible con el sistema de temas dinámicos.
"""

from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPainterPath
import pyqtgraph as pg
import numpy as np
from collections import deque
from gui.components.ui_components import LabeledParameterWidget, LabeledTimeInput
from gui.theme_manager import ThemeManager
from core.state_manager import TreatmentPhase
import logging

logger = logging.getLogger(__name__)

try:
    from logic.calculos import calculo_ptm
except ImportError:
    def calculo_ptm(a, b, c, d): return 0.0

try:
    from logic.uf_volume import litros_removidos
except ImportError:
    def litros_removidos(pulsos): return 0.0

try:
    from core.variables_map import VARIABLES
except ImportError:
    VARIABLES = {0x01: {}, 0x02: {}}


class PressureWaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.max_points = 300
        self.arterial_history = deque([-120.0] * self.max_points, maxlen=self.max_points)
        self.venous_history = deque([110.0] * self.max_points, maxlen=self.max_points)

        self.bg_color = QColor("#fcfcfc")
        self.grid_color = QColor("#64748b")
        self.art_color = QColor("#ef4444")
        self.ven_color = QColor("#0284c7")
        self.panel_bg = QColor("#2d3e58")

        tm = ThemeManager.instance()
        tm.theme_changed.connect(lambda _t: self.update())

    def add_values(self, arterial, venous):
        self.arterial_history.append(arterial)
        self.venous_history.append(venous)
        self.update()

    def paintEvent(self, event):
        if self.width() < 100 or self.height() < 100:
            return

        tokens = ThemeManager.get_tokens()
        self.bg_color = QColor(tokens["plot_bg"])
        self.grid_color = QColor(tokens["plot_grid"])
        self.art_color = QColor(tokens["val_blood"])
        self.ven_color = QColor(tokens["val_venous"])
        axis_color = QColor(tokens["plot_axis"])

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)

            width = self.width()
            height = self.height()
            right_panel_w = 155
            graph_width = max(1, width - right_panel_w - 10)

            # 1. Dibujar fondo total redondeado
            painter.setPen(Qt.NoPen)
            painter.setBrush(self.bg_color)
            painter.drawRoundedRect(0, 0, width, height, 10, 10)

            # 2. Dibujar rejilla (Grid)
            grid_pen = QPen(self.grid_color, 1, Qt.DashLine)
            painter.setPen(grid_pen)

            def to_y(val):
                if val is None or not isinstance(val, (int, float)):
                    return None
                val_clamped = max(-300.0, min(300.0, val))
                percentage = (val_clamped + 300.0) / 600.0
                return int(height - 15 - percentage * (height - 30))

            for val in [-200, -100, 0, 100, 200]:
                y_pos = to_y(val)
                if y_pos is not None:
                    painter.drawLine(0, y_pos, graph_width, y_pos)
                    painter.setPen(QPen(axis_color, 1))
                    painter.setFont(QFont("Consolas", 10, QFont.Bold))
                    painter.drawText(8, y_pos - 4, f"{val} mmHg")
                    painter.setPen(grid_pen)

            for step in range(1, 6):
                x_pos = int((step / 6) * graph_width)
                painter.drawLine(x_pos, 12, x_pos, height - 12)

            # 3. Dibujar trayectorias de ondas con trazo más nítido (2.5 px)
            art_path = QPainterPath()
            if len(self.arterial_history) > 1:
                first_valid = None
                for val in self.arterial_history:
                    if val is not None and isinstance(val, (int, float)):
                        first_valid = val
                        break
                if first_valid is not None:
                    y_pos = to_y(first_valid)
                    if y_pos is not None:
                        art_path.moveTo(0, y_pos)
                        for i, val in enumerate(self.arterial_history):
                            if val is not None and isinstance(val, (int, float)):
                                y = to_y(val)
                                if y is not None:
                                    x = int((i / (self.max_points - 1)) * graph_width)
                                    art_path.lineTo(x, y)
            painter.setPen(QPen(self.art_color, 2.5))
            painter.drawPath(art_path)

            ven_path = QPainterPath()
            if len(self.venous_history) > 1:
                first_valid = None
                for val in self.venous_history:
                    if val is not None and isinstance(val, (int, float)):
                        first_valid = val
                        break
                if first_valid is not None:
                    y_pos = to_y(first_valid)
                    if y_pos is not None:
                        ven_path.moveTo(0, y_pos)
                        for i, val in enumerate(self.venous_history):
                            if val is not None and isinstance(val, (int, float)):
                                y = to_y(val)
                                if y is not None:
                                    x = int((i / (self.max_points - 1)) * graph_width)
                                    ven_path.lineTo(x, y)
            painter.setPen(QPen(self.ven_color, 2.5))
            painter.drawPath(ven_path)

            # 4. Panel de leyendas derecho estilo tarjeta clínica
            right_panel_x = width - right_panel_w
            panel_rect = QRectF(float(right_panel_x), 6.0, float(right_panel_w - 6), float(height - 12))
            painter.setPen(QPen(QColor(tokens["border_card"]), 1.5))
            painter.setBrush(QColor(tokens["bg_card_alt"]))
            painter.drawRoundedRect(panel_rect, 10.0, 10.0)

            curr_art = self.arterial_history[-1]
            painter.setFont(QFont("Segoe UI", 13, QFont.Bold))
            painter.setPen(QPen(self.art_color))
            painter.drawText(right_panel_x + 12, 34, "● ART (mmHg)")
            painter.setFont(QFont("Consolas", 22, QFont.Bold))
            if curr_art is not None and isinstance(curr_art, (int, float)):
                painter.drawText(right_panel_x + 12, 68, f"{int(curr_art):+4d}")
            else:
                painter.drawText(right_panel_x + 12, 68, "  --")

            curr_ven = self.venous_history[-1]
            painter.setFont(QFont("Segoe UI", 13, QFont.Bold))
            painter.setPen(QPen(self.ven_color))
            painter.drawText(right_panel_x + 12, height // 2 + 28, "● VEN (mmHg)")
            painter.setFont(QFont("Consolas", 22, QFont.Bold))
            if curr_ven is not None and isinstance(curr_ven, (int, float)):
                painter.drawText(right_panel_x + 12, height // 2 + 62, f"{int(curr_ven):+4d}")
            else:
                painter.drawText(right_panel_x + 12, height // 2 + 62, "  --")
        finally:
            painter.end()


class SimpleValueDisplay(QWidget):
    """
    Widget compuesto para mostrar un parámetro clínico o temporizador de forma estandarizada.
    """

    def __init__(self, label_text: str, initial_value: str = "0.0", units: str = "", is_critical: bool = False):
        super().__init__()
        self.is_critical = is_critical
        self.setFixedHeight(92)

        self.frame = QFrame()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.frame)

        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(10, 8, 10, 8)
        frame_layout.setSpacing(4)

        tag_text = f"{label_text} ({units})" if units else label_text

        self.label_tag_units = QLabel(tag_text)
        self.label_tag_units.setAlignment(Qt.AlignCenter)

        self.label_value = QLabel(initial_value)
        self.label_value.setAlignment(Qt.AlignCenter)

        frame_layout.addWidget(self.label_tag_units)
        frame_layout.addWidget(self.label_value)

        tm = ThemeManager.instance()
        tm.theme_changed.connect(self.apply_theme_styles)
        self.apply_theme_styles(tm.current_theme_name)

    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        bg = "#FEF08A" if self.is_critical and not tokens.get("is_dark") else tokens["bg_card_alt"]
        self.frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 1.5px solid {tokens['border_card']};
                border-radius: 12px;
            }}
        """)
        self.label_tag_units.setStyleSheet(
            f"border: none; color: {tokens['text_secondary']}; font-weight: 700; font-size: 16px;"
        )
        self.label_value.setStyleSheet(
            f"border: none; color: {tokens['primary']}; font-family: Consolas, monospace; "
            f"font-weight: bold; font-size: 34px;"
        )

    def set_value(self, value):
        if isinstance(value, (int, float)):
            text = f"{value:.1f}" if value >= 10 else f"{value:.2f}"
        else:
            text = str(value)
        self.label_value.setText(text)

    def set_time_value(self, time_str: str):
        self.label_value.setText(time_str)


class DialysisScreen(QWidget):

    request_boolean_change = Signal(str, bool)

    def __init__(self, parent=None, values_dict=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_values = values_dict if values_dict is not None else {}
        self.themed_sublabels: list[QLabel] = []
        self.themed_unit_labels: list[QLabel] = []
        self._last_air_bubble_state = 0.0

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAutoFillBackground(True)

        # Historial para gráficas
        self.history_length = 600
        nan_array = [np.nan] * self.history_length
        self.venous_pressure_history = deque(nan_array, maxlen=self.history_length)
        self.arterial_pressure_history = deque(nan_array, maxlen=self.history_length)
        self.time_axis = np.arange(-self.history_length + 1, 1, dtype=np.float32)

        self.setup_ui()

        tm = ThemeManager.instance()
        tm.theme_changed.connect(self.apply_theme_styles)
        self.apply_theme_styles(tm.current_theme_name)

    def setup_ui(self):
        layout = QGridLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(16, 14, 16, 14)

        layout.setRowStretch(0, 2)
        layout.setRowStretch(1, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

        grid_params = QGridLayout()
        grid_params.setSpacing(14)
        grid_params.setRowStretch(0, 1)
        for column in range(4):
            grid_params.setColumnStretch(column, 1)

        # ==================== CARD 1: CIRCUITO DE SANGRE ====================
        self.blood_card = QFrame()
        self.blood_card.setObjectName("card")
        self.blood_card.setMinimumHeight(295)
        blood_layout = QVBoxLayout(self.blood_card)
        blood_layout.setContentsMargins(16, 14, 16, 14)
        blood_layout.setSpacing(10)

        self.blood_title = QLabel("CIRCUITO DE SANGRE")
        self.blood_title.setObjectName("card_title")
        blood_layout.addWidget(self.blood_title)

        bfr_layout = QHBoxLayout()
        bfr_v = QVBoxLayout()
        bfr_v.setSpacing(4)
        lbl_bfr_cap = QLabel("FLUJO DE SANGRE (Qb)")
        self.themed_sublabels.append(lbl_bfr_cap)
        bfr_v.addWidget(lbl_bfr_cap)

        bfr_value_row = QHBoxLayout()
        bfr_value_row.setSpacing(6)
        self.bfr_value = QLabel("0")
        self.bfr_value.setObjectName("val_large")
        bfr_unit = QLabel("mL/min")
        self.themed_unit_labels.append(bfr_unit)
        bfr_value_row.addWidget(self.bfr_value)
        bfr_value_row.addWidget(bfr_unit)
        bfr_value_row.addStretch()
        bfr_v.addLayout(bfr_value_row)
        bfr_layout.addLayout(bfr_v)
        bfr_layout.addStretch()
        blood_layout.addLayout(bfr_layout)

        art_p_layout = QHBoxLayout()
        art_p_label = QLabel("Presión Art.:")
        self.themed_sublabels.append(art_p_label)
        art_p_layout.addWidget(art_p_label)
        self.art_p_value = QLabel("-120 mmHg")
        art_p_layout.addStretch()
        art_p_layout.addWidget(self.art_p_value)
        blood_layout.addLayout(art_p_layout)

        ven_p_layout = QHBoxLayout()
        ven_p_label = QLabel("Presión Ven.:")
        self.themed_sublabels.append(ven_p_label)
        ven_p_layout.addWidget(ven_p_label)
        self.ven_p_value = QLabel("-80 mmHg")
        ven_p_layout.addStretch()
        ven_p_layout.addWidget(self.ven_p_value)
        blood_layout.addLayout(ven_p_layout)

        air_layout = QHBoxLayout()
        self.air_indicator = QLabel("DETECTOR DE AIRE")
        self.air_indicator.setAlignment(Qt.AlignCenter)
        self.air_indicator.setFixedHeight(40)
        self.air_indicator.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        air_layout.addWidget(self.air_indicator)
        blood_layout.addLayout(air_layout)

        grid_params.addWidget(self.blood_card, 0, 0)

        # ==================== CARD 2: CIRCUITO DIALIZADOR ====================
        self.dialysate_card = QFrame()
        self.dialysate_card.setObjectName("card")
        self.dialysate_card.setMinimumHeight(295)
        dialysate_layout = QVBoxLayout(self.dialysate_card)
        dialysate_layout.setContentsMargins(16, 14, 16, 14)
        dialysate_layout.setSpacing(10)

        self.dialysate_title = QLabel("CIRCUITO DIALIZADOR")
        self.dialysate_title.setObjectName("card_title")
        dialysate_layout.addWidget(self.dialysate_title)

        temp_layout = QHBoxLayout()
        temp_v = QVBoxLayout()
        temp_v.setSpacing(4)
        lbl_temp_cap = QLabel("TEMPERATURA DIALIZADO")
        self.themed_sublabels.append(lbl_temp_cap)
        temp_v.addWidget(lbl_temp_cap)

        temp_value_row = QHBoxLayout()
        temp_value_row.setSpacing(6)
        self.temp_value = QLabel("0.0")
        self.temp_value.setObjectName("val_large_green")
        self.temp_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.temp_value.setFixedWidth(140)
        temp_unit = QLabel("°C")
        self.themed_unit_labels.append(temp_unit)
        temp_value_row.addWidget(self.temp_value)
        temp_value_row.addWidget(temp_unit)
        temp_value_row.addStretch()
        temp_v.addLayout(temp_value_row)
        temp_layout.addLayout(temp_v)
        dialysate_layout.addLayout(temp_layout)

        cond_layout = QHBoxLayout()
        cond_label = QLabel("Conductividad:")
        self.themed_sublabels.append(cond_label)
        cond_layout.addWidget(cond_label)
        self.cond_val = QLabel("14.1 mS/cm")
        self.cond_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        cond_layout.addStretch()
        cond_layout.addWidget(self.cond_val)
        dialysate_layout.addLayout(cond_layout)

        dfr_layout = QHBoxLayout()
        dfr_label = QLabel("Flujo Dializado:")
        self.themed_sublabels.append(dfr_label)
        dfr_layout.addWidget(dfr_label)
        self.dfr_val_label = QLabel("500 mL/min")
        dfr_layout.addStretch()
        dfr_layout.addWidget(self.dfr_val_label)
        dialysate_layout.addLayout(dfr_layout)

        tmp_layout = QHBoxLayout()
        tmp_label = QLabel("PTM:")
        self.themed_sublabels.append(tmp_label)
        tmp_layout.addWidget(tmp_label)
        self.tmp_val = QLabel("85 mmHg")
        self.tmp_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        tmp_layout.addStretch()
        tmp_layout.addWidget(self.tmp_val)
        dialysate_layout.addLayout(tmp_layout)

        grid_params.addWidget(self.dialysate_card, 0, 1)

        # ==================== CARD 3: ULTRAFILTRACIÓN ====================
        self.uf_card = QFrame()
        self.uf_card.setObjectName("card")
        self.uf_card.setMinimumHeight(295)
        uf_layout = QVBoxLayout(self.uf_card)
        uf_layout.setContentsMargins(16, 14, 16, 14)
        uf_layout.setSpacing(10)

        self.uf_title = QLabel("ULTRAFILTRACIÓN (UF)")
        self.uf_title.setObjectName("card_title")
        uf_layout.addWidget(self.uf_title)

        meta_layout = QHBoxLayout()
        meta_v = QVBoxLayout()
        meta_v.setSpacing(4)
        lbl_meta_cap = QLabel("OBJETIVO TOTAL UF")
        self.themed_sublabels.append(lbl_meta_cap)
        meta_v.addWidget(lbl_meta_cap)

        meta_value_row = QHBoxLayout()
        meta_value_row.setSpacing(6)
        self.uf_goal_val = QLabel("0.00")
        self.uf_goal_val.setObjectName("val_large_cyan")
        uf_goal_unit = QLabel("L")
        self.themed_unit_labels.append(uf_goal_unit)
        meta_value_row.addWidget(self.uf_goal_val)
        meta_value_row.addWidget(uf_goal_unit)
        meta_value_row.addStretch()
        meta_v.addLayout(meta_value_row)
        meta_layout.addLayout(meta_v)
        meta_layout.addStretch()
        uf_layout.addLayout(meta_layout)
        
        ufr_layout = QHBoxLayout()
        ufr_label = QLabel("Tasa de UF:")
        self.themed_sublabels.append(ufr_label)
        ufr_layout.addWidget(ufr_label)
        self.uf_rate_val = QLabel("0.00 L/hora")
        self.ufr_val = self.uf_rate_val
        ufr_layout.addStretch()
        ufr_layout.addWidget(self.uf_rate_val)
        uf_layout.addLayout(ufr_layout)

        rem_layout = QHBoxLayout()
        rem_label = QLabel("UF Removida:")
        self.themed_sublabels.append(rem_label)
        rem_layout.addWidget(rem_label)
        self.uf_rem_val = QLabel("0.00 L")
        rem_layout.addStretch()
        rem_layout.addWidget(self.uf_rem_val)
        uf_layout.addLayout(rem_layout)

        # pulse_layout = QHBoxLayout()
        # pulse_label = QLabel("Pulsos UF (temp):")
        # self.themed_sublabels.append(pulse_label)
        # pulse_layout.addWidget(pulse_label)
        # self.uf_pulse_val = QLabel("0")
        # pulse_layout.addStretch()
        # pulse_layout.addWidget(self.uf_pulse_val)
        # uf_layout.addLayout(pulse_layout)

        ktv_layout = QHBoxLayout()
        ktv_label = QLabel("Kt/V Acumulado:")
        self.themed_sublabels.append(ktv_label)
        ktv_layout.addWidget(ktv_label)
        self.ktv_val = QLabel("0.00")
        ktv_layout.addStretch()
        ktv_layout.addWidget(self.ktv_val)
        uf_layout.addLayout(ktv_layout)

        grid_params.addWidget(self.uf_card, 0, 2)

        # ==================== COLUMNA 4: SIGNOS VITALES Y TIEMPO ====================
        columna_4_layout = QVBoxLayout()
        columna_4_layout.setSpacing(10)

        self.vitals_card = QFrame()
        self.vitals_card.setObjectName("card")
        self.vitals_card.setMinimumHeight(215)
        vitals_layout = QVBoxLayout(self.vitals_card)
        vitals_layout.setContentsMargins(14, 12, 14, 12)
        vitals_layout.setSpacing(6)

        self.vitals_title = QLabel("SIGNOS VITALES")
        self.vitals_title.setObjectName("card_title")
        vitals_layout.addWidget(self.vitals_title)

        nibp_layout = QHBoxLayout()
        lbl_nibp = QLabel("P.A. (NIBP):")
        self.themed_sublabels.append(lbl_nibp)
        nibp_layout.addWidget(lbl_nibp)
        self.nibp_value = QLabel("-- / --")
        nibp_layout.addStretch()
        nibp_layout.addWidget(self.nibp_value)
        vitals_layout.addLayout(nibp_layout)

        hr_layout = QHBoxLayout()
        lbl_hr = QLabel("FC:")
        self.themed_sublabels.append(lbl_hr)
        hr_layout.addWidget(lbl_hr)
        self.hr_value = QLabel("--")
        hr_layout.addStretch()
        hr_layout.addWidget(self.hr_value)
        self.hr_unit = QLabel("lpm")
        hr_layout.addWidget(self.hr_unit)
        vitals_layout.addLayout(hr_layout)

        spo2_layout = QHBoxLayout()
        lbl_spo2 = QLabel("SpO2:")
        self.themed_sublabels.append(lbl_spo2)
        spo2_layout.addWidget(lbl_spo2)
        self.spo2_value = QLabel("-- %")
        spo2_layout.addStretch()
        spo2_layout.addWidget(self.spo2_value)
        vitals_layout.addLayout(spo2_layout)

        self.spo2_status_label = QLabel("")
        vitals_layout.addWidget(self.spo2_status_label)

        self.btn_nibp_screen = QPushButton("Baumanómetro…")
        self.btn_nibp_screen.setFixedHeight(38)
        self.btn_nibp_screen.clicked.connect(self.show_nibp_config_screen)
        vitals_layout.addWidget(self.btn_nibp_screen)

        self.time_card = QFrame()
        self.time_card.setObjectName("card")
        self.time_card.setMinimumHeight(96)
        time_layout = QVBoxLayout(self.time_card)
        time_layout.setContentsMargins(10, 8, 10, 8)
        time_layout.setSpacing(6)

        self.remaining_time_display = SimpleValueDisplay("T. Restante", "00:00", "")
        self.elapsed_time_display = SimpleValueDisplay("T. Terapia", "00:00", "")
        self.elapsed_time_display.setFixedHeight(80)
        time_layout.addWidget(self.elapsed_time_display)

        columna_4_layout.addWidget(self.vitals_card, 2)
        columna_4_layout.addWidget(self.time_card, 1)
        grid_params.addLayout(columna_4_layout, 0, 3)

        layout.addLayout(grid_params, 0, 0, 1, 2)

        # ==================== ÁREA GRÁFICA ====================
        self.pressure_plot = PressureWaveformWidget()
        self.pressure_plot.setMinimumHeight(310)
        self.graph_container = QFrame()
        self.graph_container.setObjectName("graph_card")
        graph_layout = QVBoxLayout(self.graph_container)
        graph_layout.setContentsMargins(10, 10, 10, 10)
        graph_layout.addWidget(self.pressure_plot)
        layout.addWidget(self.graph_container, 1, 1, 1, 1)

        # ==================== BOTONES DE CONTROL ====================
        self.buttons_container = QFrame()
        self.buttons_container.setMinimumWidth(400)
        self.buttons_container.setObjectName("card")

        buttons_layout = QGridLayout(self.buttons_container)
        buttons_layout.setSpacing(10)
        buttons_layout.setContentsMargins(14, 14, 14, 14)
        for i in range(3):
            buttons_layout.setColumnStretch(i, 1)

        self.action_buttons = {}

        button_config = [
            ("INICIAR", "#16a34a", getattr(self.parent_window, "start_treatment", lambda: None)),
            ("PAUSAR", "#f59e0b", getattr(self.parent_window, "pause_treatment", lambda: None)),
            ("DETENER", "#dc2626", getattr(self.parent_window, "stop_treatment", lambda: None)),
            ("MENÚ TERAPIA", "nav", self.show_therapy_config),
            ("MENÚ PACIENTE", "nav", self.show_patient_config),
            ("HEPARINA", "nav", self.show_heparin_config_screen),
            ("INICIAR CEBADO", "nav", getattr(self.parent_window, "start_priming", lambda: None)),
            ("DETENER CEBADO", "nav", getattr(self.parent_window, "stop_priming", lambda: None)),
            ("Kt/V", "nav", getattr(self.parent_window, "show_ktv_screen", lambda: None)),
        ]

        for i, (text, color_role, callback) in enumerate(button_config):
            btn = QPushButton(text)
            btn.setFixedHeight(78)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setProperty("color_role", color_role)
            btn.clicked.connect(callback)
            self.action_buttons[text] = btn
            row = i // 3
            col = i % 3
            buttons_layout.addWidget(btn, row, col)

        layout.addWidget(self.buttons_container, 1, 0, 1, 1)

    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(tokens["bg_main"]))
        self.setPalette(palette)
        self.setStyleSheet(f"DialysisScreen {{ background-color: {tokens['bg_main']}; }}")

        card_style = (
            f"QFrame#card, QFrame#graph_card {{ background-color: {tokens['bg_card']}; "
            f"border: 2px solid {tokens['border_card']}; border-radius: 16px; }}"
        )
        for card in (
            self.blood_card, self.dialysate_card, self.uf_card,
            self.vitals_card, self.time_card, self.graph_container, self.buttons_container
        ):
            card.setStyleSheet(card_style)

        lbl_size = tokens.get("font_size_param_label", "25px")
        val_size = tokens.get("font_size_param_val", "30px")
        unit_size = tokens.get("font_size_param_unit", "22px")
        large_size = tokens.get("font_size_val_large", "48px")
        title_size = tokens.get("font_size_card_title", "20px")
        vital_size = tokens.get("font_size_vital_val", "24px")

        title_style = (
            f"color: {tokens['title_color']}; font-size: {title_size}; font-weight: bold; "
            f"background: transparent; border: none; border-bottom: 2px solid {tokens['border_card']}; "
            f"padding-bottom: 6px; margin-bottom: 4px;"
        )
        for t_lbl in (self.blood_title, self.dialysate_title, self.uf_title, self.vitals_title):
            t_lbl.setStyleSheet(title_style)

        sublabel_style = f"font-size: {lbl_size}; color: {tokens['text_secondary']}; font-weight: 600; border: none;"
        for lbl in self.themed_sublabels:
            lbl.setStyleSheet(sublabel_style)

        unit_style = f"font-size: {unit_size}; color: {tokens['text_muted']}; font-weight: 600; border: none;"
        for u_lbl in self.themed_unit_labels:
            u_lbl.setStyleSheet(unit_style)

        mono = ThemeManager.DEFAULT_MONOSPACE_FONTS
        self.bfr_value.setStyleSheet(
            f"color: {tokens['val_blood']}; font-family: {mono}; font-size: {large_size}; font-weight: bold; border: none;"
        )
        self.temp_value.setStyleSheet(
            f"color: {tokens['val_temp']}; font-family: {mono}; font-size: {large_size}; font-weight: bold; border: none;"
        )
        self.uf_goal_val.setStyleSheet(
            f"color: {tokens['val_uf']}; font-family: {mono}; font-size: {large_size}; font-weight: bold; border: none;"
        )

        self.art_p_value.setStyleSheet(
            f"color: {tokens['val_blood']}; font-weight: bold; font-family: {mono}; font-size: {val_size}; border: none;"
        )
        self.ven_p_value.setStyleSheet(
            f"color: {tokens['val_venous']}; font-weight: bold; font-family: {mono}; font-size: {val_size}; border: none;"
        )

        val_secondary_style = (
            f"color: {tokens['val_venous']}; font-weight: bold; font-family: {mono}; font-size: {val_size}; border: none;"
        )
        for v_lbl in (self.cond_val, self.dfr_val_label, self.tmp_val, self.uf_rate_val, self.uf_rem_val, self.ktv_val):
            v_lbl.setStyleSheet(val_secondary_style)

        # self.uf_pulse_val.setStyleSheet(
        #     f"color: {tokens['warning']}; font-weight: bold; font-family: {mono}; font-size: 24px; border: none;"
        # )

        self.nibp_value.setStyleSheet(
            f"color: {tokens['val_vital_bp']}; font-weight: bold; font-size: {vital_size}; font-family: {mono}; border: none;"
        )
        self.hr_value.setStyleSheet(
            f"color: {tokens['val_vital_hr']}; font-weight: bold; font-size: {vital_size}; font-family: {mono}; border: none;"
        )
        self.hr_unit.setStyleSheet(f"color: {tokens['text_muted']}; font-size: 15px; margin-left: 4px; border: none;")
        self.spo2_value.setStyleSheet(
            f"color: {tokens['val_vital_spo2']}; font-weight: bold; font-size: {vital_size}; font-family: {mono}; border: none;"
        )
        self.spo2_status_label.setStyleSheet(f"color: {tokens['text_muted']}; font-size: 15px; border: none;")

        self.btn_nibp_screen.setStyleSheet(f"""
            QPushButton {{
                background-color: {tokens['nav_btn_bg']};
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
                padding: 4px 10px;
                border: 1px solid {tokens['border_card']};
            }}
            QPushButton:hover {{ background-color: {tokens['primary']}; }}
        """)

        self.update_air_bubble_indicator(self._last_air_bubble_state)

        for text, btn in self.action_buttons.items():
            role = btn.property("color_role")
            bg = tokens["nav_btn_bg"] if role == "nav" else role
            btn.setStyleSheet(self._button_style(bg, btn.isEnabled()))

    def update_values(self, new_values: dict):
        """Update all displayed values."""
        self.current_values = new_values

        uf_rate_val = self.current_values.get("ultraFilterPumpSpeed", 0.0)
        uf_rate = float(uf_rate_val) if uf_rate_val is not None else 0.0
        self.uf_rate_val.setText(f"{uf_rate:.2f} L/hora")

        hep_hours_val = self.current_values.get("heparineTherapyHours", 0.0)
        hep_minutes_val = self.current_values.get("heparineTherapyMinutes", 0.0)
        uf_therapy_hours = float(hep_hours_val) if hep_hours_val is not None else 0.0
        uf_therapy_minutes = float(hep_minutes_val) if hep_minutes_val is not None else 0.0
        therapy_duration_hours = uf_therapy_hours + (uf_therapy_minutes / 60.0)

        uf_goal = uf_rate * therapy_duration_hours
        self.uf_goal_val.setText(f"{uf_goal:.2f}")

        cycle_count_val = self.current_values.get("ultraFilterCycleCount", 0.0)
        uf_pulse_count = float(cycle_count_val) if cycle_count_val is not None else 0.0
        uf_removed = litros_removidos(int(uf_pulse_count))
        self.uf_rem_val.setText(f"{uf_removed:.2f} L")

        # pulse_display = int(uf_pulse_count) if uf_pulse_count is not None else 0
        # self.uf_pulse_val.setText(str(pulse_display))

        venous_pressure_val = self.current_values.get("bloodVenousPressureData", 0.0)
        arterial_pressure_val = self.current_values.get("bloodArteryPressureData", 0.0)
        venous_pressure = venous_pressure_val if venous_pressure_val is not None else 0.0
        arterial_pressure = arterial_pressure_val if arterial_pressure_val is not None else 0.0
        self.pressure_plot.add_values(arterial_pressure, venous_pressure)

        pd_in = self.current_values.get("dialyPresIFProcessData", 0.0)
        pd_out = self.current_values.get("dialyPresOFProcessData", 0.0)
        try:
            ptm_calculated = calculo_ptm(pd_in, pd_out, arterial_pressure, venous_pressure)
        except Exception:
            ptm_calculated = 0.0
        self.current_values["CALC_PTM"] = ptm_calculated

        parameter_mapping = {
            "bloodArteryPressureData":  self.art_p_value,
            "bloodVenousPressureData":  self.ven_p_value,
            "CALC_PTM":                 self.tmp_val,
            "dialyCondVariableData":    self.cond_val,
            "bloodFlowVariableData":    self.bfr_value,
            "balanceChamberSetTiming":  self.dfr_val_label,
            "dialyTempIFProcessData":   self.temp_value,
            "ktv_projectado":           self.ktv_val,
            "airBubbleInBloodDetected": self.air_indicator,
        }

        for tag, widget in parameter_mapping.items():
            value = self.current_values.get(tag, 0.0)
            self._set_label_value(tag, widget, value)

        air_bubble = self.current_values.get("airBubbleInBloodDetected", 0.0)
        self._last_air_bubble_state = air_bubble
        self.update_air_bubble_indicator(air_bubble)

        if hasattr(self, 'parent_window') and hasattr(self.parent_window, 'state'):
            self.update_state(self.parent_window.state.current_phase)

    def _uf_removed_liters(self) -> float:
        cycle_count_val = self.current_values.get("ultraFilterCycleCount", 0.0)
        try:
            pulses = int(float(cycle_count_val)) if cycle_count_val is not None else 0
        except (TypeError, ValueError):
            pulses = 0
        return float(litros_removidos(pulses))


    def _time_to_decimal_hours(self, time_str: str) -> float:
        try:
            if ":" not in time_str:
                return 0.0
            h, m = map(int, time_str.split(":"))
            return h + (m / 60.0)
        except Exception:
            return 0.0

    def update_air_bubble_indicator(self, value):
        tokens = ThemeManager.get_tokens()
        if value == 1.0 or value == 1:
            self.air_indicator.setText("¡BURBUJA DE AIRE!")
            self.air_indicator.setStyleSheet(f"""
                background-color: {tokens['danger']};
                color: #ffffff;
                font-weight: bold;
                border-radius: 8px;
                font-size: 18px;
                border: none;
            """)
        else:
            self.air_indicator.setText("DETECTOR DE AIRE: OK")
            self.air_indicator.setStyleSheet(f"""
                background-color: {tokens['success']};
                color: #ffffff;
                font-weight: bold;
                border-radius: 8px;
                font-size: 18px;
                border: none;
            """)

    def show_heparin_config_screen(self):
        if self.parent_window and hasattr(self.parent_window, "show_heparin_config_screen"):
            self.parent_window.show_heparin_config_screen()

    def show_nibp_config_screen(self):
        if self.parent_window and hasattr(self.parent_window, "show_nibp_screen"):
            self.parent_window.show_nibp_screen()

    def _format_display_value(self, tag: str, value):
        try:
            if value is None:
                val_float = 0.0
            else:
                val_float = float(value)
        except (TypeError, ValueError):
            return str(value)

        if tag in {"bloodArteryPressureData", "bloodVenousPressureData"}:
            try:
                return f"{val_float:.1f} mmHg"
            except (TypeError, ValueError):
                return str(val_float)

        if tag == "CALC_PTM":
            try:
                return f"{val_float:.2f} mmHg"
            except (TypeError, ValueError):
                return str(val_float)

        if tag == "dialyCondVariableData":
            try:
                return f"{val_float:.2f} mS/cm"
            except (TypeError, ValueError):
                return str(val_float)

        if tag == "bloodFlowVariableData":
            try:
                return f"{val_float:.0f}"
            except (TypeError, ValueError):
                return str(val_float)

        if tag == "balanceChamberSetTiming":
            try:
                return f"{val_float:.0f} mL/min"
            except (TypeError, ValueError):
                return str(val_float)

        if tag == "dialyTempIFProcessData":
            try:
                return f"{val_float:5.1f}"
            except (TypeError, ValueError):
                return str(val_float)

        if tag in {"UF Total", "uf_goal_liters"}:
            try:
                return f"{val_float:.2f} L"
            except (TypeError, ValueError):
                return str(val_float)

        if tag in {"ktv_acumulado", "ktv_projectado"}:
            try:
                return f"{val_float:.2f}"
            except (TypeError, ValueError):
                return str(val_float)

        return str(val_float)

    def _set_label_value(self, tag: str, widget: QLabel, value):
        widget.setText(self._format_display_value(tag, value))

    def _button_style(self, background_color: str, enabled: bool = True):
        tokens = ThemeManager.get_tokens()
        if not enabled:
            return f"""
                QPushButton {{
                    background: {tokens['btn_disabled_bg']};
                    color: {tokens['btn_disabled_text']};
                    font-weight: bold;
                    font-size: 20px;
                    border-radius: 12px;
                    border: 2px solid {tokens['border_card']};
                }}
            """

        resolved_bg = tokens["nav_btn_bg"] if background_color in ("nav", "#06298a") else background_color
        return f"""
            QPushButton {{
                background: {resolved_bg};
                color: #ffffff;
                font-weight: bold;
                font-size: 20px;
                border-radius: 12px;
                border: 2px solid {tokens['border_strong']};
            }}
            QPushButton:hover {{
                background: {tokens['primary']};
            }}
            QPushButton:pressed {{
                background: {tokens['primary_pressed']};
            }}
        """

    def on_user_boolean_command(self, tag, state):
        self.request_boolean_change.emit(tag, state)

    def set_start_stop_buttons_state(self, enable_start: bool, enable_stop: bool, enable_pause: bool):
        tokens = ThemeManager.get_tokens()
        btn_iniciar = self.action_buttons.get("INICIAR")
        btn_detener = self.action_buttons.get("DETENER")
        btn_pausar = self.action_buttons.get("PAUSAR")

        if btn_iniciar:
            btn_iniciar.setEnabled(enable_start)
            btn_iniciar.setStyleSheet(self._button_style(tokens["success"], enable_start))

        if btn_detener:
            btn_detener.setEnabled(enable_stop)
            btn_detener.setStyleSheet(self._button_style(tokens["danger"], enable_stop))

        if btn_pausar:
            btn_pausar.setEnabled(enable_pause)
            btn_pausar.setStyleSheet(self._button_style(tokens["warning"], enable_pause))

    def show_therapy_config(self):
        if self.parent_window and hasattr(self.parent_window, "show_therapy_config_screen"):
            self.parent_window.show_therapy_config_screen()

    def show_patient_config(self):
        if self.parent_window and hasattr(self.parent_window, "show_patient_config_screen"):
            self.parent_window.show_patient_config_screen()

    def update_therapy_times(self, elapsed_str: str, remaining_str: str):
        if hasattr(self, 'elapsed_time_display') and self.elapsed_time_display:
            self.elapsed_time_display.set_time_value(elapsed_str)
        if hasattr(self, 'remaining_time_display') and self.remaining_time_display:
            self.remaining_time_display.set_time_value(remaining_str)

    def update_nibp_measurement(self, sys_mmhg: int, dia_mmhg: int, map_mmhg: int, hr_bpm: int):
        if sys_mmhg >= 0 and dia_mmhg >= 0:
            self.nibp_value.setText(f"{sys_mmhg} / {dia_mmhg}")
        else:
            self.nibp_value.setText("-- / --")

        if hr_bpm >= 0:
            self.hr_value.setText(str(hr_bpm))
        else:
            self.hr_value.setText("--")

    def update_spo2(self, data):
        if not data:
            self.spo2_value.setText("-- %")
            self.spo2_status_label.setText("")
            return

        value = data.get("spo2")
        self.spo2_value.setText(f"{value} %" if value is not None else "-- %")

        if data.get("sensor_off"):
            status_text = "Sensor desconectado"
        elif data.get("no_finger"):
            status_text = "Sin dedo"
        elif data.get("no_pulse"):
            status_text = "Sin pulso"
        elif data.get("searching"):
            status_text = "Buscando…"
        elif data.get("signal_weak"):
            status_text = "Señal débil"
        else:
            status_text = ""
        self.spo2_status_label.setText(status_text)

    def set_priming_buttons_state(self, enable_start_priming: bool, enable_stop_priming: bool):
        btn_start_priming = self.action_buttons.get("INICIAR CEBADO")
        btn_stop_priming = self.action_buttons.get("DETENER CEBADO")

        if btn_start_priming:
            btn_start_priming.setEnabled(enable_start_priming)
            btn_start_priming.setStyleSheet(self._button_style("nav", enable_start_priming))

        if btn_stop_priming:
            btn_stop_priming.setEnabled(enable_stop_priming)
            btn_stop_priming.setStyleSheet(self._button_style("nav", enable_stop_priming))

    def update_state(self, phase: TreatmentPhase):
        treatment_mode_selection = self.current_values.get("treatmentModeSelection", 0.0)
        if int(treatment_mode_selection or 0) == 3:
            self.set_priming_buttons_state(False, False)
            self.set_start_stop_buttons_state(False, False, False)
            return

        if hasattr(self.parent_window, '_can_start_treatment'):
            can_start = self.parent_window._can_start_treatment()
        else:
            temp_actual = self.current_values.get("dialyTempIFProcessData", 0.0) or 0.0
            temp_set = self.current_values.get("dialyTempControlSetPoint", 0.0) or 0.0
            cond_actual = self.current_values.get("dialyCondVariableData", 0.0) or 0.0
            cond_set = self.current_values.get("dialyCondControlSetPoint", 0.0) or 0.0

            temp_ok = (temp_actual - temp_set <= 2.0) and (temp_set - temp_actual <= 5.0)
            cond_ok = abs(cond_actual - cond_set) <= 2.0
            can_start = temp_ok and cond_ok

        if phase == TreatmentPhase.RUNNING:
            self.set_priming_buttons_state(False, False)
            self.set_start_stop_buttons_state(False, True, True)
        elif phase == TreatmentPhase.PAUSED:
            self.set_priming_buttons_state(False, False)
            self.set_start_stop_buttons_state(can_start, True, False)
        elif phase == TreatmentPhase.READY:
            self.set_priming_buttons_state(False, True)
            self.set_start_stop_buttons_state(can_start, False, False)
        elif phase == TreatmentPhase.PREPARING:
            self.set_priming_buttons_state(False, True)
            self.set_start_stop_buttons_state(False, False, False)
        elif phase == TreatmentPhase.IDLE:
            self.set_priming_buttons_state(True, False)
            self.set_start_stop_buttons_state(False, False, False)
        else:
            self.set_priming_buttons_state(False, False)
            self.set_start_stop_buttons_state(False, False, False)
