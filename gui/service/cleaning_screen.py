from gui.theme_manager import ThemeManager
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QProgressBar, QVBoxLayout, QHBoxLayout,
    QSizePolicy, QFrame, QButtonGroup, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, Signal, QElapsedTimer
import logging
import json
import os
from utilities.platform_runtime import get_runtime_config_path, safe_json_load

# Suponiendo que estos módulos existen en tu estructura de proyecto
from logic.calculos import convertir_flujo_a_ciclos
from core.state_manager import TreatmentPhase
from gui.components.floating_confirm import FloatingConfirmDialog

logger = logging.getLogger(__name__)

# Define constantes para las rutas de archivo y configuración
CONFIG_FILE_PATH = get_runtime_config_path("cleaning_config.json")

# Asegura que el directorio de configuración exista
CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

# Estructura de configuración por defecto
DEFAULT_CONFIG = {
    "modes": {
        "0.0": { # Desinfección Química Corta
            "time_hours": 0,
            "time_minutes": 15,
            "mode_temp": 35.0,
            "mode_flow": 100.0
        },
        "1.0": { # Desinfección Química Larga
            "time_hours": 0,
            "time_minutes": 30,
            "mode_temp": 40.0,
            "mode_flow": 120.0
        }
    }
}


class CleaningScreen(QWidget):
    request_setpoint_change = Signal(str, float)
    request_boolean_change = Signal(str, bool)
    cleaning_active_changed = Signal(bool)

    # NUEVAS SEÑALES para comunicar el estado de conteo a TimerManager
    cleaning_started_counting = Signal() # Se emite cuando CleaningScreen entra en fase ACTIVE
    cleaning_stopped_counting = Signal() # Se emite cuando CleaningScreen sale de fase ACTIVE (pause, finish, stop)

    def __init__(self, parent=None, values_dict=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_values = values_dict if values_dict is not None else {}

        # ==================== ESTADOS DE LA PANTALLA ====================
        # Define las fases del proceso de limpieza para el control interno de la UI
        # Fases: IDLE, PREPARING, ACTIVE, PAUSED, FINISHED, STOPPED
        self.cleaning_phase = "IDLE"
        self.cleaning_in_progress = False # True si hay una limpieza en cualquier fase activa (PREPARING, ACTIVE, PAUSED)
        
        self.cleaning_timer_started = False    # Indica si el QElapsedTimer para la duración ha iniciado
        self.cleaning_active_duration = 0.0    # Tiempo total acumulado de limpieza activa (segundos)

        # Timer de alta precisión para rastrear la duración activa real de la limpieza
        self.active_elapsed_timer = QElapsedTimer()

        self.mid_pause_done = False # True si la pausa a mitad de proceso ya ocurrió
        self.waiting_for_line_change_confirmation = False # True si el diálogo de cambio de línea está abierto y bloqueando

        self.selected_mode = None # Almacena 0.0 para Corta, 1.0 para Larga

        self.total_time_seconds = 0      # Tiempo total configurado para el modo seleccionado
        self.remaining_time_seconds = 0  # Tiempo restante de la cuenta regresiva

        # QTimer para la barra de progreso y la cuenta regresiva de la UI
        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(1000) # Se actualiza cada segundo
        self.progress_timer.timeout.connect(self._update_progress)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background: #0f172a;")

        self.setup_ui()
        self.apply_theme_styles()
        try:
            ThemeManager.instance().theme_changed.connect(lambda _t: self.apply_theme_styles())
        except Exception:
            pass
        self._load_config_defaults_if_needed() # Asegura que el archivo de configuración exista
        self._reset_to_initial_state()        # Inicializa la UI y el estado de forma limpia

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(60, 40, 60, 40)
        main_layout.setSpacing(30)

        self.title_label = QLabel("Limpieza / Desinfección")
        self.title_label.setStyleSheet("color: #cbd5e1; font-size: 52px; font-weight: bold; background: transparent;")
        self.title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.title_label)

        # Frame para Selección de Modo
        self.mode_frame = QFrame()
        self.mode_frame.setStyleSheet("background: #fcfcfc; border-radius: 10px;")
        mode_layout = QHBoxLayout(self.mode_frame)
        mode_layout.setContentsMargins(15, 12, 15, 12)
        mode_layout.setSpacing(20)

        self.btn_mode_group = QButtonGroup(self)
        self.btn_mode_group.setExclusive(True) # Solo un botón puede estar seleccionado a la vez

        self.btn_short = QPushButton("Desinfección Química Corta")
        self.btn_long = QPushButton("Desinfección Química Larga")
        self.btn_short.setFixedHeight(75)
        self.btn_long.setFixedHeight(75)
        self.btn_short.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_long.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Estilos de los botones para los modos de limpieza
        self.style_unchecked = """
            QPushButton {
                background: #3b82f6; color: #ffffff; font-size: 24px; font-weight: bold;
                border-radius: 12px; padding: 6px 16px; border: 2px solid #2563eb;
            }
            QPushButton:hover { background: #60a5fa; }
        """
        self.style_checked = """
            QPushButton {
                background: #22c55e; color: #ffffff; font-size: 24px; font-weight: bold;
                border-radius: 12px; padding: 6px 16px; border: 2px solid #16a34a;
            }
        """
        self.style_disabled = """
            QPushButton {
                background: #334155; color: #64748b; font-size: 24px; font-weight: bold;
                border-radius: 12px; padding: 6px 16px; border: 2px solid #475569;
            }
        """

        for btn, mode_val in [(self.btn_short, 0.0), (self.btn_long, 1.0)]:
            btn.setStyleSheet(self.style_unchecked)
            btn.setCheckable(True)
            # Conexión del evento `toggled` para manejar el cambio de selección de modo
            btn.toggled.connect(lambda checked, b=btn, val=mode_val: self._on_mode_toggled(b, val, checked))
            mode_layout.addWidget(btn)
            self.btn_mode_group.addButton(btn)

        main_layout.addWidget(self.mode_frame)

        # Etiqueta para mostrar la fase actual de la limpieza
        self.phase_label = QLabel("Esperando selección de modo...")
        self.phase_label.setStyleSheet("color: #94a3b8; font-size: 32px; font-weight: bold; background: transparent; min-height: 60px;")
        self.phase_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.phase_label)

        # Barra de Progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(1) # Valor inicial para evitar división por cero
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("0% - 0/0 seg")
        self.progress_bar.setFixedHeight(60)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #1e293b; border: 2px solid #475569; border-radius: 10px;
                text-align: center; color: #ffffff; font-size: 24px; font-weight: bold;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #60a5fa);
                border-radius: 8px;
            }
        """)
        main_layout.addWidget(self.progress_bar)

        # Etiquetas para mostrar la configuración del modo seleccionado
        self.time_label = QLabel("Tiempo configurado: --:--")
        self.temp_label = QLabel("Temperatura configurada: 0.0 °C")
        self.flow_label = QLabel("Flujo configurado: 0.0 ml/min")
        for lbl in [self.time_label, self.temp_label, self.flow_label]:
            lbl.setStyleSheet("color: #cbd5e1; font-size: 28px; font-weight: bold; background: transparent;")
            lbl.setAlignment(Qt.AlignCenter)
            main_layout.addWidget(lbl)

        main_layout.addStretch()

        # Botones de Inicio y Detención
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.start_button = QPushButton("Iniciar")
        self.start_button.setFixedSize(300, 100)
        self.start_button.setEnabled(False) # Deshabilitado inicialmente
        self.start_button.setStyleSheet("""
            QPushButton {
                background: #047857; color: #ffffff; font-size: 38px; font-weight: bold;
                border: none; border-radius: 16px; padding: 10px;
            }
            QPushButton:hover { background: #065f46; }
            QPushButton:disabled { background: #334155; color: #64748b; }
        """)
        self.start_button.clicked.connect(self._start_cleaning)
        button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Detener")
        self.stop_button.setFixedSize(300, 100)
        self.stop_button.setEnabled(False) # Deshabilitado inicialmente
        self.stop_button.setStyleSheet("""
            QPushButton {
                background: #dc2626; color: #ffffff; font-size: 38px; font-weight: bold;
                border: none; border-radius: 16px; padding: 10px;
            }
            QPushButton:hover { background: #b91c1c; }
            QPushButton:disabled { background: #334155; color: #64748b; }
        """)
        self.stop_button.clicked.connect(self._stop_cleaning)
        button_layout.addWidget(self.stop_button)

        button_layout.addStretch()
        main_layout.addLayout(button_layout)

    def _load_config_defaults_if_needed(self):
        """
        Asegura que el archivo de configuración exista y contenga las configuraciones
        por defecto para los modos de limpieza.
        """
        if not os.path.exists(CONFIG_FILE_PATH):
            logger.info(f"Archivo de configuración no encontrado en {CONFIG_FILE_PATH}. Creando con valores por defecto.")
            try:
                with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                    json.dump(DEFAULT_CONFIG, f, indent=4)
            except IOError as e:
                logger.error(f"Error al crear el archivo de configuración por defecto: {e}")
                self.config_data = DEFAULT_CONFIG # Usar configuración por defecto en memoria
                return

        try:
            config_data = safe_json_load(CONFIG_FILE_PATH, {})
            if not isinstance(config_data, dict):
                raise ValueError("La configuración de limpieza no es un objeto JSON válido.")

            if "modes" not in config_data or not isinstance(config_data["modes"], dict):
                config_data["modes"] = {}
            for mode_key, default_mode_config in DEFAULT_CONFIG["modes"].items():
                if mode_key not in config_data["modes"]:
                    config_data["modes"][mode_key] = default_mode_config

            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
            self.config_data = config_data
        except (TypeError, ValueError, IOError) as e:
            logger.error(f"Error al cargar o parsear el archivo de configuración: {e}. Usando configuración por defecto.")
            self.config_data = DEFAULT_CONFIG

    def _on_mode_toggled(self, button: QPushButton, mode_value: float, checked: bool):
        """
        Maneja el evento de selección/deselección de los botones de modo.
        Controla la habilitación del botón "Iniciar" y la carga de la configuración.
        """
        if self.cleaning_in_progress:
            # Impide cambiar el modo mientras la limpieza está activa
            button.blockSignals(True)
            button.setChecked(not checked) # Revertir el estado de marcado
            button.blockSignals(False)
            self.parent_window.show_warning_message("No se puede cambiar el modo mientras la limpieza está en curso.", 3000)
            return

        if checked:
            button.setStyleSheet(self.style_checked)
            self.selected_mode = mode_value
            self._load_mode_specific_configuration(mode_value)
            self.start_button.setEnabled(True)
            self.start_button.setText("Iniciar") # Asegura que el texto sea "Iniciar" al seleccionar un nuevo modo
        else: # Este bloque se ejecuta si se desmarca un botón (ej. al seleccionar otro en un QButtonGroup exclusivo)
            if self.selected_mode == mode_value: # Solo si el modo desmarcado era el actualmente seleccionado
                button.setStyleSheet(self.style_unchecked)
                self.selected_mode = None
                self._update_config_display_labels_to_default() # Resetear labels a valores por defecto
                self.start_button.setEnabled(False)
                self.start_button.setText("Iniciar")

    def _load_mode_specific_configuration(self, mode_value: float):
        """
        Carga y aplica la configuración específica para el modo de limpieza seleccionado.
        Actualiza las etiquetas de la UI y emite los comandos de setpoint al controlador.
        """
        mode_config = self.config_data.get("modes", {}).get(str(mode_value))
        if not mode_config:
            logger.warning(f"Configuración para el modo {mode_value} no encontrada. Usando valores por defecto para mostrar.")
            mode_config = DEFAULT_CONFIG["modes"].get(str(mode_value), DEFAULT_CONFIG["modes"]["0.0"]) # Fallback a cortos por defecto

        hours = mode_config.get("time_hours", 0)
        minutes = mode_config.get("time_minutes", 15)
        temp = mode_config.get("mode_temp", 35.0)
        flow = mode_config.get("mode_flow", 100.0)

        self.total_time_seconds = (hours * 3600) + (minutes * 60)
        self.remaining_time_seconds = self.total_time_seconds

        # Emitir setpoints al controlador (configuración del hardware)
        self.on_user_input_setpoint("heparineTherapyHours", float(hours))
        self.on_user_input_setpoint("heparineTherapyMinutes", float(minutes))
        self.on_user_input_setpoint("dialyTempControlSetPoint", float(temp))
        self._handle_cb_flow_input(flow)

        # Actualizar la UI
        self.time_label.setText(f"Tiempo configurado: {hours:02d}:{minutes:02d}")
        self.temp_label.setText(f"Temperatura configurada: {temp:.1f} °C")
        self.flow_label.setText(f"Flujo configurado: {flow:.1f} ml/min")
        self.progress_bar.setMaximum(self.total_time_seconds if self.total_time_seconds > 0 else 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f"0% - 0/{self.total_time_seconds} seg")

    def _update_config_display_labels_to_default(self):
        """Resetea las etiquetas de tiempo/temperatura/flujo a su estado por defecto sin selección."""
        self.time_label.setText("Tiempo configurado: --:--")
        self.temp_label.setText("Temperatura configurada: 0.0 °C")
        self.flow_label.setText("Flujo configurado: 0.0 ml/min")
        self.progress_bar.setMaximum(1)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("0% - 0/0 seg")

    def _handle_cb_flow_input(self, value: float):
        if value is None: return
        try:
            cycles_value = convertir_flujo_a_ciclos(value)
            self.on_user_input_setpoint("balanceChamberSetTiming", cycles_value)
        except Exception as e:
            logger.error(f"Error convirtiendo flujo a ciclos: {e}")

    # ====================== GRAFCET: INICIO ======================
    def _start_cleaning(self):
        """Inicia el proceso de limpieza."""
        if self.selected_mode is None:
            self.parent_window.show_warning_message("Seleccione un modo de desinfección antes de iniciar.", 2000)
            return

        # Asegura que la configuración para el modo seleccionado esté cargada
        self._load_mode_specific_configuration(self.selected_mode)

        # Protección: evita iniciar un ciclo que terminaría de inmediato.
        if self.total_time_seconds <= 0:
            self.parent_window.show_warning_message("El tiempo configurado de limpieza es 0. Ajuste la configuración.", 3500)
            logger.warning("Intento de iniciar limpieza con duración 0 segundos.")
            return

        # ET2: Preparación (antes de que la infusión del hardware comience)
        self.cleaning_phase = "PREPARING"
        self.cleaning_in_progress = True
        self.cleaning_timer_started = False # El QElapsedTimer aún no ha iniciado
        self.cleaning_active_duration = 0.0
        self.mid_pause_done = False
        self.waiting_for_line_change_confirmation = False # No estamos esperando confirmación al inicio

        self.cleaning_active_changed.emit(True) # Notifica al padre/state manager que la limpieza está iniciando

        try:
            # Enviar comandos para iniciar la secuencia de limpieza del hardware
            self.on_user_input_setpoint("treatmentModeSelection", 3.0) # Establecer modo de limpieza en el hardware
            self.on_user_boolean_command("dialyStartDialysisButt", True)
            self.on_user_boolean_command("dialyStopDialysisButt", False)

            self.phase_label.setText("Preparando sistema para desinfección...")
            self.phase_label.setStyleSheet("color: #facc15; font-size: 32px; font-weight: bold;")

            # Deshabilitar elementos de la UI durante el proceso activo
            self.start_button.setEnabled(False)
            self.start_button.setText("Iniciando...")
            self.stop_button.setEnabled(True)
            self.btn_short.setEnabled(False)
            self.btn_long.setEnabled(False)
            self.btn_short.setStyleSheet(self.style_disabled)
            self.btn_long.setStyleSheet(self.style_disabled)

        except Exception as e:
            logger.error(f"Error al iniciar limpieza: {e}")
            self._reset_to_initial_state() # Resetear la UI en caso de error

    # ====================== GRAFCET: TRANSICIÓN A ACTIVO (Infusión del Hardware) ======================
    def _start_real_cleaning_timer(self):
        """
        Se llama cuando `primingProcessStatus == 6` (estado de infusión) es detectado
        Y la pantalla está en fase "PREPARING" (inicio o reanudación confirmada por el usuario).
        Inicia o reanuda la cuenta regresiva de la UI y el conteo de duración activa.
        """
        # Si la fase ya es ACTIVE, no hay nada que hacer.
        if self.cleaning_phase == "ACTIVE":
            return

        self.cleaning_phase = "ACTIVE"
        self.cleaning_timer_started = True

        # Iniciar o reiniciar el temporizador de alta precisión para la duración activa acumulada
        if not self.active_elapsed_timer.isValid():
            self.active_elapsed_timer.start()
            
        else:
            self.active_elapsed_timer.restart() # Reiniciar para contar el nuevo segmento de tiempo activo

        self.phase_label.setText("Desinfección química en curso...")
        self.phase_label.setStyleSheet("color: #22c55e; font-size: 32px; font-weight: bold;")

        # Iniciar el temporizador de cuenta regresiva de la UI si no está activo
        if not self.progress_timer.isActive():
            self.progress_timer.start() # Usa el intervalo configurado (1000ms)
            logger.info("Progress timer RE-INICIADO.")
        self._update_time_display() # Actualizar inmediatamente la UI

        # **** EMITIR SEÑAL para que TimerManager comience a contar ****
        self.cleaning_started_counting.emit()
        logger.debug("cleaning_started_counting signal emitted.")


    # ====================== GRAFCET: ACTUALIZACIÓN DE PROGRESO ======================
    def _update_progress(self):
        """
        Decrementa el tiempo restante y actualiza la barra de progreso.
        Maneja la pausa a mitad de proceso.
        Esta función solo se ejecuta si `self.progress_timer` está activo.
        """
        if self.cleaning_phase != "ACTIVE":
            # Esto es una salvaguarda; idealmente, no debería ser llamado si no está en fase ACTIVE
            # Pero asegura que el timer de la UI se detenga si por alguna razón sigue activo.
            self.progress_timer.stop()
            self.cleaning_stopped_counting.emit() # Asegurar que TimerManager también pare
            logger.warning(f"Progress timer corriendo en fase incorrecta ({self.cleaning_phase}). Detenido.")
            return

        if self.remaining_time_seconds > 0:
            self.remaining_time_seconds -= 1
            self.progress_bar.setValue(self.total_time_seconds - self.remaining_time_seconds)
            self._update_time_display()

            # Transición a pausa intermedia (a la mitad del tiempo)
            if not self.mid_pause_done and self.total_time_seconds > 0 and \
               self.remaining_time_seconds <= self.total_time_seconds // 2:
                logger.info(f"Punto medio alcanzado. Iniciando pausa para cambio de línea. Tiempo restante: {self.remaining_time_seconds}")
                self._pause_for_line_change()
                return # Salir para evitar más decrementos de tiempo en este ciclo
        else:
            # Limpieza completada
            logger.info("Tiempo de limpieza agotado. Finalizando limpieza.")
            self.progress_timer.stop()
            self._finish_cleaning()

    def _pause_for_line_change(self):
        """ET4: Pausa obligatoria para cambio de línea."""
        parent = self.parent_window if self.parent_window is not None else self
        if self.mid_pause_done or getattr(parent, "_operator_dialog_open", False):
            logger.debug("Diálogo de cambio de línea suprimido por reentrancia")
            return

        self._accumulate_active_time() # Acumular tiempo activo antes de pausar
        
        # **** EMITIR SEÑAL para que TimerManager PARE de contar ****
        self.cleaning_stopped_counting.emit()
        logger.debug("cleaning_stopped_counting signal emitted for pause.")

        self.cleaning_phase = "PAUSED"
        self.mid_pause_done = True
        self.waiting_for_line_change_confirmation = True # Indica que un diálogo está abierto y bloqueando

        self.progress_timer.stop() # ¡Detener el temporizador de cuenta regresiva de la UI!
        logger.info("Progress timer DETENIDO por pausa intermedia.")

        self.phase_label.setText("PAUSA: Cambie la línea")
        self.phase_label.setStyleSheet("color: #f59e0b; font-size: 34px; font-weight: bold;")

        # Enviar comandos para detener el proceso del hardware (estado de idle)
        self.on_user_boolean_command("dialyStartDialysisButt", False)
        self.on_user_boolean_command("dialyStopDialysisButt", True)

        # Mostrar diálogo de confirmación (BLOQUEANTE)
        parent._operator_dialog_open = True
        try:
            if parent and hasattr(parent, "begin_operator_alert"):
                parent.begin_operator_alert("warning")
            user_confirmed = self._confirm_message(
                "Cambie la línea y presione 'Continuar' para reanudar.",
                "Continuar",
                "Detener",
            )
        finally:
            if parent and hasattr(parent, "end_operator_alert"):
                parent.end_operator_alert()
            parent._operator_dialog_open = False
        
        # Una vez que el diálogo se cierra (el usuario ha hecho una elección)
        if user_confirmed:
            self._resume_cleaning()
        else:
            # El usuario eligió detener la limpieza durante la pausa
            self._stop_cleaning()

    def _resume_cleaning(self):
        """Reanuda el proceso de limpieza después de una pausa intermedia."""
        logger.info("Usuario ha confirmado reanudación. Preparando para reanudar limpieza.")
        self.waiting_for_line_change_confirmation = False # El diálogo ya no está abierto
        
        # Volver a entrar en PREPARING para esperar que el hardware alcance el estado de infusión (primingProcessStatus == 6)
        self.cleaning_phase = "PREPARING"

        self.phase_label.setText("Reanudando... Esperando hardware")
        self.phase_label.setStyleSheet("color: #facc15; font-size: 32px; font-weight: bold;")

        # Enviar comandos para reiniciar el proceso del hardware
        self.on_user_boolean_command("dialyStartDialysisButt", True)
        self.on_user_boolean_command("dialyStopDialysisButt", False)

    def _finish_cleaning(self):
        """Finaliza el proceso de limpieza cuando el tiempo expira."""
        self._accumulate_active_time() # Acumular cualquier tiempo activo restante
        self.progress_timer.stop() # Asegurarse de que el temporizador esté detenido

        # **** EMITIR SEÑAL para que TimerManager PARE de contar ****
        self.cleaning_stopped_counting.emit()
        logger.debug("cleaning_stopped_counting signal emitted for finish.")

        # Enviar comandos para detener el proceso del hardware
        self.on_user_boolean_command("dialyStartDialysisButt", False)
        self.on_user_boolean_command("dialyStopDialysisButt", True)

        self.cleaning_phase = "FINISHED"
        self.cleaning_in_progress = False
        self.cleaning_timer_started = False
        self.cleaning_active_changed.emit(False) # Notificar al padre/state manager que la limpieza ha terminado

        self.phase_label.setText("Limpieza completada ✓")
        self.phase_label.setStyleSheet("color: #6ee7b7; font-size: 36px; font-weight: bold;")

        self.progress_bar.setValue(self.total_time_seconds)
        self._update_time_display() # Mostrar "00:00" para el tiempo restante

        if hasattr(self.parent_window, 'finish_cleaning_session'):
            self.parent_window.finish_cleaning_session(self.cleaning_active_duration)

        # Actualizaciones de la UI para el estado finalizado
        self.start_button.setText("Reiniciar")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        # Re-habilitar botones de selección de modo y seleccionar visualmente el modo completado
        self.btn_short.setEnabled(True)
        self.btn_long.setEnabled(True)
        
        # Necesitamos deshabilitar temporalmente la exclusividad para forzar el estado "checked"
        # sin que se desmarque el otro automáticamente si no hay un toggled real
        self.btn_mode_group.setExclusive(False) 
        if self.selected_mode == 0.0:
            self.btn_short.setChecked(True)
            self.btn_long.setChecked(False)
            self.btn_short.setStyleSheet(self.style_checked)
            self.btn_long.setStyleSheet(self.style_unchecked)
        elif self.selected_mode == 1.0:
            self.btn_long.setChecked(True)
            self.btn_short.setChecked(False)
            self.btn_long.setStyleSheet(self.style_checked)
            self.btn_short.setStyleSheet(self.style_unchecked)
        self.btn_mode_group.setExclusive(True) # Re-habilitar exclusividad

        # Reconectar el botón de inicio para reiniciar el modo actual (que aún está seleccionado)
        try:
            self.start_button.clicked.disconnect()
        except (TypeError, RuntimeError): # RuntimeError para Python 3.11+
            pass
        self.start_button.clicked.connect(self._start_cleaning) # "Reiniciar" implica iniciar el mismo modo

    def _accumulate_active_time(self):
        """
        Acumula tiempo usando QElapsedTimer (alta precisión) antes de pausar o detener.
        """
        # Solo acumular si el temporizador se inició y es válido y no ha expirado (es decir, está corriendo)
        if self.cleaning_timer_started and self.active_elapsed_timer.isValid():
            elapsed_ms = self.active_elapsed_timer.elapsed()
            self.cleaning_active_duration += elapsed_ms / 1000.0
            # Reiniciar el temporizador para el siguiente segmento activo, si lo hay
            self.active_elapsed_timer.restart()
            logger.debug(f"Acumulado {elapsed_ms/1000.0:.2f}s. Duración activa total: {self.cleaning_active_duration:.2f}s")
        elif self.cleaning_timer_started and not self.active_elapsed_timer.isValid():
             logger.warning("QElapsedTimer debería haberse iniciado pero no es válido. Omitiendo acumulación.")


    def _stop_cleaning(self):
        """Detiene el proceso de limpieza y resetea la UI a su estado inicial."""
        logger.info("Deteniendo limpieza por solicitud del usuario.")
        if self.cleaning_in_progress: # Solo acumular si estaba realmente en curso
            self._accumulate_active_time()
        
        self.progress_timer.stop() # Asegurarse de detener el contador de UI

        # **** EMITIR SEÑAL para que TimerManager PARE de contar ****
        self.cleaning_stopped_counting.emit()
        logger.debug("cleaning_stopped_counting signal emitted for stop.")

        self.cleaning_in_progress = False
        self.waiting_for_line_change_confirmation = False # Si estaba esperando, ya no lo está
        self.cleaning_active_changed.emit(False) # Notificar que la limpieza ha terminado/detenido

        try:
            # Enviar comandos para detener el proceso del hardware
            self.on_user_boolean_command("dialyStartDialysisButt", False)
            self.on_user_boolean_command("dialyStopDialysisButt", True)
        except Exception as e:
            logger.error(f"Error enviando comando de paro al hardware: {e}")

        self._reset_to_initial_state() # Realizar un reseteo completo de la UI
        self.parent_window.show_info_message("Limpieza detenida.", 2000)

    def _reset_to_initial_state(self):
        """
        Resetea todas las variables de estado internas y los elementos de la UI a su estado
        inicial por defecto (sin modo seleccionado, botones deshabilitados).
        """
        logger.info("Reseteando UI a estado inicial.")
        self.cleaning_phase = "IDLE"
        self.cleaning_in_progress = False
        self.cleaning_timer_started = False
        self.cleaning_active_duration = 0.0 # Resetear la duración activa total
        self.active_elapsed_timer = QElapsedTimer() # Resetear el temporizador de alta precisión

        self.mid_pause_done = False
        self.waiting_for_line_change_confirmation = False
        self.selected_mode = None

        self.total_time_seconds = 0
        self.remaining_time_seconds = 0

        self.progress_timer.stop()

        self.phase_label.setText("Esperando selección de modo...")
        self.phase_label.setStyleSheet("color: #94a3b8; font-size: 32px; font-weight: bold;")

        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("0% - 0/0 seg")
        self.progress_bar.setMaximum(1) # Asegurar que el máximo no sea 0
        self._update_config_display_labels_to_default()

        # Resetear estado de los botones
        self.start_button.setEnabled(False)
        self.start_button.setText("Iniciar")
        self.stop_button.setEnabled(False)

        # Resetear botones de selección de modo (desmarcarlos y habilitarlos)
        self.btn_mode_group.setExclusive(False) # Deshabilitar exclusividad temporalmente para desmarcar
        self.btn_short.setChecked(False)
        self.btn_long.setChecked(False)
        self.btn_short.setStyleSheet(self.style_unchecked)
        self.btn_long.setStyleSheet(self.style_unchecked)
        self.btn_short.setEnabled(True)
        self.btn_long.setEnabled(True)
        self.btn_mode_group.setExclusive(True) # Re-habilitar exclusividad

        # Asegurar que el botón de inicio esté conectado a la lógica de inicio original
        try:
            self.start_button.clicked.disconnect()
        except (TypeError, RuntimeError): 
            pass
        self.start_button.clicked.connect(self._start_cleaning)

    def _confirm_message(self, message: str, accept_text: str, cancel_text: str) -> bool:
        """Muestra un diálogo de confirmación personalizado."""
        # Usar la ventana padre principal como padre del diálogo para una correcta visualización
        dialog = FloatingConfirmDialog(self.parent_window)
        return dialog.show_confirm(message, accept_text, cancel_text)

    def _update_time_display(self):
        """Actualiza la etiqueta de tiempo y el formato de la barra de progreso."""
        minutes = self.remaining_time_seconds // 60
        seconds = self.remaining_time_seconds % 60
        self.time_label.setText(f"Tiempo restante: {minutes:02d}:{seconds:02d}")

        total_secs = self.total_time_seconds if self.total_time_seconds > 0 else 1
        elapsed_secs = self.total_time_seconds - self.remaining_time_seconds
        percentage = int((elapsed_secs / total_secs) * 100)
        self.progress_bar.setFormat(f"{percentage}% - {elapsed_secs}/{self.total_time_seconds} seg")

    def update_values(self, new_values: dict):
        """
        Recibe valores actualizados del controlador/state manager.
        Este es el punto de entrada principal para cambios de estado externos
        que afectan la lógica de limpieza.
        """
        self.current_values = new_values
        priming_status = int(new_values.get("primingProcessStatus", 0))

        logger.debug(f"CleaningScreen update_values: phase={self.cleaning_phase}, priming_status={priming_status}, in_progress={self.cleaning_in_progress}, waiting_confirm={self.waiting_for_line_change_confirmation}")

        # Lógica para iniciar/reanudar el temporizador de limpieza activa basado en el estado del hardware
        # Esto ocurre cuando:
        # 1. Una limpieza está en progreso (self.cleaning_in_progress es True).
        # 2. El hardware reporta estado de infusión (priming_status == 6).
        # 3. La pantalla está en la fase 'PREPARING', lo que significa que está lista para que el hardware
        #    entre en infusión (ya sea al inicio o después de una reanudación confirmada por el usuario).
        if (self.cleaning_in_progress and
            priming_status == 6 and
            self.cleaning_phase == "PREPARING"): # Solo si la fase es PREPARING (esperando hardware)
            
            logger.info(f"Detectado primingProcessStatus=6 y cleaning_phase='PREPARING'. Transicionando a ACTIVE.")
            self._start_real_cleaning_timer()

        # Blindaje: si estábamos activos y el hardware sale de infusión,
        # se detiene el conteo para no correr desacoplado del estado real.
        if self.cleaning_in_progress and self.cleaning_phase == "ACTIVE" and priming_status != 6:
            logger.warning(
                f"Hardware salió de estado 6 durante limpieza ACTIVE (status={priming_status}). "
                "Pausando conteo hasta nueva confirmación."
            )
            self._accumulate_active_time()
            if self.progress_timer.isActive():
                self.progress_timer.stop()
            self.cleaning_stopped_counting.emit()

            # Si el hardware cayó a espera/fin, cerrar ciclo de limpieza.
            if priming_status in (1, 16):
                self.parent_window.show_warning_message(
                    "Limpieza interrumpida: el hardware salió de infusión.",
                    4000
                )
                self._stop_cleaning()
                return

            # Para estados intermedios (p.ej. 10), volver a PREPARING y esperar reingreso a 6.
            self.cleaning_phase = "PREPARING"
            self.phase_label.setText("Esperando regreso a infusión (estado 6)...")
            self.phase_label.setStyleSheet("color: #facc15; font-size: 32px; font-weight: bold;")
            
        # Asegurar que los estados de los botones de la UI sean consistentes
        # con el progreso general de la limpieza.
        self.update_buttons_state(self.cleaning_in_progress)

    def update_state(self, phase: TreatmentPhase):
        """
        Recibe la fase de tratamiento de alto nivel actualizada del state manager.
        Asegura que CleaningScreen reaccione si el tratamiento cambia fuera de limpieza.
        """
        # Si la fase global NO es limpieza, y nuestra pantalla cree que la limpieza ESTÁ en progreso
        if phase != TreatmentPhase.CLEANING and self.cleaning_in_progress:
            logger.warning(f"La fase de tratamiento cambió a {phase} mientras la limpieza estaba en curso. Deteniendo limpieza.")
            self._stop_cleaning() # Forzar la detención de la limpieza si la fase global ya no es CLEANING
        
        # Si la fase global ES limpieza, asegurar que nuestra pantalla esté preparada
        if phase == TreatmentPhase.CLEANING:
            # Si no hay limpieza activa en esta pantalla Y se ha seleccionado un modo,
            # habilitar el botón de iniciar y los botones de modo.
            if not self.cleaning_in_progress and self.selected_mode is not None:
                self.start_button.setEnabled(True)
                self.btn_short.setEnabled(True)
                self.btn_long.setEnabled(True)
                # Asegurar que el modo seleccionado visualmente esté marcado
                if self.selected_mode == 0.0: self.btn_short.setStyleSheet(self.style_checked)
                elif self.selected_mode == 1.0: self.btn_long.setStyleSheet(self.style_checked)
                # Asegurar que el otro modo esté desmarcado
                if self.selected_mode == 0.0: self.btn_long.setStyleSheet(self.style_unchecked)
                elif self.selected_mode == 1.0: self.btn_short.setStyleSheet(self.style_unchecked)
                
            elif self.cleaning_in_progress: # Si la limpieza está en curso, deshabilitar modos y habilitar detener
                 self.start_button.setEnabled(False)
                 self.stop_button.setEnabled(True)
                 self.btn_short.setEnabled(False)
                 self.btn_long.setEnabled(False)
                 self.btn_short.setStyleSheet(self.style_disabled)
                 self.btn_long.setStyleSheet(self.style_disabled)
        else: # No está en fase de limpieza global
            if not self.cleaning_in_progress: # Solo si nuestro estado local no es de limpieza activa
                # Resetear la UI para reflejar que no estamos en el modo de limpieza
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(False)
                self.btn_short.setEnabled(True)
                self.btn_long.setEnabled(True)
                self.btn_short.setStyleSheet(self.style_unchecked)
                self.btn_long.setStyleSheet(self.style_unchecked)
                self.btn_mode_group.setExclusive(False)
                self.btn_short.setChecked(False)
                self.btn_long.setChecked(False)
                self.btn_mode_group.setExclusive(True)


    def update_buttons_state(self, cleaning_active: bool):
        """
        Actualiza el estado de habilitado/deshabilitado de los botones de inicio/detención
        y selección de modo según si la limpieza está activa o no.
        """
        if cleaning_active:
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.btn_short.setEnabled(False)
            self.btn_long.setEnabled(False)
            self.btn_short.setStyleSheet(self.style_disabled)
            self.btn_long.setStyleSheet(self.style_disabled)
        else: # Limpieza no activa
            self.stop_button.setEnabled(False)
            self.btn_short.setEnabled(True)
            self.btn_long.setEnabled(True)
            # Re-aplicar el estilo correcto para los botones de modo seleccionados/no seleccionados
            if self.selected_mode is not None:
                self.start_button.setEnabled(True)
                if self.selected_mode == 0.0:
                    self.btn_short.setStyleSheet(self.style_checked)
                    self.btn_long.setStyleSheet(self.style_unchecked)
                else: # self.selected_mode == 1.0
                    self.btn_long.setStyleSheet(self.style_checked)
                    self.btn_short.setStyleSheet(self.style_unchecked)
            else: # Ningún modo seleccionado
                self.start_button.setEnabled(False)
                self.btn_short.setStyleSheet(self.style_unchecked)
                self.btn_long.setStyleSheet(self.style_unchecked)

    # --- Comunicación Externa (Señales) ---
    def on_user_boolean_command(self, tag, state):
        """Emite una señal para cambiar un valor booleano en el controlador."""
        self.request_boolean_change.emit(tag, state)

    def on_user_input_setpoint(self, tag, value):
        """Emite una señal para cambiar un setpoint (valor flotante) en el controlador."""
        self.request_setpoint_change.emit(tag, value)



    def showEvent(self, event):
        super().showEvent(event)
        self.apply_theme_styles()

    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        is_mono = bool(tokens.get("monochrome", False))
        is_dark = bool(tokens.get("is_dark", False))

        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(tokens.get("bg_main", "#FCFCFC")))
        self.setPalette(palette)
        self.setStyleSheet(f"background: {tokens.get('bg_main', '#FCFCFC')};")

        if is_mono:
            title_color = "#374151"
            mode_frame_style = "background: #FFFFFF; border: 1px solid #D1D5DB; border-radius: 10px;"
            self.style_unchecked = """
                QPushButton {
                    background: #D9E0E8; color: #374151; font-size: 24px; font-weight: bold;
                    border-radius: 12px; padding: 6px 16px; border: 2px solid #C5CDD6;
                }
                QPushButton:hover { background: #C5CED6; }
                QPushButton:pressed { background: #B0B8C4; }
            """
            self.style_checked = """
                QPushButton {
                    background: #9CA3AF; color: #111827; font-size: 24px; font-weight: bold;
                    border-radius: 12px; padding: 6px 16px; border: 2px solid #6B7280;
                }
            """
            self.style_disabled = """
                QPushButton {
                    background: #E5E7EB; color: #B0B8C2; font-size: 24px; font-weight: bold;
                    border-radius: 12px; padding: 6px 16px; border: 2px solid #D1D5DB;
                }
            """
            phase_lbl_style = "color: #374151; font-size: 32px; font-weight: bold; background: transparent; min-height: 60px;"
            config_lbl_style = "color: #374151; font-size: 28px; font-weight: bold; background: transparent;"
            progress_bar_style = """
                QProgressBar {
                    background: #E5E7EB; border: 2px solid #D1D5DB; border-radius: 10px;
                    text-align: center; color: #111827; font-size: 24px; font-weight: bold;
                }
                QProgressBar::chunk {
                    background: #9CA3AF;
                    border-radius: 8px;
                }
            """
            btn_start_style = """
                QPushButton {
                    background: #D9E0E8; color: #374151; font-size: 38px; font-weight: bold;
                    border: 2px solid #C5CDD6; border-radius: 16px; padding: 10px;
                }
                QPushButton:hover { background: #C5CED6; }
                QPushButton:pressed { background: #B0B8C4; }
                QPushButton:disabled { background: #E5E7EB; color: #B0B8C2; border: 2px solid #D1D5DB; }
            """
            btn_stop_style = """
                QPushButton {
                    background: #D9E0E8; color: #374151; font-size: 38px; font-weight: bold;
                    border: 2px solid #C5CDD6; border-radius: 16px; padding: 10px;
                }
                QPushButton:hover { background: #C5CED6; }
                QPushButton:pressed { background: #B0B8C4; }
                QPushButton:disabled { background: #E5E7EB; color: #B0B8C2; border: 2px solid #D1D5DB; }
            """
        elif is_dark:
            title_color = tokens.get('text_primary', '#F8FAFC')
            mode_frame_style = f"background: {tokens.get('bg_card', '#1E293B')}; border: 1px solid {tokens.get('border_card', '#334155')}; border-radius: 10px;"
            self.style_unchecked = f"""
                QPushButton {{
                    background: {tokens.get('primary', '#38BDF8')}; color: #ffffff; font-size: 24px; font-weight: bold;
                    border-radius: 12px; padding: 6px 16px; border: 2px solid {tokens.get('primary_hover', '#0284C7')};
                }}
                QPushButton:hover {{ background: {tokens.get('primary_hover', '#0284C7')}; }}
            """
            self.style_checked = f"""
                QPushButton {{
                    background: {tokens.get('success', '#10B981')}; color: #ffffff; font-size: 24px; font-weight: bold;
                    border-radius: 12px; padding: 6px 16px; border: 2px solid {tokens.get('border_strong', '#059669')};
                }}
            """
            self.style_disabled = f"""
                QPushButton {{
                    background: {tokens.get('btn_disabled_bg', '#334155')}; color: {tokens.get('btn_disabled_text', '#64748b')}; font-size: 24px; font-weight: bold;
                    border-radius: 12px; padding: 6px 16px; border: 2px solid {tokens.get('border_card', '#475569')};
                }}
            """
            phase_lbl_style = f"color: {tokens.get('text_secondary', '#94A3B8')}; font-size: 32px; font-weight: bold; background: transparent; min-height: 60px;"
            config_lbl_style = f"color: {tokens.get('text_secondary', '#cbd5e1')}; font-size: 28px; font-weight: bold; background: transparent;"
            progress_bar_style = f"""
                QProgressBar {{
                    background: {tokens.get('bg_card_alt', '#1E293B')}; border: 2px solid {tokens.get('border_card', '#475569')}; border-radius: 10px;
                    text-align: center; color: {tokens.get('text_primary', '#FFFFFF')}; font-size: 24px; font-weight: bold;
                }}
                QProgressBar::chunk {{
                    background: {tokens.get('primary', '#38BDF8')};
                    border-radius: 8px;
                }}
            """
            btn_start_style = f"""
                QPushButton {{
                    background: {tokens.get('success', '#047857')}; color: #ffffff; font-size: 38px; font-weight: bold;
                    border: none; border-radius: 16px; padding: 10px;
                }}
                QPushButton:hover {{ background: {tokens.get('success_bright', '#065f46')}; }}
                QPushButton:disabled {{ background: {tokens.get('btn_disabled_bg', '#334155')}; color: {tokens.get('btn_disabled_text', '#64748b')}; }}
            """
            btn_stop_style = f"""
                QPushButton {{
                    background: {tokens.get('danger', '#dc2626')}; color: #ffffff; font-size: 38px; font-weight: bold;
                    border: none; border-radius: 16px; padding: 10px;
                }}
                QPushButton:hover {{ background: #b91c1c; }}
                QPushButton:disabled {{ background: {tokens.get('btn_disabled_bg', '#334155')}; color: {tokens.get('btn_disabled_text', '#64748b')}; }}
            """
        else:
            title_color = "#cbd5e1"
            mode_frame_style = "background: #fcfcfc; border-radius: 10px;"
            self.style_unchecked = """
                QPushButton {
                    background: #3b82f6; color: #ffffff; font-size: 24px; font-weight: bold;
                    border-radius: 12px; padding: 6px 16px; border: 2px solid #2563eb;
                }
                QPushButton:hover { background: #60a5fa; }
            """
            self.style_checked = """
                QPushButton {
                    background: #22c55e; color: #ffffff; font-size: 24px; font-weight: bold;
                    border-radius: 12px; padding: 6px 16px; border: 2px solid #16a34a;
                }
            """
            self.style_disabled = """
                QPushButton {
                    background: #334155; color: #64748b; font-size: 24px; font-weight: bold;
                    border-radius: 12px; padding: 6px 16px; border: 2px solid #475569;
                }
            """
            phase_lbl_style = "color: #94a3b8; font-size: 32px; font-weight: bold; background: transparent; min-height: 60px;"
            config_lbl_style = "color: #cbd5e1; font-size: 28px; font-weight: bold; background: transparent;"
            progress_bar_style = """
                QProgressBar {
                    background: #1e293b; border: 2px solid #475569; border-radius: 10px;
                    text-align: center; color: #ffffff; font-size: 24px; font-weight: bold;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #60a5fa);
                    border-radius: 8px;
                }
            """
            btn_start_style = """
                QPushButton {
                    background: #047857; color: #ffffff; font-size: 38px; font-weight: bold;
                    border: none; border-radius: 16px; padding: 10px;
                }
                QPushButton:hover { background: #065f46; }
                QPushButton:disabled { background: #334155; color: #64748b; }
            """
            btn_stop_style = """
                QPushButton {
                    background: #dc2626; color: #ffffff; font-size: 38px; font-weight: bold;
                    border: none; border-radius: 16px; padding: 10px;
                }
                QPushButton:hover { background: #b91c1c; }
                QPushButton:disabled { background: #334155; color: #64748b; }
            """

        if hasattr(self, "title_label"):
            self.title_label.setStyleSheet(f"color: {title_color}; font-size: 52px; font-weight: bold; background: transparent;")
        if hasattr(self, "mode_frame"):
            self.mode_frame.setStyleSheet(mode_frame_style)
        if hasattr(self, "phase_label"):
            self.phase_label.setStyleSheet(phase_lbl_style)
        if hasattr(self, "progress_bar"):
            self.progress_bar.setStyleSheet(progress_bar_style)
        for attr in ("time_label", "temp_label", "flow_label"):
            lbl = getattr(self, attr, None)
            if lbl:
                lbl.setStyleSheet(config_lbl_style)

        if hasattr(self, "btn_short") and hasattr(self, "btn_long"):
            for b in [self.btn_short, self.btn_long]:
                if not b.isEnabled():
                    b.setStyleSheet(self.style_disabled)
                elif b.isChecked():
                    b.setStyleSheet(self.style_checked)
                else:
                    b.setStyleSheet(self.style_unchecked)

        if hasattr(self, "start_button"):
            self.start_button.setStyleSheet(btn_start_style)
        if hasattr(self, "stop_button"):
            self.stop_button.setStyleSheet(btn_stop_style)
