from gui.theme_manager import ThemeManager
# gui/components/real_time_variables_monitor.py
"""
Módulo para el monitor de variables en tiempo real de la máquina de hemodiálisis.

Este módulo define la clase `RealTimeVariablesMonitor`, una herramienta de diagnóstico
avanzada que proporciona una visión tabular completa de todas las variables
internas de la máquina de hemodiálisis. Muestra el estado actual de sensores,
setpoints y actuadores, junto con sus propiedades de configuración y el estado
de las alarmas asociadas.

Características principales:
-----------------------------
- **Visualización Tabular Completa**: Presenta una `QTableWidget` que muestra
  de forma organizada la siguiente información para cada variable:
    - Índice y Grupo
    - Nombre legible y Tag (identificador único)
    - Tipo de variable (doble o booleana)
    - Valor actual en tiempo real
    - Límites de alarma configurados
    - Unidades de medida
    - Estado de alarma (NORMAL, ALARMA)
    - Acceso de lectura/escritura (R/W)
- **Actualizaciones en Tiempo Real**: Los valores de las variables y el estado
  de las alarmas se actualizan periódicamente (cada 500 ms) para reflejar
  el comportamiento dinámico del sistema.
- **Integración con Sistema de Alarmas**: Consulta el estado de las alarmas
  activas a través de una instancia de `AlarmSystem` para resaltar las variables
  que están fuera de rango o en condición de alarma.
- **Feedback Visual de Alarmas**: Las celdas de estado de alarma cambian de
  color (ej. verde para normal, diferentes tonos de rojo/amarillo/azul para alarmas
  según su severidad) para una identificación rápida.
- **Configuración Dinámica**: La tabla se construye dinámicamente a partir del
  mapa `VARIABLES` del sistema, asegurando que todas las variables definidas
  estén representadas.
- **Diseño Ergonómico**: Utiliza un estilo visual coherente con la HMI y
  permite el redimensionamiento de columnas para mejorar la legibilidad.

Clase principal:
----------------
- `RealTimeVariablesMonitor`: Widget que encapsula la lógica para construir,
  mostrar y actualizar la tabla de variables en tiempo real.

Dependencias:
-------------
- `PySide6.QtWidgets`: Componentes de UI como `QTableWidget`, `QLabel`, `QVBoxLayout`.
- `PySide6.QtCore`: `Qt`, `QTimer` para la actualización periódica.
- `PySide6.QtGui.QColor`: Para la coloración de las celdas de alarma.
- `core.variables_map.VARIABLES`, `core.variables_map.TVAR_TO_GROUP`:
  Mapeos que definen las variables del sistema y sus propiedades.

Uso:
----
La clase `RealTimeVariablesMonitor` se instancia en el `HemodialysisHMI`
principal y se añade a su `QStackedWidget` como una pantalla de servicio.
Requiere acceso al diccionario `current_values` (que contiene los últimos
valores recibidos del controlador) y a una instancia del `AlarmSystem`
para funcionar correctamente.
"""


from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from core.variables_map import VARIABLES, TVAR_TO_GROUP
import logging
logger = logging.getLogger(__name__)


class RealTimeVariablesMonitor(QWidget):
    """
    Widget para la monitorización en tiempo real de todas las variables
    de la máquina de hemodiálisis en una tabla.

    Muestra el valor actual, los límites de alarma, las unidades, el tipo
    de acceso (lectura/escritura) y el estado de alarma para cada variable
    definida en `VARIABLES`. La tabla se actualiza cada 500 ms.

    Args:
        parent (QWidget, optional): El widget padre.
        values_dict (dict, optional): Diccionario compartido con los valores
                                      actuales de todas las variables.
        alarm_system (AlarmSystem, optional): Instancia del sistema de alarmas
                                             para obtener el estado de las alarmas.
    """

    def __init__(self, parent=None, values_dict=None, alarm_system=None):
        super().__init__(parent)
        self.setStyleSheet("background: #f8fafc; font-family: 'Segoe UI';")

        # References
        self.current_values = values_dict if values_dict is not None else {}
        self.alarm_system = alarm_system

        layout = QVBoxLayout(self)

        # Title
                # Title
        self.title_label = QLabel("MONITOR DE VARIABLES - MÁQUINA HEMODIÁLISIS")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        
        columns = ["#", "Grupo", "Nombre", "Tag", "Tipo", "Valor", "Límites", "Unidad", "Estado", "R/W"]
        self.table = QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)

        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #cbd5e1;
                font-size: 13px;
                background-color: #ffffff;
                alternate-background-color: #f1f5f9;
            }
            QTableWidget::item {
                background-color: #ffffff;
                color: #000000;
                padding: 6px;
            }
            QTableWidget::item:selected {
                background-color: #3b82f6;
                color: white;
            }
            QHeaderView::section {
                background: #1e40af;
                color: white;
                padding: 10px;
                font-weight: bold;
            }
        """)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # #
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Tag

        layout.addWidget(self.table)

        
        self.cell_references = {}

        self._build_table()

        # Update timer
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_data)
        self.update_timer.start(500)
        self.apply_theme_styles()
        try:
            ThemeManager.instance().theme_changed.connect(lambda _t: self.apply_theme_styles())
        except Exception:
            pass

    def _build_table(self):
        """Populate the table with all variables from VARIABLES map."""
        self.table.setRowCount(0)
        row_index = 0

        for group_key, vars_in_group in VARIABLES.items():
            group_name = TVAR_TO_GROUP.get(group_key, f"0x{group_key:02X}")

            for address, info in sorted(vars_in_group.items(), key=lambda x: x[0]):
                display_name = info["name"]
                tag = info.get("tag", "N/A")
                var_type = info["type"]
                read_write = "R/W" if info.get("rw", False) else "R"
                unit = info.get("unit", "")
                limits = info.get("limites")
                limits_str = f"{limits[0]}-{limits[1]}" if limits else "-"

                row = self.table.rowCount()
                self.table.insertRow(row)

                # Static columns
                self.table.setItem(row, 0, QTableWidgetItem(str(row_index + 1)))
                self.table.setItem(row, 1, QTableWidgetItem(group_name))
                self.table.setItem(row, 2, QTableWidgetItem(display_name))
                self.table.setItem(row, 3, QTableWidgetItem(tag))
                self.table.setItem(row, 4, QTableWidgetItem("DOUBLE" if var_type == "double" else "BOOL"))

                # Dynamic: Value
                value_item = QTableWidgetItem("---")
                value_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 5, value_item)

                self.table.setItem(row, 6, QTableWidgetItem(limits_str))
                self.table.setItem(row, 7, QTableWidgetItem(unit))

                # Dynamic: Status
                status_item = QTableWidgetItem("NORMAL")
                status_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 8, status_item)

                self.table.setItem(row, 9, QTableWidgetItem(read_write))

                # Store references using TAG as key
                self.cell_references[tag] = (value_item, var_type, status_item, display_name)

                row_index += 1

    def update_data(self):
        """Refresh value and alarm status columns."""
        if not self.isVisible():
            return

        
        alarm_system = self.alarm_system or (
            self.parent().alarm_system
            if hasattr(self.parent(), 'alarm_system') else None
        )

        for tag, (value_item, var_type, status_item, display_name) in self.cell_references.items():
            # 1. Update Value
            raw_value = self.current_values.get(tag, 0.0)

            if var_type == "double":
                display_text = f"{raw_value:.3f}"
            else:
                display_text = "ON" if raw_value > 0 else "OFF"

            if value_item.text() != display_text:
                value_item.setText(display_text)

            # 2. Update Status (based on alarm system using display_name)
            status_text = "NORMAL"
            bg_color = QColor(255, 255, 255)
            text_color = QColor(0, 0, 0)

            if alarm_system:
                try:
                    if display_name in alarm_system.display_names:
                        idx = alarm_system.display_names.index(display_name)
                        if idx < len(alarm_system.previous_states) and alarm_system.previous_states[idx]:
                            status_text = "ALARM"
                            level = alarm_system.severity_levels[idx]

                            if level == "rojo":
                                bg_color = QColor(254, 205, 211)
                                text_color = QColor(127, 29, 29)
                            elif level == "amarillo":
                                bg_color = QColor(255, 255, 191)
                                text_color = QColor(120, 53, 15)
                            else:
                                bg_color = QColor(220, 252, 255)
                                text_color = QColor(15, 66, 93)
                except Exception:
                    pass  

            if status_item.text() != status_text:
                status_item.setText(status_text)
                status_item.setBackground(bg_color)
                status_item.setForeground(text_color)

    def showEvent(self, event):
        super().showEvent(event)
        self.apply_theme_styles()

    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        is_mono = bool(tokens.get("monochrome", False))
        is_dark = bool(tokens.get("is_dark", False))

        if is_mono:
            self.setStyleSheet("background: #F3F4F6; font-family: 'Segoe UI';")
            if hasattr(self, "title_label"):
                self.title_label.setStyleSheet(
                    "font-size: 22px; font-weight: bold; color: #374151; "
                    "padding: 14px; background: #D9E0E8; border: 1px solid #C5CDD6; border-radius: 10px;"
                )
            self.table.setStyleSheet("""
                QTableWidget {
                    gridline-color: #D1D5DB;
                    font-size: 14px;
                    background-color: #FFFFFF;
                    color: #374151;
                    border: 1px solid #D1D5DB;
                    border-radius: 8px;
                }
                QTableWidget::item {
                    background-color: #FFFFFF;
                    color: #374151;
                    padding: 6px;
                }
                QTableWidget::item:selected {
                    background-color: #9CA3AF;
                    color: #111827;
                }
                QHeaderView::section {
                    background: #E5E7EB;
                    color: #374151;
                    padding: 8px;
                    font-weight: bold;
                    border: 1px solid #D1D5DB;
                }
            """)
        elif is_dark:
            self.setStyleSheet(f"background: {tokens.get('bg_main', '#0F172A')}; font-family: 'Segoe UI';")
            if hasattr(self, "title_label"):
                self.title_label.setStyleSheet(
                    f"font-size: 22px; font-weight: bold; color: {tokens.get('text_primary', '#F8FAFC')}; "
                    f"padding: 14px; background: {tokens.get('bg_card_alt', '#1E293B')}; border: 1px solid {tokens.get('border_card', '#334155')}; border-radius: 10px;"
                )
            self.table.setStyleSheet(f"""
                QTableWidget {{
                    gridline-color: {tokens.get('border_card', '#334155')};
                    font-size: 14px;
                    background-color: {tokens.get('bg_card', '#1E293B')};
                    color: {tokens.get('text_primary', '#F8FAFC')};
                    border: 1px solid {tokens.get('border_card', '#334155')};
                    border-radius: 8px;
                }}
                QTableWidget::item {{
                    background-color: {tokens.get('bg_card', '#1E293B')};
                    color: {tokens.get('text_primary', '#F8FAFC')};
                    padding: 6px;
                }}
                QTableWidget::item:selected {{
                    background-color: {tokens.get('table_sel_bg', '#334155')};
                    color: {tokens.get('table_sel_text', '#FFFFFF')};
                }}
                QHeaderView::section {{
                    background: {tokens.get('table_header_bg', '#1E293B')};
                    color: {tokens.get('text_secondary', '#94A3B8')};
                    padding: 8px;
                    font-weight: bold;
                    border: 1px solid {tokens.get('border_card', '#334155')};
                }}
            """)
        else:
            self.setStyleSheet("background: #f8fafc; font-family: 'Segoe UI';")
            if hasattr(self, "title_label"):
                self.title_label.setStyleSheet(
                    "font-size: 20px; font-weight: bold; color: #1e40af; "
                    "padding: 15px; background: #e0e7ff; border-radius: 10px;"
                )
            self.table.setStyleSheet("""
                QTableWidget {
                    gridline-color: #cbd5e1;
                    font-size: 13px;
                    background-color: #ffffff;
                    alternate-background-color: #f1f5f9;
                }
                QTableWidget::item {
                    background-color: #ffffff;
                    color: #000000;
                    padding: 6px;
                }
                QTableWidget::item:selected {
                    background-color: #3b82f6;
                    color: white;
                }
                QHeaderView::section {
                    background: #1e40af;
                    color: white;
                    padding: 10px;
                    font-weight: bold;
                }
            """)
