import logging
from typing import Callable, Dict, Optional

from PySide6.QtCore import QObject, QTimer, QDateTime, Signal # Import QObject, QTimer, QDateTime, Signal
from core.ktv.ktv_grafcet import KtvGrafcet, KtvStep # Import KtvGrafcet and KtvStep
from logic.ktv_calculator import CalculadoraKtV # Import CalculadoraKtV
from core.state_manager import TreatmentPhase # Import TreatmentPhase
from logic.heitmann import heitmann # Import heitmann
from logic.calculos import convertir_ciclos_a_flujo # Import convertir_ciclos_a_flujo


logger = logging.getLogger(__name__)

class KtvController(QObject): # KtvController ahora hereda de QObject
    # Señales que el KtvController puede emitir a la interfaz principal o a la pantalla KTV
    ktv_calculated = Signal(dict) # Emite un diccionario con los resultados Kt/V
    schedule_info_updated = Signal(str) # Emite el texto para la próxima medición programada
    
    # Señales para solicitar acciones a la ventana principal (HemodialysisHMI)
    request_setpoint_change = Signal(str, float) # Solicita al Main que cambie un setpoint
    request_bioz_command = Signal(str) # Solicita al Main que envíe un comando a BioZ/Urea
    show_message_signal = Signal(str, str, int) # Para mostrar mensajes al usuario (text, level, timeout)
    
    # Señales para notificar eventos del ciclo de vida de la medición
    measurement_started = Signal() # Señal que indica que una medición Kt/V ha comenzado
    measurement_aborted = Signal(str) # Señal que indica que una medición Kt/V ha sido abortada
    measurement_finished = Signal() # Señal que indica que una medición Kt/V ha finalizado con éxito


    def __init__(self, parent=None): # Changed parent_window to parent for QObject
        super().__init__(parent)
        self.main_window = parent # Referencia a la ventana principal (HemodialysisHMI), se asigna en set_dependencies

        # Dependencias que serán inyectadas desde appMainHemodialysis
        self._bioz_urea_controller = None
        self._current_values_accessor: Optional[Callable[[], Dict]] = None # Callable para obtener el diccionario current_values
        self._get_elapsed_therapy_minutes_accessor: Optional[Callable[[], float]] = None # Callable para obtener minutos de terapia
        self._write_setpoint_callback: Optional[Callable[[str, float], None]] = None
        self._write_bioz_command_callback: Optional[Callable[[str], None]] = None
        self._show_message_callback: Optional[Callable[[str, str, int], None]] = None
        
        # Atributos internos para la lógica Kt/V
        self.calculadora_ktv = CalculadoraKtV(parent=self) # Instancia de la calculadora
        self._original_conductivity_setpoint: Optional[float] = None
        self._automatic_frequency_minutes: int = 0 # Default: 0 (deshabilitado)
        self._next_automatic_measurement_time_s: float = float('inf') # En segundos, tiempo absoluto de terapia para próxima medición

        # Validación de BIOZ / fase θ
        self._bioz_retry_count: int = 0
        self._bioz_retry_max_attempts: int = 3
        self._bioz_phase_max_abs_degrees: float = 20.0
        self._last_bioz_validation_issue: Optional[str] = None

        self.is_paused: bool = False # Controla si la secuencia de Kt/V está pausada (a nivel de KtvController)
        self._grafcet_is_paused_internally: bool = False # Controla si el KtvGrafcet está en su estado PAUSED_SEQUENCE
        self._suppress_measurement_popups: bool = True # Evita popups durante la secuencia Kt/V
        self._connection_warning_sent: bool = False # Evita repetir el aviso de falta de conexión durante un mismo ciclo

        # El GRAFCET de la secuencia de medición de Kt/V
        # Le pasamos los callbacks que este KtvController implementa.
        self.grafcet = KtvGrafcet(self._make_internal_callbacks(), parent=self)
        
        logger.info("KtvController inicializado.")

    def _notify_user(self, text: str, level: str, timeout: int, force: bool = False) -> None:
        """Envía mensajes al operador; puede silenciarse durante la medición Kt/V."""
        if not self._show_message_callback:
            return

        measurement_active = self.grafcet.is_running() or self._grafcet_is_paused_internally
        if self._suppress_measurement_popups and measurement_active and not force:
            return

        self._show_message_callback(text, level, timeout)

    def set_dependencies(self, main_window: QObject, bioz_urea_controller: QObject,
                         current_values_accessor: Callable[[], Dict],
                         get_elapsed_therapy_minutes_accessor: Callable[[], float],
                         write_setpoint_callback: Callable[[str, float], None],
                         write_bioz_command_callback: Callable[[str], None],
                         show_message_callback: Callable[[str, str, int], None]):
        """
        Inyecta las dependencias necesarias de la ventana principal.
        Esto permite que el KtvController acceda a recursos sin una referencia directa y fuerte.
        """
        self.main_window = main_window # La ventana principal (HMI)
        self._bioz_urea_controller = bioz_urea_controller
        self._current_values_accessor = current_values_accessor
        self._get_elapsed_therapy_minutes_accessor = get_elapsed_therapy_minutes_accessor
        self._write_setpoint_callback = write_setpoint_callback
        self._write_bioz_command_callback = write_bioz_command_callback
        self._show_message_callback = show_message_callback
        
        # Después de setear las dependencias, aseguramos que los callbacks del grafcet estén correctos
        self.grafcet.callbacks = self._make_internal_callbacks()
        logger.info("KtvController: Dependencias inyectadas.")

    def update_current_values(self, new_values: dict):
        """
        Actualiza el diccionario de valores actuales que KtvController utiliza.
        Es importante que este controlador siempre tenga acceso a los datos más recientes.
        """
        # El accessor se encarga de que KtvController siempre tenga acceso a los current_values más recientes
        pass 

    def on_master_tick(self):
        """
        Gestiona la lógica de programación automática de Kt/V.
        Se llama desde el master_timer de HemodialysisHMI.
        """
        # Si el Grafcet está pausado internamente, no hacer nada más que actualizar la UI
        if self._grafcet_is_paused_internally:
            # Podríamos actualizar el tiempo restante para la próxima medición en la UI aquí si queremos
            self._update_schedule_display_text(self._get_elapsed_therapy_seconds())
            return

        # Si el tratamiento no está corriendo, o está pausado globalmente
        if not self.is_therapy_running() or self.is_paused:
            # Si el grafcet está corriendo y la terapia se pausó/detuvo, abortar la medición en curso
            if self.grafcet.is_running():
                self.abort("Terapia pausada/detenida durante medición.")
            self.schedule_info_updated.emit("Terapia no activa") # Informar a la UI
            return 

        # Si hay una medición manual o automática en curso, no iniciar una nueva automática.
        if self.grafcet.is_running():
            self.schedule_info_updated.emit("Medición en curso...") # Indicar a la UI que hay una medición activa
            return

        elapsed_seconds = self._get_elapsed_therapy_seconds()

        # Calcular la próxima medición solo cuando no exista programación activa.
        # Recalcular en cada tick puede adelantar el objetivo y perder disparos automáticos.
        if self._automatic_frequency_minutes > 0 and (
            self._next_automatic_measurement_time_s == 0 or
            self._next_automatic_measurement_time_s == float('inf')
        ):
            self._update_next_scheduled_time(elapsed_seconds)

        self._update_schedule_display_text(elapsed_seconds) # Actualizar el texto en la pantalla

        if self._automatic_frequency_minutes > 0 and \
           self._next_automatic_measurement_time_s != float('inf') and \
           elapsed_seconds >= self._next_automatic_measurement_time_s:
            
            logger.info(f"[KtvController] Iniciando medición automática de Kt/V. Tiempo de terapia: {elapsed_seconds // 60} min.")
            self.start_manual_measurement(is_automatic=True) # Reutilizar la lógica de inicio
            if self.grafcet.is_running():
                # Evita un segundo intento del mismo slot mientras la secuencia está activa.
                self._next_automatic_measurement_time_s = float('inf')
            # Una vez que se inicia la medición, recalcula la próxima para el siguiente ciclo
            # (El grafcet se encargará de resetear self._next_automatic_measurement_time_s a inf si termina)
            # o se recalculará automáticamente al final del grafcet cuando no haya medición en curso.



    # Calcula el próximo slot automático como múltiplo de frecuencia,
    # respetando un buffer al final de la terapia.

    def _update_next_scheduled_time(self, current_elapsed_seconds: int):
        """Calcula el próximo tiempo de medición automática."""
        if self._automatic_frequency_minutes <= 0:
            self._next_automatic_measurement_time_s = float('inf')
            return

        total_therapy_seconds = int(self.main_window.treatment_controller.total_therapy_seconds)
        if total_therapy_seconds <= 0:
            self._next_automatic_measurement_time_s = float('inf')
            return

        freq_s = self._automatic_frequency_minutes * 60
        if freq_s <= 0:
            self._next_automatic_measurement_time_s = float('inf')
            return

        # Smallest multiple of freq_s that is >= current_elapsed_seconds
        next_schedule_s = ((current_elapsed_seconds + freq_s - 1) // freq_s) * freq_s
        if next_schedule_s == 0:
            next_schedule_s = freq_s

        # Buffer para no programar muy cerca del final de la terapia
        measurement_duration_buffer_s = 250
        last_allowed_s = max(0, total_therapy_seconds - measurement_duration_buffer_s)

        if next_schedule_s > last_allowed_s:
            self._next_automatic_measurement_time_s = float('inf')
        else:
            self._next_automatic_measurement_time_s = next_schedule_s

        logger.debug(f"Próxima medición automática calculada para {self._next_automatic_measurement_time_s / 60:.0f} minutos.")

    def _update_schedule_display_text(self, current_elapsed_seconds: int):
        """Emite la señal para actualizar el texto de la próxima medición."""
        if self._automatic_frequency_minutes <= 0:
            self.schedule_info_updated.emit("Deshabilitado")
        elif self._next_automatic_measurement_time_s == float('inf'):
            self.schedule_info_updated.emit("No hay más mediciones programadas")
        else:
            remaining_s = max(0, int(self._next_automatic_measurement_time_s - current_elapsed_seconds))
            remaining_min = remaining_s // 60
            self.schedule_info_updated.emit(f"en {remaining_min} minutos")


    def start_manual_measurement(self, is_automatic: bool = False) -> None:
        """Arranca la secuencia de medición Kt/V, con validaciones iniciales."""
        if not self.is_therapy_running():
            self._notify_user("El tratamiento debe estar en curso para iniciar una medición Kt/V.", "warning", 3000)
            return

        if self.grafcet.is_running():
            self._notify_user("Ya hay una medición de Kt/V en curso.", "warning", 3000)
            return

        if not self._bioz_urea_controller or not self._bioz_urea_controller.is_enabled(): # Asumiendo .is_enabled()
            self._notify_user("Controlador de Bioimpedancia/Urea no disponible o deshabilitado.", "error", 5000)
            logger.warning("Intento de iniciar Kt/V sin controlador BioZ/Urea disponible.")
            return
        
        # Configurar la bandera para que el grafcet sepa si es auto o manual
        self.grafcet.is_auto_trigger = is_automatic

        self._bioz_retry_count = 0
        self._last_bioz_validation_issue = None
        self._connection_warning_sent = False
        logger.info(f"[KtvController] Iniciando secuencia de medición Kt/V {'(AUTOMÁTICA)' if is_automatic else '(MANUAL)'}.")
        self.grafcet.start()
        self.measurement_started.emit()


    def set_bioz_validation_config(self, max_phase_degrees: float = 20.0, max_retry_attempts: int = 3) -> None:
        """Configura los límites de validación de fase y el número máximo de reintentos."""
        self._bioz_phase_max_abs_degrees = max(0.0, float(max_phase_degrees))
        self._bioz_retry_max_attempts = max(1, int(max_retry_attempts))
        logger.info(
            "[KtvController] Config BIOZ: phase_max_abs=%s°, max_retries=%s",
            self._bioz_phase_max_abs_degrees,
            self._bioz_retry_max_attempts,
        )

    def _validate_bioz(self, resistance: float, phase: float) -> bool:
        """Valida la medición de bioimpedancia para decidir si es usable para V(t)."""
        if not (50.0 <= resistance <= 3000.0):
            logger.warning("[KtvController] BIOZ inválida por resistencia: %.2f Ω", resistance)
            return False

        phase_abs = abs(float(phase))
        if not (0.0 <= phase_abs <= self._bioz_phase_max_abs_degrees):
            logger.warning(
                "[KtvController] BIOZ inválida por fase fuera de rango: %.2f° (máx %.2f°)",
                phase_abs,
                self._bioz_phase_max_abs_degrees,
            )
            return False

        logger.info("[KtvController] BIOZ válida: R=%.2f Ω | θ=%.2f°", resistance, phase_abs)
        return True

    def abort(self, reason: str = "Abortado por usuario") -> None:
        """Aborta la secuencia de medición Kt/V y emite una señal."""
        if self.grafcet.step not in (KtvStep.IDLE, KtvStep.FINISHED, KtvStep.ERROR):
            self.grafcet.abort(reason)
            self._notify_user(f"Medición Kt/V abortada: {reason}", "error", 4000)
            self.measurement_aborted.emit(reason) # Notificar a la UI

        self._restore_original_conductivity_if_needed(f"abort: {reason}")
        self._grafcet_is_paused_internally = False # Asegurarse de que no quede en estado de pausa interna
        self._bioz_retry_count = 0
        self._last_bioz_validation_issue = None
        self._connection_warning_sent = False

    def _restore_original_conductivity_if_needed(self, reason: str) -> None:
        """Restaura el setpoint original solo si el flujo Kt/V lo alteró."""
        if self._original_conductivity_setpoint is None:
            return

        if self._write_setpoint_callback:
            self._write_setpoint_callback("dialyCondControlSetPoint", self._original_conductivity_setpoint)
            logger.info(
                "[KtvController] Conductividad restaurada (%s): %.2f mS/cm",
                reason,
                self._original_conductivity_setpoint,
            )
        else:
            logger.warning(
                "[KtvController] No se pudo restaurar conductividad (%s): callback no disponible.",
                reason,
            )

        self._original_conductivity_setpoint = None

    def pause_measurement(self):
        """Pausa la secuencia del Grafcet si es posible."""
        if self.grafcet.is_running():
            self.grafcet.pause_sequence()
            self.is_paused = True # Bandera de pausa global
            self._grafcet_is_paused_internally = True # Bandera de pausa del grafcet
            logger.info("[KtvController] Medición Kt/V pausada.")

    def resume_measurement(self):
        """Reanuda la secuencia del Grafcet."""
        if self.is_paused and self.grafcet.step == KtvStep.PAUSED_SEQUENCE:
            self.grafcet.resume_sequence()
            self.is_paused = False
            self._grafcet_is_paused_internally = False
            logger.info("[KtvController] Medición Kt/V reanudada.")

    def set_automatic_frequency(self, minutes: int):
        """Establece la frecuencia de las mediciones automáticas (0 para deshabilitar)."""
        self._automatic_frequency_minutes = minutes
        self._next_automatic_measurement_time_s = 0 # Forzar recálculo en el próximo tick
        self.schedule_info_updated.emit("Recalculando...")
        logger.info(f"[KtvController] Frecuencia automática de Kt/V establecida a {minutes} minutos.")

    def get_calculadora_ktv(self) -> CalculadoraKtV:
        """Devuelve la instancia de CalculadoraKtV."""
        return self.calculadora_ktv

    def get_original_conductivity_setpoint(self) -> Optional[float]:
        """Devuelve el setpoint de conductividad original guardado."""
        return self._original_conductivity_setpoint

    def set_original_conductivity_setpoint(self, value: float):
        """Guarda el setpoint de conductividad original."""
        self._original_conductivity_setpoint = value

    def is_therapy_running(self) -> bool:
        """Verifica si la terapia está en estado RUNNING en el main HMI."""
        if not self.main_window: return False
        return self.main_window.state.current_phase == TreatmentPhase.RUNNING
    
    def _get_elapsed_therapy_minutes(self) -> float:
        """Obtiene el tiempo total de terapia transcurrido en minutos."""
        if self._get_elapsed_therapy_minutes_accessor:
            return self._get_elapsed_therapy_minutes_accessor()
        return 0.0

    def _get_elapsed_therapy_seconds(self) -> int:
        """Obtiene el tiempo total de terapia transcurrido en segundos."""
        return int(self._get_elapsed_therapy_minutes() * 60)

    def reset_on_treatment_start(self):
        """Resetea el estado del controlador Kt/V para un nuevo tratamiento."""
        logger.info("[KtvController] Reseteando estado para nuevo tratamiento.")
        self.grafcet.reset() # Pone el grafcet en IDLE
        self.calculadora_ktv.reset()
        self._original_conductivity_setpoint = None
        self._next_automatic_measurement_time_s = 0 # Recalculará al inicio del primer tick
        self._bioz_retry_count = 0
        self._connection_warning_sent = False
        self.is_paused = False
        self._grafcet_is_paused_internally = False
        self.schedule_info_updated.emit("No programado") # Limpiar la etiqueta de programación


    # ==================== Métodos internos (callbacks del Grafcet) ====================
    # Estos métodos son llamados por el KtvGrafcet para ejecutar las acciones.

    def _warn_bioz_connection_issue_once(self) -> None:
        """Emite el aviso de falta de conexión solo una vez por ciclo de medición."""
        if self._connection_warning_sent:
            return
        self._connection_warning_sent = True
        self._notify_user("Controlador BioZ/Urea no disponible o deshabilitado.", "error", 5000)

    def _perform_send_bioz_command(self, command: str) -> None:
        """Callback: Envía un comando al controlador de BioZ/Urea."""
        if self._write_bioz_command_callback and self._bioz_urea_controller and self._bioz_urea_controller.is_enabled():
            self._write_bioz_command_callback(command)
            logger.debug(f"[KtvController] Enviando comando '{command}' a BioZ/Urea.")
        else:
            self._warn_bioz_connection_issue_once()
            self.grafcet.abort("BioZ/Urea no disponible")

    def _perform_validate_bioz(self) -> bool:
        """Valida la última BIOZ capturada antes de seguir con la secuencia de Kt/V."""
        current_values = self._current_values_accessor()
        resistance = float(current_values.get("bioz_resistance", 0.0) or 0.0)
        phase = float(current_values.get("bioz_phase", 0.0) or 0.0)

        if self._validate_bioz(resistance, phase):
            self._bioz_retry_count = 0
            self._last_bioz_validation_issue = None
            return True

        self._bioz_retry_count += 1
        issue = f"R={resistance:.2f} Ω | θ={abs(phase):.2f}° fuera de rango"
        self._last_bioz_validation_issue = issue
        logger.warning(
            "[KtvController] BIOZ inválida. Intento %s/%s. %s",
            self._bioz_retry_count,
            self._bioz_retry_max_attempts,
            issue,
        )

        if self._bioz_retry_count < self._bioz_retry_max_attempts:
            self._notify_user(
                f"Bioimpedancia no confiable ({issue}). Reintentando adquisición...",
                "warning",
                2500,
            )
            if self._write_bioz_command_callback:
                self._write_bioz_command_callback("SRTB")
            self.grafcet._transition_to(KtvStep.WAIT_BIOIMPEDANCE)
            return False

        self._notify_user(
            f"Bioimpedancia no confiable: {issue}. Se descarta la medición Kt/V.",
            "error",
            5000,
            force=True,
        )
        logger.error(
            "[KtvController] BIOZ descartada tras %s reintentos. %s. No se actualiza V(t).",
            self._bioz_retry_count,
            issue,
        )
        self.measurement_aborted.emit("Bioimpedancia no confiable - medición descartada")
        self._bioz_retry_count = 0
        self._restore_original_conductivity_if_needed("BIOZ inválida")
        self.grafcet.abort("Bioimpedancia no confiable para Kt/V")
        return False

    def _perform_capture_t1(self) -> None:
        """Callback: Captura conductividades T1 y guarda el setpoint original."""
        current_values = self._current_values_accessor()
        cd_in_t1 = current_values.get("dialyConductIFProcessData", 0.0)
        cd_out_t1 = current_values.get("dialyConductOFProcessData", 0.0)
        self.calculadora_ktv.store_conductivity_t1(cd_in_t1, cd_out_t1)
        logger.info(f"[KtvController] T1 capturado: CdEF={cd_in_t1:.2f}, CdSF={cd_out_t1:.2f} (ya a 25°C desde firmware)")

        # Guardar el setpoint original de conductividad antes de modificarlo
        self._original_conductivity_setpoint = current_values.get("dialyCondControlSetPoint", 13.5)
        logger.info(f"[KtvController] Original conductivity setpoint saved: {self._original_conductivity_setpoint:.2f} mS/cm")

    def _perform_set_step_conductivity(self) -> None:
        """Callback: Calcula y envía el nuevo setpoint de conductividad escalado."""
        if self._original_conductivity_setpoint is None:
            logger.error("[KtvController] Error: original_conductivity_setpoint no definido al intentar cambiar setpoint.")
            self.grafcet.abort("Error interno: SP original no guardado.")
            return

        step_value = 1.0 # Puedes hacer esto configurable
        new_conductivity_target = self._original_conductivity_setpoint + step_value
        if self._write_setpoint_callback:
            self._write_setpoint_callback("dialyCondControlSetPoint", new_conductivity_target)
            logger.info(f"[KtvController] Conductivity setpoint changed to: {new_conductivity_target:.2f} mS/cm")
        else:
            logger.error("[KtvController] Error: write_setpoint_callback no definido.")
            self.grafcet.abort("Error interno: Callback de escritura no disponible.")


    def _perform_capture_t2(self) -> None:
        """Callback: Captura conductividades T2."""
        current_values = self._current_values_accessor()
        cd_in_t2 = current_values.get("dialyConductIFProcessData", 0.0)
        cd_out_t2 = current_values.get("dialyConductOFProcessData", 0.0)
        self.calculadora_ktv.store_conductivity_t2(cd_in_t2, cd_out_t2)
        logger.info(f"[KtvController] T2 capturado: CdEF={cd_in_t2:.2f}, CdSF={cd_out_t2:.2f} (ya a 25°C desde firmware)")

    def _perform_restore_conductivity(self) -> None:
        """Callback: Restaura el setpoint de conductividad original."""
        if self._original_conductivity_setpoint is None:
            logger.error("[KtvController] Error: original_conductivity_setpoint no definido al intentar restaurar setpoint.")
            self.grafcet.abort("Error interno: SP original no disponible.")
            return
        if self._write_setpoint_callback:
            self._write_setpoint_callback("dialyCondControlSetPoint", self._original_conductivity_setpoint)
            logger.info(f"[KtvController] Conductivity setpoint restored to: {self._original_conductivity_setpoint:.2f} mS/cm")
        else:
            logger.error("[KtvController] Error: write_setpoint_callback no definido.")
            self.grafcet.abort("Error interno: Callback de escritura no disponible.")

    def _perform_calculate_ktv(self) -> None:
        """Callback: Realiza el cálculo de Kt/V con acumulación correcta."""
        current_values = self._current_values_accessor()
        
        # balanceChamberSetTiming is a cycle timing value, convert it to mL/min
        chamber_cycles = current_values.get("balanceChamberSetTiming", 0)
        qd = convertir_ciclos_a_flujo(chamber_cycles)

        # If conversion returns 0, skip D calculation
        if qd == 0:
            logger.warning("[KtvController] balanceChamberSetTiming conversion returned 0, skipping Kt/V calculation")
            return
        qf = current_values.get("ultraFilterPumpSpeed", 10)  # L/h
        qb = current_values.get("bloodFlowVariableData", 300)  # ml/min
        r = current_values.get("recirculation_rate", 0.0)  # Factor de recirculación

        z_resistencia = current_values.get("bioz_resistance", 0.0)
        
        patient_data = {
            "patient_pre_weight_kg": current_values.get("patient_pre_weight_kg", 70),
            "patient_height_cm": current_values.get("patient_height_cm", 170),
            "patient_age": current_values.get("patient_age", 40),
            "patient_gender": current_values.get("patient_gender", 1),  # 1=Masculino, 2=Femenino
        }

        peso = patient_data["patient_pre_weight_kg"]
        altura = patient_data["patient_height_cm"]
        edad = patient_data["patient_age"]
        genero = patient_data["patient_gender"]

        genero_heitmann = 0 if genero == 2 else 1  # 1 = Hombre, 0 = Mujer para Heitmann
        v_bis_litros = heitmann(z_resistencia, altura, peso, genero_heitmann, edad) 
        
        current_values["heitmann_value"] = v_bis_litros 
        
        if v_bis_litros and v_bis_litros > 0:
            self.calculadora_ktv.set_volumen_bioimpedancia(v_bis_litros)
        else:
            self.calculadora_ktv.config_paciente(peso, altura, edad, genero)

        # Tiempos: total programado y transcurrido
        t_programmed_min = (current_values.get("heparineTherapyHours", 0) * 60 + 
                            current_values.get("heparineTherapyMinutes", 0))
        t_elapsed_min = self._get_elapsed_therapy_minutes()

        # Actualizar Kt acumulado con la D vigente anterior, luego D_vigente = D nueva
        self.calculadora_ktv.update_kt(t_elapsed_min, qd, qf, qb, r)

        # Obtener Kt/V entregado y proyectado
        ktv_delivered = self.calculadora_ktv.get_ktv_delivered(t_elapsed_min)
        ktv_projected = self.calculadora_ktv.get_ktv_projected(t_elapsed_min, t_programmed_min)

        # Obtener D vigente para logging
        d_vigente = self.calculadora_ktv.d_vigente
        kt_acumulado = self.calculadora_ktv.kt_acumulado

        results_dict = {
            "ktv_acumulado": ktv_delivered,
            "ktv_projectado": ktv_projected,
            "heitmann_value": v_bis_litros,
            "bioz_resistance": z_resistencia,
            "d_ionic": d_vigente,
            "kt_total": kt_acumulado,
            "type": "Automatic" if self.grafcet.is_auto_trigger else "Manual",
            "therapy_minutes": t_elapsed_min,
            "calculation_event": True,
            "event_id": f"{QDateTime.currentMSecsSinceEpoch()}_{'A' if self.grafcet.is_auto_trigger else 'M'}",
        }

        # Actualizar diccionario global para UI
        current_values["ktv_projectado"] = ktv_projected
        current_values["ktv_acumulado"] = ktv_delivered
        current_values["heitmann_value"] = v_bis_litros
        current_values["bioz_resistance"] = z_resistencia
        current_values["d_ionic"] = d_vigente
        current_values["kt_total"] = kt_acumulado
        current_values["type"] = results_dict["type"]
        current_values["therapy_minutes"] = t_elapsed_min
        current_values["calculation_event"] = True
        current_values["event_id"] = results_dict["event_id"]

        logger.info(
            f"[KtvController] Cálculo Kt/V: D_vigente={d_vigente:.1f} mL/min | "
            f"Kt={kt_acumulado:.1f} | Entregado={ktv_delivered:.3f} | Proyectado={ktv_projected:.3f}"
        )

        self.ktv_calculated.emit(results_dict)


    def _on_grafcet_finish(self) -> None:
        """Callback: La secuencia del Grafcet ha finalizado correctamente."""
        logger.info("[KtvController] Secuencia Kt/V finalizada correctamente.")
        self.measurement_finished.emit() # Notificar a la UI
        # Resetear setpoint original, ya no es necesario
        self._original_conductivity_setpoint = None
        self._connection_warning_sent = False
        self.grafcet.reset() # Resetear el Grafcet a IDLE
        # Recalcular el tiempo de la próxima medición automática si el modo es auto
        self._update_next_scheduled_time(self._get_elapsed_therapy_seconds())


    def _on_grafcet_error(self) -> None:
        """Callback: La secuencia del Grafcet ha terminado con un error."""
        logger.error("[KtvController] Secuencia Kt/V terminada con error.")
        if self._last_bioz_validation_issue:
            self._notify_user(
                f"Medición Kt/V descartada: Bioimpedancia no confiable ({self._last_bioz_validation_issue}).",
                "error",
                6000,
                force=True,
            )
            self.measurement_aborted.emit("Bioimpedancia no confiable")
        else:
            self._notify_user("Error durante la medición de Kt/V. Verifique logs.", "error", 5000)
            self.measurement_aborted.emit("Error interno")

        self._restore_original_conductivity_if_needed("error del grafcet")
        self.grafcet.reset() # Resetear el Grafcet a IDLE
        self._last_bioz_validation_issue = None
        self._connection_warning_sent = False
        self._update_next_scheduled_time(self._get_elapsed_therapy_seconds()) # Recalcular próxima medición

    def _make_internal_callbacks(self) -> Dict[str, Callable]:
        """
        Crea un diccionario de callbacks que KtvGrafcet usará para interactuar
        con el sistema a través de los métodos de este KtvController.
        """
        return {
            "send_bioz_command": self._perform_send_bioz_command,
            "show_info": lambda text, timeout: self._notify_user(text, "info", timeout),
            "show_warning": lambda text, timeout: self._notify_user(text, "warning", timeout),
            "show_error": lambda text, timeout: self._notify_user(text, "error", timeout),
            "capture_t1": self._perform_capture_t1,
            "validate_bioz": self._perform_validate_bioz,
            "set_step_conductivity": self._perform_set_step_conductivity,
            "capture_t2": self._perform_capture_t2,
            "restore_conductivity": self._perform_restore_conductivity,
            "calculate_ktv": self._perform_calculate_ktv,
            "is_therapy_running": self.is_therapy_running,
            "on_finish": self._on_grafcet_finish,
            "on_error": self._on_grafcet_error,
        }

    def update_app_state(self, phase: TreatmentPhase):
        """
        Método para informar al KtvController de cambios de fase globales en la aplicación.
        Utilizado para pausar/reanudar o abortar mediciones de Kt/V si el estado de la terapia cambia.
        """
        if phase == TreatmentPhase.PAUSED:
            self.pause_measurement()
        elif phase == TreatmentPhase.RUNNING:
            self.resume_measurement()
        else:
            # Salir de RUNNING/PAUSED (READY, IDLE, FINISHING, CLEANING, ERROR).
            # No cierra en pausa: el reloj se congela y la D vigente sigue.
            self.finalize_delivered_dose()
            if phase in (TreatmentPhase.IDLE, TreatmentPhase.CLEANING):
                if self.grafcet.step not in (KtvStep.IDLE, KtvStep.FINISHED, KtvStep.ERROR):
                    self.abort(f"Terapia finalizada/cambio de fase a {phase.name}")

    def finalize_delivered_dose(self) -> float:
        """Suma el último tramo y publica el Kt/V entregado.

        Durante la sesión la etiqueta sigue el proyectado. Al salir de la
        terapia el número que queda, en pantalla y en el registro, es el entregado.
        """
        if self.calculadora_ktv._cierre_hecho:
            if self.calculadora_ktv.volumen_distribucion_v <= 0:
                return 0.0
            return self.calculadora_ktv.kt_acumulado / self.calculadora_ktv.volumen_distribucion_v

        had_measurement = self.calculadora_ktv.tiempo_ultima_medicion is not None
        t_elapsed_min = self._get_elapsed_therapy_minutes()
        delivered = self.calculadora_ktv.commit_final_interval(t_elapsed_min)

        current_values = {}
        if self._current_values_accessor is not None:
            current_values = self._current_values_accessor() or {}
        if isinstance(current_values, dict):
            current_values["ktv_acumulado"] = delivered
            # La etiqueta de diálisis lee este tag. Al cerrar debe mostrar el entregado.
            current_values["ktv_projectado"] = delivered

        if had_measurement:
            results_dict = {
                "ktv_acumulado": delivered,
                "ktv_projectado": delivered,
                "heitmann_value": current_values.get("heitmann_value", 0.0) if isinstance(current_values, dict) else 0.0,
                "d_ionic": self.calculadora_ktv.d_vigente,
                "kt_total": self.calculadora_ktv.kt_acumulado,
                "type": "Cierre",
                "therapy_minutes": t_elapsed_min,
                "calculation_event": True,
                "event_id": f"{QDateTime.currentMSecsSinceEpoch()}_CIERRE",
            }
            logger.info(
                "[KtvController] Cierre Kt/V entregado=%.3f | Kt=%.1f | t=%.2f min",
                delivered,
                self.calculadora_ktv.kt_acumulado,
                t_elapsed_min,
            )
            self.ktv_calculated.emit(results_dict)
        return delivered

