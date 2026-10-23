# gui/configuration/alarm_screen_service_config.py
# pantalla de para configuracion de alarmas para servicio tecnico 
# gui/configuration/alarm_screen_service_config.py
from PySide6.QtWidgets import (
    QSizePolicy, QWidget, QVBoxLayout, QLabel, QScrollArea, QGridLayout, 
    QPushButton, QHBoxLayout, QCheckBox, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from gui.components.floating_message import FloatingMessage
from gui.theme_manager import ThemeManager

from core.alarm_config_manager import AlarmConfigManager
from typing import Dict, List
import logging
logger = logging.getLogger(__name__)

try:
    from core.variables_map import VARIABLES
except ImportError:
    VARIABLES = {0x01: {}, 0x02: {}}


class AlarmScreenServiceConfig(QWidget):
    """Pantalla para Servicio Técnico: Habilitar/Deshabilitar variables como alarmas"""

    def __init__(self, config_manager: AlarmConfigManager, parent=None):
        super().__init__(parent)
        self.parent_window = parent # parent_window es HemodialysisHMI
        self.config_manager = config_manager
        self.checkboxes: Dict[str, QCheckBox] = {}
        self.row_labels: Dict[str, QLabel] = {}
        self.header_labels: List[QLabel] = []
        self.title_label: QLabel | None = None
        self.scroll_area: QScrollArea | None = None
        self.scroll: QScrollArea | None = None
        self.scroll_content: QWidget | None = None
        self.panel: QScrollArea | None = None
        self.btn_save: QPushButton | None = None

        self.setObjectName("AlarmScreenServiceConfig")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.setup_ui()

        tm = ThemeManager.instance()
        tm.theme_changed.connect(self.apply_theme_styles)
        self.apply_theme_styles(tm.current_theme_name)

    def setup_ui(self):
        tokens = ThemeManager.get_tokens()
        is_mono = bool(tokens.get("monochrome", False))

        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(tokens["bg_main"]))
        self.setPalette(palette)
        self.setStyleSheet(f"QWidget#AlarmScreenServiceConfig {{ background-color: {tokens['bg_main']}; }}")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(20)

        # Título
        self.title_label = QLabel("Configuración de Alarmas - Servicio Técnico")
        self.title_label.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {tokens['title_color']}; background: transparent;")
        main_layout.addWidget(self.title_label)

        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll = self.scroll_area
        self.panel = self.scroll_area
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {tokens['border_card']};
                background-color: {tokens['bg_card']};
                border-radius: 12px;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: {tokens['bg_card']};
            }}
            QScrollBar:vertical {{
                border: none;
                background: {tokens['bg_card_alt']};
                width: 34px;
                margin: 0px;
                border-radius: 10px;
            }}
            QScrollBar::handle:vertical {{
                background: {tokens['text_muted']};
                min-height: 50px;
                border-radius: 8px;
                margin: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {tokens['primary']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """)

        # Contenedor interno del scroll
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet(f"background-color: {tokens['bg_card']}; border: none;")
        grid = QGridLayout(self.scroll_content)
        grid.setSpacing(18)
        grid.setContentsMargins(20, 20, 20, 20)
        grid.setColumnStretch(1, 1)

        # Encabezados
        headers = ["Habilitar", "Señal de control (Variable)"]
        self.header_labels = []
        for col, text in enumerate(headers):
            lbl = QLabel(text)
            lbl.setStyleSheet(f"font-weight: bold; font-size: 24px; color: {tokens['text_secondary']}; padding-bottom: 8px; background: transparent;")
            self.header_labels.append(lbl)
            grid.addWidget(lbl, 0, col)

        # Estilo para los Checkboxes
        chk_style = f"""
            QCheckBox {{
                color: {tokens['text_primary']};
                font-size: 22px;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 30px;
                height: 32px;
                border: 2px solid {tokens['border_strong']};
                border-radius: 4px;
                background: transparent;
            }}
            QCheckBox::indicator:checked {{
                background-color: {tokens['primary']};
            }}
        """

        row = 1
        self.checkboxes.clear()
        self.row_labels.clear()
        for group in VARIABLES.values():
            for info in group.values():
                if info.get("tag") and info.get("type") in ("double", "bool"):
                    tag = info["tag"]
                    name = info.get("name", tag)
                    unit = info.get("unit", "")

                    # Checkbox
                    chk = QCheckBox()
                    chk.setChecked(self.config_manager.is_enabled(tag))
                    chk.setStyleSheet(chk_style)
                    self.checkboxes[tag] = chk

                    # Nombre de la variable
                    display_text = f"{name}"
                    if unit:
                        display_text += f" ({unit})"
                    if info.get("type") == "bool":
                        display_text += "  [DIGITAL]"

                    lbl_name = QLabel(display_text)
                    lbl_name.setStyleSheet(f"color: {tokens['text_primary']}; font-size: 22px; background: transparent;")
                    self.row_labels[tag] = lbl_name

                    grid.addWidget(chk, row, 0, alignment=Qt.AlignCenter)
                    grid.addWidget(lbl_name, row, 1, alignment=Qt.AlignLeft)
                    row += 1

        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area)

        # Botón Guardar
        btn_text_color = tokens["text_primary"] if is_mono else "#ffffff"
        btn_border = f"border: 1px solid {tokens['border_input']};" if is_mono else "border: none;"
        btn_style = f"""
            QPushButton {{
                background-color: {tokens['nav_btn_bg']};
                color: {btn_text_color};
                font-size: 24px;
                font-weight: bold;
                border-radius: 12px;
                {btn_border}
            }}
            QPushButton:hover {{
                background-color: {tokens.get('nav_btn_hover', tokens['primary_hover'])};
            }}
            QPushButton:pressed {{
                background-color: {tokens.get('primary_pressed', tokens['primary'])};
            }}
        """

        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Guardar Configuración")
        self.btn_save.setFixedSize(400, 80)
        self.btn_save.setStyleSheet(btn_style)
        self.btn_save.clicked.connect(self.save_enabled)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        main_layout.addLayout(btn_layout)

    # def setup_ui(self):
    #     main_layout = QVBoxLayout(self)
    #     main_layout.setContentsMargins(25, 25, 25, 25)
    #     main_layout.setSpacing(20)

    #     # Título
    #     title = QLabel("Configuración de Alarmas - Servicio Técnico")
    #     title.setStyleSheet("font-size: 28px; font-weight: bold; color: #34495e;")
    #     main_layout.addWidget(title)

    #     # Scroll Area
    #     scroll_area = QScrollArea()
    #     scroll_area.setWidgetResizable(True)
    #     scroll_area.setStyleSheet("""
    #         QScrollArea { 
    #             border: none; 
    #             background: transparent; 
    #         }
    #         QScrollBar:vertical {
    #             border: none;
    #             background: #e0e0e5;
    #             width: 34px;
    #             margin: 0px 0px 0px 0px;
    #             border-radius: 14px;
    #         }
    #         QScrollBar::handle:vertical {
    #             background: #8a8a9c;
    #             min-height: 60px;
    #             border-radius: 14px;
    #         }
    #         QScrollBar::handle:vertical:hover {
    #             background: #6b6b7a;
    #         }
    #         QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    #             height: 0px;
    #         }
    #         QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    #             background: none;
    #         }
    #     """)

    #     scroll_content = QWidget()
    #     grid = QGridLayout(scroll_content)
    #     grid.setSpacing(18)
    #     grid.setColumnStretch(1, 1)   # Hace que la columna de nombre ocupe el espacio restante

    #     # Encabezados
    #     headers = ["Habilitar", "Señal de control (Variable)"]
    #     for col, text in enumerate(headers):
    #         lbl = QLabel(text)
    #         lbl.setStyleSheet("font-weight: bold; font-size: 24px; color: #7f8c8d; padding-bottom: 8px;")
    #         grid.addWidget(lbl, 0, col)

    #     row = 1
    #     for group in VARIABLES.values():
    #         for info in group.values():
    #             if info.get("tag") and info.get("type") in ("double", "bool"):
    #                 tag = info["tag"]
    #                 name = info.get("name", info.get("name", tag))
    #                 unit = info.get("unit", "")

    #                 # Checkbox más grande y visible
    #                 chk = QCheckBox()
    #                 chk.setChecked(self.config_manager.is_enabled(tag))
    #                 chk.setMinimumHeight(32)
    #                 chk.setStyleSheet("""
    #                     QCheckBox { color: #000000; font-size: 26px;  border: 2px solid #000000; border-radius: 6px; padding: 4px; }
    #                     QCheckBox::indicator { width: 25px; height: 25px; }
    #                 """)
    #                 self.checkboxes[tag] = chk

    #                 # Nombre de la variable
    #                 display_text = f"{name}"
    #                 if unit:
    #                     display_text += f" ({unit})"
    #                 # Indicador visual si es booleana
    #                 if info.get("type") == "boolean":
    #                     display_text += "  [Booleana]"

    #                 lbl_name = QLabel(display_text)
    #                 lbl_name.setStyleSheet("color: #0f172a; font-size: 22px; padding: 4px 0;")

    #                 # Agregar al grid
    #                 grid.addWidget(chk, row, 0, alignment=Qt.AlignCenter)
    #                 grid.addWidget(lbl_name, row, 1, alignment=Qt.AlignLeft)
    #                 row += 1

    #     scroll_area.setWidget(scroll_content)
    #     main_layout.addWidget(scroll_area)

    #     # Botones
    #     btn_layout = QHBoxLayout()
    #     btn_save = QPushButton("Guardar Configuración de Alarmas")
    #     btn_save.setFixedSize(380, 60)
    #     btn_save.setStyleSheet("""
    #         QPushButton {
    #             background: #0f172a; 
    #             color: #ffffff; 
    #             font-size: 18px; 
    #             font-weight: bold; 
    #             border-radius: 10px;
    #         }
    #         QPushButton:hover {
    #             background: #1e2937;
    #         }
    #     """)
    #     btn_save.clicked.connect(self.save_enabled)

    #     btn_layout.addStretch()
    #     btn_layout.addWidget(btn_save)
    #     main_layout.addLayout(btn_layout)


    def save_enabled(self):
        enabled_count = 0
        for tag, chk in self.checkboxes.items():
            self.config_manager.set_enabled(tag, chk.isChecked())
            if chk.isChecked():
                enabled_count += 1
    
        self.config_manager.save_config()
        logger.info(f"Configuración de alarmas guardada. {enabled_count} variables habilitadas como alarmas.")


        self.show_success_message(f"Configuración guardada. {enabled_count} alarmas habilitadas.", 3500)
        # 1. Recargar automáticamente la pantalla del Operador
        if self.parent_window is not None and hasattr(self.parent_window, 'alarm_config_limits_screen'):
            # Llamar al método refresh_ui en la instancia de la pantalla del operador
            self.parent_window.alarm_config_limits_screen.refresh_ui()

        # 2. Informar al AlarmSystem en HemodialysisHMI para que recargue su configuración de monitoreo
        if self.parent_window is not None and hasattr(self.parent_window, 'update_alarm_system_monitor_config'):
            self.parent_window.update_alarm_system_monitor_config()

    def show_floating_message(self, text: str, timeout_ms: int = 3800):
        """Método genérico (recomendado)"""
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        
        self._floating_msg.show_floating_message(text, timeout_ms)

    # Métodos específicos (más semánticos)
    def show_success_message(self, text: str, timeout_ms: int = 4000):
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        self._floating_msg.show_success_message(text, timeout_ms)

    def show_info_message(self, text: str, timeout_ms: int = 3800):
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        self._floating_msg.show_info_message(text, timeout_ms)

    def show_warning_message(self, text: str, timeout_ms: int = 4500):
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        self._floating_msg.show_warning_message(text, timeout_ms)
    
    def show_error_message(self, text: str, timeout_ms: int = 5000):
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        self._floating_msg.show_error_message(text, timeout_ms)

    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        is_mono = bool(tokens.get("monochrome", False))

        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(tokens["bg_main"]))
        self.setPalette(palette)
        self.setStyleSheet(f"QWidget#AlarmScreenServiceConfig {{ background-color: {tokens['bg_main']}; }}")

        if hasattr(self, "title_label") and self.title_label is not None:
            self.title_label.setStyleSheet(
                f"font-size: 32px; font-weight: bold; color: {tokens['title_color']}; background: transparent;"
            )

        if hasattr(self, "scroll_area") and self.scroll_area is not None:
            self.scroll_area.setStyleSheet(f"""
                QScrollArea {{
                    border: 1px solid {tokens['border_card']};
                    background-color: {tokens['bg_card']};
                    border-radius: 12px;
                }}
                QScrollArea > QWidget > QWidget {{
                    background-color: {tokens['bg_card']};
                }}
                QScrollBar:vertical {{
                    border: none;
                    background: {tokens['bg_card_alt']};
                    width: 34px;
                    margin: 0px;
                    border-radius: 10px;
                }}
                QScrollBar::handle:vertical {{
                    background: {tokens['text_muted']};
                    min-height: 50px;
                    border-radius: 8px;
                    margin: 4px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background: {tokens['primary']};
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                    background: transparent;
                }}
            """)

        if hasattr(self, "scroll_content") and self.scroll_content is not None:
            self.scroll_content.setStyleSheet(f"background-color: {tokens['bg_card']}; border: none;")

        if hasattr(self, "header_labels"):
            for lbl in self.header_labels:
                lbl.setStyleSheet(
                    f"font-weight: bold; font-size: 24px; color: {tokens['text_secondary']}; padding-bottom: 8px; background: transparent;"
                )

        btn_text_color = tokens["text_primary"] if is_mono else "#ffffff"
        btn_border = f"border: 1px solid {tokens['border_input']};" if is_mono else "border: none;"
        btn_style = f"""
            QPushButton {{
                background-color: {tokens['nav_btn_bg']};
                color: {btn_text_color};
                font-size: 24px;
                font-weight: bold;
                border-radius: 12px;
                {btn_border}
            }}
            QPushButton:hover {{
                background-color: {tokens.get('nav_btn_hover', tokens['primary_hover'])};
            }}
            QPushButton:pressed {{
                background-color: {tokens.get('primary_pressed', tokens['primary'])};
            }}
        """
        if hasattr(self, "btn_save") and self.btn_save is not None:
            self.btn_save.setStyleSheet(btn_style)

        chk_style = f"""
            QCheckBox {{
                color: {tokens['text_primary']};
                font-size: 22px;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 30px;
                height: 32px;
                border: 2px solid {tokens['border_strong']};
                border-radius: 4px;
                background: transparent;
            }}
            QCheckBox::indicator:checked {{
                background-color: {tokens['primary']};
            }}
        """
        if hasattr(self, "checkboxes"):
            for chk in self.checkboxes.values():
                chk.setStyleSheet(chk_style)

        lbl_style = f"color: {tokens['text_primary']}; font-size: 22px; background: transparent;"
        if hasattr(self, "row_labels"):
            for lbl in self.row_labels.values():
                lbl.setStyleSheet(lbl_style)

    def showEvent(self, event):
        super().showEvent(event)
        self.apply_theme_styles(ThemeManager.instance().current_theme_name)
        self.setFocus()