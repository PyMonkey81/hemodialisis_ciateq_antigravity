# gui/service/options_screen.py
# Service / Settings screen (stacked index 4)
# Provides access to test panels, manual mode, calibration, network config, variable monitor, and themes
"""
Módulo para la pantalla de Opciones y Configuración de Servicio.

Este módulo define la clase `OptionsScreen`, que funciona como un menú principal
para acceder a diversas herramientas y configuraciones relacionadas con el
servicio, diagnóstico, calibración, monitorización y temas visuales del
dispositivo de hemodiálisis.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFrame, QLabel, QPushButton, QComboBox, QSizePolicy
)
from PySide6.QtCore import Qt
import logging
from gui.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class OptionsScreen(QWidget):
    """
    Options / Settings screen for service and configuration access.
    Acts as a hub to enter diagnostic, manual operation, calibration,
    network setup, real-time variable monitoring, and visual themes.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent  # Reference to main HemodialysisHMI window
        self.values = parent.current_values if parent else {}  # Shared values dict
        self.option_buttons: list[QPushButton] = []

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setup_ui()

        tm = ThemeManager.instance()
        tm.theme_changed.connect(self.apply_theme_styles)
        self.apply_theme_styles(tm.current_theme_name)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(36, 24, 36, 24)
        main_layout.setSpacing(18)

        # Encabezado con título y selector rápido de tema
        header_row = QHBoxLayout()
        self.title_label = QLabel("AJUSTES Y CONFIGURACIÓN DE SERVICIO")
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header_row.addWidget(self.title_label)
        header_row.addStretch()

        # Selector rápido de tema en la barra superior de Servicio
        self.quick_theme_frame = QFrame()
        qt_layout = QHBoxLayout(self.quick_theme_frame)
        qt_layout.setContentsMargins(14, 6, 14, 6)
        qt_layout.setSpacing(10)

        self.lbl_quick_theme = QLabel("Tema Visual:")
        qt_layout.addWidget(self.lbl_quick_theme)

        self.theme_combo = QComboBox()
        tm = ThemeManager.instance()
        self.theme_combo.addItems(tm.get_available_themes())
        self.theme_combo.setCurrentText(tm.current_theme_name)
        self.theme_combo.setFixedWidth(230)
        self.theme_combo.setFixedHeight(44)
        self.theme_combo.currentTextChanged.connect(self._on_quick_theme_changed)
        qt_layout.addWidget(self.theme_combo)

        header_row.addWidget(self.quick_theme_frame)
        main_layout.addLayout(header_row)

        # Contenedor de tarjetas de servicio
        self.buttons_frame = QFrame()
        self.buttons_frame.setObjectName("card")
        buttons_layout = QGridLayout(self.buttons_frame)
        buttons_layout.setSpacing(20)
        buttons_layout.setContentsMargins(28, 28, 28, 28)

        options = [
            ("Panel de Pruebas", getattr(self.parent_window, "show_test_panel_screen", lambda: None)),
            ("Modo Manual", getattr(self.parent_window, "show_manual_mode_screen", lambda: None)),
            ("Calibración", getattr(self.parent_window, "show_calibration_screen", lambda: None)),
            ("Configuración Red", getattr(self.parent_window, "show_network_config_screen", lambda: None)),
            ("Monitor de Variables", getattr(self.parent_window, "show_real_time_var_screen", lambda: None)),
            ("Configuración\nPuertos COM", getattr(self.parent_window, "show_config_comm_screen", lambda: None)),
            ("Mantenimiento\nPreventivo", getattr(self.parent_window, "show_maintenance_screen", lambda: None)),
            ("Alarmas\nServicio Técnico", getattr(self.parent_window, "show_alarm_service_screen_config", lambda: None)),
            ("Modos de\nDesinfección", getattr(self.parent_window, "show_cleanning_config_screen", lambda: None)),
            ("Temas y Apariencia\nVisual", getattr(self.parent_window, "show_theme_config_screen", lambda: None)),
        ]

        cols = 5
        for i, (text, callback) in enumerate(options):
            btn = QPushButton(text)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            btn.setMinimumHeight(140)
            btn.setProperty("is_theme_btn", i == 9)
            btn.clicked.connect(callback)
            row = i // cols
            col = i % cols
            buttons_layout.addWidget(btn, row, col)
            self.option_buttons.append(btn)

        for c in range(cols):
            buttons_layout.setColumnStretch(c, 1)
        for r in range(2):
            buttons_layout.setRowStretch(r, 1)

        main_layout.addWidget(self.buttons_frame, stretch=1)
        logger.info("OptionsScreen UI setup complete with service and theme options.")

    def _on_quick_theme_changed(self, theme_name: str):
        if not theme_name:
            return
        tm = ThemeManager.instance()
        if tm.current_theme_name != theme_name:
            tm.apply_theme(theme_name)
            if self.parent_window and hasattr(self.parent_window, "show_info_message"):
                self.parent_window.show_info_message(f"Tema cambiado a: {theme_name}", 2000)

    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        active_name = ThemeManager.instance().current_theme_name

        if self.theme_combo.currentText() != active_name:
            self.theme_combo.blockSignals(True)
            self.theme_combo.setCurrentText(active_name)
            self.theme_combo.blockSignals(False)

        self.setStyleSheet(f"background-color: {tokens['bg_main']};")
        self.title_label.setStyleSheet(
            f"color: {tokens['title_color']}; font-size: 34px; font-weight: bold; background: transparent;"
        )
        self.quick_theme_frame.setStyleSheet(
            f"QFrame {{ background-color: {tokens['bg_card']}; "
            f"border: 2px solid {tokens['border_card']}; border-radius: 12px; }}"
        )
        self.lbl_quick_theme.setStyleSheet(
            f"color: {tokens['text_secondary']}; font-size: 18px; font-weight: bold; border: none;"
        )
        self.buttons_frame.setStyleSheet(
            f"QFrame#card {{ background-color: {tokens['bg_card']}; "
            f"border: 2px solid {tokens['border_card']}; border-radius: 20px; }}"
        )

        for btn in self.option_buttons:
            is_theme_btn = bool(btn.property("is_theme_btn"))
            bg = tokens["primary"] if is_theme_btn else tokens["nav_btn_bg"]
            hover_bg = tokens["primary_hover"] if is_theme_btn else tokens["primary"]
            border_col = tokens["nav_btn_active_border"] if is_theme_btn else tokens["border_card"]
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: #FFFFFF;
                    font-weight: bold;
                    font-size: 22px;
                    border-radius: 14px;
                    border: 2px solid {border_col};
                    padding: 12px;
                }}
                QPushButton:hover {{
                    background-color: {hover_bg};
                }}
                QPushButton:pressed {{
                    background-color: {tokens['primary_pressed']};
                }}
            """)

    def update_values(self, new_values: dict):
        """Method to receive updated values, for consistency."""
        self.values = new_values
