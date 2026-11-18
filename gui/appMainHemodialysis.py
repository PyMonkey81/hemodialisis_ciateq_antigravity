


# gui/appMainHemodialysis.py

"""
Módulo principal de la Interfaz Hombre-Máquina (HMI) para el dispositivo de Hemodiálisis.

Este módulo define la clase `HemodialysisHMI`, que actúa como el punto de entrada
y el controlador central de la interfaz gráfica de usuario (GUI). Gestiona la navegación
entre pantallas, la comunicación con el hardware (controladores, sensores), el sistema
de alarmas y el registro de datos (logging).

Responsabilidades principales:
------------------------------
1. **Gestión de Ventanas (Stack):** Administra un `QStackedWidget` para navegar entre
   diferentes pantallas (Inicio, Diálisis, Limpieza, Servicio, Alarmas, etc.).
2. **Comunicación Serial:** Inicializa y maneja `SerialCommunication` para el intercambio
   de datos con el hardware de control en tiempo real.
3. **Monitoreo de Sensores:** Integra controladores específicos para Bioimpedancia/Urea
   (`BiozUreaController`) y Conductividad (`PatternConductivity`).
4. **Sistema de Alarmas:** Centraliza la lógica de alarmas (`AlarmSystem`), monitoreando
   variables críticas y controlando la retroalimentación visual (GUI) y física (Barra LED/Buzzer).
5. **Registro de Datos (Logging):** Gestiona la escritura de datos de telemetría en archivos CSV
   tanto para procesos de cebado como de tratamiento.
6. **Lógica de Tratamiento:** Controla el flujo de estados del tratamiento (Inicio, Pausa,
   Parada), incluyendo el cálculo de tiempo de terapia y métricas como Kt/V.
7. **Interfaz Visual:** Construye el layout principal, incluyendo encabezados de estado,
   paneles laterales de indicadores (gauges) y la barra de navegación inferior.

Dependencias Externas:
----------------------
- PySide6 (Qt for Python): Framework gráfico.
- Core Modules: `alarms`, `variables_map`.
- Connection Modules: `serial_communication`, `led_bar_controller`, `bioz_urea_controller`.
- GUI Components: Pantallas específicas (`DialysisScreen`, `MainScreen`, etc.) y widgets personalizados.

Uso:
----
Esta clase se instancia desde archivo `main.py`:

    app = QApplication(sys.argv)
    window = HemodialysisHMI()
    window.showFullScreen()
    sys.exit(app.exec())

Author: Miguel de Jesus C. Espinoza Calderón
Version: 2.21.0
"""


from cmath import phase
from cmath import phase
import os
import sys
import time
import logging
import json
from collections import deque
from typing import List, Tuple

from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, QTimer, QDateTime, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QPixmap, QColor, QImage

# === MODULES ===
from connection.mega_conductivity_sensor import MegaConductivitySensor
from core.alarms import AlarmSystem
from core.alarm_config_manager import AlarmConfigManager
from core.state_manager import AppStateManager, TreatmentPhase
from core.timer_manager import TimerManager
from core.treatment_controller import TreatmentController
from core.hardware_state_mapper import HardwareStateMapper
from core.variables_map import TAG_TO_ADDRESS, VARIABLES
from core.ktv.ktv_controller import KtvController
from connection.serial_communication import SerialCommunication
from connection.led_bar_controller import LedBarController
from connection.bioz_urea_controller import BiozUreaController
from connection.conductivity_sensor_comm import PatternConductivity
from connection.nibp_par_communication import NibpParCommunication
from connection.firmware_gateway import (
    FirmwareGateway,
    THERAPY_CONFIG_PATH,
    THERAPY_LOCAL_TAGS,
    THERAPY_FIRMWARE_TAGS,
    HEPARIN_DOSE_FIRMWARE_TAGS,
)


from gui.screen_state_manager import ScreenStateManager
from gui.therapy.main_screen import MainScreen
from gui.therapy.alarms_screen import AlarmsScreen
from gui.therapy.dialysis_screenV2 import DialysisScreen
from gui.therapy.treatment_mode_screen import TreatmentModeScreen
from gui.therapy.ktv_screen import KTVScreen
from gui.service.options_screen import OptionsScreen
from gui.service.history_screen import HistoryScreen
from gui.service.cleaning_screen import CleaningScreen
from gui.service.comm_port_screen import CommPortScreen
from gui.components.real_time_variables import RealTimeVariablesMonitor
from gui.components.tank_gauge import TankGauge
from gui.components.conductivity_bar import ConductivityBar
from gui.components.floating_message import FloatingMessage
from gui.components.floating_confirm import FloatingConfirmDialog

from gui.configuration.alarm_screen_config import AlarmScreenConfig 
from gui.configuration.alarm_screen_service_config import AlarmScreenServiceConfig
from gui.configuration.cleanning_config_screen import CleanningConfigScreen

from gui.service.manual_mode_screen import ManualModeScreen
from gui.service.test_panel_screen import TestPanelScreen
from gui.service.calibration_screen import CalibrationScreen
from gui.service.network_config_screen import NetworkConfigScreen
from gui.service.maintenance_screen import MaintenanceScreen

from gui.therapy.patient_config_screen import PatientConfigScreen
from gui.therapy.therapy_config_screenV2 import TherapyConfigScreen
from gui.therapy.conductivity_profile_screen import ConductivityProfileScreen
from gui.therapy.uf_profile_screen import UFProfileScreen
from gui.therapy.heparin_config_screenV2 import (
    HeparinConfigScreen,
    HEPARIN_AUTO_STOP_HOURS_TAG,
    HEPARIN_AUTO_STOP_MINUTES_TAG,
)
from gui.therapy.nibp_config_screen import NibpConfigScreen
from gui.therapy.nibp_history_screen import NibpHistoryScreen, NibpChartScreen
from gui.therapy.nibp_limits_screen import NibpLimitsScreen
from core.nibp_pressure_history import NibpPressureHistory
from core.therapy_session_tracker import TherapySessionTracker
from utilities.therapy_report_generator import TherapyReportGenerator
from gui.theme_manager import ThemeManager
from gui.service.theme_config_screen import ThemeConfigScreen
from gui.session.session_recorder import SessionRecorder
from gui.session.operator_alerts import OperatorAlerts
from gui.session.hardware_state_sync import HardwareStateSync
from connection.telemetry_inlet import TelemetryInlet, LOCAL_SETPOINT_TAGS
from gui.session.app_shutdown import AppShutdown
from gui.session.priming_session import PrimingSession
from gui.session.comm_binding import CommBinding
from gui.session.cleaning_session import CleaningSession
from gui.session.connection_presence import ConnectionPresence
from gui.session.active_alarms import ActiveAlarms
from gui.session.master_clock import MasterClock
from gui.shell.main_shell import MainShell
from gui.shell.side_indicators import SideIndicators
from gui.therapy.profile_coordinator import ProfileCoordinator
from gui.therapy.heparin_coordinator import HeparinCoordinator
from gui.therapy.treatment_start import TreatmentStart
from gui.therapy.nibp_coordinator import (
    NibpCoordinator,
    NIBP_CONFIG_PATH,
    NIBP_DEFAULT_CONFIG,
    NIBP_AUTO_FIRST_MEASURE_DELAY_S,
)
from logic.heparin_time import reference_minutes, clamp_heparin_time, was_clamped
from logic.start_checklist import missing_start_items
from pathlib import Path

from logic.calculos import (
    convertir_ciclos_a_flujo,
    convertir_flujo_a_ciclos,
    convertir_litros_h_a_ml_min,
    convertir_ml_min_a_litros_h,
)
from logic.conductivity_profile import (
    ConductivityProfile,
    ProfileType,
    calculate_target_conductivity,
    load_profile,
    save_profile,
    step_index_by_seconds,
    validate_profile,
)
from logic.uf_profile import (
    UFProfile,
    calculate_target_uf,
    load_profile as load_uf_profile,
    save_profile as save_uf_profile,
    validate_profile as validate_uf_profile,
)
from utilities.csv_logger import CsvLogger
from utilities.platform_runtime import (
    get_runtime_config_path,
    get_runtime_data_path,
    safe_float,
    safe_int,
    safe_json_load,
)

logger = logging.getLogger(__name__)

#===============================================================================
#======================CODIGO PARA ADJUNTAR LOGOS EN EJECUTABLE=================
#===============================================================================


def resource_path(relative_path):
    """Obtiene la ruta absoluta al recurso usando pathlib."""
    # Comprueba si estamos corriendo como un ejecutable de PyInstaller
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = Path(sys._MEIPASS)
    else:
        # Si estamos en desarrollo, usa el directorio de este archivo
        base_path = Path(__file__).parent.parent 
        # (ajusta los .parent dependiendo de dónde esté este script respecto a tus recursos)

    return str(base_path / relative_path)


class LogoButton(QPushButton):
    """Botón plano para logo CIATEQ que maneja toque corto (salida) y largo (sin acción).
    Solo abre diálogo de salida si está en pantalla de inicio (INDEX_HOME)."""
    
    def __init__(self, icon_path: str, close_callback=None, screen_stack=None, parent=None):
        super().__init__(parent)
        self.close_callback = close_callback
        self.screen_stack = screen_stack
        self.press_time = None
        self.long_press_threshold = 800  # ms
        self.long_press_timer = QTimer()
        self.long_press_timer.setSingleShot(True)
        self.long_press_timer.timeout.connect(self._handle_long_press)
        
        # Configurar botón plano
        self.setFlat(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setStyleSheet("border: none; padding: 0px;")
        
        # Cargar icono
        pixmap = QPixmap(icon_path).scaled(180, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setIcon(pixmap)
        self.setIconSize(pixmap.size())
        self.setFixedSize(180, 120)
    
    def mousePressEvent(self, event):
        """Registrar inicio del toque."""
        super().mousePressEvent(event)
        self.press_time = time.time()
        self.long_press_timer.start(self.long_press_threshold)
    
    def mouseReleaseEvent(self, event):
        """Diferenciar entre toque corto y largo."""
        self.long_press_timer.stop()
        if self.press_time is not None:
            elapsed = (time.time() - self.press_time) * 1000
            if elapsed < self.long_press_threshold:
                # Toque corto: abrir diálogo de salida solo si está en pantalla de inicio
                self._handle_short_press()
        super().mouseReleaseEvent(event)
    
    def _handle_short_press(self):
        """Toque corto: abrir diálogo de confirmación para salir si está en INDEX_HOME."""
        # Solo actuar si estamos en la pantalla de inicio (INDEX_HOME = 0)
        if self.screen_stack and self.screen_stack.currentIndex() == 0:
            if self.close_callback:
                self.close_callback()
    
    def _handle_long_press(self):
        """Toque largo: no hacer nada (sin dibujar recuadro ni seleccionar)."""
        pass


class ClickableTreatmentLabel(QLabel):
    """QLabel clickeable para seleccionar tipo de tratamiento desde el header."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.click_callback = None
        self.setCursor(Qt.PointingHandCursor)

    def set_callback(self, callback):
        """Establece el callback a ejecutar al hacer click."""
        self.click_callback = callback

    def mousePressEvent(self, event):
        """Ejecuta el callback al hacer click si el label está habilitado."""
        super().mousePressEvent(event)
        if self.isEnabled() and self.click_callback:
            self.click_callback()


class HemodialysisHMI(QMainWindow):

    # Screen indices
    INDEX_HOME = 0

    BTN_ENABLED_DEFAULT_STYLE = """
        QPushButton { background: #06298a; color: #ffffff; font-family: 'Segoe UI', Arial, sans-serif; font-weight: bold; font-size: 30px; border-radius: 10px; }
        QPushButton:pressed { background: #334155; }
    """
    BTN_ENABLED_START_TREATMENT_STYLE = """
        QPushButton { background: #39ec21; color: #ffffff; font-family: 'Segoe UI', Arial, sans-serif; border-radius: 8px; font-weight: bold; font-size: 30px;}
        QPushButton:pressed { background: #1e40af; }
    """
    BTN_ENABLED_EXIT_STYLE = """
        QPushButton { background: #dc2626; color: #ffffff; font-family: 'Segoe UI', Arial, sans-serif; font-weight: bold; font-size: 30px; border-radius: 10px; }
        QPushButton:pressed { background: #b91c1c; }
    """
    BTN_DISABLED_STYLE = """
        QPushButton { background: #334155; color: #94a3b8; font-family: 'Segoe UI', Arial, sans-serif; font-weight: bold; font-size: 30px; border-radius: 10px; }
    """
    BTN_ACTIVE_STYLE = """
        QPushButton { background: #3b82f6; color: white; font-family: 'Segoe UI', Arial, sans-serif; font-weight: bold; font-size: 30px; border-radius: 10px; border: 2px solid #60a5fa;}
        QPushButton:pressed { background: #1e40af; }
    """
    QMESSAGEBOX_GLOBAL_STYLE = """
        QMessageBox {
            background-color: #2b2b2b; /* Fondo de la ventana oscuro */
            color: #ffffff;            /* Texto del QMessageBox (principal) */
        }
        QMessageBox QLabel { /* Reglas para QLabel DENTRO de un QMessageBox */
            color: #ffffff;            /* Asegura que el texto del mensaje sea blanco */
            background-color: #2b2b2b; /* <-- ¡Añadido! Fondo del QLabel explícitamente oscuro */
            padding: 5px;              /* Opcional: un pequeño padding para que el texto no se pegue al borde */
        }
        QMessageBox QPushButton { /* Reglas para QPushButton DENTRO de un QMessageBox */
            background-color: #4CAF50; /* Color de fondo del botón (Verde ejemplo) */
            color: #ffffff;              /* Color del texto del botón */
            border-radius: 5px;        /* Bordes redondeados */
            padding: 5px 15px;         /* Relleno para hacerlo más grande */
            font-weight: bold;
        }
        QMessageBox QPushButton:hover {
            background-color: #45a049; /* Color al pasar el mouse por encima */
        }
        QMessageBox QPushButton:pressed {
            background-color: #3e8e41; /* Color al presionar */
        }
    """



    def _get_main_shell(self) -> MainShell:
        shell = getattr(self, "main_shell", None)
        if shell is None:
            shell = MainShell(self)
            self.main_shell = shell
        return shell

    def _get_side_indicators(self) -> SideIndicators:
        indicators = getattr(self, "side_indicators", None)
        if indicators is None:
            indicators = SideIndicators(self)
            self.side_indicators = indicators
        return indicators

    def _build_header_label_style(self, background: str = "", is_process: bool = False) -> str:
        return self._get_main_shell()._build_header_label_style(background, is_process=is_process)


    def __init__(self):
        super().__init__()
        self.csv_logger = None
        self.treatment_logger = None
        self.cleaning_logger = None
        # Atributos críticos inicializados temprano para evitar fallos durante arranque parcial.
        self.current_values = {}
        self.temp_readings = deque()  # (timestamp, value) pairs
        self.dialyTempIFProcessData_avg = 0.0  # Promedio de los últimos 3 segundos
        self.bioz_urea_controller = None
        
        # Diccionario para ignorar lecturas de ciertos tags hasta un tiempo especificado (evita
        # que la lectura vieja del firmware pise valores recién enviados).
        # Formato: {tag: expiration_time_in_seconds_since_epoch}
        self.ignore_tags_until = {}

        self.parameter_mapping = {  
            "dialyLinePresProcessData": "PT-3",
            "dialyPresIFProcessData": "PT-4",
            "dialyPresOFProcessData": "PT-5",
            "dialyLineWaterPresData": "PT-6",
            "dialyBChamPresProcessData": "PT-7",
            "bloodArteryPressureData": "PT-8",
            "bloodVenousPressureData": "PT-9",
            "dialyPFilPmpPresProcessData": "PT-10",
            "dialyTempIFProcessData": "Temperatura EF",
            "dialyTempIOFProcessData": "Temperatura SF",
            "dialyTempVariableData": "Temperatura Tanque",
            "dialyCondControlSetPoint": "Setpoint Conductividad",
            "dialyConductIFProcessData": "Conductividad EF",
            "dialyConductOFProcessData": "Conductividad SF",
            "dialyCondControlOutput": "Salida Conductividad",
            "dialyTempControlSetPoint": "Setpoint Temperatura",
            "CALC_PTM": "Presión Transmembrana",
            "dialyTankHiLevelSwitch": "Nivel",
            "dialyWaterInletValveButt": "Valvula 27",
            "dialyDeaerChamLevSwitch": "C. Deareación",
            "watterTankHeaterProtect": "Protector Calefactor",
            "airBubbleInBloodDetected": "Aire en Sangre",
            "bloodInDialyCircDetected": "Sangre en dializante",
            "dialyPurgePumpStartButt": "Purga de aire",
            "patternCondSensor": "Cond. Sensor patrón",
            "patternTempSensor": "Temp. Sensor patrón",
            "patternCondRaw": "Cond. Sensor raw",             
        }

        # Control de llenado de filtro + delay de 90 segundos
        self.filter_fill_start_time = None
        self.filter_fill_waiting = False
        self.MIN_FILTER_FILL_WAIT_SECONDS = 90


        #======================= GESTOR DE ESTADOS ==========================

        self.state = AppStateManager()
        self.state.state_changed.connect(self._on_state_changed)
        
        #Conectar señañes 
        self.state.treatment_started.connect(self._on_treatment_started)
        self.state.treatment_paused.connect(self._on_treatment_paused)
        self.state.treatment_resumed.connect(self._on_treatment_resumed)
        self.state.treatment_finished.connect(self._on_treatment_finished)
        self.state.cleaning_started.connect(self._on_cleaning_started)
        self.state.cleaning_finished.connect(self._on_cleaning_finished)
        self.state.error_occurred.connect(self._on_state_error)

    # ====================== 2. TIMER MANAGER ======================
        
        self.timer_manager = TimerManager(self)

    # ====================== 3. TREATMENT CONTROLLER ======================

        self.treatment_controller = TreatmentController(self)

    # ====================== 4. SCREEN STATE MANAGER ======================

        self.screen_state_manager = ScreenStateManager(self)

        self.hardware_mapper = HardwareStateMapper()
        self.timer_manager.hardware_mapper = self.hardware_mapper


        self._last_priming_status = -1
        self._treatment_map = {
            0: "Hemodiálisis",
            1: "Hemodiafiltración",
            2: "Ultrafiltración",
            3: "Limpieza"
        }

        # ====================== KTV CONTROLLER ===========================
        self.ktv_controller = KtvController(self) # MODIFICADO: Instanciamos el KtvController

        # La inyección de dependencias del KtvController se realiza más adelante,
        # después de crear current_values y bioz_urea_controller.
        # ====================== TIMER MAESTRO (ÚNICO) ======================
        self.master_timer = QTimer(self)
        self.master_timer.setInterval(500)
        self.master_timer.timeout.connect(self._master_timer_tick)

        # Variables de control para el timer maestro
        self.last_second_update = QDateTime.currentDateTime()
        self.last_minute_update = QDateTime.currentDateTime()
        self._timer_lock = False  # ← NUEVO: protección contra reentrancia


        # ====================== HISTORIAL DE TRATAMIENTOS Y LIMPIEZA ======================
        self.treatment_history = []   # Se cargará desde JSON
        self.cleaning_history = []
        
        self.current_treatment_start = None   # Para registrar cuando inicia un tratamiento

        # ====================== VARIABLES DE HORAS ======================
        self.total_operation_hours = 0.0   # Tratamiento activo
        self.power_on_hours = 0.0          # Máquina encendida
        self.cleaning_hours = 0.0          # Tiempo en limpieza

        # Timers de conteo
        self.operation_start_time = None
        self.cleaning_start_time = None
        self.last_resume_time = None
        
        self.is_treatment_running = False
        self.is_cleaning_in_progress = False

        self._current_elapsed_therapy_min = 0.0 # Variable para cálculo de Kt/V acumulado en tiempo real        
        self._original_conductivity_setpoint = None # Para almacenar el setpoint original de conductividad antes de cualquier ajuste por terapia    
        self.conductivity_profile: ConductivityProfile = load_profile()
        self._last_profile_target = None
        self._last_profile_written = None      # último SP enviado por el perfil
        self._last_profile_step_index = None
        self._last_profile_write_ts = 0         # epoch seconds
        self._last_profile_step_ts_s = 0        # t_terapia_s del último cambio de escalón
        self._last_profile_log_second = -1

        self.uf_profile: UFProfile = load_uf_profile()
        self._last_uf_profile_target = None
        self._last_uf_profile_written = None
        self._last_uf_profile_step_index = None
        self._last_uf_profile_write_ts = 0
        self._last_uf_profile_step_ts_s = 0
        
        # Control de tiempo de terapia (global)
        self.therapy_start_time = None
        self.total_therapy_seconds = 0
        self.accumulated_therapy_seconds = 0       

        self.current_treatment_start_date_time = None # Variable para reporte de inicio/tratamiento
        self.navigation_buttons = {} # nuevo
        self._heparin_auto_stop_latched = False
        self._heparin_running_clamped = False
        self._heparin_infusion_forced_stop_latched = False
        self.setup_ui()
        

        self._load_histories()     
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        

        # Serial communication
        self.current_values.clear()
        for group_key, vars_group in VARIABLES.items():
            if isinstance(vars_group, dict):
                for var_id, info in vars_group.items():
                    if "tag" in info:
                        self.current_values[info["tag"]] = 0.0 # Inicializar todos a 0.0

        # Tags locales (no se escriben al controlador)
        self.current_values.setdefault("heparineTherapyHours", 0.0)
        self.current_values.setdefault("heparineTherapyMinutes", 0.0)
        self.current_values.setdefault("heparineInfusionEnabled", 1.0)  # Default: comportamiento actual (habilitada)

        self._therapy_config_loaded = False
        self._therapy_config_applied_to_firmware = False
        self._load_therapy_config_json()

        self.serial_comm = SerialCommunication()
        self.serial_comm.data_received.connect(self.update_value)
        self._is_connected_prev_state = False # Rastrea estado de conexción

        self._get_nibp_coordinator().start_module()
        self._get_telemetry_inlet().start_bioz()
        self._get_telemetry_inlet().start_sensors()
        self._get_active_alarms().start_monitoring_stack()
        self._get_main_shell().build_screens()
        self._get_main_shell().start_shown()

    
    def _on_state_changed(self, phase: TreatmentPhase, reason: str):
        return self._get_treatment_start()._on_state_changed(phase, reason)

    def _get_nibp_coordinator(self) -> NibpCoordinator:
        coordinator = getattr(self, "_nibp_coordinator", None)
        if coordinator is None:
            coordinator = NibpCoordinator(self)
            self._nibp_coordinator = coordinator
        return coordinator

    @property
    def nibp_coordinator(self) -> NibpCoordinator:
        return self._get_nibp_coordinator()

    @nibp_coordinator.setter
    def nibp_coordinator(self, value):
        self._nibp_coordinator = value

    def _apply_nibp_auto_spo2_for_phase(self, phase: TreatmentPhase):
        return self._get_nibp_coordinator()._apply_nibp_auto_spo2_for_phase(phase)

    def _on_nibp_measure_requested(self):
        return self._get_nibp_coordinator()._on_nibp_measure_requested()

    def _on_treatment_started(self, start_time):
        return self._get_treatment_start()._on_treatment_started(start_time)

    def _on_treatment_paused(self):
        return self._get_treatment_start()._on_treatment_paused()

    def _on_treatment_resumed(self):
        return self._get_treatment_start()._on_treatment_resumed()

    def _on_treatment_finished(self):
        return self._get_treatment_start()._on_treatment_finished()


    def _on_cleaning_started(self):
        return self._get_cleaning_session()._on_cleaning_started()

    def _on_cleaning_finished(self):
        return self._get_cleaning_session()._on_cleaning_finished()

    def _on_state_error(self, message: str):
        return self._get_treatment_start()._on_state_error(message)

    def _get_hardware_state_sync(self) -> HardwareStateSync:
        syncer = getattr(self, "hardware_state_sync", None)
        if syncer is None:
            syncer = HardwareStateSync(self)
            self.hardware_state_sync = syncer
        return syncer

    def _sync_state_with_hardware(self):
        """Sincroniza el estado interno con el estado real del hardware (fuente de verdad)"""
        return self._get_hardware_state_sync()._sync_state_with_hardware()

    


# ===============================================================================================
#                   UI Setup
#================================================================================================
    def setup_ui(self):
        return self._get_main_shell().setup_ui()
#==========================================================================================
#               FIN DE SETUP UI
#==========================================================================================


    # ────────────────────────────────────────────────
    #              Navigation Methods
    # ────────────────────────────────────────────────

    def _get_treatment_start(self) -> TreatmentStart:
        starter = getattr(self, "treatment_start", None)
        if starter is None:
            starter = TreatmentStart(self)
            self.treatment_start = starter
        return starter

    def start_treatment(self):
        return self._get_treatment_start().start_treatment()
    
    def _show_start_confirmation_dialog(self):
        return self._get_treatment_start()._show_start_confirmation_dialog()

    def _show_filter_fill_dialog_main(self):
        return self._get_treatment_start()._show_filter_fill_dialog_main()

    def pause_treatment(self):
        return self._get_treatment_start().pause_treatment()

    def stop_treatment(self):
        return self._get_treatment_start().stop_treatment()

    def _update_therapy_time_displays(self):
        """Actualiza displays de tiempo (delegado)"""
        self.treatment_controller.update_therapy_times()
    
    def _get_heparin_coordinator(self) -> HeparinCoordinator:
        coordinator = getattr(self, "_heparin_coordinator", None)
        if coordinator is None:
            coordinator = HeparinCoordinator(self)
            self._heparin_coordinator = coordinator
        return coordinator

    @property
    def heparin_coordinator(self) -> HeparinCoordinator:
        return self._get_heparin_coordinator()

    @heparin_coordinator.setter
    def heparin_coordinator(self, value):
        self._heparin_coordinator = value

    def _validate_and_clamp_heparin_auto_stop_time(self):
        return self._get_heparin_coordinator()._validate_and_clamp_heparin_auto_stop_time()
    
    def _get_heparin_flow_ml_per_h(self) -> float:
        return self._get_heparin_coordinator()._get_heparin_flow_ml_per_h()
    
    def _get_priming_session(self) -> PrimingSession:
        session = getattr(self, "_priming_session", None)
        if session is None:
            session = PrimingSession(self)
            self._priming_session = session
        return session

    def start_priming(self):
        return self._get_priming_session().start_priming()

    def stop_priming(self):
        return self._get_priming_session().stop_priming()

        



    def end_dialysis_session(self):
        return self._get_session_recorder().end_dialysis_session()
        

    def show_home_screen(self):
        return self._get_main_shell().show_home_screen()

    def show_dialysis_screen(self):
        return self._get_main_shell().show_dialysis_screen()

    def show_treatment_mode_screen(self):
        return self._get_main_shell().show_treatment_mode_screen()

    def show_cleaning_screen(self):
        return self._get_main_shell().show_cleaning_screen()

    def show_options_screen(self):
        return self._get_main_shell().show_options_screen()

    def show_theme_config_screen(self):
        return self._get_main_shell().show_theme_config_screen()

    def _apply_main_shell_theme(self, _theme_name: str = ""):
        """Actualiza dinámicamente los colores del contenedor principal, header, barra de navegación y tarjetas."""
        return self._get_main_shell()._apply_main_shell_theme(_theme_name)

    def show_alarms_screen(self):
        return self._get_main_shell().show_alarms_screen()

    def show_manual_mode_screen(self):
        return self._get_main_shell().show_manual_mode_screen()

    def show_test_panel_screen(self):
        return self._get_main_shell().show_test_panel_screen()

    def show_calibration_screen(self):
        return self._get_main_shell().show_calibration_screen()

    def show_network_config_screen(self):
        return self._get_main_shell().show_network_config_screen()

    def show_real_time_var_screen(self):
        return self._get_main_shell().show_real_time_var_screen()

    def show_patient_config_screen(self):
        return self._get_main_shell().show_patient_config_screen()

    def show_therapy_config_screen(self):
        return self._get_main_shell().show_therapy_config_screen()

    def show_conductivity_profile_screen(self):
        return self._get_main_shell().show_conductivity_profile_screen()

    def show_uf_profile_screen(self):
        return self._get_main_shell().show_uf_profile_screen()

    def show_heparin_config_screen(self):
        return self._get_main_shell().show_heparin_config_screen()

    def show_config_comm_screen(self):
        return self._get_main_shell().show_config_comm_screen()

    def show_maintenance_screen(self):
        return self._get_main_shell().show_maintenance_screen()

    def show_alarm_config_limits_screen(self):
        return self._get_main_shell().show_alarm_config_limits_screen()

    def show_alarm_service_screen_config(self):
        return self._get_main_shell().show_alarm_service_screen_config()

    def show_cleanning_config_screen(self):
        return self._get_main_shell().show_cleanning_config_screen()

    def show_history_screen(self):
        return self._get_main_shell().show_history_screen()

    def show_ktv_screen(self):
        return self._get_main_shell().show_ktv_screen()

    def show_nibp_screen(self):
        return self._get_main_shell().show_nibp_screen()

    def show_nibp_history_screen(self):
        return self._get_main_shell().show_nibp_history_screen()

    def show_nibp_chart_screen(self):
        return self._get_main_shell().show_nibp_chart_screen()

    def show_nibp_limits_screen(self):
        return self._get_main_shell().show_nibp_limits_screen()

    def get_therapy_duration_minutes(self) -> int:
        return self._get_treatment_start().get_therapy_duration_minutes()

    def get_remaining_therapy_minutes(self) -> float:
        return self._get_treatment_start().get_remaining_therapy_minutes()

    def _get_profile_coordinator(self) -> ProfileCoordinator:
        coordinator = getattr(self, "_profile_coordinator", None)
        if coordinator is None:
            coordinator = ProfileCoordinator(self)
            self._profile_coordinator = coordinator
        return coordinator

    @property
    def profile_coordinator(self) -> ProfileCoordinator:
        return self._get_profile_coordinator()

    @profile_coordinator.setter
    def profile_coordinator(self, value):
        self._profile_coordinator = value

    def can_configure_conductivity_profile(self, allow_disable: bool = False) -> tuple[bool, str]:
        return self._get_profile_coordinator().can_configure_conductivity_profile(allow_disable)

    def is_conductivity_profile_active(self) -> bool:
        return self._get_profile_coordinator().is_conductivity_profile_active()

    def set_conductivity_profile(self, profile: ConductivityProfile, show_message: bool = False) -> bool:
        return self._get_profile_coordinator().set_conductivity_profile(profile, show_message)

    def disable_conductivity_profile(self, show_message: bool = False) -> bool:
        return self._get_profile_coordinator().disable_conductivity_profile(show_message)

    # ────────────────────────────────────────────────
    #              Perfil de Ultrafiltración (UF)
    # ────────────────────────────────────────────────

    def can_configure_uf_profile(self, allow_disable: bool = False) -> tuple[bool, str]:
        return self._get_profile_coordinator().can_configure_uf_profile(allow_disable)

    def is_uf_profile_active(self) -> bool:
        return self._get_profile_coordinator().is_uf_profile_active()

    def set_uf_profile(self, profile: UFProfile, show_message: bool = False) -> bool:
        return self._get_profile_coordinator().set_uf_profile(profile, show_message)

    def disable_uf_profile(self, show_message: bool = False) -> bool:
        return self._get_profile_coordinator().disable_uf_profile(show_message)

    # ────────────────────────────────────────────────
    #              Utility Methods
    # ────────────────────────────────────────────────
    def _get_master_clock(self) -> MasterClock:
        clock = getattr(self, "_master_clock", None)
        if clock is None:
            clock = MasterClock(self)
            self._master_clock = clock
        return clock

    def _master_timer_tick(self):
        return self._get_master_clock()._master_timer_tick()

    def _coerce_heparin_auto_stop_seconds(self) -> int:
        return self._get_heparin_coordinator()._coerce_heparin_auto_stop_seconds()

    def set_heparin_infusion_enabled(self, enabled: bool):
        return self._get_heparin_coordinator().set_heparin_infusion_enabled(enabled)

    # ============================================================
    # MÉTODOS DE NAVEGACIÓN MEJORADOS
    # ============================================================

    def _apply_home_chrome(self, *_):
        """En Inicio oculta los indicadores del header (deja solo logos) y deja solo Resumen Terapia/Diálisis y Servicio en la barra."""
        return self._get_main_shell()._apply_home_chrome(*_)

    def _on_treatment_mode_label_click(self):
        return self._get_main_shell()._on_treatment_mode_label_click()

    def _update_treatment_mode_label_state(self):
        return self._get_main_shell()._update_treatment_mode_label_state()

    def _get_current_screen_nav_text(self) -> str:
        """Devuelve el texto del botón de navegación correspondiente a la pantalla actual."""
        return self._get_main_shell()._get_current_screen_nav_text()

    def _highlight_active_nav_button(self, active_button_text: str):
        """Resalta el botón activo y restaura el resto."""
        return self._get_main_shell()._highlight_active_nav_button(active_button_text)

    def _refresh_navigation_bar(self):
        """Lógica centralizada y clara según especificación del usuario"""
        return self._get_main_shell()._refresh_navigation_bar()

    def _handle_disconnected_state(self):
        """Estado sin conexión"""
        return self._get_main_shell()._handle_disconnected_state()

    def _update_buttons_state(self):
        return self._get_main_shell()._update_buttons_state()

    def _can_start_treatment(self) -> bool:
        return self._get_treatment_start()._can_start_treatment()

    
    def _start_filter(self):
        return self._get_treatment_start()._start_filter()

    def _reset_filter_fill_flags(self):
        return self._get_treatment_start()._reset_filter_fill_flags()

    def _update_header_during_filter_fill(self):
        return self._get_treatment_start()._update_header_during_filter_fill()

    def _set_button_style(self, button: QPushButton, style_type: str):
        """Aplica estilos predefinidos a los botones"""
        return self._get_main_shell()._set_button_style(button, style_type)

    def _get_connection_presence(self) -> ConnectionPresence:
        presence = getattr(self, "_connection_presence", None)
        if presence is None:
            presence = ConnectionPresence(self)
            self._connection_presence = presence
        return presence

    def _set_ui_connected_state(self, is_connected: bool):
        return self._get_connection_presence()._set_ui_connected_state(is_connected)


    def _get_cleaning_session(self) -> CleaningSession:
        session = getattr(self, "_cleaning_session", None)
        if session is None:
            session = CleaningSession(self)
            self._cleaning_session = session
        return session

    def _handle_cleaning_status_change(self, is_cleaning_active: bool):
        return self._get_cleaning_session()._handle_cleaning_status_change(is_cleaning_active)

    def _set_cleaning_start_time(self):
        return self._get_cleaning_session()._set_cleaning_start_time()

    def pause_cleaning_timer(self):
        return self._get_cleaning_session().pause_cleaning_timer()

    def resume_cleaning_timer(self):
        return self._get_cleaning_session().resume_cleaning_timer()

    def handleGlobalValueChange(self, tag: str, value: float):
        return self._get_active_alarms().handleGlobalValueChange(tag, value)

    def _sync_alarm_values_from_current_state(self):
        return self._get_active_alarms()._sync_alarm_values_from_current_state()

    def update_date_time(self):
        return self._get_main_shell().update_date_time()

    def _get_telemetry_inlet(self) -> TelemetryInlet:
        inlet = getattr(self, "telemetry_inlet", None)
        if inlet is None:
            inlet = TelemetryInlet(self)
            self.telemetry_inlet = inlet
        return inlet

    def update_value(self, tag: str, value: float):
        return self._get_telemetry_inlet().update_value(tag, value)

    def _get_temperature_display_value(self):
        return self._get_telemetry_inlet()._get_temperature_display_value()

    def _update_gauges(self):
        return self._get_side_indicators()._update_gauges()
   


    def refresh_alarms_label(self):
        """
        Reutiliza status_label para mostrar conexión/estado/alarmas.
        """
        return self._get_main_shell().refresh_alarms_label()

    def refresh_treatment_selected(self):
        return self._get_main_shell().refresh_treatment_selected()

    def update_remaining_time_header(self, remaining_str: str):
        return self._get_main_shell().update_remaining_time_header(remaining_str)

    def update_alarm_system_monitor_config(self):
        return self._get_active_alarms().update_alarm_system_monitor_config()

    
    def _get_active_alarms(self) -> ActiveAlarms:
        alarms = getattr(self, "_active_alarms_handler", None)
        if alarms is None:
            alarms = ActiveAlarms(self)
            self._active_alarms_handler = alarms
        return alarms

    def handle_alarm(self, idx, active, value, name, level, limits):
        return self._get_active_alarms().handle_alarm(idx, active, value, name, level, limits)

    # ────────────────────────────────────────────────
    #              LED Bar Logic
    # ────────────────────────────────────────────────

    def _get_operator_alerts(self) -> OperatorAlerts:
        alerts = getattr(self, "operator_alerts", None)
        if alerts is None:
            alerts = OperatorAlerts(self)
            self.operator_alerts = alerts
        return alerts

    def begin_operator_alert(self, level: str = "warning"):
        return self._get_operator_alerts().begin_operator_alert(level)

    def end_operator_alert(self):
        return self._get_operator_alerts().end_operator_alert()

    def update_led_bar_state(self):
        return self._get_operator_alerts().update_led_bar_state()

#==============================inicio de codigo de prueba========================

    def show_operator_message(self, text: str, level: str = "info", timeout_ms: int = 4000):
        return self._get_operator_alerts().show_operator_message(text, level, timeout_ms)


# ====================== MÉTODOS DE MENSAJES FLOTANTES ======================
    def _can_show_operator_toast(self, text: str, level: str) -> bool:
        return self._get_operator_alerts()._can_show_operator_toast(text, level)

    def _get_or_create_floating_msg(self) -> FloatingMessage:
        return self._get_operator_alerts()._get_or_create_floating_msg()

    def show_floating_message(self, text: str, timeout_ms: int = 3800):
        return self._get_operator_alerts().show_floating_message(text, timeout_ms)

    def show_success_message(self, text: str, timeout_ms: int = 4000):
        return self._get_operator_alerts().show_success_message(text, timeout_ms)

    def show_info_message(self, text: str, timeout_ms: int = 3800):
        return self._get_operator_alerts().show_info_message(text, timeout_ms)

    def show_warning_message(self, text: str, timeout_ms: int = 4500):
        return self._get_operator_alerts().show_warning_message(text, timeout_ms)
    
    def show_error_message(self, text: str, timeout_ms: int = 5000):
        return self._get_operator_alerts().show_error_message(text, timeout_ms)
    
    def show_catalog_message(self, clave: str, **campos):
        return self._get_operator_alerts().show_catalog_message(clave, **campos)

    def _show_catalog_dialog(self, texto: str):
        return self._get_operator_alerts()._show_catalog_dialog(texto)

    def update_connection_status(self):
        return self._get_connection_presence().update_connection_status()

    def log_event(self, event, value, timestamp):
        logger.error(f"[EVENT] {timestamp} → {event}")

    def __del__(self):
        return self._get_app_shutdown().on_del()


    def _get_app_shutdown(self) -> AppShutdown:
        shutdown_handler = getattr(self, "_app_shutdown", None)
        if shutdown_handler is None:
            shutdown_handler = AppShutdown(self)
            self._app_shutdown = shutdown_handler
        return shutdown_handler

    def shutdown(self):
        return self._get_app_shutdown().shutdown()

    # ====================== MÉTODOS DE LOGGING ======================

    def _get_session_recorder(self) -> SessionRecorder:
        recorder = getattr(self, "_session_recorder", None)
        if recorder is None:
            recorder = SessionRecorder(self)
            self._session_recorder = recorder
        return recorder

    def _prepare_log_data(self, values_dict: dict) -> dict:
        return self._get_session_recorder()._prepare_log_data(values_dict)

    def _log_current_data(self):
        return self._get_session_recorder()._log_current_data()

    def _log_treatment_current_data(self):
        return self._get_session_recorder()._log_treatment_current_data()

    def _start_cleaning_logger(self):
        return self._get_session_recorder()._start_cleaning_logger()

    def _stop_cleaning_logger(self):
        return self._get_session_recorder()._stop_cleaning_logger()

    def _log_cleaning_current_data(self):
        return self._get_session_recorder()._log_cleaning_current_data()


    # ====================== ESCRITURA HACIA HARDWARE ======================

    def _get_firmware_gateway(self) -> FirmwareGateway:
        gateway = getattr(self, "_firmware_gateway", None)
        if gateway is None:
            gateway = FirmwareGateway(self)
            self._firmware_gateway = gateway
        return gateway

    def _write_setpoint(self, tag: str, value: float):
        if tag in LOCAL_SETPOINT_TAGS:
            return self._get_heparin_coordinator().write_local_setpoint(tag, value)
        return self._get_firmware_gateway()._write_setpoint(tag, value)

    def _build_therapy_config_payload(self) -> dict:
        return self._get_firmware_gateway()._build_therapy_config_payload()

    def _save_therapy_config_json(self):
        return self._get_firmware_gateway()._save_therapy_config_json()

    def _persist_therapy_config_tag(self, tag: str, value: float):
        return self._get_firmware_gateway()._persist_therapy_config_tag(tag, value)

    def _load_therapy_config_json(self):
        return self._get_firmware_gateway()._load_therapy_config_json()

    def _to_firmware_setpoint_value(self, tag: str, user_value: float) -> float:
        return self._get_firmware_gateway()._to_firmware_setpoint_value(tag, user_value)

    def _apply_therapy_config_to_firmware(self, force: bool = False):
        return self._get_firmware_gateway()._apply_therapy_config_to_firmware(force)

    def _write_boolean_command(self, tag: str, state: bool):
        return self._get_firmware_gateway()._write_boolean_command(tag, state)

    def _emit_pressure_alarm_limits(
        self,
        art_min,
        art_max,
        ven_min,
        ven_max,
        ptm_min,
        ptm_max,
        water_min=None,
        water_max=None,
        cond_min=None,
        cond_max=None,
    ):
        return self._get_firmware_gateway()._emit_pressure_alarm_limits(
            art_min,
            art_max,
            ven_min,
            ven_max,
            ptm_min,
            ptm_max,
            water_min=water_min,
            water_max=water_max,
            cond_min=cond_min,
            cond_max=cond_max,
        )

    def _write_pressure_limits_on_connection(self):
        return self._get_firmware_gateway()._write_pressure_limits_on_connection()

    def _resolve_tag(self, tag: str) -> tuple[int | None, int | None]:
        return self._get_firmware_gateway()._resolve_tag(tag)
    
    #===============================FIN ESCRITURA A HARDWARE===============================


    def on_pattern_data(self, tag: str, value: float):
        return self._get_telemetry_inlet().on_pattern_data(tag, value)

    # Código de prueba para el sensor de Conductividad (MegaCond), si esta conectada la tarjeta mega y no el patron, 
    # asigna los valores a VARIABLES[0x0C] y a current_values
    def on_mega_cond_data(self, tag: str, value: float):
        return self._get_telemetry_inlet().on_mega_cond_data(tag, value)

    def _get_comm_binding(self) -> CommBinding:
        binding = getattr(self, "_comm_binding", None)
        if binding is None:
            binding = CommBinding(self)
            self._comm_binding = binding
        return binding

    def handle_comm_config_change(self, sensor_id, port, is_enabled, simulation_enabled=False):
        return self._get_comm_binding().handle_comm_config_change(
            sensor_id, port, is_enabled, simulation_enabled=simulation_enabled
        )

    def _load_nibp_config_and_apply(self):
        return self._get_nibp_coordinator()._load_nibp_config_and_apply()

    def _on_nibp_connected_changed(self, connected: bool, port: str):
        return self._get_nibp_coordinator()._on_nibp_connected_changed(connected, port)

    def _on_nibp_error_message(self, error_code: str, error_text: str):
        return self._get_nibp_coordinator()._on_nibp_error_message(error_code, error_text)

    def _on_nibp_measurement_ready(self, sys_mmhg: int, dia_mmhg: int, map_mmhg: int, hr_bpm: int):
        return self._get_nibp_coordinator()._on_nibp_measurement_ready(sys_mmhg, dia_mmhg, map_mmhg, hr_bpm)

    def _on_nibp_measure_requested_for_history(self):
        return self._get_nibp_coordinator()._on_nibp_measure_requested_for_history()

    def _on_nibp_measurement_ready_for_history(self, sys_mmhg: int, dia_mmhg: int, map_mmhg: int, hr_bpm: int):
        return self._get_nibp_coordinator()._on_nibp_measurement_ready_for_history(sys_mmhg, dia_mmhg, map_mmhg, hr_bpm)

    def _on_spo2_updated_for_tracker(self, data: dict):
        return self._get_nibp_coordinator()._on_spo2_updated_for_tracker(data)

    def _on_nibp_settings_applied(self, config: dict):
        return self._get_nibp_coordinator()._on_nibp_settings_applied(config)

    def _on_nibp_reset_requested(self):
        return self._get_nibp_coordinator()._on_nibp_reset_requested()

    # ====================== PERSISTENCIA DE HORAS DE HARDWARE ======================


    def _load_histories(self):
        return self._get_session_recorder()._load_histories()

    def _save_history_to_file(self, file_path: str | Path, history_data: list, label: str):
        return self._get_session_recorder()._save_history_to_file(file_path, history_data, label)

    def _save_treatment_history(self):
        return self._get_session_recorder()._save_treatment_history()

    def _save_cleaning_history(self):
        return self._get_session_recorder()._save_cleaning_history()

    def _validate_session(self, start_time: QDateTime, end_time: QDateTime) -> bool:
        return self._get_session_recorder()._validate_session(start_time, end_time)

    def register_treatment_session(self):
        return self._get_session_recorder().register_treatment_session()

    def build_current_clinical_report(
        self,
        completion_status: str = "En curso / Vista previa",
        start_time_str: str = None,
        end_time_str: str = None,
        override_elapsed_s: float = None,
    ) -> dict:
        return self._get_session_recorder().build_current_clinical_report(
            completion_status=completion_status,
            start_time_str=start_time_str,
            end_time_str=end_time_str,
            override_elapsed_s=override_elapsed_s,
        )


    def finish_cleaning_session(self, active_duration_seconds: float):
        return self._get_session_recorder().finish_cleaning_session(active_duration_seconds)


    def register_cleaning_session_with_duration(self, duration_seconds: float):
        return self._get_session_recorder().register_cleaning_session_with_duration(duration_seconds)
        


        
    def register_cleaning_session(self):
        return self._get_session_recorder().register_cleaning_session()

    @property
    def session_recorder(self) -> SessionRecorder:
        return self._get_session_recorder()

    @session_recorder.setter
    def session_recorder(self, value):
        self._session_recorder = value

    @property
    def unclean_close(self) -> SessionRecorder:
        return self._get_session_recorder()
        

    def _show_exit_confirmation(self):
        return self._get_app_shutdown()._show_exit_confirmation()

    def closeEvent(self, event):
        return self._get_app_shutdown().closeEvent(event)



