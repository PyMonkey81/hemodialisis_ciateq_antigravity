from gui.theme_manager import ThemeManager
# gui/service/calibration_screen.py
# Low-level calibration and controller tuning screen
# Allows enabling control loops, adjusting PID gains, feedforward, and monitoring setpoints/variables/outputs

"""
Módulo para la pantalla de calibración y ajuste de controladores de bajo nivel.

Este módulo define la clase `CalibrationScreen`, una interfaz de usuario crítica
diseñada para el personal técnico e ingenieros, que permite la inspección detallada,
el ajuste fino y la calibración de los algoritmos de control de la máquina de
hemodiálisis. Ofrece herramientas esenciales para optimizar el rendimiento de
los bucles de control y asegurar la precisión de los parámetros operativos.

Características principales:
-----------------------------
- **Visualización Gráfica de Tendencias (PyQtGraph):**
    - Muestra gráficas en tiempo real de setpoints, variables medidas y salidas
      de control para los bucles de flujo de sangre (CFS), conductividad (CC)
      y temperatura (CTD). Esto permite observar el comportamiento dinámico de
      los controladores y su respuesta a los cambios.
- **Control de Bucles y Modos:**
    - `DoubleToggleBox`s para habilitar/deshabilitar los bucles de control
      (CFS, CC, CTD) y para alternar sus modos de operación (ej. manual/automático).
- **Ajuste de Parámetros de Control:**
    - **Setpoints y Salidas:** Permite al usuario configurar los setpoints deseados
      y ajustar directamente las salidas de control (en modo manual) para CFS, CC y CTD.
    - **Ganancias PID:** Proporciona campos de entrada para ajustar las ganancias
      proporcionales (Kp), integrales (Ki) y derivativas (Kd) de los controladores
      PID para cada bucle (CFS, CC, CTD).
    - **Ganancias Feedforward:** Permite ajustar los parámetros de ganancia
      (`bloodFlowFeedForwardGain`) y el avance (`bloodFlowFeedForwardLead`)
      del control feedforward para el flujo de sangre.
- **Monitorización de Variables Clave:**
    - Muestra la velocidad de la bomba de sangre en RPM y otras variables
      relevantes para el ajuste de los controladores.
- **Interacción Táctil:** Utiliza `NumpadDialog`s para una entrada numérica
  precisa y optimizada para pantallas táctiles.
- **Comunicación con el Controlador:** Emite señales (`request_setpoint_change`
  y `request_boolean_change`) al controlador principal de la HMI para aplicar
  los cambios de configuración en el hardware.

Clase principal:
----------------
- `CalibrationScreen`: Widget principal que orquesta la interfaz, la lógica
  y la comunicación para la calibración y ajuste de los controladores.

Dependencias:
-------------
- `PySide6`: Para la construcción de la interfaz gráfica y la gestión de eventos/señales.
- `pyqtgraph`: Para la creación de gráficas interactivas y eficientes en tiempo real.
- `numpy`: Para la gestión de datos numéricos y el historial de las gráficas.
- `collections.deque`: Para mantener eficientemente el historial de datos para las gráficas.
- `gui.components.numpad_modal.NumpadDialog`: Diálogo para la entrada numérica táctil.
- `gui.components.ui_components.ClickableLineEdit`, `DoubleToggleBox`: Widgets UI personalizados.
- `core.variables_map.VARIABLES`: Para el mapeo de tags de variables y la configuración
  de los controladores en el sistema.

Uso:
----
La clase `CalibrationScreen` se instancia en el `HemodialysisHMI` principal
y se añade a su `QStackedWidget` como una pantalla de servicio. Es fundamental
que el `HemodialysisHMI` conecte sus señales de solicitud de cambio a métodos
que envíen los setpoints y comandos booleanos al controlador serial, y que
proporcione actualizaciones constantes de `current_values` para que la
pantalla pueda refrescar sus displays y gráficas.
"""


from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QSizePolicy, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
import pyqtgraph as pg
import numpy as np
from collections import deque

from gui.components.numpad_modal import NumpadDialog
from gui.components.ui_components import ClickableLineEdit, DoubleToggleBox
import logging
logger = logging.getLogger(__name__)

try:
    from core.variables_map import VARIABLES
except ImportError:
    VARIABLES = {0x01: {}, 0x02: {}}


class CalibrationScreen(QWidget):
    """
    Calibration and low-level controller tuning screen.
    Enables/disables control loops, adjusts PID gains/feedforward,
    and displays real-time setpoint/variable/output trends for blood flow,
    conductivity, and temperature controllers.
    """
    valueChanged = Signal(str, float)
    request_setpoint_change = Signal(str, float)
    request_boolean_change = Signal(str, bool)

    def __init__(self, parent=None, values_dict=None):        
        super().__init__(parent)
        self.parent_window = parent
        self.current_values = values_dict if values_dict is not None else {}

        # 1. FORZAR FONDO CLARO AL WIDGET PRINCIPAL
        self.setObjectName("CalibrationScreen")
        self.setStyleSheet("QWidget#CalibrationScreen { background-color: #FCFCFC; }")

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Toggle switches mapping (tag → ToggleSwitch widget)
        self.control_loop_toggles = {}

        # Plot history buffers (600 points ~5 min at 500 ms update)
        self.history_length = 600
        nan_array = [np.nan] * self.history_length

        # Blood flow control
        self.blood_flow_setpoint_history = deque(nan_array, maxlen=self.history_length)
        self.blood_flow_variable_history = deque(nan_array, maxlen=self.history_length)
        self.blood_flow_output_history   = deque(nan_array, maxlen=self.history_length)

        # Conductivity control
        self.cond_setpoint_history = deque(nan_array, maxlen=self.history_length)
        self.cond_variable_history = deque(nan_array, maxlen=self.history_length)
        self.cond_output_history   = deque(nan_array, maxlen=self.history_length)

        # Temperature control
        self.temp_setpoint_history = deque(nan_array, maxlen=self.history_length)
        self.temp_variable_history = deque(nan_array, maxlen=self.history_length)
        self.temp_output_history   = deque(nan_array, maxlen=self.history_length)

        self.time_axis = np.arange(-self.history_length + 1, 1, dtype=np.float32)
        
        self.setup_ui()
        self.apply_theme_styles()
        try:
            ThemeManager.instance().theme_changed.connect(lambda _t: self.apply_theme_styles())
        except Exception:
            pass

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        tick_font = QFont()
        tick_font.setPixelSize(12)

        # Backwards compatibility attributes
        self.control_area = self
        self.graphics_area = self
        self._calib_rows = []

        # Configuración de columnas idéntica en las 3 cards para alineación horizontal perfecta:
        # Col 0: Toggles (DoubleToggleBox)
        # Col 1: Label Setpoint / Salida / Variable
        # Col 2: Input o Display Setpoint / Salida / Variable
        # Col 3: Unidad Setpoint / Salida / Variable
        # Col 4: Label columna media (Velocidad BS / FFWD / Lead FFWD en Card 1; dummy en Cards 2 y 3)
        # Col 5: Input o Display columna media
        # Col 6: Unidad columna media
        # Col 7: Label PID (CFS / Cond. / Temp.)
        # Col 8: Input PID
        # Col 9: Unidad PID (kp / ki / kd)
        # Col 10: PlotWidget (Expanding)
        col_widths = [230, 145, 95, 60, 125, 95, 45, 70, 95, 35]

        # ═════════════════════════════════════════════════════════════════════
        # CARD 1: Control de Flujo de Sangre
        # ═════════════════════════════════════════════════════════════════════
        self.blood_card = QFrame()
        self.blood_card.setObjectName("card")
        main_layout.addWidget(self.blood_card, 1)

        blood_layout = QVBoxLayout(self.blood_card)
        blood_layout.setContentsMargins(14, 8, 14, 8)
        blood_layout.setSpacing(4)

        self.blood_card_title = QLabel("Control de Flujo de Sangre")
        self.blood_card_title.setObjectName("card_title")
        blood_layout.addWidget(self.blood_card_title)

        grid_blood = QGridLayout()
        grid_blood.setContentsMargins(0, 0, 0, 0)
        grid_blood.setSpacing(10)
        for c, w in enumerate(col_widths):
            grid_blood.setColumnMinimumWidth(c, w)
        grid_blood.setColumnStretch(10, 1)
        for r in range(3):
            grid_blood.setRowMinimumHeight(r, 38)
        blood_layout.addLayout(grid_blood)

        # 1. Toggles (ocupan las 2 primeras filas)
        double_box_blood = DoubleToggleBox("Hab. CFS", "Hab. Modo CFS")
        double_box_blood.setFixedWidth(230)
        double_box_blood.toggle1.toggled.connect(lambda checked, t="bloodControlLoopEnable": self._toggle_control_loop(t, checked))
        double_box_blood.toggle2.toggled.connect(lambda checked, t="bloodControlLoopMode": self._toggle_control_loop(t, checked))
        self.control_loop_toggles["bloodControlLoopEnable"] = double_box_blood.toggle1
        self.control_loop_toggles["bloodControlLoopMode"]   = double_box_blood.toggle2
        grid_blood.addWidget(double_box_blood, 0, 0, 2, 1, Qt.AlignVCenter)

        # 2. Setpoint / Salida / Variable
        self.blood_flow_setpoint_input = self._add_control_row(
            grid_blood, 0, 1, "SetPoint CFS", "ml/min",
            tag="bloodFlowControlSetPoint", numpad_title="Setpoint CFS (ml/min)"
        )
        self.blood_flow_output_input = self._add_control_row(
            grid_blood, 1, 1, "Salida CFS", "%",
            tag="bloodFlowControlOutput", numpad_title="Salida CFS (%)"
        )
        self.blood_flow_variable_label = self._add_control_row(
            grid_blood, 2, 1, "Variable CFS", "ml/min", is_input=False
        )

        # 3. Velocidad BS / FFWD / Lead FFWD
        self.blood_speed_rpm_label = self._add_control_row(
            grid_blood, 0, 4, "Velocidad BS", "RPM", is_input=False
        )
        self.feedforward_gain_input = self._add_control_row(
            grid_blood, 1, 4, "FFWD", "",
            tag="bloodFlowFeedForwardGain", numpad_title="Ganancia FFWD"
        )
        self.feedforward_lead_input = self._add_control_row(
            grid_blood, 2, 4, "Lead FFWD", "",
            tag="bloodFlowFeedForwardLead", numpad_title="Lead FFWD"
        )

        # 4. PID Gains
        self.blood_flow_kp_input = self._add_control_row(
            grid_blood, 0, 7, "CFS", "kp",
            tag="bloodFlowControlPropGain", numpad_title="CFS Kp Gain"
        )
        self.blood_flow_ki_input = self._add_control_row(
            grid_blood, 1, 7, "CFS", "ki",
            tag="bloodFlowControlInteGain", numpad_title="CFS Ki Gain"
        )
        self.blood_flow_kd_input = self._add_control_row(
            grid_blood, 2, 7, "CFS", "kd",
            tag="bloodFlowControlDeriGain", numpad_title="CFS Kd Gain"
        )

        # 5. Plot
        self.blood_flow_control_plot = pg.PlotWidget()
        self.blood_flow_control_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.blood_flow_control_plot.setBackground("#e0e0e0")
        self.blood_flow_control_plot.setTitle('<span style="font-size: 11pt; color: black;">Control de Flujo de Sangre</span>')
        self.blood_flow_control_plot.setLabel('left', '<span style="font-size: 9pt; color: black;">Qb / Salida (%)</span>')
        self.blood_flow_control_plot.setLabel('bottom', '<span style="font-size: 9pt; color: black;">Tiempo (s)</span>')
        self.blood_flow_control_plot.addLegend()
        self.curve_bf_setpoint = self.blood_flow_control_plot.plot(pen=pg.mkPen(color=(0, 0, 255), width=2), name="Setpoint CFS")
        self.curve_bf_variable = self.blood_flow_control_plot.plot(pen=pg.mkPen(color=(0, 150, 0), width=2), name="Variable CFS")
        self.curve_bf_output   = self.blood_flow_control_plot.plot(pen=pg.mkPen(color=(255, 0, 0),   width=2), name="Salida CFS (%)")
        self.blood_flow_control_plot.getAxis('bottom').setStyle(tickFont=tick_font, tickTextOffset=5)
        self.blood_flow_control_plot.getAxis('left').setStyle(tickFont=tick_font, tickTextOffset=5)
        grid_blood.addWidget(self.blood_flow_control_plot, 0, 10, 3, 1)

        # ═════════════════════════════════════════════════════════════════════
        # CARD 2: Control de Conductividad
        # ═════════════════════════════════════════════════════════════════════
        self.cond_card = QFrame()
        self.cond_card.setObjectName("card")
        main_layout.addWidget(self.cond_card, 1)

        cond_layout = QVBoxLayout(self.cond_card)
        cond_layout.setContentsMargins(14, 8, 14, 8)
        cond_layout.setSpacing(4)

        self.cond_card_title = QLabel("Control de Conductividad")
        self.cond_card_title.setObjectName("card_title")
        cond_layout.addWidget(self.cond_card_title)

        grid_cond = QGridLayout()
        grid_cond.setContentsMargins(0, 0, 0, 0)
        grid_cond.setSpacing(10)
        for c, w in enumerate(col_widths):
            grid_cond.setColumnMinimumWidth(c, w)
        grid_cond.setColumnStretch(10, 1)
        for r in range(3):
            grid_cond.setRowMinimumHeight(r, 38)
        cond_layout.addLayout(grid_cond)

        # 1. Toggles (ocupan las 2 primeras filas)
        double_box_cond = DoubleToggleBox("Hab. CC", "Hab. Modo CC")
        double_box_cond.setFixedWidth(230)
        double_box_cond.toggle1.toggled.connect(lambda checked, t="dialyCondCtrlLoopEnable": self._toggle_control_loop(t, checked))
        double_box_cond.toggle2.toggled.connect(lambda checked, t="dialyCondCtrlLoopMode": self._toggle_control_loop(t, checked))
        self.control_loop_toggles["dialyCondCtrlLoopEnable"] = double_box_cond.toggle1
        self.control_loop_toggles["dialyCondCtrlLoopMode"]   = double_box_cond.toggle2
        grid_cond.addWidget(double_box_cond, 0, 0, 2, 1, Qt.AlignVCenter)

        # 2. Setpoint / Salida / Variable
        self.cond_setpoint_input = self._add_control_row(
            grid_cond, 0, 1, "SetPoint Cond.", "mS/cm",
            tag="dialyCondControlSetPoint", numpad_title="Setpoint Conductividad (mS/cm)"
        )
        self.cond_output_input = self._add_control_row(
            grid_cond, 1, 1, "Salida Cond.", "%",
            tag="dialyCondControlOutput", numpad_title="Salida Conductividad (%)"
        )
        self.cond_variable_label = self._add_control_row(
            grid_cond, 2, 1, "Variable Cond.", "mS/cm", is_input=False
        )

        # 3. Columna de en medio vacía (no se compacta para alinear kp y la gráfica con Card 1)
        d4_cond = QWidget(); d4_cond.setFixedWidth(125); d4_cond.setStyleSheet("background: transparent;")
        d5_cond = QWidget(); d5_cond.setFixedWidth(95); d5_cond.setStyleSheet("background: transparent;")
        d6_cond = QWidget(); d6_cond.setFixedWidth(45); d6_cond.setStyleSheet("background: transparent;")
        grid_cond.addWidget(d4_cond, 0, 4)
        grid_cond.addWidget(d5_cond, 0, 5)
        grid_cond.addWidget(d6_cond, 0, 6)

        # 4. PID Gains
        self.cond_kp_input = self._add_control_row(
            grid_cond, 0, 7, "Cond.", "kp",
            tag="dialyCondControlPropGain", numpad_title="Cond. Kp Gain"
        )
        self.cond_ki_input = self._add_control_row(
            grid_cond, 1, 7, "Cond.", "ki",
            tag="dialyCondControlInteGain", numpad_title="Cond. Ki Gain"
        )
        self.cond_kd_input = self._add_control_row(
            grid_cond, 2, 7, "Cond.", "kd",
            tag="dialyCondControlDeriGain", numpad_title="Cond. Kd Gain"
        )

        # 5. Plot
        self.cond_control_plot = pg.PlotWidget()
        self.cond_control_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.cond_control_plot.setBackground("#e0e0e0")
        self.cond_control_plot.setTitle('<span style="font-size: 11pt; color: black;">Control de Conductividad</span>')
        self.cond_control_plot.setLabel('left', '<span style="font-size: 9pt; color: black;">Cond.(mS/cm)</span>')
        self.cond_control_plot.setLabel('bottom', '<span style="font-size: 9pt; color: black;">Tiempo (s)</span>')
        self.cond_control_plot.addLegend()
        self.curve_cond_setpoint = self.cond_control_plot.plot(pen=pg.mkPen(color=(0, 0, 255), width=2), name="Setpoint Cond.")
        self.curve_cond_variable = self.cond_control_plot.plot(pen=pg.mkPen(color=(0, 150, 0), width=2), name="Variable Cond.")
        self.curve_cond_output   = self.cond_control_plot.plot(pen=pg.mkPen(color=(255, 0, 0),   width=2), name="Salida Cond. (%)")
        self.cond_control_plot.getAxis('bottom').setStyle(tickFont=tick_font, tickTextOffset=5)
        self.cond_control_plot.getAxis('left').setStyle(tickFont=tick_font, tickTextOffset=5)
        grid_cond.addWidget(self.cond_control_plot, 0, 10, 3, 1)

        # ═════════════════════════════════════════════════════════════════════
        # CARD 3: Control de Temperatura
        # ═════════════════════════════════════════════════════════════════════
        self.temp_card = QFrame()
        self.temp_card.setObjectName("card")
        main_layout.addWidget(self.temp_card, 1)

        temp_layout = QVBoxLayout(self.temp_card)
        temp_layout.setContentsMargins(14, 8, 14, 8)
        temp_layout.setSpacing(4)

        self.temp_card_title = QLabel("Control de Temperatura")
        self.temp_card_title.setObjectName("card_title")
        temp_layout.addWidget(self.temp_card_title)

        grid_temp = QGridLayout()
        grid_temp.setContentsMargins(0, 0, 0, 0)
        grid_temp.setSpacing(10)
        for c, w in enumerate(col_widths):
            grid_temp.setColumnMinimumWidth(c, w)
        grid_temp.setColumnStretch(10, 1)
        for r in range(3):
            grid_temp.setRowMinimumHeight(r, 38)
        temp_layout.addLayout(grid_temp)

        # 1. Toggles (ocupan las 2 primeras filas)
        double_box_temp = DoubleToggleBox("Hab. CTD", "Hab. Modo CTD")
        double_box_temp.setFixedWidth(230)
        double_box_temp.toggle1.toggled.connect(lambda checked, t="dialyTempCtrlLoopEnable": self._toggle_control_loop(t, checked))
        double_box_temp.toggle2.toggled.connect(lambda checked, t="dialyTempCtrlLoopMode": self._toggle_control_loop(t, checked))
        self.control_loop_toggles["dialyTempCtrlLoopEnable"] = double_box_temp.toggle1
        self.control_loop_toggles["dialyTempCtrlLoopMode"]   = double_box_temp.toggle2
        grid_temp.addWidget(double_box_temp, 0, 0, 2, 1, Qt.AlignVCenter)

        # 2. Setpoint / Salida / Variable
        self.temp_setpoint_input = self._add_control_row(
            grid_temp, 0, 1, "SetPoint Temp.", "°C",
            tag="dialyTempControlSetPoint", numpad_title="Setpoint Temperatura (°C)"
        )
        self.temp_output_input = self._add_control_row(
            grid_temp, 1, 1, "Salida Temp.", "%",
            tag="dialyTempControlOutput", numpad_title="Salida Temperatura (%)"
        )
        self.temp_variable_label = self._add_control_row(
            grid_temp, 2, 1, "Variable Temp.", "°C", is_input=False
        )

        # 3. Columna de en medio vacía (no se compacta para alinear kp y la gráfica con Card 1)
        d4_temp = QWidget(); d4_temp.setFixedWidth(125); d4_temp.setStyleSheet("background: transparent;")
        d5_temp = QWidget(); d5_temp.setFixedWidth(95); d5_temp.setStyleSheet("background: transparent;")
        d6_temp = QWidget(); d6_temp.setFixedWidth(45); d6_temp.setStyleSheet("background: transparent;")
        grid_temp.addWidget(d4_temp, 0, 4)
        grid_temp.addWidget(d5_temp, 0, 5)
        grid_temp.addWidget(d6_temp, 0, 6)

        # 4. PID Gains
        self.temp_kp_input = self._add_control_row(
            grid_temp, 0, 7, "Temp.", "kp",
            tag="dialyTempControlPropGain", numpad_title="Temp. Kp Gain"
        )
        self.temp_ki_input = self._add_control_row(
            grid_temp, 1, 7, "Temp.", "ki",
            tag="dialyTempControlInteGain", numpad_title="Temp. Ki Gain"
        )
        self.temp_kd_input = self._add_control_row(
            grid_temp, 2, 7, "Temp.", "kd",
            tag="dialyTempControlDeriGain", numpad_title="Temp. Kd Gain"
        )

        # 5. Plot
        self.temp_control_plot = pg.PlotWidget()
        self.temp_control_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.temp_control_plot.setBackground("#e0e0e0")
        self.temp_control_plot.setTitle('<span style="font-size: 11pt; color: black;">Control de Temperatura</span>')
        self.temp_control_plot.setLabel('left', '<span style="font-size: 9pt; color: black;">T. Dializante (°C)</span>')
        self.temp_control_plot.setLabel('bottom', '<span style="font-size: 9pt; color: black;">Tiempo (s)</span>')
        self.temp_control_plot.addLegend()
        self.curve_temp_setpoint = self.temp_control_plot.plot(pen=pg.mkPen(color=(0, 0, 255), width=2), name="Setpoint Temp.")
        self.curve_temp_variable = self.temp_control_plot.plot(pen=pg.mkPen(color=(0, 150, 0), width=2), name="Variable Temp.")
        self.curve_temp_output   = self.temp_control_plot.plot(pen=pg.mkPen(color=(255, 0, 0),   width=2), name="Salida Temp. (%)")
        self.temp_control_plot.getAxis('bottom').setStyle(tickFont=tick_font, tickTextOffset=5)
        self.temp_control_plot.getAxis('left').setStyle(tickFont=tick_font, tickTextOffset=5)
        grid_temp.addWidget(self.temp_control_plot, 0, 10, 3, 1)

        logger.debug("UI de calibración configurada en 3 cards con controles y gráficos.")

    def _add_control_row(self, grid, row, col, label_text, unit_text, tag=None, numpad_title="", is_input=True, initial_value="0.0"):
        """Helper to add a labeled control row (label + input/display + unit)."""
        label = QLabel(label_text)
        label.setStyleSheet("color: #0f172a; font-size: 18px; font-weight: bold; border: none; background: transparent;")
        grid.addWidget(label, row, col, Qt.AlignVCenter | Qt.AlignLeft)
        indicator_style = "color: #22d3ee; font-size: 20px; font-weight: bold; border: 2px solid #0f172a; border-radius: 5px; padding: 2px;"

        input_style = """
            background: #FFFFE5; color: #0f172a; font-size: 18px; font-weight: bold;
            border: 2px solid #000000; border-radius: 5px; padding: 4px;
        """

        if is_input:
            widget = ClickableLineEdit(initial_value)
            widget.setReadOnly(True)
            widget.setStyleSheet(input_style)
            if tag and numpad_title:
                widget.clicked.connect(lambda: self.open_numpad(tag, widget, numpad_title))
        else:
            widget = QLabel(initial_value)            
            widget.setStyleSheet(indicator_style)                                 
            widget.setProperty("class", "highlighted")

        widget.setFixedSize(80, 35)
        widget.setAlignment(Qt.AlignCenter)
        grid.addWidget(widget, row, col + 1, Qt.AlignVCenter)

        unit_label = QLabel(unit_text)
        unit_label.setStyleSheet("color: #94a3b8; font-size: 16px;")
        grid.addWidget(unit_label, row, col + 2, Qt.AlignVCenter | Qt.AlignLeft)

        if not hasattr(self, "_calib_rows"):
            self._calib_rows = []
        self._calib_rows.append((label, widget, unit_label, is_input))

        return widget

    def _toggle_control_loop(self, tag: str, enabled: bool):
        """Enable/disable a control loop."""
        if enabled:
            print(f"[CONTROL] Habilitado {tag}")
            self.on_user_boolean_command(tag, True)
        else:
            print(f"[CONTROL] Deshabilitado {tag}")
            self.on_user_boolean_command(tag, False)



    def open_numpad(self, tag: str, input_widget: ClickableLineEdit, title: str = "Ingrese valor"):
        """Open numeric keypad for setpoint entry."""
        current_text = input_widget.text()
        dialog = NumpadDialog(self, initial_value="", title=title)
        if dialog.exec():
            new_value = dialog.get_value()
            if new_value is not None:
                input_widget.setText(str(new_value))
                self.on_user_input_setpoint(tag, input_widget)
                if hasattr(input_widget, 'clearFocus'):
                    input_widget.clearFocus()
                self.setFocus()




    def update_values(self, new_values: dict):
        """Update displayed values, plots, and inputs from shared dictionary."""
    

        self.current_values = new_values

        # ── Blood Flow ───────────────────────────────────────────────────────────
        bf_setpoint = self.current_values.get("bloodFlowControlSetPoint", 0.0)
        bf_variable = self.current_values.get("bloodFlowVariableData", 0.0)
        bf_output_raw = self.current_values.get("bloodFlowControlOutput", 0.0)
        bf_output_percent = bf_output_raw * 10  # escala 0-10 → %

        self.blood_flow_setpoint_history.append(bf_setpoint)
        self.blood_flow_variable_history.append(bf_variable)
        self.blood_flow_output_history.append(bf_output_percent)

        self.curve_bf_setpoint.setData(self.time_axis, list(self.blood_flow_setpoint_history))
        self.curve_bf_variable.setData(self.time_axis, list(self.blood_flow_variable_history))
        self.curve_bf_output.setData(self.time_axis, list(self.blood_flow_output_history))

        # ── Conductivity ─────────────────────────────────────────────────────────
        cond_setpoint = self.current_values.get("dialyCondControlSetPoint", 0.0)
        cond_variable = self.current_values.get("dialyCondVariableData", 0.0)
        cond_output_raw = self.current_values.get("dialyCondControlOutput", 0.0) # Salida de conductividad
        cond_output_percent = cond_output_raw #/ 5   se escala en el main 

        self.cond_setpoint_history.append(cond_setpoint)
        self.cond_variable_history.append(cond_variable)
        self.cond_output_history.append(cond_output_percent)

        self.curve_cond_setpoint.setData(self.time_axis, list(self.cond_setpoint_history))
        self.curve_cond_variable.setData(self.time_axis, list(self.cond_variable_history))
        self.curve_cond_output.setData(self.time_axis, list(self.cond_output_history))

        # ── Temperature ──────────────────────────────────────────────────────────
        temp_setpoint = self.current_values.get("dialyTempControlSetPoint", 0.0)
        temp_variable = self.current_values.get("dialyTempVariableData", 0.0)
        temp_output_raw = self.current_values.get("dialyTempControlOutput", 0.0)
        temp_output_percent = temp_output_raw / 2  # escala

        self.temp_setpoint_history.append(temp_setpoint)
        self.temp_variable_history.append(temp_variable)
        self.temp_output_history.append(temp_output_percent)

        self.curve_temp_setpoint.setData(self.time_axis, list(self.temp_setpoint_history))
        self.curve_temp_variable.setData(self.time_axis, list(self.temp_variable_history))
        self.curve_temp_output.setData(self.time_axis, list(self.temp_output_history))

        # Fixed X range
        for plot in [self.blood_flow_control_plot, self.cond_control_plot, self.temp_control_plot]:
            plot.setXRange(-self.history_length + 1, 0)

        # ── Numeric Inputs & Labels ──────────────────────────────────────────────
        self._update_input_display(self.blood_flow_setpoint_input, "bloodFlowControlSetPoint")
        self._update_input_display(self.blood_flow_output_input, "bloodFlowControlOutput")
        self._update_label_display(self.blood_flow_variable_label, "bloodFlowVariableData")

        self._update_input_display(self.cond_setpoint_input, "dialyCondControlSetPoint")
        self._update_input_display(self.cond_output_input, "dialyCondControlOutput") # Salida conductividad
        self._update_label_display(self.cond_variable_label, "dialyCondVariableData")

        self._update_input_display(self.temp_setpoint_input, "dialyTempControlSetPoint")
        self._update_input_display(self.temp_output_input, "dialyTempControlOutput")
        self._update_label_display(self.temp_variable_label, "dialyTempVariableData")

        self._update_label_display(self.blood_speed_rpm_label, "bloodSpeedVariableData")

        self._update_input_display(self.feedforward_gain_input, "bloodFlowFeedForwardGain")
        self._update_input_display(self.feedforward_lead_input, "bloodFlowFeedForwardLead")

        # PID Gains
        self._update_input_display(self.blood_flow_kp_input, "bloodFlowControlPropGain")
        self._update_input_display(self.blood_flow_ki_input, "bloodFlowControlInteGain")
        self._update_input_display(self.blood_flow_kd_input, "bloodFlowControlDeriGain")

        self._update_input_display(self.cond_kp_input, "dialyCondControlPropGain")
        self._update_input_display(self.cond_ki_input, "dialyCondControlInteGain")
        self._update_input_display(self.cond_kd_input, "dialyCondControlDeriGain")

        self._update_input_display(self.temp_kp_input, "dialyTempControlPropGain")
        self._update_input_display(self.temp_ki_input, "dialyTempControlInteGain")
        self._update_input_display(self.temp_kd_input, "dialyTempControlDeriGain")

    def _update_input_display(self, widget: ClickableLineEdit, tag: str, precision: int = 1):
        """Update input field if not focused."""
        value = self.current_values.get(tag, 0.0)
        if not widget.hasFocus():
            widget.setText(f"{value:.{precision}f}")

    def _update_label_display(self, label, tag: str, precision: int = 1):
        """Update read-only label."""
        value = self.current_values.get(tag, 0.0)
        label.setText(f"{value:.{precision}f}")

    def on_user_boolean_command(self, tag, state):
        self.request_boolean_change.emit(tag, state)

    def on_user_input_setpoint(self, tag: str, input_widget: ClickableLineEdit):
        text = input_widget.text().replace(',', '.')
        if not text:
            current_value = self.current_values.get(tag, 0.0)
            input_widget.setText(f"{current_value:.1f}")
            return
        value = float(text) 
        
        self.request_setpoint_change.emit(tag, value) 

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()

    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        is_mono = bool(tokens.get("monochrome", False))
        is_dark = bool(tokens.get("is_dark", False))

        self.setStyleSheet(f"QWidget#CalibrationScreen {{ background-color: {tokens['bg_main']}; }}")

        # Cards styling
        card_style = (
            f"QFrame#card {{ background-color: {tokens.get('bg_card', '#FFFFFF')}; "
            f"border: 2px solid {tokens.get('border_card', '#E2E8F0')}; border-radius: 16px; }}"
        )
        for card in (getattr(self, "blood_card", None), getattr(self, "cond_card", None), getattr(self, "temp_card", None)):
            if card:
                card.setStyleSheet(card_style)

        # Card titles styling
        title_size = tokens.get("font_size_card_title", "20px")
        title_style = (
            f"color: {tokens.get('title_color', '#0f172a')}; font-size: {title_size}; font-weight: bold; "
            f"background: transparent; border: none;"
        )
        for t_lbl in (getattr(self, "blood_card_title", None), getattr(self, "cond_card_title", None), getattr(self, "temp_card_title", None)):
            if t_lbl:
                t_lbl.setStyleSheet(title_style)

        if is_mono:
            inp_style = (
                "background: #F8F9FA; color: #374151; font-size: 18px; font-weight: bold; "
                "border: 2px solid #C5CDD6; border-radius: 5px; padding: 4px;"
            )
            ind_style = (
                "color: #374151; font-size: 20px; font-weight: bold; "
                "border: 2px solid #C5CDD6; border-radius: 5px; padding: 2px; background: #FFFFFF;"
            )
            lbl_style = "color: #374151; font-size: 18px; font-weight: bold; border: none; background: transparent;"
            unt_style = "color: #6B7280; font-size: 16px; border: none; background: transparent;"

            # Plots
            for plot, title_text, y_label in [
                (getattr(self, "blood_flow_control_plot", None), "Control de Flujo de Sangre", "Qb / Salida (%)"),
                (getattr(self, "cond_control_plot", None), "Control de Conductividad", "Cond.(mS/cm)"),
                (getattr(self, "temp_control_plot", None), "Control de Temperatura", "T. Dializante (°C)")
            ]:
                if plot:
                    plot.setBackground("#FFFFFF")
                    plot.setTitle(f'<span style="font-size: 11pt; color: #374151;">{title_text}</span>')
                    plot.setLabel('left', f'<span style="font-size: 9pt; color: #374151;">{y_label}</span>')
                    plot.setLabel('bottom', '<span style="font-size: 9pt; color: #374151;">Tiempo (s)</span>')

            if hasattr(self, "curve_bf_setpoint"):
                self.curve_bf_setpoint.setPen(pg.mkPen(color="#374151", width=2, style=Qt.SolidLine))
                self.curve_bf_variable.setPen(pg.mkPen(color="#6B7280", width=2, style=Qt.DashLine))
                self.curve_bf_output.setPen(pg.mkPen(color="#9CA3AF", width=2, style=Qt.DotLine))

            if hasattr(self, "curve_cond_setpoint"):
                self.curve_cond_setpoint.setPen(pg.mkPen(color="#374151", width=2, style=Qt.SolidLine))
                self.curve_cond_variable.setPen(pg.mkPen(color="#6B7280", width=2, style=Qt.DashLine))
                self.curve_cond_output.setPen(pg.mkPen(color="#9CA3AF", width=2, style=Qt.DotLine))

            if hasattr(self, "curve_temp_setpoint"):
                self.curve_temp_setpoint.setPen(pg.mkPen(color="#374151", width=2, style=Qt.SolidLine))
                self.curve_temp_variable.setPen(pg.mkPen(color="#6B7280", width=2, style=Qt.DashLine))
                self.curve_temp_output.setPen(pg.mkPen(color="#9CA3AF", width=2, style=Qt.DotLine))

        elif is_dark:
            inp_style = f"background: {tokens.get('bg_input', '#1E293B')}; color: {tokens.get('text_primary', '#F8FAFC')}; font-size: 18px; font-weight: bold; border: 2px solid {tokens.get('border_input', '#334155')}; border-radius: 5px; padding: 4px;"
            ind_style = f"color: {tokens.get('primary', '#38BDF8')}; font-size: 20px; font-weight: bold; border: 2px solid {tokens.get('border_card', '#334155')}; border-radius: 5px; padding: 2px; background: {tokens.get('bg_card_alt', '#1E293B')};"
            lbl_style = f"color: {tokens.get('text_primary', '#F8FAFC')}; font-size: 18px; font-weight: bold; border: none; background: transparent;"
            unt_style = f"color: {tokens.get('text_muted', '#64748B')}; font-size: 16px; border: none; background: transparent;"

            for plot, title_text, y_label in [
                (getattr(self, "blood_flow_control_plot", None), "Control de Flujo de Sangre", "Qb / Salida (%)"),
                (getattr(self, "cond_control_plot", None), "Control de Conductividad", "Cond.(mS/cm)"),
                (getattr(self, "temp_control_plot", None), "Control de Temperatura", "T. Dializante (°C)")
            ]:
                if plot:
                    plot.setBackground(tokens.get("bg_card_alt", "#1E293B"))
                    plot.setTitle(f'<span style="font-size: 11pt; color: {tokens.get("text_primary", "#F8FAFC")};">{title_text}</span>')
                    plot.setLabel('left', f'<span style="font-size: 9pt; color: {tokens.get("text_primary", "#F8FAFC")};">{y_label}</span>')
                    plot.setLabel('bottom', f'<span style="font-size: 9pt; color: {tokens.get("text_primary", "#F8FAFC")};">Tiempo (s)</span>')

            if hasattr(self, "curve_bf_setpoint"):
                self.curve_bf_setpoint.setPen(pg.mkPen(color=(56, 189, 248), width=2, style=Qt.SolidLine))
                self.curve_bf_variable.setPen(pg.mkPen(color=(74, 222, 128), width=2, style=Qt.SolidLine))
                self.curve_bf_output.setPen(pg.mkPen(color=(248, 113, 113), width=2, style=Qt.SolidLine))

            if hasattr(self, "curve_cond_setpoint"):
                self.curve_cond_setpoint.setPen(pg.mkPen(color=(56, 189, 248), width=2, style=Qt.SolidLine))
                self.curve_cond_variable.setPen(pg.mkPen(color=(74, 222, 128), width=2, style=Qt.SolidLine))
                self.curve_cond_output.setPen(pg.mkPen(color=(248, 113, 113), width=2, style=Qt.SolidLine))

            if hasattr(self, "curve_temp_setpoint"):
                self.curve_temp_setpoint.setPen(pg.mkPen(color=(56, 189, 248), width=2, style=Qt.SolidLine))
                self.curve_temp_variable.setPen(pg.mkPen(color=(74, 222, 128), width=2, style=Qt.SolidLine))
                self.curve_temp_output.setPen(pg.mkPen(color=(248, 113, 113), width=2, style=Qt.SolidLine))

        else:
            inp_style = """
                background: #FFFFE5; color: #0f172a; font-size: 18px; font-weight: bold;
                border: 2px solid #000000; border-radius: 5px; padding: 4px;
            """
            ind_style = "color: #22d3ee; font-size: 20px; font-weight: bold; border: 2px solid #0f172a; border-radius: 5px; padding: 2px;"
            lbl_style = "color: #0f172a; font-size: 18px; font-weight: bold; border: none; background: transparent;"
            unt_style = "color: #94a3b8; font-size: 16px; border: none; background: transparent;"

            for plot, title_text, y_label in [
                (getattr(self, "blood_flow_control_plot", None), "Control de Flujo de Sangre", "Qb / Salida (%)"),
                (getattr(self, "cond_control_plot", None), "Control de Conductividad", "Cond.(mS/cm)"),
                (getattr(self, "temp_control_plot", None), "Control de Temperatura", "T. Dializante (°C)")
            ]:
                if plot:
                    plot.setBackground("#e0e0e0")
                    plot.setTitle(f'<span style="font-size: 11pt; color: black;">{title_text}</span>')
                    plot.setLabel('left', f'<span style="font-size: 9pt; color: black;">{y_label}</span>')
                    plot.setLabel('bottom', '<span style="font-size: 9pt; color: black;">Tiempo (s)</span>')

            if hasattr(self, "curve_bf_setpoint"):
                self.curve_bf_setpoint.setPen(pg.mkPen(color=(0, 0, 255), width=2, style=Qt.SolidLine))
                self.curve_bf_variable.setPen(pg.mkPen(color=(0, 150, 0), width=2, style=Qt.SolidLine))
                self.curve_bf_output.setPen(pg.mkPen(color=(255, 0, 0), width=2, style=Qt.SolidLine))

            if hasattr(self, "curve_cond_setpoint"):
                self.curve_cond_setpoint.setPen(pg.mkPen(color=(0, 0, 255), width=2, style=Qt.SolidLine))
                self.curve_cond_variable.setPen(pg.mkPen(color=(0, 150, 0), width=2, style=Qt.SolidLine))
                self.curve_cond_output.setPen(pg.mkPen(color=(255, 0, 0), width=2, style=Qt.SolidLine))

            if hasattr(self, "curve_temp_setpoint"):
                self.curve_temp_setpoint.setPen(pg.mkPen(color=(0, 0, 255), width=2, style=Qt.SolidLine))
                self.curve_temp_variable.setPen(pg.mkPen(color=(0, 150, 0), width=2, style=Qt.SolidLine))
                self.curve_temp_output.setPen(pg.mkPen(color=(255, 0, 0), width=2, style=Qt.SolidLine))

        for lbl, wid, unt, is_input in getattr(self, "_calib_rows", []):
            lbl.setStyleSheet(lbl_style)
            unt.setStyleSheet(unt_style)
            if is_input:
                wid.setStyleSheet(inp_style)
            else:
                wid.setStyleSheet(ind_style)

        # Fallback to style all ClickableLineEdit and indicators
        for wid in self.findChildren(ClickableLineEdit):
            wid.setStyleSheet(inp_style)
        for lbl in self.findChildren(QLabel):
            if lbl.property("class") == "highlighted":
                lbl.setStyleSheet(ind_style)

        # Update DoubleToggleBox widgets
        for box in self.findChildren(DoubleToggleBox):
            try:
                box.apply_theme_styles()
            except Exception:
                pass
