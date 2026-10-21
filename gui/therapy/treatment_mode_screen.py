# gui/therapy/treatment_mode_screen.py
"""
Módulo para la selección del modo de tratamiento de la máquina de hemodiálisis,
modernizado y compatible con el sistema de temas dinámicos.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QButtonGroup, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
import time
import logging
from gui.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class TreatmentModeScreen(QWidget):
    """
    Pantalla exclusiva para seleccionar el tipo de tratamiento:
    Hemodiálisis, Hemodiafiltración, Ultrafiltración, Limpieza
    """
    request_setpoint_change = Signal(str, float)

    def __init__(self, parent=None, values_dict=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_values = values_dict if values_dict is not None else {}
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.pending_mode_change_deadline = None
        self.commanded_mode_value = None

        self.setup_ui()

        tm = ThemeManager.instance()
        tm.theme_changed.connect(self.apply_theme_styles)
        self.apply_theme_styles(tm.current_theme_name)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 30, 40, 30)
        main_layout.setSpacing(24)

        # Título
        self.title_lbl = QLabel("SELECCIÓN DE MODALIDAD DE TERAPIA")
        self.title_lbl.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.title_lbl)

        self.sep = QFrame()
        self.sep.setFrameShape(QFrame.HLine)
        self.sep.setFixedHeight(2)
        main_layout.addWidget(self.sep)

        # Frame de botones
        self.mode_frame = QFrame()
        self.mode_frame.setObjectName("card")
        mode_layout = QVBoxLayout(self.mode_frame)
        mode_layout.setContentsMargins(32, 32, 32, 32)
        mode_layout.setSpacing(24)

        self.lbl_mode = QLabel("Seleccione la modalidad operativa que desea ejecutar:")
        mode_layout.addWidget(self.lbl_mode)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(20)

        # Botones de modo
        self.btn_hemodialysis      = QPushButton("Hemodiálisis\n(HD)")
        self.btn_hemodiafiltration = QPushButton("Hemodiafiltración\n(HDF)")
        self.btn_ultrafiltration   = QPushButton("Ultrafiltración\n(UF Aislada)")
        self.btn_cleaning          = QPushButton("Desinfección /\nLimpieza")

        self.mode_button_group = QButtonGroup(self)
        self.mode_button_group.setExclusive(True)

        self.mode_buttons_info = [
            (self.btn_hemodialysis,      "treatmentModeSelection", 0.0),
            (self.btn_hemodiafiltration, "treatmentModeSelection", 1.0),
            (self.btn_ultrafiltration,   "treatmentModeSelection", 2.0),
            (self.btn_cleaning,          "treatmentModeSelection", 3.0),
        ]

        self.style_mode_unchecked = ""
        self.style_mode_checked = ""

        for btn, tag, value in self.mode_buttons_info:
            btn.setMinimumHeight(160)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            btn.setCheckable(True)
            btn.toggled.connect(lambda checked, b=btn, t=tag, v=value:
                                self._on_mode_toggled(b, t, v, checked))
            buttons_layout.addWidget(btn)
            self.mode_button_group.addButton(btn)

        mode_layout.addLayout(buttons_layout)
        main_layout.addWidget(self.mode_frame)

        main_layout.addStretch(1)

        # # Botón Volver
        # self.btn_back = QPushButton("← Volver a Diálisis")
        # self.btn_back.setFixedSize(260, 64)
        # if self.parent_window and hasattr(self.parent_window, "show_dialysis_screen"):
        #     self.btn_back.clicked.connect(self.parent_window.show_dialysis_screen)
        # main_layout.addWidget(self.btn_back, alignment=Qt.AlignRight)

    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        self.setStyleSheet(f"background-color: {tokens['bg_main']};")

        self.title_lbl.setStyleSheet(
            f"font-size: 38px; font-weight: bold; color: {tokens['title_color']}; background: transparent;"
        )
        self.sep.setStyleSheet(f"background-color: {tokens['border_card']}; border: none;")
        self.mode_frame.setStyleSheet(
            f"QFrame#card {{ background-color: {tokens['bg_card']}; "
            f"border: 2px solid {tokens['border_card']}; border-radius: 18px; }}"
        )
        self.lbl_mode.setStyleSheet(
            f"font-size: 24px; font-weight: bold; color: {tokens['text_secondary']}; border: none;"
        )

        self.style_mode_unchecked = f"""
            QPushButton {{
                background-color: {tokens['nav_btn_bg']};
                color: #FFFFFF;
                font-size: 26px;
                font-weight: bold;
                border-radius: 16px;
                padding: 24px 20px;
                border: 2px solid {tokens['border_card']};
            }}
            QPushButton:hover {{
                background-color: {tokens['primary']};
                border: 2px solid {tokens['nav_btn_active_border']};
            }}
        """
        self.style_mode_checked = f"""
            QPushButton {{
                background-color: {tokens['success']};
                color: #FFFFFF;
                font-size: 26px;
                font-weight: bold;
                border-radius: 16px;
                padding: 24px 20px;
                border: 3px solid {tokens['success_bright']};
            }}
            QPushButton:hover {{
                background-color: {tokens['success']};
            }}
        """

        for btn, _, _ in self.mode_buttons_info:
            btn.setStyleSheet(self.style_mode_checked if btn.isChecked() else self.style_mode_unchecked)

        # self.btn_back.setStyleSheet(f"""
        #     QPushButton {{
        #         background-color: {tokens['danger']};
        #         color: #FFFFFF;
        #         font-size: 20px;
        #         font-weight: bold;
        #         border-radius: 12px;
        #         border: none;
        #     }}
        #     QPushButton:hover {{ background-color: #B91C1C; }}
        # """)

    def _on_mode_toggled(self, button: QPushButton, tag: str, value: float, checked: bool):
        if checked:
            button.setStyleSheet(self.style_mode_checked)
            self.on_user_input_setpoint(tag, value)
            self.pending_mode_change_deadline = time.monotonic() + 0.7
            self.commanded_mode_value = value
        else:
            button.setStyleSheet(self.style_mode_unchecked)

    def update_values(self, new_values: dict):
        """Sincroniza botones con el valor real recibido"""
        self.current_values = new_values
        current_mode = self.current_values.get("treatmentModeSelection", -1.0)
        now = time.monotonic()

        if self.pending_mode_change_deadline is not None:
            if current_mode == self.commanded_mode_value:
                self.pending_mode_change_deadline = None
                self.commanded_mode_value = None
                return
            elif now > self.pending_mode_change_deadline:
                self.pending_mode_change_deadline = None
                self.commanded_mode_value = None
            else:
                return

        mode_map = {
            0.0: self.btn_hemodialysis,
            1.0: self.btn_hemodiafiltration,
            2.0: self.btn_ultrafiltration,
            3.0: self.btn_cleaning,
        }

        for mode_value, btn in mode_map.items():
            should_be_checked = (current_mode == mode_value)
            if btn.isChecked() != should_be_checked:
                btn.blockSignals(True)
                btn.setChecked(should_be_checked)
                btn.setStyleSheet(self.style_mode_checked if should_be_checked else self.style_mode_unchecked)
                btn.blockSignals(False)

    def on_user_boolean_command(self, tag, state):
        self.request_boolean_change.emit(tag, state)

    def on_user_input_setpoint(self, tag, value):
        self.request_setpoint_change.emit(tag, value)
