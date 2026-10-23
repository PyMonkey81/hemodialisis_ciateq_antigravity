# gui/configuration/alarm_screen_config.py
# pantalla de configuracion de alarmas para usuario
from wsgiref import headers

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QGridLayout, 
    QPushButton, QHBoxLayout, QComboBox, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from gui.components.ui_components import ClickableLineEdit
from gui.components.numpad_modal import NumpadDialog
from gui.components.floating_message import FloatingMessage
from gui.components.floating_confirm import FloatingConfirmDialog
from core.alarm_config_manager import AlarmConfigManager
from gui.theme_manager import ThemeManager
from typing import Dict, List
import logging
logger = logging.getLogger(__name__)


try:
    from core.variables_map import VARIABLES
except ImportError:
    VARIABLES = {0x01: {}, 0x02: {}}


class AlarmScreenConfig(QWidget):
    """
    Pantalla de configuración de alarmas para el Operador.
    Muestra tanto variables numéricas (con límites) como booleanas (solo severidad).
    """

    def __init__(self, config_manager: AlarmConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.inputs: Dict[str, dict] = {}   # tag -> {'min': widget, 'max': widget, 'level': widget, 'type': str}
        self.header_labels: List[QLabel] = []
        self.row_labels: List[QLabel] = []
        self.dash_labels: List[QLabel] = []
        self.title_label: QLabel | None = None
        self.scroll_area: QScrollArea | None = None
        self.scroll: QScrollArea | None = None
        self.scroll_content: QWidget | None = None
        self.grid_widget: QWidget | None = None
        self.panel: QWidget | None = None
        self.btn_restore: QPushButton | None = None
        self.btn_save: QPushButton | None = None

        self.setObjectName("AlarmScreenConfig")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.setup_ui() 

        tm = ThemeManager.instance()
        tm.theme_changed.connect(self.apply_theme_styles)
        self.apply_theme_styles(tm.current_theme_name)

    def setup_ui(self):
        tokens = ThemeManager.get_tokens()

        self.setObjectName("AlarmScreenConfig")
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(tokens["bg_main"]))
        self.setPalette(palette)
        self.setStyleSheet(f"QWidget#AlarmScreenConfig {{ background-color: {tokens['bg_main']}; }}")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(20)

        self.title_label = QLabel("Configuración de Alarmas")
        self.title_label.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {tokens['title_color']}; background: transparent;")
        main_layout.addWidget(self.title_label)

        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll = self.scroll_area
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: {tokens['bg_card']};
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: {tokens['bg_card']};
            }}
            QScrollBar:vertical {{
                border: none;
                background: {tokens['bg_card_alt']};
                width: 34px;
                margin: 0px;
                border-radius: 14px;
            }}
            QScrollBar::handle:vertical {{
                background: {tokens['text_muted']};
                min-height: 60px;
                border-radius: 14px;
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

        self.scroll_content = QWidget()   
        self.scroll_content.setObjectName("AlarmScrollContent")
        self.scroll_content.setStyleSheet(f"background-color: {tokens['bg_card']}; border: none;")
        v_layout = QVBoxLayout(self.scroll_content)
        v_layout.setContentsMargins(0, 0, 0, 0)

        self.grid_widget = QWidget() 
        self.panel = self.grid_widget
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_widget.setObjectName("AlarmGridWidget")
        self.grid_widget.setStyleSheet(f"""
            QWidget#AlarmGridWidget {{
                background-color: {tokens['bg_card']};
                border-radius: 12px;
                border: 1px solid {tokens['border_card']};
            }}
        """)
        self.grid_layout.setSpacing(15)

        v_layout.addWidget(self.grid_widget)
        v_layout.addStretch() 

        # Encabezados dinámicos
        headers = ["Parámetro", "Límite Inferior", "Límite Superior", "Nivel de Alarma"]
        self.header_labels = []
        for col, text in enumerate(headers):
            lbl = QLabel(text)
            lbl.setStyleSheet(f"font-weight: bold; font-size: 24px; color: {tokens['text_secondary']}; background: transparent;")
            self.header_labels.append(lbl)
            self.grid_layout.addWidget(lbl, 0, col)

        self.populate_variables()
        
        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area)

        # Botones
        is_mono = bool(tokens.get("monochrome", False))
        btn_text_color = tokens["text_primary"] if is_mono else "#ffffff"
        btn_border = f"border: 1px solid {tokens['border_input']};" if is_mono else "border: none;"
        btn_style = f"""
            QPushButton {{
                background-color: {tokens['nav_btn_bg']};
                color: {btn_text_color};
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
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
        self.btn_restore = QPushButton("Restaurar Todo")
        self.btn_restore.setFixedSize(180, 55)
        self.btn_restore.setStyleSheet(btn_style)
        self.btn_restore.clicked.connect(self.restore_all_defaults)

        self.btn_save = QPushButton("Guardar Cambios")
        self.btn_save.setFixedSize(180, 55)
        self.btn_save.setStyleSheet(btn_style)
        self.btn_save.clicked.connect(self.save_configuration)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_restore)
        btn_layout.addWidget(self.btn_save)
        main_layout.addLayout(btn_layout)


    def populate_variables(self):
        tokens = ThemeManager.get_tokens()
        is_mono = bool(tokens.get("monochrome", False))
        sel_color = tokens.get("text_on_primary", "#374151") if is_mono else "#FFFFFF"

        combo_style = f"""
            QComboBox {{
                background-color: {tokens['bg_card_alt']};
                color: {tokens['text_primary']};
                font-size: 23px;
                border: 1px solid {tokens['border_input']};
                border-radius: 6px;
                padding: 2px 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {tokens['bg_card']};
                color: {tokens['text_primary']};
                selection-background-color: {tokens['primary']};
                selection-color: {sel_color};
            }}
        """
        lineedit_style = f"""
            ClickableLineEdit {{
                background-color: {tokens['bg_card_alt']};
                color: {tokens['text_primary']};
                font-size: 23px;
                border: 1px solid {tokens['border_input']};
                border-radius: 6px;
                padding: 2px 4px;
            }}
            ClickableLineEdit:focus {{
                border: 2px solid {tokens['primary']};
            }}
        """
        lbl_name_style = f"color: {tokens['text_primary']}; font-size: 23px; font-weight: bold; background: transparent;"
        dash_style = f"color: {tokens['text_muted']}; font-size: 23px; font-weight: bold; background: transparent;"

        row = 1
        self.row_labels.clear()
        self.dash_labels.clear()

        enabled_tags = set(self.config_manager.get_enabled_tags())
        label_short = ""
        for group in VARIABLES.values():
            for info in group.values():
                if "tag" not in info:
                    continue
                
                tag = info["tag"]                
                if tag not in enabled_tags:
                    continue

                name = info.get("name", info.get("label", tag))
                label_short = info.get("label", tag)
                unit = info.get("unit", "")
                var_type = info.get("type", "numeric")

                current_level = self.config_manager.get_severity(tag)

                lbl_name = QLabel(f"{name} {f'({unit})' if unit else ''}")
                lbl_name.setStyleSheet(lbl_name_style)
                self.row_labels.append(lbl_name)

                combo_level = QComboBox()
                combo_level.addItems(["cian", "naranja", "amarillo", "rojo"])
                combo_level.setStyleSheet(combo_style)
                combo_level.setCurrentText(current_level)
                combo_level.setFixedWidth(130)

                # Guardamos la información del tipo
                widget_dict = {'level': combo_level, 'type': var_type, 'lbl_name': lbl_name}

                if var_type == "double":
                    # Variables numéricas → mostrar límites
                    min_val, max_val = self.config_manager.get_limits(tag)

                    min_edit = ClickableLineEdit(f"{min_val:.1f}")
                    max_edit = ClickableLineEdit(f"{max_val:.1f}")
                    min_edit.setStyleSheet(lineedit_style)
                    max_edit.setStyleSheet(lineedit_style)
                    min_edit.setFixedWidth(100)
                    max_edit.setFixedWidth(100)

                    min_edit.clicked.connect(lambda c=False, e=min_edit, t=label_short, f="min": self.open_numpad(e, t, f))
                    max_edit.clicked.connect(lambda c=False, e=max_edit, t=label_short, f="max": self.open_numpad(e, t, f))

                    self.grid_layout.addWidget(lbl_name, row, 0)
                    self.grid_layout.addWidget(min_edit, row, 1)
                    self.grid_layout.addWidget(max_edit, row, 2)
                    self.grid_layout.addWidget(combo_level, row, 3)

                    widget_dict.update({'min': min_edit, 'max': max_edit})

                else:
                    # Variables booleanas → solo mostrar nombre y nivel de alarma
                    lbl_dash1 = QLabel("—")
                    lbl_dash2 = QLabel("—")
                    lbl_dash1.setStyleSheet(dash_style)
                    lbl_dash2.setStyleSheet(dash_style)
                    self.dash_labels.extend([lbl_dash1, lbl_dash2])

                    self.grid_layout.addWidget(lbl_name, row, 0)
                    self.grid_layout.addWidget(lbl_dash1, row, 1)   # placeholder
                    self.grid_layout.addWidget(lbl_dash2, row, 2)   # placeholder
                    self.grid_layout.addWidget(combo_level, row, 3)

                    widget_dict.update({'dash_min': lbl_dash1, 'dash_max': lbl_dash2})

                self.inputs[tag] = widget_dict
                row += 1

    def open_numpad(self, line_edit, tag, field):
        # dialog = NumpadDialog(self, initial_value=line_edit.text(), 
                            #  title=f"Límite {field.upper()} \n {tag}")
        dialog = NumpadDialog(self, initial_value="", 
                             title=f"Límite {field.upper()} \n {tag}")
        
        if dialog.exec():
            val = dialog.get_value()
            line_edit.setText(f"{val:.1f}")
            # line_edit.setText(" ")

    def show_floating_message(self, text: str, timeout_ms: int = 3800):
        """Método genérico (recomendado)"""
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        
        self._floating_msg.show_floating_message(text, timeout_ms)

    # Métodos específicos (más semánticos)
    def show_success_message(self, text: str, timeout_ms: int = 2000):
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        self._floating_msg.show_success_message(text, timeout_ms)

    def show_info_message(self, text: str, timeout_ms: int = 2000):
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        self._floating_msg.show_info_message(text, timeout_ms)

    def show_warning_message(self, text: str, timeout_ms: int = 2000):
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        self._floating_msg.show_warning_message(text, timeout_ms)

    def show_error_message(self, text: str, timeout_ms: int = 3000):
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        self._floating_msg.show_error_message(text, timeout_ms)
        
    def save_configuration(self):
        for tag, widgets in self.inputs.items():
            try:
                level = widgets['level'].currentText()
                self.config_manager.set_severity(tag, level)

                # Solo guardar límites si es variable numérica
                if widgets.get('type') == "double":
                    min_v = float(widgets['min'].text())
                    max_v = float(widgets['max'].text())

                    if min_v >= max_v:
                        
                        self.show_warning_message("Límite inferior debe ser menor que el superior.", timeout_ms=2000)
                        return

                    self.config_manager.set_limits(tag, min_v, max_v)

            except ValueError:
                self.show_error_message(f"Valor inválido en {tag}.", timeout_ms=3000)
                return
        self.config_manager.save_config()
        self.show_success_message("Configuración de alarmas guardada correctamente.", timeout_ms=2000)

    def restore_all_defaults(self):
        dialog = FloatingConfirmDialog(self)
      
        mensaje = "Confirmar Restauración\n\n¿Está seguro de que desea restaurar TODOS los límites y niveles de alarma a sus valores por defecto?\nEsta acción no se puede deshacer."
        
        reply = dialog.show_confirm(mensaje, accept_text="Sí, Restaurar", cancel_text="Cancelar")

        if reply == False:
            return

        for tag, widgets in self.inputs.items():
            # Restaurar severidad
            default_severity = self.config_manager.get_default_severity_from_variables_map(tag)
            widgets['level'].setCurrentText(default_severity)
            self.config_manager.set_severity(tag, default_severity)

            # Restaurar límites si es numérica
            if widgets.get('type') == "double":
                default_min, default_max = self.config_manager.get_default_limits_from_variables_map(tag)
                widgets['min'].setText(f"{default_min:.1f}")
                widgets['max'].setText(f"{default_max:.1f}")
                self.config_manager.set_limits(tag, default_min, default_max)
        
        # Guardar todos los cambios al archivo JSON
        self.config_manager.save_config()
        
        self.show_info_message("Todos los límites y niveles han sido restaurados a sus valores por defecto.", timeout_ms=2000)

    def clear_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self.clear_layout(item.layout())

    def refresh_ui(self):
        # 1. Limpiar el layout actual
        self.clear_layout(self.grid_layout)

        # 2. Re-crear los encabezados (ya que clear_layout borra todo)
        tokens = ThemeManager.get_tokens()
        headers = ["Parámetro", "Límite Inferior", "Límite Superior", "Nivel de Alarma"]
        self.header_labels = []
        for col, text in enumerate(headers):
            lbl = QLabel(text)
            lbl.setStyleSheet(f"font-weight: bold; font-size: 24px; color: {tokens['text_secondary']}; background: transparent;")
            self.header_labels.append(lbl)
            self.grid_layout.addWidget(lbl, 0, col) # row 0 para los encabezados

        # 3. Limpiar el diccionario de inputs y volver a poblar
        self.inputs.clear()
        self.populate_variables()

    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        is_mono = bool(tokens.get("monochrome", False))

        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(tokens["bg_main"]))
        self.setPalette(palette)
        self.setStyleSheet(f"QWidget#AlarmScreenConfig {{ background-color: {tokens['bg_main']}; }}")

        if hasattr(self, "title_label") and self.title_label is not None:
            self.title_label.setStyleSheet(
                f"font-size: 28px; font-weight: bold; color: {tokens['title_color']}; background: transparent;"
            )

        if hasattr(self, "scroll_area") and self.scroll_area is not None:
            self.scroll_area.setStyleSheet(f"""
                QScrollArea {{
                    border: none;
                    background-color: {tokens['bg_card']};
                }}
                QScrollArea > QWidget > QWidget {{
                    background-color: {tokens['bg_card']};
                }}
                QScrollBar:vertical {{
                    border: none;
                    background: {tokens['bg_card_alt']};
                    width: 34px;
                    margin: 0px;
                    border-radius: 14px;
                }}
                QScrollBar::handle:vertical {{
                    background: {tokens['text_muted']};
                    min-height: 60px;
                    border-radius: 14px;
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

        if hasattr(self, "panel") and self.panel is not None:
            self.panel.setStyleSheet(f"""
                QWidget#AlarmGridWidget {{
                    background-color: {tokens['bg_card']};
                    border-radius: 12px;
                    border: 1px solid {tokens['border_card']};
                }}
            """)

        if hasattr(self, "header_labels"):
            for lbl in self.header_labels:
                lbl.setStyleSheet(
                    f"font-weight: bold; font-size: 24px; color: {tokens['text_secondary']}; background: transparent;"
                )

        btn_text_color = tokens["text_primary"] if is_mono else "#ffffff"
        btn_border = f"border: 1px solid {tokens['border_input']};" if is_mono else "border: none;"
        btn_style = f"""
            QPushButton {{
                background-color: {tokens['nav_btn_bg']};
                color: {btn_text_color};
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
                {btn_border}
            }}
            QPushButton:hover {{
                background-color: {tokens.get('nav_btn_hover', tokens['primary_hover'])};
            }}
            QPushButton:pressed {{
                background-color: {tokens.get('primary_pressed', tokens['primary'])};
            }}
        """
        if hasattr(self, "btn_restore") and self.btn_restore is not None:
            self.btn_restore.setStyleSheet(btn_style)
        if hasattr(self, "btn_save") and self.btn_save is not None:
            self.btn_save.setStyleSheet(btn_style)

        sel_color = tokens.get("text_on_primary", "#374151") if is_mono else "#FFFFFF"
        combo_style = f"""
            QComboBox {{
                background-color: {tokens['bg_card_alt']};
                color: {tokens['text_primary']};
                font-size: 23px;
                border: 1px solid {tokens['border_input']};
                border-radius: 6px;
                padding: 2px 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {tokens['bg_card']};
                color: {tokens['text_primary']};
                selection-background-color: {tokens['primary']};
                selection-color: {sel_color};
            }}
        """
        lineedit_style = f"""
            ClickableLineEdit {{
                background-color: {tokens['bg_card_alt']};
                color: {tokens['text_primary']};
                font-size: 23px;
                border: 1px solid {tokens['border_input']};
                border-radius: 6px;
                padding: 2px 4px;
            }}
            ClickableLineEdit:focus {{
                border: 2px solid {tokens['primary']};
            }}
        """
        lbl_name_style = f"color: {tokens['text_primary']}; font-size: 23px; font-weight: bold; background: transparent;"
        dash_style = f"color: {tokens['text_muted']}; font-size: 23px; font-weight: bold; background: transparent;"

        if hasattr(self, "inputs"):
            for tag, widgets in self.inputs.items():
                if "lbl_name" in widgets:
                    widgets["lbl_name"].setStyleSheet(lbl_name_style)
                if "level" in widgets:
                    widgets["level"].setStyleSheet(combo_style)
                if widgets.get("type") == "double":
                    if "min" in widgets:
                        widgets["min"].setStyleSheet(lineedit_style)
                    if "max" in widgets:
                        widgets["max"].setStyleSheet(lineedit_style)
                else:
                    if "dash_min" in widgets:
                        widgets["dash_min"].setStyleSheet(dash_style)
                    if "dash_max" in widgets:
                        widgets["dash_max"].setStyleSheet(dash_style)

    def showEvent(self, event):
        super().showEvent(event)
        self.apply_theme_styles(ThemeManager.instance().current_theme_name)
        self.setFocus()

