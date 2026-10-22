from gui.theme_manager import ThemeManager
# gui/service/manual_mode_screen.py
# Manual mode screen for direct control of pumps, valves, and critical actuators
# Critical safety features: REQ-SW-005, REQ-SW-010, REQ-SW-012, REQ-SW-020

"""
Módulo para la pantalla de control manual de la máquina de hemodiálisis.

Este módulo define la clase `ManualModeScreen`, que proporciona una interfaz
avanzada para el control directo de bombas, válvulas y otros actuadores
críticos del sistema. Es una herramienta esencial para el personal técnico
durante la configuración, mantenimiento, diagnóstico y pruebas de la máquina,
ofreciendo un control granular y funcionalidades de temporización.

Características principales:
-----------------------------
- **Control Directo de Actuadores:**
    - **Bombas:** Controles ON/OFF mediante `ToggleSwitch` para bombas de sangre,
      heparina, UF, dializante, purga, bicarbonato (Na+) y ácido cítrico.
      Incluye control de dirección (FWD/REV) y posición HOME para algunas bombas.
    - **Válvulas:** Control ON/OFF de válvulas de circuito mediante `ValveCard`
      reutilizables.
- **Configuración de Setpoints:**
    - Ajuste de flujos (ml/min, L/h), dosis de heparina (ml/h), bolo (ml),
      tamaño de jeringa y salidas de bombas (%) mediante `NumpadDialog`s táctiles.
- **Temporización y Automatización:**
    - **Temporizadores Locales:** Cada bomba puede configurarse para operar
      durante un tiempo determinado, con displays de tiempo transcurrido y restante.
    - **Agrupación de Bombas:** Una característica avanzada que permite al usuario
      seleccionar un grupo de bombas que se detendrán automáticamente cuando
      expire un temporizador principal (ej. el de la bomba de heparina para
      el "tiempo de terapia"). Esto responde a la REQ-SW-012.
- **Monitorización de Estado:**
    - **Indicadores LED:** Muestra el estado de actuadores y sensores clave
      mediante LEDs virtuales.
    - Sincronización constante con los valores recibidos del controlador.
- **Manejo de Interacciones:**
    - Utiliza `PushbuttonEvent` para una respuesta más rápida en botones táctiles.
    - Implementa "hold-off" en las escrituras para evitar conflictos y asegurar
      la consistencia de la UI con el controlador (REQ-SW-005).
    - `ToggleSwitch` personalizado para control de estado ON/OFF con feedback visual.

Requisitos de Seguridad (REQ-SW):
----------------------------------
Este módulo implementa o es crucial para cumplir con varios requisitos de seguridad
del software, como:
- **REQ-SW-005:** Control individual y seguro de componentes (bombas, válvulas).
- **REQ-SW-010:** Monitorización y visualización del estado de los actuadores.
- **REQ-SW-012:** Gestión de la interrupción automática de la terapia o componentes
  (ej. agrupamiento de bombas por tiempo de terapia).
- **REQ-SW-020:** Habilidad para activar/desactivar el modo manual solo por personal autorizado.

Clases principales:
-------------------
- `ManualModeScreen`: El widget principal que orquesta todos los controles, displays,
  temporizadores y la lógica de interacción para el modo manual.
- `PushbuttonEvent`: Extiende `QPushButton` para manejar eventos táctiles con mayor
  precisión, útil para botones de acción rápida como FWD/REV.
- `ValveCard`: Un widget reutilizable para controlar una válvula individual,
  mostrando su código, descripción y un `ToggleSwitch`.

Dependencias:
-------------
- `PySide6`: Para la construcción de la interfaz gráfica y la gestión de eventos.
- `gui.components.*`: Varios componentes UI personalizados (`LED`, `ToggleSwitch`,
  `NumpadDialog`, `TimeNumpadDialog`, `ClickableLineEdit`, `LabeledParameterWidget`, `LabeledTimeInput`).
- `core.variables_map.VARIABLES`: Mapeo de tags de variables para comunicación con el controlador.
- `logic.calculos`: Funciones para conversiones entre unidades de flujo (ml/min, L/h, ciclos).

Uso:
----
La clase `ManualModeScreen` se instancia en el `HemodialysisHMI` principal
y se añade a su `QStackedWidget` como una pantalla de servicio. Se espera
que el `HemodialysisHMI` conecte sus señales `request_setpoint_change` y
`request_boolean_change` a métodos que envíen los comandos al controlador serial.
"""



from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QGridLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, QSizePolicy, QCheckBox, QDialog
from PySide6.QtCore import Qt, QTimer, QDateTime, QEvent, Signal
from PySide6.QtGui import QColor


from gui.components.LED import LED
from gui.components.ToggleSwitch import ToggleSwitch
from gui.components.numpad_modal import NumpadDialog
from gui.components.time_numpad_modal import TimeNumpadDialog
from gui.components.ui_components import ClickableLineEdit, LabeledParameterWidget, LabeledTimeInput
import logging
logger = logging.getLogger(__name__)

from core.variables_map import VARIABLES
from logic.calculos import (
    convertir_flujo_a_ciclos,
    convertir_ciclos_a_flujo,
    convertir_litros_h_a_ml_min,
    convertir_ml_min_a_litros_h
)



class PushbuttonEvent(QPushButton):
    """
    QPushButton personalizado que optimiza la detección de eventos táctiles.

    Este widget se usa para mejorar la capacidad de respuesta en entornos táctiles
    al aceptar `Qt.WA_AcceptTouchEvents` y manejar directamente `QEvent.Type.TouchBegin`,
    `QEvent.Type.TouchEnd` y `QEvent.Type.TouchCancel` para emitir señales `pressed` y `released`.
    Esto puede proporcionar una retroalimentación más inmediata que el clic tradicional
    para operaciones como FWD/REV en bombas.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)

    def event(self, event):
        if event.type() == QEvent.Type.TouchBegin:
            self.setDown(True)
            self.pressed.emit()
            return True

        elif event.type() in (QEvent.Type.TouchEnd, QEvent.Type.TouchCancel):
            self.setDown(False)
            self.released.emit()
            return True

        return super().event(event)

class ValveCard(QFrame):
    """
    Componente reutilizable para el control individual de una válvula.

    Representa visualmente una válvula con su código, una breve descripción
    y un `ToggleSwitch` para cambiar su estado (abrir/cerrar). La tarjeta
    se integra en la interfaz para ofrecer un control claro y táctil sobre
    elementos discretos del sistema de fluidos. Responde a la REQ-SW-005.

    Args:
        code (str): Identificador de la válvula (ej. "SV_24").
        description (str): Descripción funcional de la válvula (ej. "E. Filtro UF").
        parent (QWidget, optional): Widget padre.
    """


    def __init__(self, code: str, description: str, parent=None):
        super().__init__(parent)
        self.code = code
        self.description = description
        self.setFixedHeight(80)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.info_label = QLabel(f"<b>{code}</b><br><span style='font-size:18px;'>{description}</span>")
        self.info_label.setAlignment(Qt.AlignLeft | Qt.AlignCenter)

        self.toggle = ToggleSwitch(width=70, height=30, parent=self)
        layout.addWidget(self.info_label)
        layout.addStretch()
        layout.addWidget(self.toggle)

        self.apply_theme_styles()
        try:
            ThemeManager.instance().theme_changed.connect(lambda _t: self.apply_theme_styles())
        except Exception:
            pass

    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        is_mono = bool(tokens.get("monochrome", False))
        is_dark = bool(tokens.get("is_dark", False))

        if is_mono:
            self.setStyleSheet("""
                QFrame {
                    background-color: #FFFFFF;
                    border-radius: 6px;
                    border: 1px solid #D1D5DB;
                }
            """)
            self.info_label.setText(f"<b>{self.code}</b><br><span style='font-size:18px; color:#6B7280;'>{self.description}</span>")
            self.info_label.setStyleSheet("color: #111827; font-size: 18px; border:none; background: transparent;")
        elif is_dark:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {tokens.get('bg_card', '#1E293B')};
                    border-radius: 6px;
                    border: 1px solid {tokens.get('border_card', '#334155')};
                }}
            """)
            self.info_label.setText(f"<b>{self.code}</b><br><span style='font-size:18px; color:{tokens.get('text_secondary', '#94A3B8')};'>{self.description}</span>")
            self.info_label.setStyleSheet(f"color: {tokens.get('text_primary', '#F8FAFC')}; font-size: 18px; border:none; background: transparent;")
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #1e293b;
                    border-radius: 2px;
                    border: 1px solid #334155;
                }
            """)
            self.info_label.setText(f"<b>{self.code}</b><br><span style='font-size:18px; color:#cbd5e1;'>{self.description}</span>")
            self.info_label.setStyleSheet("color: #ffffff; font-size: 18px; border:none; background: transparent;")


class ManualModeScreen(QWidget):
    valueChanged = Signal(str, float)
    request_setpoint_change = Signal(str, float)
    request_boolean_change = Signal(str, bool)

    def __init__(self, parent=None, values_dict=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_values = values_dict if values_dict is not None else {}
        self.heparin_pause_latched = False

        self.write_hold_off = {}
        self.toggle_hold_off = {}
        self.grouped_pumps = set()

        
        self.pump_configs = {
            "balance_chamber": {
                "stop_tag": "dialiserBalChambStpButt",
                "start_tag": "dialiserBalChambStrButt",
                "toggle": lambda: self.balance_chamber_toggle,
                "timer_key": "balance_chamber"
            },
            "heparin_pump": {
                "stop_tag": "heparinePumpsStopButton",
                "start_tag": "heparinePumpsStartButton",
                "toggle": lambda: self.heparin_pump_toggle,
                "timer_key": "heparin_pump"
            },
            "uf_pump": {
                "stop_tag": "dialyUltraFPumpStoptButt",
                "start_tag": "dialyUltraFPumpStartButt",
                "toggle": lambda: self.uf_pump_toggle,
                "timer_key": "uf_pump"
            },
            "purge_pump": {
                "stop_tag": "dialyPurgePumpStopButt",
                "start_tag": "dialyPurgePumpStartButt",
                "toggle": lambda: self.purge_pump_toggle,
                "timer_key": None  # No tiene timer propio, pero se apaga igual
            },
            "dialysate_pump": {
                "stop_tag": "dialyserPumpStopButton",
                "start_tag": "dialyserPumpStartButton",
                "toggle": lambda: self.dialysate_pump_toggle,
                "timer_key": "dialysate_pump"
            },
            "blood_pump": {
                "stop_tag": "bloodPumpStopButton",
                "start_tag": "bloodPumpStartButton",
                "toggle": lambda: self.blood_pump_toggle,
                "timer_key": "blood_pump"
            },
            "bicarbonate_pump": {  # NA+
                "stop_tag": "dialyBicarbonPumpStopButt",
                "start_tag": "dialyBicarbonPumpStartButt",
                "toggle": lambda: self.bicarbonate_pump_toggle,
                "timer_key": None
            },
            "citric_acid_pump": {  # Ácido
                "stop_tag": "dialyCitricAcPumpStopButt",
                "start_tag": "dialyCitricAcPumpStartButt",
                "toggle": lambda: self.citric_acid_pump_toggle,
                "timer_key": None
            },
        }


        self._setup_timers()
        self.setup_ui()
        logger.info("Manual mode module initialized (v1.0.0)")
        self.apply_theme_styles()
        try:
            ThemeManager.instance().theme_changed.connect(lambda _t: self.apply_theme_styles())
        except Exception:
            pass

    def _setup_timers(self):
        self.blood_pump_timer = QTimer(self)
        self.blood_pump_timer.timeout.connect(self._stop_blood_pump_on_timeout)

        self.dialysate_pump_timer = QTimer(self)
        self.dialysate_pump_timer.timeout.connect(self._stop_dialysate_pump_on_timeout)

        self.uf_pump_timer = QTimer(self)
        self.uf_pump_timer.timeout.connect(self._stop_uf_pump_on_timeout)

        self.heparin_pump_timer = QTimer(self)
        self.heparin_pump_timer.timeout.connect(self._stop_heparin_pump_on_timeout)

        self.balance_chamber_timer = QTimer(self)
        self.balance_chamber_timer.timeout.connect(self._stop_balance_chamber_on_timeout)

        self.display_update_timer = QTimer(self)
        self.display_update_timer.timeout.connect(self._update_local_time_displays)
        self.display_update_timer.start(500)

        self.local_timer_states = {
            "blood_pump":     {"duration_ms": 0, "start_ms": 0, "active": False, "elapsed_lbl": None, "remaining_lbl": None},
            "dialysate_pump": {"duration_ms": 0, "start_ms": 0, "active": False, "elapsed_lbl": None, "remaining_lbl": None},
            "uf_pump":        {"duration_ms": 0, "start_ms": 0, "active": False, "elapsed_lbl": None, "remaining_lbl": None},
            "heparin_pump":   {"duration_ms": 0, "start_ms": 0, "active": False, "elapsed_lbl": None, "remaining_lbl": None},
            "balance_chamber": {"duration_ms": 0, "start_ms": 0, "active": False, "elapsed_lbl": None, "remaining_lbl": None},          
        }

    def setup_ui(self):
        layout = QGridLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        label_style = "color: #000000; font-size: 18px; font-weight: bold; border: none; background: transparent;"
        indicator_style = "color: #22d3ee; font-size: 20px; font-weight: bold; border: 2px solid #000000; border-radius: 5px; padding: 2px;"
        button_style = """
            QPushButton { background: #3b82f6; color: #ffffff; border-radius: 20px; font-weight: bold; }
            QPushButton:pressed { background: #1e40af; }
        """
        input_style = """
            background: #FFFFE5; color: #000000; font-size: 18px; font-weight: bold;
            border: 2px solid #000000; border-radius: 5px; padding: 4px;
        """

        self.control_area = QWidget(self)
        self.control_area.setStyleSheet("background: #fcfcfc; border: None;")
        self.control_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        grid = QGridLayout(self.control_area)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        grid.setContentsMargins(8, 8, 8, 8)

        # Afinar distribución manteniendo posiciones actuales de controles.
        # Bloque izquierdo (0-3), separador (4), bloque derecho (5-12).
        grid.setColumnMinimumWidth(0, 170)
        grid.setColumnMinimumWidth(1, 70)
        grid.setColumnMinimumWidth(2, 170)
        grid.setColumnMinimumWidth(3, 70)
        grid.setColumnMinimumWidth(4, 42)
        grid.setColumnMinimumWidth(5, 80)
        grid.setColumnMinimumWidth(6, 88)
        grid.setColumnMinimumWidth(7, 92)
        grid.setColumnMinimumWidth(8, 92)
        grid.setColumnMinimumWidth(9, 125)
        grid.setColumnMinimumWidth(10, 125)
        grid.setColumnMinimumWidth(11, 125)
        grid.setColumnMinimumWidth(12, 125)

        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 2)
        grid.setColumnStretch(3, 1)
        grid.setColumnStretch(4, 1)
        grid.setColumnStretch(5, 1)
        grid.setColumnStretch(6, 1)
        grid.setColumnStretch(7, 1)
        grid.setColumnStretch(8, 1)
        grid.setColumnStretch(9, 2)
        grid.setColumnStretch(10, 2)
        grid.setColumnStretch(11, 2)
        grid.setColumnStretch(12, 2)

        for r in (0, 1, 2, 4, 5, 6, 8):
            grid.setRowMinimumHeight(r, 84)

        # ==============================================================================
        # --- FILA 0: Dosis Heparina(1), Bolo(2) | Sangre(3,4,5,6,7) ---
        # ==============================================================================
        
        # 1. Dosis de heparina (Izq)
        self.input_heparin = LabeledParameterWidget(
            label_text="Dosis Hep.", tag="heparineTherapyDosage",
            value="", units="ml/h", numpad_title="Dosis Heparina",
            is_editable=True, parent=self.control_area
        )
        self.input_heparin.request_numpad.connect(self.open_numpad)
        grid.addWidget(self.input_heparin, 0, 0, 1, 2)

        # 2. Bolus (Izq)
        self.input_bolus = LabeledParameterWidget(
            label_text="Bolo", tag="heparineBolusQuantity",
            value="", units="ml", numpad_title="Dosis Bolo",
            is_editable=True, parent=self.control_area
        )
        self.input_bolus.request_numpad.connect(self.open_numpad)
        grid.addWidget(self.input_bolus, 0, 2, 1, 2)

        # 3. Toggle b. sangre (Der)
        self.lbl_blood_pump = QLabel("B. S.")
        self.lbl_blood_pump.setStyleSheet(label_style)
        grid.addWidget(self.lbl_blood_pump, 0, 5, 1, 1)

        self.blood_pump_toggle = ToggleSwitch(width=70, height=35, parent=self.control_area)
        self.blood_pump_toggle.toggled.connect(
            lambda checked: self._handle_dual_pump_toggle(
                "bloodPumpStartButton", "bloodPumpStopButton", checked, timer_id="blood_pump"
            )
        )
        grid.addWidget(self.blood_pump_toggle, 0, 6, 1, 1)

        # 4. Btn REV sangre (Der)
        self.btn_rev = PushbuttonEvent("REV", self.control_area)
        self.btn_rev.setFixedSize(80, 70) 
        self.btn_rev.setStyleSheet(button_style)        
        self.btn_rev.pressed.connect(lambda: self.on_user_boolean_command("bloodPumpREVButton", True))
        self.btn_rev.released.connect(lambda: self.on_user_boolean_command("bloodPumpREVButton", False))
        grid.addWidget(self.btn_rev, 0, 7, 1, 1)

        # 5. Btn FWD sangre (Der)
        self.btn_fwd = PushbuttonEvent("FWD", self.control_area)
        self.btn_fwd.setFixedSize(80, 70)
        self.btn_fwd.setStyleSheet(button_style)
        self.btn_fwd.pressed.connect(lambda: self.on_user_boolean_command("bloodPumpFWDButton", True))
        self.btn_fwd.released.connect(lambda: self.on_user_boolean_command("bloodPumpFWDButton", False))
        grid.addWidget(self.btn_fwd, 0, 8, 1, 1)

        # 6. Flujo Sangre (Der)
        self.blood_flow_input = LabeledParameterWidget(
            label_text="Flujo", tag="bloodFlowControlSetPoint",
            value="0", units="ml/min", numpad_title="Flujo de Sangre",
            is_editable=True, parent=self.control_area
        )
        self.blood_flow_input.request_numpad.connect(self.open_numpad)
        grid.addWidget(self.blood_flow_input, 0, 9, 1, 2)

        # 7. Velocidad Sangre (Der)
        self.blood_speed_display = LabeledParameterWidget(
            label_text="Vel", tag="bloodSpeedVariableData",
            value="", units="rpm", is_editable=False, parent=self.control_area
        )
        grid.addWidget(self.blood_speed_display, 0, 11, 1, 2)


        # ==============================================================================
        # --- FILA 1: Jeringa(8), Btn Bolo(9) | Tiempos Sangre(10, 11) ---
        # ==============================================================================

        # 8. Jeringa (Izq)
        self.input_syringe_size = LabeledParameterWidget(
            label_text="Jeringa", tag="heparineSyrinjeScaleSize",
            value="", units="mm/ml", numpad_title="Tamaño de jeringa",
            is_editable=True, parent=self.control_area
        )
        self.input_syringe_size.request_numpad.connect(self.open_numpad)
        grid.addWidget(self.input_syringe_size, 1, 0, 1, 2)

        # 9. Btn aplicar bolo (Izq)
        self.btn_bolus_apply = QPushButton("Aplicar\nbolo", self.control_area)
        self.btn_bolus_apply.setFixedSize(120, 70)
        self.btn_bolus_apply.setStyleSheet(button_style)
        self.btn_bolus_apply.pressed.connect(lambda: self.on_user_boolean_command("heparinApplyBolusDose", True))
        # btn_bolus_apply.released.connect(lambda: self.on_user_boolean_command("heparinApplyBolusDose", False))
        grid.addWidget(self.btn_bolus_apply, 1, 2, 1, 2, alignment=Qt.AlignCenter)

        # 10. Tiempo operación b. sangre (Der)
        self.blood_pump_time_input = LabeledTimeInput(
            label_text="Tiempo Op.:", initial_hh_mm="00:00",
            tag_hours=None, tag_minutes=None, local_timer_id="blood_pump",
            numpad_title="Tiempo de operación de bomba de sangre",
            is_editable=True,
            parent=self.control_area
        )
        self.blood_pump_time_input.request_time_numpad.connect(self.open_time_numpad)
        grid.addWidget(self.blood_pump_time_input, 1, 9, 1, 2)

        # 11. Rest b. sangre (Der)
        self.remaining_blood_time_label = LabeledTimeInput(
            label_text="Rest.:", 
            initial_hh_mm="00:00",
            is_editable=False,
            parent=self.control_area
        )        
        grid.addWidget(self.remaining_blood_time_label, 1, 11, 1, 2)
        self.local_timer_states["blood_pump"]["remaining_lbl"] = self.remaining_blood_time_label.time_display
        


        # ==============================================================================
        # --- FILA 2: Terapia(12, 43) | B. Heparina (13-18) ---
        # ==============================================================================

        # 12. Tiempo terapia (Izq)
        self.heparin_time_input = LabeledTimeInput(
            label_text="T. Terapia:", initial_hh_mm="00:00",
            tag_hours="heparineTherapyHours", tag_minutes="heparineTherapyMinutes",
            local_timer_id="heparin_pump", numpad_title="Tiempo de terapia",
            is_editable=True,
            parent=self.control_area
        )
        self.heparin_time_input.request_time_numpad.connect(self.open_time_numpad)
        grid.addWidget(self.heparin_time_input, 2, 0, 1, 2) 

        # 43. Rest. Terapia (Izq)
        self.remaining_heparin_pump = LabeledTimeInput(
            label_text="Rest.:", 
            initial_hh_mm="00:00",
            is_editable=False,
            parent=self.control_area
        )        
        grid.addWidget(self.remaining_heparin_pump, 2, 2, 1, 2)       

        self.local_timer_states["heparin_pump"]["remaining_lbl"] = self.remaining_heparin_pump.time_display

        # 13. Toggle b. heparina (Der)
        lbl_heparin_pump = QLabel("B. Hep.", self.control_area)
        lbl_heparin_pump.setStyleSheet(label_style)
        grid.addWidget(lbl_heparin_pump, 2, 5, 1, 1)

        self.heparin_pump_toggle = ToggleSwitch(width=70, height=35, parent=self.control_area)
        self.heparin_pump_toggle.toggled.connect(
            lambda checked: self._handle_dual_pump_toggle("heparinePumpsStartButton", "heparinePumpsStopButton", checked, timer_id="heparin_pump")
        )
        grid.addWidget(self.heparin_pump_toggle, 2, 6, 1, 1)

        # 14. Btn HOME heparina
        self.btn_heparin_home = PushbuttonEvent("HOME", self.control_area)
        self.btn_heparin_home.setFixedSize(80, 70)
        self.btn_heparin_home.setStyleSheet(button_style)
        self.btn_heparin_home.pressed.connect(lambda: self.on_user_boolean_command("heparinePumpHomePosition", True))
        # btn_heparin_home.released.connect(lambda: self.on_user_boolean_command("heparinePumpHomePosition", False))
        grid.addWidget(self.btn_heparin_home, 2, 7, 1, 1)

        # 15. Btn REV heparina
        self.btn_rev_hep = PushbuttonEvent("REV", self.control_area)
        self.btn_rev_hep.setFixedSize(80, 70)
        self.btn_rev_hep.setStyleSheet(button_style)
        self.btn_rev_hep.pressed.connect(lambda: self.on_user_boolean_command("heparinePumpREVButton", True))
        self.btn_rev_hep.released.connect(lambda: self.on_user_boolean_command("heparinePumpREVButton", False))
        grid.addWidget(self.btn_rev_hep, 2, 8, 1, 1)

        # 16. Btn PAUSE heparina
        self.btn_pause_hep = PushbuttonEvent("PAUSE", self.control_area)
        self.btn_pause_hep.setFixedSize(80, 70)
        self.btn_pause_hep.setStyleSheet(button_style)
        self.btn_pause_hep.clicked.connect(self._toggle_heparin_pause_resume)
        grid.addWidget(self.btn_pause_hep, 2, 9, 1, 1)

        # 17. Btn FWD heparina
        self.btn_fwd_hep = PushbuttonEvent("FWD", self.control_area)
        self.btn_fwd_hep.setFixedSize(80, 70)
        self.btn_fwd_hep.setStyleSheet(button_style)
        self.btn_fwd_hep.pressed.connect(lambda: self.on_user_boolean_command("heparinePumpFWDButton", True))
        self.btn_fwd_hep.released.connect(lambda: self.on_user_boolean_command("heparinePumpFWDButton", False))
        grid.addWidget(self.btn_fwd_hep, 2, 10, 1, 1)

        # 18. Heparina (Acumulado)
        self.heparin_current_dosage_display = LabeledParameterWidget(
            label_text="Hep.", tag="heparineCurrentDosage",
            value="", units="ml", is_editable=False, parent=self.control_area
        )
        grid.addWidget(self.heparin_current_dosage_display, 2, 11, 1, 2)


        # ==============================================================================
        # --- FILA 4: Camara Balance(19,20) | B. Dializante (21-24) ---
        # ==============================================================================

        # 19. Toggle camara balance (Izq)
        lbl_cb = QLabel("C. Balance", self.control_area)
        lbl_cb.setStyleSheet(label_style)
        grid.addWidget(lbl_cb, 4, 0, 1, 1)

        self.balance_chamber_toggle = ToggleSwitch(width=70, height=35, parent=self.control_area)
        self.balance_chamber_toggle.toggled.connect(
            lambda chk: self._handle_dual_pump_toggle("dialiserBalChambStrButt", "dialiserBalChambStpButt", chk, timer_id="balance_chamber")
        )
        grid.addWidget(self.balance_chamber_toggle, 4, 1, 1, 1)

        # 20. Flujo CB (Izq)
        self.input_flow_cb = LabeledParameterWidget(
            label_text="Flujo", 
            tag="balanceChamberSetTiming", 
            value="0.0", 
            units="ml/min", # mostrar unidades 
            is_editable=True, 
            parent=self.control_area
        )
        self.input_flow_cb.request_numpad.connect(lambda tag, wid, tit: self._handle_cb_flow_input())
        grid.addWidget(self.input_flow_cb, 4, 2, 1, 2)    

        # 21. Toggle dializante (Der)
        lbl_dialysate = QLabel("B. Dial.", self.control_area)
        lbl_dialysate.setStyleSheet(label_style)
        grid.addWidget(lbl_dialysate, 4, 5, 1, 1)
        self.dialysate_pump_toggle = ToggleSwitch(width=70, height=35, parent=self.control_area)
        self.dialysate_pump_toggle.toggled.connect(            
            lambda chk: self._handle_dual_pump_toggle("dialyserPumpStartButton", "dialyserPumpStopButton", chk, timer_id="dialysate_pump")
        )
        grid.addWidget(self.dialysate_pump_toggle, 4, 6, 1, 1)

        # 22. Salida dializante (Der)
   
        self.dialysate_output_display = LabeledParameterWidget(
            label_text="Salida", tag="dialyFlowControlOutput",
            value="", units="%", is_editable=True, parent=self.control_area
        )
        self.dialysate_output_display.request_numpad.connect(self.open_numpad)
        grid.addWidget(self.dialysate_output_display, 4, 7, 1, 2)

        # 23. Tiempo op. b dializante (Der)

        self.dialysate_time_display = LabeledTimeInput(
            label_text="T. Terapia:", initial_hh_mm="00:00",
            tag_hours=None, tag_minutes=None,
            local_timer_id="dialysate_pump", numpad_title="tiempo de Operación",
            is_editable=True,
            parent=self.control_area
        )
        self.dialysate_time_display.request_time_numpad.connect(self.open_time_numpad)
        grid.addWidget(self.dialysate_time_display, 4, 9, 1, 2)

        # 24. Tiempo rest dializante (Der)
        self.lbl_remaining_pd = LabeledTimeInput(
            label_text="Rest:",
            initial_hh_mm="00:00",
            is_editable=False,
            parent=self.control_area,
        )
        grid.addWidget(self.lbl_remaining_pd, 4, 11, 1, 2)

        self.local_timer_states["dialysate_pump"]["remaining_lbl"] = self.lbl_remaining_pd.time_display
        


        # ==============================================================================
        # --- FILA 5: Ciclos(25, 26) | B. Purga (27, 28) ---
        # ==============================================================================

        # 25. Set Ciclos CB (Izq)
        self.balance_cycles_set_input = LabeledParameterWidget(
            label_text="Ciclos CB", tag="balanceChamberCycleSet",
            value="",numpad_title="No. Ciclos CB",is_editable=True,
            parent=self.control_area
        )
        self.balance_cycles_set_input.request_numpad.connect(self.open_numpad)
        grid.addWidget(self.balance_cycles_set_input, 5, 0, 1, 2)

        # 26. Ciclos actuales (Izq)
        self.balance_cycles_actual_label = LabeledParameterWidget(
            label_text="Ciclos Act.", tag="balanceChamberCycleCount",
            value="", units="",is_editable=False, parent=self.control_area
        )
        grid.addWidget(self.balance_cycles_actual_label, 5, 2, 1, 2)

        # 27. Bomba Purga (Der)
        lbl_purga = QLabel("B. Purga", self.control_area)
        lbl_purga.setStyleSheet(label_style)
        grid.addWidget(lbl_purga, 5, 5, 1, 1)

        self.purge_pump_toggle = ToggleSwitch(width=70, height=35, parent=self.control_area)
        self.purge_pump_toggle.toggled.connect(            
            lambda chk: self._handle_dual_pump_toggle("dialyPurgePumpStartButt", "dialyPurgePumpStopButt", chk, timer_id=None)
        )
        grid.addWidget(self.purge_pump_toggle, 5, 6, 1, 1)

        # 28. Salida purga % (Der)
        self.purge_output_display = LabeledParameterWidget(
            label_text="Salida", tag="dialyDeaerControlOutput",
            value="", units="%", is_editable=True, parent=self.control_area
        )
        self.purge_output_display.request_numpad.connect(self.open_numpad)
        grid.addWidget(self.purge_output_display, 5, 7, 1, 2)

        # ==============================================================================
        # --- FILA 6: Tiempos CB (29, 30) | B. UF (31-34) ---
        # ==============================================================================

        # 29. Tiempo Op CB (Izq)
        self.balance_chamber_time_input = LabeledTimeInput(
            label_text="T. Operacion CB",
            initial_hh_mm="00:00", tag_hours=None, tag_minutes=None,
            local_timer_id="balance_chamber",numpad_title="Tiempo de operación CB",
            is_editable=True,
            parent=self.control_area
        )
        self.balance_chamber_time_input.request_time_numpad.connect(self.open_time_numpad)
        grid.addWidget(self.balance_chamber_time_input, 6, 0, 1, 2)

        # 30. Tiempo Rest CB (Izq)
        self.lbl_remaining_cb = LabeledTimeInput(
            label_text="Rest:",
            initial_hh_mm="00:00",
            is_editable=False,
            parent=self.control_area,
        )
        grid.addWidget(self.lbl_remaining_cb, 6, 2, 1, 2)
        self.local_timer_states["balance_chamber"]["remaining_lbl"] = self.lbl_remaining_cb.time_display
        

        # 31. Bomba UF (Der)
        lbl_ultrafiltado = QLabel("B. UF", self.control_area)
        lbl_ultrafiltado.setStyleSheet(label_style)
        grid.addWidget(lbl_ultrafiltado, 6, 5, 1, 1)
        
        self.uf_pump_toggle = ToggleSwitch(width=70, height=35, parent=self.control_area)
        self.uf_pump_toggle.toggled.connect(
            lambda chk: self._handle_dual_pump_toggle("dialyUltraFPumpStartButt", "dialyUltraFPumpStoptButt", chk, timer_id="uf_pump")
        )
        grid.addWidget(self.uf_pump_toggle, 6, 6, 1, 1)

        # 32. Salida UF (Der)        
        self.lbl_input_indUF = LabeledParameterWidget(
            label_text="Flujo", tag="ultraFilterPumpSpeed",
            value="", units="L/h",
            numpad_title="Flujo UF",is_editable=True,
            parent=self.control_area
        )
        self.lbl_input_indUF.request_numpad.connect(lambda tag, wid, tit: self._handle_uf_flow_input())
        grid.addWidget(self.lbl_input_indUF, 6, 7, 1, 2)

        # 33. Tiempo Op B UF (Der) 
        self.uf_time_display = LabeledTimeInput(
            label_text="T. Operación:",initial_hh_mm="00:00",
            tag_hours=None, tag_minutes=None,
            local_timer_id="uf_pump", numpad_title="T. Operación B. UF",
            is_editable=True, parent=self.control_area
        )
        self.uf_time_display.request_time_numpad.connect(self.open_time_numpad)
        grid.addWidget(self.uf_time_display, 6, 9, 1, 2)

        # 34. Tiempo Rest B UF (Der)
        self.lbl_remaining_puf = LabeledTimeInput(
            label_text="Rest:", initial_hh_mm="00:00",
            tag_hours=None, tag_minutes= None,
            local_timer_id="uf_pump", is_editable=False,
            parent=self.control_area
        )
        grid.addWidget(self.lbl_remaining_puf, 6, 11, 1, 2)

        self.local_timer_states["uf_pump"]["remaining_lbl"] = self.lbl_remaining_puf.time_display
        


        # ==============================================================================
        # SEPARADOR HORIZONTAL
        # ==============================================================================
        linea2 = QFrame(); linea2.setFrameShape(QFrame.HLine); linea2.setStyleSheet("color: #ccc;")
        grid.addWidget(linea2, 7, 0, 1, 13)


        # ==============================================================================
        # --- FILA 8: B. Na+ (35, 36) | B. Acido Citrico (39, 40) ---
        # ==============================================================================
        
        # 35. Toggle NA (Izq)
        lbl_bicarbonate = QLabel("B. Na+", self.control_area)
        lbl_bicarbonate.setStyleSheet(label_style)
        grid.addWidget(lbl_bicarbonate, 8, 0, 1, 1)

        self.bicarbonate_pump_toggle = ToggleSwitch(width=70, height=35, parent=self.control_area)
        self.bicarbonate_pump_toggle.toggled.connect(
            lambda chk: self._handle_dual_pump_toggle("dialyBicarbonPumpStartButt", "dialyBicarbonPumpStopButt", chk, timer_id=None)
        )
        grid.addWidget(self.bicarbonate_pump_toggle, 8, 1, 1, 1)

        # 36. Salida NA (Izq)
        self.bicarbonate_output_display = LabeledParameterWidget(
            label_text="Salida Na+", tag="dialyCondControlOutput",
            value="", units="%", is_editable=True, parent=self.control_area
        )
        self.bicarbonate_output_display.request_numpad.connect(self.open_numpad)
        grid.addWidget(self.bicarbonate_output_display, 8, 2, 1, 2)

        # 39. Toggle Acido Citrico (Der)
        lbl_acidocitrico = QLabel("B. A. Citrico", self.control_area)
        lbl_acidocitrico.setStyleSheet(label_style)
        grid.addWidget(lbl_acidocitrico, 8, 5, 1, 1)

        self.citric_acid_pump_toggle = ToggleSwitch(width=70, height=35, parent=self.control_area)
        self.citric_acid_pump_toggle.toggled.connect(
            lambda chk: self._handle_dual_pump_toggle("dialyCitricAcPumpStartButt", "dialyCitricAcPumpStopButt", chk, timer_id=None)
        )
        grid.addWidget(self.citric_acid_pump_toggle, 8, 6, 1, 1)

        # 40. Salida Acido Citrico (Der)
        self.citric_acid_output_display = LabeledParameterWidget(
            label_text=" B.A.C. Salida", tag="dialyCondControlOutput",
            value="", units="%", is_editable=True, parent=self.control_area
        )
        self.citric_acid_output_display.request_numpad.connect(self.open_numpad)
        grid.addWidget(self.citric_acid_output_display, 8, 7, 1, 2)

        # 41 boton de configuraciones de prueba
        self.test_parameter_configuration = QPushButton("Parámetros de prueba")
        self.test_parameter_configuration.setFixedSize(200, 60)
        self.test_parameter_configuration.setStyleSheet("""
            QPushButton { background: #3b82f6; color: white; font-size: 18px; font-weight: bold; border-radius: 10px; }
            QPushButton:hover { background: #60a5fa; }
        """)
        self.test_parameter_configuration.clicked.connect(self._open_group_pumps_dialog)
        grid.addWidget(self.test_parameter_configuration, 8, 9, 1, 3)


        grid.setColumnMinimumWidth(3, 70)
        grid.setColumnMinimumWidth(12, 110)

        

        # --- VALVULAS ---
        self.valves_container = QWidget()
        valves_layout = QHBoxLayout(self.valves_container)
        valves_layout.setContentsMargins(0, 0, 0, 0)
        valves_layout.setSpacing(5)

        self.mode_frame = QFrame()
        self.mode_frame.setFixedSize(100, 180)
        self.mode_frame.setStyleSheet("background-color: #0f172a; border-radius:8px; border: 2px solid #334155;")
        mode_layout = QVBoxLayout(self.mode_frame)

        self.mode_label = QLabel("Modo de<br>Op.")
        self.mode_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 18px;")
        self.mode_label.setAlignment(Qt.AlignCenter)

        self.operation_mode_toggle = ToggleSwitch(width=70, height=30, active_color="#facc15", parent=self.mode_frame)
        self.operation_mode_toggle.toggled.connect(
            lambda checked: self.on_user_boolean_command("dialyCircuitElementsOpSel", checked)
        )

        mode_layout.addStretch()
        mode_layout.addWidget(self.mode_label)
        mode_layout.addSpacing(10)
        mode_layout.addWidget(self.operation_mode_toggle, 0, Qt.AlignCenter)
        mode_layout.addStretch()

        valves_layout.addWidget(self.mode_frame)

        valves_grid_widget = QWidget()
        valves_grid = QGridLayout(valves_grid_widget)
        valves_grid.setContentsMargins(0, 0, 0, 0)
        valves_grid.setSpacing(10)

        valve_info = [
            (0, 0, "SV_24", "E. Filtro UF", "dialyInputFilterCutButt"),
            (0, 1, "SV_25", "S. Filtro UF", "dialyOutputFilterCutButt"),
            (1, 0, "SV_26", "Bypass UF",    "dialyBypassFilterButt"),
            (1, 1, "SV_27", "E. Agua",      "dialyWaterInletValveButt"),
            (2, 0, "SV_39", "Recirculación","dialyRecirculatValveButt"),
            (2, 1, "SV_43", "Venteo CS Aire","dialyAirVentSepChambButt"),
            (3, 0, "SV_50", "C. Caliente",  "dialyHotChambValveButt"),
            (3, 1, "SV_30", "Drenaje",      "dialyWaterDrainValveButt"),
        ]
        self.valve_cards = {}

        for r, c, code, desc, tag in valve_info:
            card = ValveCard(code, desc, parent=valves_grid_widget)
            self.valve_cards[tag] = card
            valves_grid.addWidget(card, r, c)
            card.toggle.toggled.connect(lambda checked, t=tag: self.on_user_boolean_command(t, checked))
        valves_layout.addWidget(valves_grid_widget)
        
        #======================================================================================
        #                           --- LEDS ---
        #======================================================================================
        self.indicators_area = QWidget()
        self.indicators_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.indicators_area.setStyleSheet("background: #fcfcfc;")
        led_grid = QGridLayout(self.indicators_area)
        led_grid.setSpacing(10)
        led_grid.setContentsMargins(10, 10, 10, 10)

        led_info = [
            (0, 0, 0, 1,"B. Sangre",     "bloodPumpStartButton"),
            (1, 0, 1, 1,"B. Dialante", "dialyserPumpStartButton"),
            (2, 0, 2, 1,"B.Heparina.",   "heparinePumpsStartButton"),
            (3, 0, 3, 1,"B. UF",     "dialyUltraFPumpStartButt"),
            (4, 0, 4, 1,"Purga de aire", "dialyPurgePumpStartButt"),
            (5, 0, 5, 1,"C.Balance",     "dialiserBalChambStrButt"),
            (0, 2, 0, 3,"Aire en sangre",     "airBubbleInBloodDetected"),
            (1, 2, 1, 3,"C.Deaereación", "dialyDeaerChamLevSwitch"),
            (2, 2, 2, 3,"Fin de ciclos", "dialyBalanceChambCycleEnd"),
            (3, 2, 3, 3,"Protec. R.","watterTankHeaterProtect"),
            (4, 2, 4, 3,"Sangre en Dial.",  "bloodInDialyCircDetected"),
            (5, 2, 5, 3,"Nivel Tanque","dialyTankHiLevelSwitch"),        ]

        self.led_indicators = []
        self.led_labels = []
        for rowl,coll, rled,cled, name, tag in led_info:
            lbl = QLabel(name)
            lbl.setStyleSheet("color: #000000; font-size: 18px; font-weight: bold;") 
            lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            led_grid.addWidget(lbl, rowl, coll)
            self.led_labels.append(lbl)

            led = LED(self.indicators_area)
            led.setFixedSize(45, 45)
            led_grid.addWidget(led, rled, cled, alignment=Qt.AlignLeft | Qt.AlignVCenter)
            self.led_indicators.append((led, tag))

        layout.addWidget(self.control_area, 0, 0, 2, 2) 
        layout.addWidget(self.valves_container, 0, 2, 1, 1) 
        layout.addWidget(self.indicators_area, 1, 2, 1, 1)

        layout.setColumnStretch(0, 4)
        layout.setColumnStretch(1, 4)
        layout.setColumnStretch(2, 3)
        layout.setRowStretch(0, 1)
        layout.setRowStretch(1, 1)

    # ────────────────────────────────────────────────
    # Métodos Lógicos
    # ────────────────────────────────────────────────



    def _open_group_pumps_dialog(self):
        """Abre el popup estilizado para seleccionar bombas a agrupar."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Sincronización de Bombas")
        dialog.setFixedSize(650, 500) 
        
        # Estilo general del Dialog
        dialog.setStyleSheet("""
            QDialog { background-color: #f1f5f9; }
            QLabel { color: #334155; }
        """)

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(20)

        # ─── 1. Encabezado ───
        header_layout = QVBoxLayout()
        header_layout.setSpacing(5)
        
        title = QLabel("Agrupación de Bombas")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1e293b;")
        title.setAlignment(Qt.AlignCenter)
        
        subtitle = QLabel("Seleccione los elementos que se detendrán\nal finalizar el Tiempo de Terapia.")
        subtitle.setStyleSheet("font-size: 16px; color: #64748b;")
        subtitle.setAlignment(Qt.AlignCenter)
        
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        main_layout.addLayout(header_layout)

        # Separador visual
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #cbd5e1;")
        main_layout.addWidget(line)

        # ─── 2. Grid de Selección (Checkboxes estilo tarjeta) ───
        grid_layout = QGridLayout()
        grid_layout.setSpacing(15)
        
        self.checkboxes = {}
        pump_labels = [
            ("Cámara de Balance", "balance_chamber"),
            ("Bomba de Heparina", "heparin_pump"),
            ("Bomba de UF", "uf_pump"),
            ("Bomba de Purga", "purge_pump"),
            ("Bomba Dializante", "dialysate_pump"),
            ("Bomba de Sangre", "blood_pump"),
            ("Bomba de Na+", "bicarbonate_pump"),
            ("Bomba de Ácido", "citric_acid_pump"),
        ]

        # Estilo CSS avanzado para los checkboxes
        checkbox_style = """
            QCheckBox {
                spacing: 10px;
                font-size: 16px;
                font-weight: bold;
                color: #475569;
                background-color: #ffffff;
                border: 2px solid #e2e8f0;
                border-radius: 10px;
                padding: 15px;
            }
            QCheckBox::indicator {
                width: 24px;
                height: 24px;
                border-radius: 6px;
                border: 2px solid #94a3b8;
                background: white;
            }
            QCheckBox::indicator:checked {
                background-color: #3b82f6;
                border-color: #3b82f6;
                image: url(resources/icons/check.png); /* Si tienes icono, sino usa estilo por defecto */
            }
            /* Estado Hover */
            QCheckBox:hover {
                border-color: #3b82f6;
                background-color: #f8fafc;
            }
            /* Estado Checked (Cambia todo el fondo para feedback claro) */
            QCheckBox:checked {
                background-color: #eff6ff; /* Azul muy claro */
                border-color: #3b82f6;
                color: #1e3a8a;
            }
        """

        for i, (label_text, pump_id) in enumerate(pump_labels):
            checkbox = QCheckBox(label_text)
            checkbox.setCursor(Qt.PointingHandCursor)
            checkbox.setStyleSheet(checkbox_style)
            checkbox.setChecked(pump_id in self.grouped_pumps)
            
            # Añadir al grid (2 columnas)
            row = i // 2
            col = i % 2
            grid_layout.addWidget(checkbox, row, col)
            
            self.checkboxes[pump_id] = checkbox

        main_layout.addLayout(grid_layout)
        main_layout.addStretch() 

        # ─── 3. Botones de Acción ───
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedSize(180, 50)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #64748b;
                border: 2px solid #cbd5e1;
                font-size: 18px;
                font-weight: bold;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                color: #334155;
                border-color: #94a3b8;
            }
            QPushButton:pressed {
                background-color: #e2e8f0;
            }
        """)
        btn_cancel.clicked.connect(dialog.reject)

        btn_accept = QPushButton("Guardar Configuración")
        btn_accept.setCursor(Qt.PointingHandCursor)
        btn_accept.setFixedHeight(50) # Que ocupe el resto del ancho
        btn_accept.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_accept.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                font-size: 18px;
                font-weight: bold;
                border-radius: 12px;
            }
            QPushButton:hover { background-color: #2563eb; }
            QPushButton:pressed { background-color: #1d4ed8; }
        """)
        btn_accept.clicked.connect(lambda: self._apply_group_selection(dialog))

        buttons_layout.addWidget(btn_cancel)
        buttons_layout.addWidget(btn_accept)

        main_layout.addLayout(buttons_layout)

        dialog.exec()


    def _apply_group_selection(self, dialog):
        """Aplica la selección de checkboxes al set grouped_pumps."""
        self.grouped_pumps.clear()
        for pump_id, checkbox in self.checkboxes.items():
            if checkbox.isChecked():
                self.grouped_pumps.add(pump_id)
        logger.info(f"Bombas agrupadas bajo timer de terapia: {self.grouped_pumps}")
        dialog.accept()

    def _stop_heparin_pump_on_timeout(self):
        # Apagar la bomba de heparina (como antes)
        self._stop_pump_generic("heparin_pump", "heparinePumpsStopButton", "heparinePumpsStartButton", self.heparin_pump_toggle)

        # Apagar todas las bombas agrupadas
        for pump_id in self.grouped_pumps:
            if pump_id != "heparin_pump":  
                config = self.pump_configs.get(pump_id)
                if config:
                    self._stop_pump_generic(
                        config["timer_key"] or pump_id, 
                        config["stop_tag"],
                        config["start_tag"],
                        config["toggle"]()
                    )
        logger.info("Grupo de bombas apagado por timeout de terapia")

    def update_values(self, new_values: dict):
        self.current_values = new_values
        current_ms = QDateTime.currentMSecsSinceEpoch()

        for led, tag in self.led_indicators:
            value = self.current_values.get(tag, 0.0)
            if tag == "dialyDeaerChamLevSwitch":
                led.set_state("off" if value > 0 else "on")
            else:
                led.set_state("on" if value > 0 else "off")

        for tag, card in self.valve_cards.items():
            value = self.current_values.get(tag, 0.0)
            new_state = value > 0
            if card.toggle.is_checked() != new_state:
                card.toggle.blockSignals(True)
                card.toggle.setChecked(new_state)
                card.toggle.blockSignals(False)

     
        self._update_input_display(self.input_flow_cb, self.current_values.get("balanceChamberSetTiming", 0.0)) 
        self._update_input_display(self.lbl_input_indUF, self.current_values.get("ultraFilterPumpSpeed", 0.0))

    

        self._update_input_display(self.blood_flow_input, self.current_values.get("bloodFlowControlSetPoint", 0.0))
        self._update_input_display(self.input_heparin, self.current_values.get("heparineTherapyDosage", 0.0))
        self._update_input_display(self.input_bolus, self.current_values.get("heparineBolusQuantity", 0.0))
        self._update_input_display(self.input_syringe_size, self.current_values.get("heparineSyrinjeScaleSize", 0.0))
        self._update_input_display(self.dialysate_output_display, self.current_values.get("dialyFlowControlOutput", 0.0))
        self._update_input_display(self.purge_output_display, self.current_values.get("dialyDeaerControlOutput", 0.0))
        self._update_input_display(self.balance_cycles_set_input, self.current_values.get("balanceChamberCycleSet", 0))
        self._update_label_display(self.balance_cycles_actual_label, self.current_values.get("balanceChamberCycleCount", 0))

        self._update_label_display(self.blood_speed_display, self.current_values.get("bloodSpeedVariableData", 0.0))
        self._update_label_display(self.bicarbonate_output_display, self.current_values.get("dialyCondControlOutput", 0.0))
        self._update_label_display(self.citric_acid_output_display, self.current_values.get("dialyCondControlOutput", 0.0))
        self._update_label_display(self.heparin_current_dosage_display, self.current_values.get("heparineCurrentDosage", 0.0))

        self._update_time_display(self.blood_pump_time_input, None, None, "blood_pump")
        self._update_time_display(self.heparin_time_input, "heparineTherapyHours", "heparineTherapyMinutes", "heparin_pump")
        self._update_time_display(self.dialysate_time_display, None, None, "dialysate_pump")
        self._update_time_display(self.uf_time_display, None, None, "uf_pump")
        self._update_time_display(self.balance_chamber_time_input, None, None, "balance_chamber")

        self._sync_toggle(self.blood_pump_toggle, self.current_values.get("bloodPumpStartButton", 0.0))
        self._sync_toggle(self.heparin_pump_toggle, self.current_values.get("heparinePumpsStartButton", 0.0))
        self._sync_toggle(self.dialysate_pump_toggle, self.current_values.get("dialyserPumpStartButton", 0.0))
        self._sync_toggle(self.citric_acid_pump_toggle, self.current_values.get("dialyCitricAcPumpStartButt", 0.0))
        self._sync_toggle(self.bicarbonate_pump_toggle, self.current_values.get("dialyBicarbonPumpStartButt", 0.0))
        self._sync_toggle(self.purge_pump_toggle, self.current_values.get("dialyPurgePumpStartButt", 0.0))
        self._sync_toggle(self.uf_pump_toggle, self.current_values.get("dialyUltraFPumpStartButt", 0.0))
        self._sync_toggle(self.operation_mode_toggle, self.current_values.get("dialyCircuitElementsOpSel", 0.0))
        self._sync_toggle(self.balance_chamber_toggle, self.current_values.get("dialiserBalChambStrButt", 0.0))

        logger.debug("Manual mode values updated from machine")

    # verificcar cual es la buena
    # def _sync_toggle(self, toggle_widget, value: float):
    #     new_state = value > 0
    #     if toggle_widget.is_checked() != new_state:
    #         toggle_widget.blockSignals(True)
    #         toggle_widget.setChecked(new_state)
    #         toggle_widget.blockSignals(False)

    def _sync_toggle(self, toggle_widget, value: float):
        """Sincroniza el toggle solo si NO está en hold-off"""    
    
        tag = self._get_start_tag_for_toggle(toggle_widget)
        if not tag:
            return  

        current_ms = QDateTime.currentMSecsSinceEpoch()
    
        # Si hay hold-off activo → ignoramos la sincronización 
        if tag in self.toggle_hold_off and current_ms < self.toggle_hold_off[tag]:
            logger.debug(f"Hold-off activo para {tag} → ignorando sync")
            return

        new_state = value > 0
        if toggle_widget.is_checked() != new_state:
            toggle_widget.blockSignals(True)
            toggle_widget.setChecked(new_state)
            toggle_widget.blockSignals(False)
            logger.debug(f"Toggle {tag} sincronizado a {new_state}")

    def _get_start_tag_for_toggle(self, toggle_widget):
        """Devuelve el tag que indica ON para este toggle"""
        toggle_map = {
            self.blood_pump_toggle:       "bloodPumpStartButton",
            self.heparin_pump_toggle:     "heparinePumpsStartButton",
            self.dialysate_pump_toggle:   "dialyserPumpStartButton",
            self.uf_pump_toggle:          "dialyUltraFPumpStartButt",
            self.balance_chamber_toggle:  "dialiserBalChambStrButt",
            self.purge_pump_toggle:       "dialyPurgePumpStartButt",
            self.bicarbonate_pump_toggle: "dialyBicarbonPumpStartButt",
            self.citric_acid_pump_toggle: "dialyCitricAcPumpStartButt",
            self.operation_mode_toggle:   "dialyCircuitElementsOpSel",
            # si hubiera mas, se agregan aqui 
        }
        return toggle_map.get(toggle_widget)

   

    def _update_time_display(self, time_widget, tag_hours: str, tag_minutes: str, timer_id: str):
        if not tag_hours and not tag_minutes:
            return
        
        # Verificacion de que sea correcto 
        if not isinstance(time_widget, LabeledTimeInput) and not hasattr(time_widget, 'text'):
            logger.error(f"Error: time_widget no es un widget válido en _update_time_display para {timer_id}. Tipo: {type(time_widget)}")
            return 
        
        current_ms = QDateTime.currentMSecsSinceEpoch()       
        
        if time_widget.hasFocus() or time_widget.underMouse():
            return
        
        # Hold-off después de escritura
        hold_hours   = self.write_hold_off.get(tag_hours,   0) if tag_hours   else 0
        hold_minutes = self.write_hold_off.get(tag_minutes, 0) if tag_minutes else 0
        
        if current_ms < max(hold_hours, hold_minutes):
            return
        
        # Obtener valor real del serial
        hours   = int(self.current_values.get(tag_hours,   0)) if tag_hours   else 0
        minutes = int(self.current_values.get(tag_minutes, 0)) if tag_minutes else 0
        new_hh_mm = f"{hours:02d}:{minutes:02d}"
        
        current_display = ""
        if hasattr(time_widget, 'get_time_value'):
            current_display = time_widget.get_time_value()
        elif hasattr(time_widget, 'text'):
            current_display = time_widget.text()
        
        if current_display != new_hh_mm:
            if isinstance(time_widget, LabeledTimeInput):
                time_widget.set_time_value(hours, minutes)
            elif hasattr(time_widget, 'setText'):
                time_widget.setText(new_hh_mm)
            logger.debug(f"Actualizado T. Terapia a {new_hh_mm} desde serial")
        
        if timer_id and timer_id in self.local_timer_states:
            state = self.local_timer_states[timer_id]
            if not state["active"]:
                total_ms = (hours * 3600 + minutes * 60) * 1000
                if state["duration_ms"] != total_ms: 
                    state["duration_ms"] = total_ms
                    if state["remaining_lbl"]:
                        state["remaining_lbl"].setText(new_hh_mm)
                    logger.debug(f"Actualizada duración local de {timer_id} a {total_ms} ms")



    def _update_input_display(self, widget, value, precision=1):
        if not widget.hasFocus():
            if isinstance(widget, LabeledParameterWidget):
                widget.set_value(value)
            elif hasattr(widget, 'setText'):
                widget.setText(f"{value:.{precision}f}")

    def _update_label_display(self, label, value, precision=1):
        if isinstance(label, LabeledParameterWidget):
            label.set_value(value)
        elif hasattr(label, 'setText'):
            label.setText(f"{value:.{precision}f}")


        #dialiserBalChambStrButt", "dialiserBalChambStpButt"
    def _handle_dual_pump_toggle(self, start_tag: str, stop_tag: str, enabled: bool, timer_id: str = None):
        """Handle dual start/stop pump control (REQ-SW-005)."""
        if enabled:
            logger.info(f"Starting pump: {start_tag}")
            self.on_user_boolean_command(start_tag, True)
            # self.on_user_boolean_command(stop_tag, False)
            self.toggle_hold_off[start_tag] = QDateTime.currentMSecsSinceEpoch() + 3000
            if timer_id and timer_id in self.local_timer_states:
                state = self.local_timer_states[timer_id]
                total_ms = state["duration_ms"]
                if total_ms > 0:
                    state["active"] = True
                    state["start_ms"] = QDateTime.currentMSecsSinceEpoch()
                    timer = getattr(self, f"{timer_id}_timer", None)
                    if timer: timer.start(total_ms)
                    logger.info(f"Timer '{timer_id}' started for {total_ms} ms")
        else:
            logger.info(f"Stopping pump: {start_tag}")
            self.on_user_boolean_command(stop_tag, True)
            # self.on_user_boolean_command(start_tag, False)
            self.toggle_hold_off[start_tag] = QDateTime.currentMSecsSinceEpoch() + 3000
            if timer_id and timer_id in self.local_timer_states:
                state = self.local_timer_states[timer_id]
                if state["active"]:
                    state["active"] = False
                    timer = getattr(self, f"{timer_id}_timer", None)
                    if timer and timer.isActive():
                        timer.stop()
                    if state["elapsed_lbl"]:
                        state["elapsed_lbl"].setText("00:00")
                    if state["remaining_lbl"]:
                        h = state["duration_ms"] // 3600000
                        m = (state["duration_ms"] % 3600000) // 60000
                        state["remaining_lbl"].setText(f"{h:02d}:{m:02d}")
                    logger.info(f"Timer '{timer_id}' stopped")

    def _toggle_heparin_pause_resume(self):
        """Alterna PAUSE/CONTINUAR para la bomba de heparina con comando latch."""
        self.heparin_pause_latched = not self.heparin_pause_latched
        self.on_user_boolean_command("heparineOperPauseResume", self.heparin_pause_latched)

        if hasattr(self, "btn_pause_hep") and self.btn_pause_hep is not None:
            self.btn_pause_hep.setText("CONT.." if self.heparin_pause_latched else "PAUSE")

        logger.info(
            f"Heparina pause/resume latch -> {self.heparin_pause_latched}"
        )


    def open_numpad(self, tag: str, input_widget, title: str = "Ingrese valor"):
        if isinstance(input_widget, LabeledParameterWidget):
            current_text = ""
        elif hasattr(input_widget, 'text'):
            current_text = ""

        else:
            current_text = ""

        dialog = NumpadDialog(self, initial_value=current_text, title=title)

        if dialog.exec():
            new_value = dialog.get_value()
            if new_value is not None:
                if isinstance(input_widget, LabeledParameterWidget):
                    input_widget.set_value(new_value)
                elif hasattr(input_widget, 'setText'):
                    input_widget.setText(str(new_value))                
                self.on_user_input_setpoint(tag, new_value)                
                self.write_hold_off[tag] = QDateTime.currentMSecsSinceEpoch() + 3000
                if hasattr(input_widget, 'clearFocus'):
                    input_widget.clearFocus()
                self.setFocus()



    def open_time_numpad(self, time_widget, tag_hours: str = None, tag_minutes: str = None,
                         timer_id: str = None, title: str = "Config. Tiempo"):
        if isinstance(time_widget, LabeledTimeInput):
            current_text = time_widget.get_time_value()
        elif hasattr(time_widget, 'text'):
            current_text = time_widget.text()
        else:
            current_text = "00:00"

        dialog = TimeNumpadDialog(self, initial_hh_mm="", title=title)
      
        if dialog.exec():
            hours, minutes = dialog.get_hours_minutes()
            if hours is not None and minutes is not None:
                if isinstance(time_widget, LabeledTimeInput):
                    time_widget.set_time_value(hours, minutes)
                elif hasattr(time_widget, 'setText'):
                    time_widget.setText(f"{hours:02d}:{minutes:02d}")

                total_ms = (hours * 3600 + minutes * 60) * 1000
                current_ms = QDateTime.currentMSecsSinceEpoch()
                hold_duration = 3000

                if tag_hours and tag_minutes:
                    self.on_user_input_setpoint(tag_hours, float(hours))
                    self.write_hold_off[tag_hours] = current_ms + hold_duration
                    self.on_user_input_setpoint(tag_minutes, float(minutes))
                    self.write_hold_off[tag_minutes] = current_ms + hold_duration

                if timer_id and timer_id in self.local_timer_states:
                    state = self.local_timer_states[timer_id]
                    state["duration_ms"] = total_ms
                    if state["elapsed_lbl"]:
                        state["elapsed_lbl"].setText("00:00")
                    if state["remaining_lbl"]:
                        state["remaining_lbl"].setText(f"{hours:02d}:{minutes:02d}")

    def _stop_pump_generic(self, timer_key: str, stop_tag: str, start_tag: str, toggle_widget):
        logger.warning(f"Timeout: {timer_key} - Automatic pump stop")
        timer = getattr(self, f"{timer_key}_timer")
        if timer:
            timer.stop()

        self.local_timer_states[timer_key]["active"] = False
        self.on_user_boolean_command(stop_tag, True)
        self.on_user_boolean_command(start_tag, False)

        toggle_widget.blockSignals(True)
        toggle_widget.setChecked(False)
        toggle_widget.blockSignals(False)

        state = self.local_timer_states[timer_key]
        if state["elapsed_lbl"]:
            state["elapsed_lbl"].setText("00:00")
        if state["remaining_lbl"]:
            h = state["duration_ms"] // 3600000
            m = (state["duration_ms"] % 3600000) // 60000
            state["remaining_lbl"].setText(f"{h:02d}:{m:02d}")

    def _stop_blood_pump_on_timeout(self):
        self._stop_pump_generic("blood_pump", "bloodPumpStopButton", "bloodPumpStartButton", self.blood_pump_toggle)

    def _stop_dialysate_pump_on_timeout(self):
        self._stop_pump_generic("dialysate_pump", "dialyserPumpStopButton", "dialyserPumpStartButton", self.dialysate_pump_toggle)

    def _stop_uf_pump_on_timeout(self):
        self._stop_pump_generic("uf_pump", "dialyUltraFPumpStoptButt", "dialyUltraFPumpStartButt", self.uf_pump_toggle)

    def _stop_heparin_pump_on_timeout(self):
        self._stop_pump_generic("heparin_pump", "heparinePumpsStopButton", "heparinePumpsStartButton", self.heparin_pump_toggle)

    def _stop_balance_chamber_on_timeout(self):
        self._stop_pump_generic("balance_chamber", "dialiserBalChambStpButt", "dialiserBalChambStrButt", self.balance_chamber_toggle)

    def _update_local_time_displays(self):
        logger.debug("Actualizando displays de tiempo locales...")
        current_ms = QDateTime.currentMSecsSinceEpoch()
        expired = [k for k, v in self.toggle_hold_off.items() if current_ms >= v]
        for k in expired:
            del self.toggle_hold_off[k]

        for timer_id, state in self.local_timer_states.items():
            if state["active"] and state["duration_ms"] > 0 and state["start_ms"] > 0:
                elapsed_ms = current_ms - state["start_ms"]
                remaining_ms = max(0, state["duration_ms"] - elapsed_ms)

                
                if state["elapsed_lbl"]:
                    state["elapsed_lbl"].setText(self._format_ms_to_hh_mm(elapsed_ms))
                    
                if state["remaining_lbl"]:
                    state["remaining_lbl"].setText(self._format_ms_to_hh_mm(remaining_ms))
                    if remaining_ms < 30000:  # menos de 30 segundos → alerta
                        state["remaining_lbl"].setStyleSheet("color: #ef4444; font-weight: bold;")
                    else:
                        state["remaining_lbl"].setStyleSheet("color: #000000;")

                # Si se acabó el tiempo → detener todo
                if remaining_ms <= 0:
                    # Forzar parada (por si el timer falló por algún motivo)
                    self._stop_pump_generic(
                        timer_id,
                        f"{timer_id.replace('_', '')}StopButton",  
                        f"{timer_id.replace('_', '')}StartButton",
                        getattr(self, f"{timer_id}_toggle", None)
                    )   

            else:
                # Estado inactivo
                if state["elapsed_lbl"]:
                    state["elapsed_lbl"].setText("00:00")
                if state["remaining_lbl"]:
                    state["remaining_lbl"].setText(self._format_ms_to_hh_mm(state["duration_ms"]))


    
    def _format_ms_to_label(self, label_widget, ms):
        total_seconds = max(0, int(ms//1000))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        label_widget.setText(f"{hours:02d}:{minutes:02d}")

    def _format_ms_to_hh_mm(self, ms: int) -> str:
        total_seconds = max(0, ms // 1000)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"

    def _handle_cb_flow_input(self):
        """Handle balance chamber flow input (ml/min → cycles)."""        
        try:
            current_text = ""            
        except AttributeError:
            current_text = "0.0"

        dialog = NumpadDialog(self, initial_value=current_text, title="Flujo CB (ml/min)")
        if dialog.exec():
            new_value = dialog.get_value()
            if hasattr(self.input_flow_cb, 'setText'):
                self.input_flow_cb.setText(str(new_value))
            
            try:
                cycles = convertir_flujo_a_ciclos(float(new_value))
                self.on_user_input_setpoint("balanceChamberSetTiming", cycles)
                self.write_hold_off["balanceChamberSetTiming"] = QDateTime.currentMSecsSinceEpoch() + 3000
            except Exception as e:
                logger.error(f"Error converting CB flow: {e}")

    def _handle_uf_flow_input(self):
        """Handle UF flow input (L/h → ml/min)."""
        
        try:            
            current_text = ""
        except AttributeError:
            current_text = "0.0"
            
        dialog = NumpadDialog(self, initial_value=current_text, title="Flujo UF (L/h)")
        if dialog.exec():
            new_value = dialog.get_value()
            if hasattr(self.lbl_input_indUF, 'setText'):
                self.lbl_input_indUF.setText(str(new_value))

            try:
                ml_min = convertir_litros_h_a_ml_min(new_value)
                self.on_user_input_setpoint("ultraFilterPumpSpeed", ml_min)
                self.write_hold_off["ultraFilterPumpSpeed"] = QDateTime.currentMSecsSinceEpoch() + 3000
            except Exception as e:
                logger.error(f"Error converting UF flow: {e}")

    def on_user_boolean_command(self, tag, state):
        self.request_boolean_change.emit(tag, state)

    def on_user_input_setpoint(self, tag, value):
        self.request_setpoint_change.emit(tag, value)
    
    def hideEvent(self, event):
        super().hideEvent(event)
        if self.local_timer_states:
            for timer_id, state in self.local_timer_states.items():
                if state["active"]:
                    timer = getattr(self, f"{timer_id}_timer", None)
                    if timer and timer.isActive():
                        timer.stop()
                    state["active"] = False
                    logger.info(f"Timer '{timer_id}' stopped due to screen hide")

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()

    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        is_mono = bool(tokens.get("monochrome", False))
        is_dark = bool(tokens.get("is_dark", False))

        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(tokens.get("bg_main", "#F3F4F6")))
        self.setPalette(palette)
        self.setStyleSheet(f"background-color: {tokens.get('bg_main', '#F3F4F6')};")

        if is_mono:
            card_style = """
                background-color: #FFFFFF;
                border-radius: 8px;
                border: 1px solid #D1D5DB;
            """
            mode_frame_style = """
                background-color: #FFFFFF;
                border-radius: 8px;
                border: 1px solid #D1D5DB;
            """
            mode_lbl_style = "color: #111827; font-weight: bold; font-size: 18px; border: none; background: transparent;"
            lbl_color = "color: #374151; font-size: 18px; font-weight: bold; border: none; background: transparent;"
            btn_style = """
                QPushButton {
                    background: #D9E0E8;
                    color: #374151;
                    border: 2px solid #C5CDD6;
                    border-radius: 20px;
                    font-weight: bold;
                    font-size: 18px;
                }
                QPushButton:hover { background: #C5CED6; }
                QPushButton:pressed { background: #B0B8C4; }
            """
            test_btn_style = """
                QPushButton {
                    background: #D9E0E8;
                    color: #374151;
                    border: 2px solid #C5CDD6;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 18px;
                }
                QPushButton:hover { background: #C5CED6; }
                QPushButton:pressed { background: #B0B8C4; }
            """
        elif is_dark:
            card_style = f"""
                background-color: {tokens.get('bg_card', '#1E293B')};
                border-radius: 8px;
                border: 1px solid {tokens.get('border_card', '#334155')};
            """
            mode_frame_style = f"""
                background-color: {tokens.get('bg_card', '#1E293B')};
                border-radius: 8px;
                border: 1px solid {tokens.get('border_card', '#334155')};
            """
            mode_lbl_style = f"color: {tokens.get('text_primary', '#F8FAFC')}; font-weight: bold; font-size: 18px; border: none; background: transparent;"
            lbl_color = f"color: {tokens.get('text_primary', '#F8FAFC')}; font-size: 18px; font-weight: bold; border: none; background: transparent;"
            btn_style = f"""
                QPushButton {{
                    background: {tokens.get('primary', '#38BDF8')};
                    color: #ffffff;
                    border-radius: 20px;
                    font-weight: bold;
                    font-size: 18px;
                }}
                QPushButton:hover {{ background: {tokens.get('primary_hover', '#0284C7')}; }}
            """
            test_btn_style = f"""
                QPushButton {{
                    background: {tokens.get('primary', '#38BDF8')};
                    color: #ffffff;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 18px;
                }}
                QPushButton:hover {{ background: {tokens.get('primary_hover', '#0284C7')}; }}
            """
        else:
            card_style = "background: #fcfcfc; border: None;"
            mode_frame_style = "background-color: #0f172a; border-radius: 8px; border: 2px solid #334155;"
            mode_lbl_style = "color: #ffffff; font-weight: bold; font-size: 18px; border: none; background: transparent;"
            lbl_color = "color: #000000; font-size: 18px; font-weight: bold; border: none; background: transparent;"
            btn_style = """
                QPushButton { background: #3b82f6; color: #ffffff; border-radius: 20px; font-weight: bold; }
                QPushButton:pressed { background: #1e40af; }
                QPushButton:hover { background: #60a5fa; }
            """
            test_btn_style = """
                QPushButton { background: #3b82f6; color: white; font-size: 18px; font-weight: bold; border-radius: 8px; }
                QPushButton:hover { background: #60a5fa; }
            """

        if hasattr(self, "control_area"):
            self.control_area.setStyleSheet(card_style)
        if hasattr(self, "indicators_area"):
            self.indicators_area.setStyleSheet(card_style)
        if hasattr(self, "mode_frame"):
            self.mode_frame.setStyleSheet(mode_frame_style)
        if hasattr(self, "mode_label"):
            self.mode_label.setStyleSheet(mode_lbl_style)

        # Style all push buttons in control area
        if hasattr(self, "control_area"):
            for btn in self.control_area.findChildren(QPushButton):
                if hasattr(self, "test_parameter_configuration") and btn is self.test_parameter_configuration:
                    btn.setStyleSheet(test_btn_style)
                else:
                    btn.setStyleSheet(btn_style)

        # Style all labels in control area
        if hasattr(self, "control_area"):
            for lbl in self.control_area.findChildren(QLabel):
                # Don't overwrite LabeledParameterWidget internals if any
                if lbl.parent() is self.control_area:
                    lbl.setStyleSheet(lbl_color)

        # Style LED labels
        for lbl in getattr(self, "led_labels", []):
            lbl.setStyleSheet(lbl_color)

        # Apply to valve cards
        for card in getattr(self, "valve_cards", {}).values():
            try:
                card.apply_theme_styles(theme_name)
            except Exception:
                pass

        # Apply to parameter widgets
        for wid in self.findChildren(LabeledParameterWidget):
            try:
                wid.apply_theme_styles(theme_name)
            except Exception:
                pass

