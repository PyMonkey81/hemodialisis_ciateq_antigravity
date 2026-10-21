# gui/therapy/therapy_config_screenV2.py
# Pantalla de configuración de parámetros de terapia (sin selección de modo)

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QGridLayout, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QDateTime, QEvent
from pyqtgraph import colors


from gui.components.numpad_modal import NumpadDialog
from gui.components.time_numpad_modal import TimeNumpadDialog
from gui.components.ui_components import ClickableLineEdit
from gui.theme_manager import ThemeManager
from logic.calculos import convertir_flujo_a_ciclos, convertir_litros_h_a_ml_min
from core.state_manager import TreatmentPhase

import logging
logger = logging.getLogger(__name__)

try:
    from core.variables_map import VARIABLES
except ImportError:
    VARIABLES = {0x01: {}, 0x02: {}}

class PushbuttonEvent(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.setFocusPolicy(Qt.NoFocus) 


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
    
class TherapyConfigScreen(QWidget):
    """
    Pantalla de configuración de parámetros numéricos para la terapia.
    Solo inputs de heparina, flujos, temperatura, conductividad, sodio y duración.
    """
    valueChanged = Signal(str, float)  # Emite el tag y el nuevo valor
    request_setpoint_change = Signal(str, float)
    request_boolean_change = Signal(str, bool)    


    def __init__(self, parent=None, values_dict=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_values = values_dict if values_dict is not None else {}         
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.setStyleSheet("background: #0f172a;")
        self.write_hold_off = {}
        self.toggle_hold_off = {}
        self.status_code = 0.0
        self._field_labels = []
        
        self.setup_ui()
        try:
            ThemeManager.instance().theme_changed.connect(self._on_theme_changed)
        except Exception:
            pass



    def setup_ui(self):
        # ==================== CARGA DE ESTILOS Y CONFIGURACIÓN ====================
        baseline = ThemeManager.get_therapy_config_baseline() or {}
        colors = baseline.get("colors", {})
        dims = baseline.get("dimensions", {})
        typo = baseline.get("typography", {})
        layout_cfg = baseline.get("layout", {})

        btn_w, btn_h = dims.get("pump_button", [120, 80])
        input_w, input_h = dims.get("input_field", [120, 50])

        label_font_size = typo.get("section_label", {}).get("size", 26)
        label_min_height = typo.get("section_label", {}).get("min_height", 50)
        self.input_font_size = typo.get("input", {}).get("size", 24)
        self.input_font_family = typo.get("input", {}).get("family", 'Consolas, "Courier New", monospace')
        self.button_font_size = typo.get("button", {}).get("size", 20)
        title_font_size = typo.get("title", {}).get("size", 42)

        self.style_enabled = """
            QPushButton {{ background: {enabled_bg}; color: {button_text}; font-weight: bold; font-size: {button_size}px; border-radius: 15px; border: 3px solid {button_border}; }}
            QPushButton:pressed {{ background: {pressed_bg}; }}
        """.format(
            enabled_bg=colors.get("button_enabled_bg", "#39ec21"),
            button_text=colors.get("button_text", "#ffffff"),
            button_size=self.button_font_size,
            button_border=colors.get("button_border", "#06298a"),
            pressed_bg=colors.get("button_pressed_bg", "#334155"),
        )

        self.style_disabled = """
            QPushButton {{ background: {disabled_bg}; color: {disabled_text}; font-weight: bold; font-size: {button_size}px; border-radius: 15px; border: 3px solid {button_border}; }}
        """.format(
            disabled_bg=colors.get("button_disabled_bg", "#334155"),
            disabled_text=colors.get("button_disabled_text", "#94a3b8"),
            button_size=self.button_font_size,
            button_border=colors.get("button_border", "#06298a"),
        )

        self.style_stop_enabled = """
             QPushButton {{ background: {stop_bg}; color: {button_text}; font-weight: bold; font-size: {button_size}px; border-radius: 15px; border: 3px solid {button_border}; }}
             QPushButton:pressed {{ background: {pressed_bg}; }}
        """.format(
            stop_bg=colors.get("button_stop_bg", "#DD2911"),
            button_text=colors.get("button_text", "#ffffff"),
            button_size=self.button_font_size,
            button_border=colors.get("button_border", "#06298a"),
            pressed_bg=colors.get("button_pressed_bg", "#334155"),
        )

        # ==================== LAYOUT PRINCIPAL ====================
        main_layout = QGridLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(18, 18, 18, 18)

        # ===================== CARD 1: Bomba de Sangre =====================
        blood_card = QFrame()
        blood_card.setObjectName("card")
        blood_layout = QVBoxLayout(blood_card)
        blood_layout.setContentsMargins(20, 20, 20, 20)
        blood_layout.setSpacing(18)

        title = QLabel("BOMBA DE SANGRE")
        title.setObjectName("card_title")
        blood_layout.addWidget(title)

        # Crear botones
        self.btn_start_blood_pump = PushbuttonEvent("START", self)
        self.btn_stop_blood_pump = PushbuttonEvent("STOP", self)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        self.btn_start_blood_pump.setFixedSize(btn_w, btn_h)
        self.btn_start_blood_pump.setStyleSheet(self.style_enabled)
        self.btn_start_blood_pump.pressed.connect(self._start_blood_pump)

        self.btn_stop_blood_pump.setFixedSize(btn_w, btn_h)
        self.btn_stop_blood_pump.setStyleSheet(self.style_stop_enabled)
        self.btn_stop_blood_pump.pressed.connect(self._stop_blood_pump)

        btn_layout.addWidget(self.btn_start_blood_pump)
        btn_layout.addWidget(self.btn_stop_blood_pump)
        blood_layout.addLayout(btn_layout)
        blood_layout.addStretch(1)

        main_layout.addWidget(blood_card, 0, 0)

        # ===================== CARD 2: Llenado de Filtro =====================
        filter_card = QFrame()
        filter_card.setObjectName("card")
        filter_layout = QVBoxLayout(filter_card)
        filter_layout.setContentsMargins(20, 20, 20, 20)
        filter_layout.setSpacing(18)

        title = QLabel("LLENADO DE FILTRO")
        title.setObjectName("card_title")
        filter_layout.addWidget(title)

        # Crear botón
        self.btn_filter_fill = PushbuttonEvent("START", self)

        btn_layout2 = QHBoxLayout()
        btn_layout2.setSpacing(15)

        self.btn_filter_fill.setFixedSize(btn_w, btn_h)
        self.btn_filter_fill.setStyleSheet(self.style_enabled)
        self.btn_filter_fill.pressed.connect(self._start_filter_fill)

        btn_layout2.addWidget(self.btn_filter_fill)
        filter_layout.addLayout(btn_layout2)
        filter_layout.addStretch(1)

        main_layout.addWidget(filter_card, 1, 0)

        # ===================== CARD GRANDE: PARÁMETROS =====================
        params_card = QFrame()
        params_card.setObjectName("card")
        params_layout = QVBoxLayout(params_card)
        params_layout.setContentsMargins(20, 20, 20, 20)
        params_layout.setSpacing(20)

        title = QLabel("PARÁMETROS DE TERAPIA")
        title.setObjectName("card_title")
        params_layout.addWidget(title)

        # Crear inputs (por si acaso no existen)
        self.input_blood_flow = ClickableLineEdit("0.0")
        self.input_dialysate_flow = ClickableLineEdit("0.0")
        self.lbl_input_UF = ClickableLineEdit("0.0")
        self.input_temperature = ClickableLineEdit("0.0")
        self.input_conductivity = ClickableLineEdit("0.0")
        self.input_duration = ClickableLineEdit("00:00")

        # Campos
        fields = [
            ("Flujo de Sangre (Qb, mL/min):", self.input_blood_flow, "bloodFlowControlSetPoint", "Flujo de Sangre (Qb)"),
            ("Flujo Dializante (Qd, mL/min):", self.input_dialysate_flow, None, None),
            ("Flujo UF (L/h):", self.lbl_input_UF, None, None),
            ("Temperatura (°C):", self.input_temperature, "dialyTempControlSetPoint", "Temperatura"),
            ("Conductividad (mS/cm):", self.input_conductivity, "dialyCondControlSetPoint", "Conductividad"),
            ("Tiempo de Terapia (hh:mm)", self.input_duration, None, None),
        ]

        for label_text, widget, tag, numpad_title in fields:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            self._field_labels.append(lbl)
            row.addWidget(lbl)

            # Conexiones
            if widget == self.input_blood_flow:
                widget.clicked.connect(lambda t=tag, w=widget, n=numpad_title: self.open_numpad(t, w, n))            
            elif widget == self.input_dialysate_flow:
                widget.clicked.connect(self._handle_cb_flow_input)
            elif widget == self.lbl_input_UF:
                widget.clicked.connect(self._handle_uf_flow_input)
            elif widget == self.input_temperature:
                widget.clicked.connect(lambda t=tag, w=widget, n=numpad_title: self.open_numpad(t, w, n))
            elif widget == self.input_conductivity:
                widget.clicked.connect(lambda t=tag, w=widget, n=numpad_title: self.open_numpad(t, w, n))
            elif widget == self.input_duration:
                widget.clicked.connect(
                    lambda w=widget: self.open_time_numpad(
                        w, "heparineTherapyHours", "heparineTherapyMinutes", "Tiempo de Terapia (hh:mm)"
                    )
                )

            widget.setFixedSize(130, 52)
            widget.setAlignment(Qt.AlignCenter)
            widget.setReadOnly(True)

            row.addWidget(widget)
            params_layout.addLayout(row)

            if widget == self.input_conductivity:
                profile_row = QHBoxLayout()
                profile_row.addStretch(1)
                self.btn_conductivity_profile = PushbuttonEvent("Perfil de Conductividad", self)
                self.btn_conductivity_profile.setFixedWidth(320)
                self.btn_conductivity_profile.pressed.connect(self._on_open_conductivity_profile)
                profile_row.addWidget(self.btn_conductivity_profile)
                params_layout.addLayout(profile_row)

            if widget == self.lbl_input_UF:
                uf_profile_row = QHBoxLayout()
                uf_profile_row.addStretch(1)
                self.btn_uf_profile = PushbuttonEvent("Perfil UF", self)
                self.btn_uf_profile.setFixedWidth(320)
                self.btn_uf_profile.pressed.connect(self._on_open_uf_profile)
                uf_profile_row.addWidget(self.btn_uf_profile)
                params_layout.addLayout(uf_profile_row)

        params_layout.addStretch(1)

        main_layout.addWidget(params_card, 0, 1, 2, 1)

        # Distribución
        main_layout.setColumnStretch(0, 1)
        main_layout.setColumnStretch(1, 1)
        main_layout.setRowStretch(0, 1)
        main_layout.setRowStretch(1, 1)

        self._apply_theme_styles()

    def _on_theme_changed(self, _theme_name: str):
        self._apply_theme_styles()

    def _apply_theme_styles(self):
        t = ThemeManager.get_tokens()
        bg_card = t.get("bg_card", "#ffffff")
        bg_input = t.get("bg_input", "#e2e8f0")
        text_primary = t.get("text_primary", "#0f172a")
        text_secondary = t.get("text_secondary", "#334155")
        border = t.get("border", "#cbd5e1")
        border_strong = t.get("border_strong", "#64748b")
        accent = t.get("accent", "#3b82f6")
        btn_bg = t.get("btn_primary_bg", "#0f172a")

        label_style = f"font-family: 'Segoe UI', Arial, sans-serif; font-size: 26px; color: {text_secondary}; font-weight: 600;"
        for lbl in self._field_labels:
            lbl.setStyleSheet(label_style)

        input_style = f"""
            ClickableLineEdit {{
                font-family: {self.input_font_family};
                font-size: {self.input_font_size}px;
                color: {text_primary};
                background: {bg_input};
                border: 2px solid {border_strong};
                border-radius: 8px;
                padding: 5px;
                min-width: 120px;
            }}
            ClickableLineEdit:focus {{
                border: 2px solid {accent};
                background: {bg_card};
            }}
        """
        for widget in [self.input_blood_flow, self.input_dialysate_flow,
                       self.lbl_input_UF, self.input_temperature, self.input_conductivity,
                       self.input_duration]:
            widget.setStyleSheet(input_style)

        self.profile_btn_style = f"""
            QPushButton {{
                background: {btn_bg};
                color: #ffffff;
                font-weight: bold;
                font-size: 20px;
                border-radius: 12px;
                border: 2px solid {accent};
                min-height: 48px;
                padding: 4px 12px;
            }}
            QPushButton:pressed {{
                background: {accent};
            }}
        """
        self.profile_btn_active_style = """
            QPushButton {
                background: #16a34a;
                color: #ffffff;
                font-weight: bold;
                font-size: 20px;
                border-radius: 12px;
                border: 2px solid #14532d;
                min-height: 48px;
                padding: 4px 12px;
            }
            QPushButton:pressed {
                background: #15803d;
            }
        """
        self._refresh_conductivity_profile_button()
        self._refresh_uf_profile_button()

        self.setStyleSheet(f"""
            QWidget {{ background-color: transparent; }}
            QFrame#card {{
                background-color: {bg_card};
                border: 1px solid {border};
                border-radius: 14px;
            }}
            QLabel#card_title {{
                font-family: 'Segoe UI', Arial, sans-serif;
                color: {text_primary};
                font-size: 28px;
                font-weight: bold;
                border-bottom: 1px solid {border};
                padding-bottom: 10px;
                margin-bottom: 12px;
            }}
            QFrame#card QLabel {{
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
        """)


    def _start_blood_pump(self):
        """Maneja el encendido seguro de la bomba de sangre"""
        try:
            logger.info("Comando START bomba de sangre solicitado")
          
            self._handle_dual_pump_toggle("bloodPumpStartButton", "bloodPumpStopButton", True)
            self.setFocus()        

        except Exception as e:
            logger.error(f"Error en _start_blood_pump: {e}", exc_info=True)

    def _start_filter_fill(self):
        try:
            logger.info("Comando Start de llenado de filtro")
            self.on_user_boolean_command("dialyFilterFillButton",True)
            if hasattr(self.parent_window, '_start_filter'):
                self.parent_window._start_filter()
            self.setFocus()
        except Exception as e:
            logger.error(f"Error en _start_filter_fill: {e}",exc_info=True)

    def _stop_blood_pump(self):
        """Maneja el apagado seguro de la bomba de sangre"""
        try:
            logger.info("Comando STOP bomba de sangre solicitado")

            # 1. Deshabilitar loop de control
            # self.on_user_boolean_command("bloodControlLoopEnable", False)

            # 2. Activar secuencia de parada de la bomba
            self._handle_dual_pump_toggle("bloodPumpStartButton", "bloodPumpStopButton", False)

            # 3. Detener movimiento hacia adelante
            # self.on_user_boolean_command("bloodPumpFWDButton", False)
            self.setFocus()
        except Exception as e:
            logger.error(f"Error en _stop_blood_pump: {e}", exc_info=True)

    def _update_filter_fill_button_state(self, enable: bool):
        """Habilita/deshabilita botón de llenado de filtro"""
        if enable:
            self.btn_filter_fill.setEnabled(True)
            self.btn_filter_fill.setStyleSheet(self.style_enabled)
            logger.info("Botón Llenado de Filtro → HABILITADO (Estado 7)")
        else:
            self.btn_filter_fill.setEnabled(False)
            self.btn_filter_fill.setStyleSheet(self.style_disabled)
            logger.debug("Botón Llenado de Filtro → DESHABILITADO")

    def _update_bloop_pump_controls_state(self):   
        current_phase = None
        if hasattr(self, 'parent_window') and hasattr(self.parent_window, 'state'):
            current_phase = self.parent_window.state.current_phase
        status_code = int(self.current_values.get("primingProcessStatus", 0))

        # Restricción aplicada solo a botones de bomba de sangre.
        # Se bloquean en RUNNING o en estado 14 de priming.
        if current_phase == TreatmentPhase.RUNNING or status_code == 14:
            self.btn_start_blood_pump.setEnabled(False)
            self.btn_stop_blood_pump.setEnabled(False)
            self.btn_start_blood_pump.setStyleSheet(self.style_disabled)
            self.btn_stop_blood_pump.setStyleSheet(self.style_disabled)
            logger.debug(f"Bomba de sangre bloqueada (phase={current_phase}, priming={status_code})")
            return
        
        pump_start_state = self.current_values.get("bloodPumpStartButton", 0)         
        pump_stop_state = self.current_values.get("bloodPumpStopButton", 0)
        # fwd_state = self.current_values.get("bloodPumpFWDButton", 0)
        
        logger.info(f" Start: {pump_start_state}, Stop: {pump_stop_state} ") 
        can_start = True  
        can_stop = False  
        # Estado: Bomba funcionando (START debería estar deshabilitado, STOP habilitado)
        # Esto ocurre cuando el lazo de control está activo, el botón de inicio fue presionado,
        # el botón de parada NO fue presionado y la dirección es hacia adelante.
        if (pump_start_state == 1 and 
            pump_stop_state == 0):
            can_start = False
            can_stop = True
            logger.info("Estado de la bomba: FUNCIONANDO")

        # Estado: Bomba explícitamente detenida (START habilitado, STOP deshabilitado)
        # Esto ocurre cuando el lazo de control está inactivo, el botón de inicio no fue presionado,
        # el botón de parada SI fue presionado y la dirección no es hacia adelante.
        elif (pump_start_state == 0 and 
              pump_stop_state == 1):
            can_start = True
            can_stop = False
            logger.info("Estado de la bomba: DETENIDA")
        
        # Si no encaja en ninguno de los estados anteriores, el comportamiento por defecto ya está definido.
        # (can_start = True, can_stop = False), lo que significa que la app asume un estado detenido/listo para arrancar.
        else:
            logger.info("Estado de la bomba: INDETERMINADO o listo para arrancar (por defecto)")
            #
            # can_start = False
            # can_stop = False
            # Pero normalmente es mejor que el usuario pueda intentar arrancar si no hay una señal clara de que está corriendo.

        # Referencias a los botones
        btn_startbp = self.btn_start_blood_pump
        btn_stop_bp = self.btn_stop_blood_pump

        # Actualizar el estado 'enabled' y el estilo del botón START
        # Solo actualizamos si el estado ha cambiado para evitar repintados innecesarios
        if btn_startbp.isEnabled() != can_start:
            btn_startbp.setEnabled(can_start)
            btn_startbp.setStyleSheet(self.style_enabled if can_start else self.style_disabled)
            logger.info(f"Botón START: {'HABILITADO' if can_start else 'DESHABILITADO'}")

        # Actualizar el estado 'enabled' y el estilo del botón STOP
        if btn_stop_bp.isEnabled() != can_stop:
            btn_stop_bp.setEnabled(can_stop)
            # Usa el estilo apropiado para el botón STOP cuando está habilitado/deshabilitado
            btn_stop_bp.setStyleSheet(self.style_stop_enabled if can_stop else self.style_disabled)
            logger.info(f"Botón STOP: {'HABILITADO' if can_stop else 'DESHABILITADO'}")

    def _handle_single_pump_toggle(self, tag: str, enabled: bool):
        if enabled:
            logger.info(f"Enviando comando START para {tag}")
            self.on_user_boolean_command(tag, True)
            # self.toggle_hold_off[tag] = QDateTime.currentMSecsSinceEpoch() + 1000
        else:
            logger.info(f"Enviando comando STOP para {tag}")
            self.on_user_boolean_command(tag, False)
            # self.toggle_hold_off[tag] = QDateTime.currentMSecsSinceEpoch() + 1000

    def _handle_dual_pump_toggle(self, start_tag: str, stop_tag:str, enabled: bool):
        if enabled:
            logger.info(f"Enviando comando START para {start_tag}")
            self.on_user_boolean_command(start_tag, True)
            self.on_user_boolean_command(stop_tag, False)
            # self.toggle_hold_off[start_tag] = QDateTime.currentMSecsSinceEpoch() + 1000
        else:
            logger.info(f"Enviando comando STOP para {stop_tag}")
            self.on_user_boolean_command(stop_tag, True)
            self.on_user_boolean_command(start_tag, False)
            # self.toggle_hold_off[stop_tag] = QDateTime.currentMSecsSinceEpoch() + 1000
            
    def open_numpad(self, tag: str, input_widget: ClickableLineEdit, title: str):
        current_text = input_widget.text()
        dialog = NumpadDialog(self, initial_value="", title=title)
        if dialog.exec():
            new_value = dialog.get_value()
            if new_value is not None:
                float_val = float(new_value)
                input_widget.setText(str(new_value))   
                self.current_values[tag] = float_val                         
                self.on_user_input_setpoint(tag, float_val)  #solicitar cambio en comunicación serial
                self.write_hold_off[tag] = QDateTime.currentMSecsSinceEpoch() + 300 
                if hasattr(input_widget, 'clearFocus'):
                    input_widget.clearFocus()
                self.setFocus()


    def open_time_numpad(self, input_widget: ClickableLineEdit,
                         tag_hours: str = None, tag_minutes: str = None,
                         title: str = "Config. Tiempo"):
        current_text = input_widget.text()
       
        dialog = TimeNumpadDialog(self, initial_hh_mm="", title=title)

        if dialog.exec():
            hours, minutes = dialog.get_hours_minutes()
            if hours is not None and minutes is not None:
                input_widget.setText(f"{hours:02d}:{minutes:02d}")
                input_widget.clearFocus()  
                if tag_hours:
                    self.current_values[tag_hours] = float(hours)
                    self.parent_window.current_values[tag_hours] = float(hours)   
                if tag_minutes:
                    self.current_values[tag_minutes] = float(minutes)
                    self.parent_window.current_values[tag_minutes] = float(minutes)
                if tag_hours and tag_minutes:
                    self.on_user_input_setpoint(tag_hours, float(hours))
                    self.on_user_input_setpoint(tag_minutes, float(minutes))
                  

    def _update_time_display(self, widget: ClickableLineEdit, tag_hours: str, tag_minutes: str):
        if not widget.hasFocus():
            hours = int(self.current_values.get(tag_hours, 0))
            minutes = int(self.current_values.get(tag_minutes, 0))
            widget.setText(f"{hours:02d}:{minutes:02d}")

    def update_values(self, new_values: dict):
        """Actualiza solo los campos numéricos y de tiempo"""

        self.current_values = new_values
        current_ms = QDateTime.currentMSecsSinceEpoch()

        self.current_values.get("dialyFilterFillButton", 0.0)
        self.current_values.get("bloodPumpStartButton", 0.0)
        self.current_values.get("bloodPumpStopButton", 0.0)
        self._update_input_display(self.input_blood_flow, "bloodFlowControlSetPoint")
        self._update_input_display(self.input_temperature, "dialyTempControlSetPoint")
        self._update_input_display(self.input_conductivity, "dialyCondControlSetPoint")
        self._update_input_display(self.input_dialysate_flow, self.current_values.get("balanceChamberSetTiming", 0.0)) 
        self._update_input_display(self.lbl_input_UF, self.current_values.get("ultraFilterPumpSpeed", 0.0))
        self._update_time_display(self.input_duration, "heparineTherapyHours", "heparineTherapyMinutes")
        self._update_bloop_pump_controls_state()
        self._refresh_conductivity_profile_button()
        self._refresh_uf_profile_button()
        
        if hasattr(self, 'parent_window') and hasattr(self.parent_window, 'state'):
            self.update_state(self.parent_window.state.current_phase)
        




    def _handle_cb_flow_input(self):
        """
        Maneja el input del usuario:
        1. Abre el numpad para pedir mL/min.
        2. Convierte mL/min -> Ciclos/timing.
        3. Escribe el valor en ciclos a la máquina.
        """
        dialog = NumpadDialog(self, initial_value="", title="Flujo Dializante (mL/min)")
        
        if dialog.exec():
            # El usuario ingresó un valor en mL/min (ej: 500)
            value_str = dialog.get_value()
            if hasattr(self.input_dialysate_flow, 'setText'):
                self.input_dialysate_flow.setText(str(value_str))

            flow_ml_min = float(value_str)            
            
            self.setFocus()
            
            try:
                cycles_value = convertir_flujo_a_ciclos(flow_ml_min)
                tag = "balanceChamberSetTiming"
                self.on_user_input_setpoint(tag, cycles_value)
                print(f"Flujo {flow_ml_min} mL/min convertido a {cycles_value} ciclos/timing y enviado a la máquina.")                               
                self.write_hold_off["balanceChamberSetTiming"] = QDateTime.currentMSecsSinceEpoch() + 3000
                
            except Exception as e:
                logger.error(f"Error convirtiendo flujo a ciclos: {e}")


  

    def _handle_uf_flow_input(self):
        """Handle UF flow input (L/h → ml/min). Edición manual pisa un perfil UF activo (modo Sin perfil)."""

        # 1. Obtener el valor actual del widget para mostrarlo en el numpad
        current_text = ""

        dialog = NumpadDialog(self, initial_value=current_text, title="Flujo UF (L/h)")

        if dialog.exec():
            new_value_str = dialog.get_value()

            if new_value_str is not None:
                try:
                    # 2. Convertir a float una sola vez y validar
                    val_float = float(new_value_str)

                    # 2b. Rango de edición: 0.00 - 2.00 L/h. Fuera de rango: no escribir.
                    if val_float > 2.0:
                        if self.parent_window and hasattr(self.parent_window, "show_warning_message"):
                            self.parent_window.show_warning_message(
                                "Flujo UF fuera de rango (máximo 2.00 L/h)", 4000
                            )
                        return
                    val_float = max(0.0, val_float)

                    # 3. Actualizar la interfaz inmediatamente
                    if hasattr(self.lbl_input_UF, 'setText'):
                        self.lbl_input_UF.setText(f"{val_float:.2f}")

                    # 4. Realizar el cálculo matemático con el número, NO con el texto
                    ml_min = convertir_litros_h_a_ml_min(val_float)

                    # 5. Editar el numpad manualmente cancela un perfil UF activo (el usuario lo pisa a propósito).
                    if self.parent_window and hasattr(self.parent_window, "is_uf_profile_active"):
                        if self.parent_window.is_uf_profile_active():
                            self.parent_window.disable_uf_profile(show_message=False)

                    # 6. Enviar al controlador
                    self.on_user_input_setpoint("ultraFilterPumpSpeed", ml_min)

                    # 7. Bloquear actualización de lectura por 3 segundos para dar tiempo al PLC
                    self.write_hold_off["ultraFilterPumpSpeed"] = QDateTime.currentMSecsSinceEpoch() + 3000

                except ValueError:
                    logger.error(f"El valor ingresado no es un número válido: {new_value_str}")
                except Exception as e:
                    logger.error(f"Error convirtiendo flujo UF: {e}")



    def _update_input_display(self, widget: ClickableLineEdit, tag_or_value, precision: int = 1):
        if widget.hasFocus():
            return
        val_to_show = 0.0
        if isinstance(tag_or_value, str):
            val_to_show = self.current_values.get(tag_or_value, 0.0)
        elif isinstance(tag_or_value, (int, float)):
            val_to_show = tag_or_value

        widget.setText(f"{val_to_show:.{precision}f}")

    def on_user_input_setpoint(self, tag, value):
        self.request_setpoint_change.emit(tag, value)

    def on_user_boolean_command(self, tag, state):
        self.request_boolean_change.emit(tag, state)
        print("confirmado")

    def _on_open_conductivity_profile(self):
        if not self.parent_window:
            return

        if (
            hasattr(self.parent_window, "can_configure_conductivity_profile")
            and hasattr(self.parent_window, "is_conductivity_profile_active")
            and hasattr(self.parent_window, "disable_conductivity_profile")
        ):
            can_open, _msg = self.parent_window.can_configure_conductivity_profile()
            if not can_open and self.parent_window.is_conductivity_profile_active():
                self.parent_window.disable_conductivity_profile(show_message=True)
                return

        if hasattr(self.parent_window, "show_conductivity_profile_screen"):
            self.parent_window.show_conductivity_profile_screen()

    def _refresh_conductivity_profile_button(self):
        if not hasattr(self, "btn_conductivity_profile"):
            return

        is_active = False
        if self.parent_window and hasattr(self.parent_window, "is_conductivity_profile_active"):
            is_active = bool(self.parent_window.is_conductivity_profile_active())

        if is_active:
            self.btn_conductivity_profile.setText("Perfil Na+ ACTIVO")
            self.btn_conductivity_profile.setStyleSheet(self.profile_btn_active_style)
        else:
            self.btn_conductivity_profile.setText("Perfil Na+")
            self.btn_conductivity_profile.setStyleSheet(self.profile_btn_style)

    def _on_open_uf_profile(self):
        if not self.parent_window:
            return

        if (
            hasattr(self.parent_window, "can_configure_uf_profile")
            and hasattr(self.parent_window, "is_uf_profile_active")
            and hasattr(self.parent_window, "disable_uf_profile")
        ):
            can_open, _msg = self.parent_window.can_configure_uf_profile()
            if not can_open and self.parent_window.is_uf_profile_active():
                self.parent_window.disable_uf_profile(show_message=True)
                return

        if hasattr(self.parent_window, "show_uf_profile_screen"):
            self.parent_window.show_uf_profile_screen()

    def _refresh_uf_profile_button(self):
        if not hasattr(self, "btn_uf_profile"):
            return

        is_active = False
        if self.parent_window and hasattr(self.parent_window, "is_uf_profile_active"):
            is_active = bool(self.parent_window.is_uf_profile_active())

        if is_active:
            self.btn_uf_profile.setText("Perfil UF ACTIVO")
            self.btn_uf_profile.setStyleSheet(self.profile_btn_active_style)
        else:
            self.btn_uf_profile.setText("Perfil UF")
            self.btn_uf_profile.setStyleSheet(self.profile_btn_style)

    def update_state(self, phase: TreatmentPhase):
        """Actualiza el estado de botones de bomba de sangre y deja el resto habilitado."""
        treatment_mode = int(self.current_values.get("treatmentModeSelection", 0))
        status_code = int(self.current_values.get("primingProcessStatus", 0))

        logger.debug(f"TherapyConfigScreen - update_state: Phase={phase.name}, Status={status_code}")

        # ==================== BOTÓN LLENADO DE FILTRO ====================
        if phase == TreatmentPhase.PREPARING and status_code == 7:
            self._update_filter_fill_button_state(True)   # Solo se habilita en estado 7
        else:
            self._update_filter_fill_button_state(False)

        # ==================== BOTONES BOMBA DE SANGRE ====================
        self._update_bloop_pump_controls_state()

        # ==================== OTROS BOTONES / CONTROLES ====================
        # Mantener inputs habilitados incluso durante terapia activa (RUNNING/PAUSED)
        enabled_inputs = phase not in (TreatmentPhase.CLEANING, TreatmentPhase.ERROR)

        for widget in [self.input_blood_flow, self.input_dialysate_flow,
                       self.lbl_input_UF, self.input_temperature, self.input_conductivity,
                       self.input_duration]:
            if hasattr(widget, 'setEnabled'):
                widget.setEnabled(enabled_inputs)

        if hasattr(self, "btn_conductivity_profile"):
            self.btn_conductivity_profile.setEnabled(enabled_inputs)

        if hasattr(self, "btn_uf_profile"):
            self.btn_uf_profile.setEnabled(enabled_inputs)

   

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()
