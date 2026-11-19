# core/treatment_controller.py
import logging
from PySide6.QtCore import QDateTime
from core.state_manager import GemmaState, TreatmentPhase
from utilities.csv_logger import CsvLogger   # ← Importación agregada
from utilities.platform_runtime import get_runtime_data_path

logger = logging.getLogger(__name__)


class TreatmentController:
    """
    Controlador dedicado a toda la lógica del ciclo de tratamiento.
    """

    def __init__(self, main_window):
        self.main = main_window
        self.state = main_window.state
        self.timer_manager = main_window.timer_manager
        self.bioz_urea_controller = getattr(main_window, 'bioz_urea_controller', None)

        # Variables de control de terapia
        self.current_elapsed = 0
        self.remaining = 0
        self.accumulated_therapy_seconds = 0
        self.last_resume_time = None
        self.total_therapy_seconds = 0
        
        # self.total_therapy_seconds = 0
        self.therapy_start_time = None        # Para esta sesión de terapia
        self.accumulated_therapy_seconds = 0  # Tiempo acumulado (pausas)

        # Bandera para enviar pausa una sola vez cuando tiempo llega a 0 en bypass
        self.bypass_pause_sent = False

        # Bandera para UI: cuando terapia se pausa por timeout en bypass (no por botón)
        self.therapy_finished_by_time = False

        # Bandera para evitar cerrar registros dos veces en timeout
        self.therapy_records_closed = False

    def _get_programmed_total_seconds(self) -> int:
        """Obtiene la duración programada desde los setpoints actuales."""
        hours = int(self.main.current_values.get("heparineTherapyHours", 0))
        minutes = int(self.main.current_values.get("heparineTherapyMinutes", 0))
        return (hours * 3600) + (minutes * 60)

    def _reset_session_counters(self, reset_total: bool = False):
        """Limpia acumuladores de la sesión actual sin cerrar reportes/KTV."""
        self.current_elapsed = 0
        self.remaining = 0
        self.accumulated_therapy_seconds = 0
        self.last_resume_time = None
        self.therapy_start_time = None
        if reset_total:
            self.total_therapy_seconds = 0

    def prepare_new_treatment_session(self):
        """Prepara una sesión nueva (no reanudación) desde estado listo."""
        self._reset_session_counters(reset_total=False)
        self.total_therapy_seconds = self._get_programmed_total_seconds()
        self.bypass_pause_sent = False  # Reiniciar bandera para nueva terapia
        self.therapy_finished_by_time = False  # Limpiar UI flag
        self.therapy_records_closed = False  # Permitir nuevo cierre de registros en próxima terapia
        if hasattr(self.main, '_heparin_running_clamped'):
            self.main._heparin_running_clamped = False

    # ====================== START TREATMENT ======================

    def start_treatment(self):
        """Inicia o reanuda tratamiento con mensaje correcto"""
        logger.info("=== INTENTO DE INICIO DE TRATAMIENTO ===")

        # Si registros ya fueron cerrados por timeout (therapy_records_closed=True),
        # NO enviar ningún comando - la pausa queda para maniobras
        if self.therapy_records_closed:
            logger.info("therapy_records_closed activa: start_treatment no hace nada")
            return False

        if getattr(self.state, "current_gemma_state", None) in (GemmaState.D1, GemmaState.D2):
            logger.warning("Inicio bloqueado: falla activa en estado GEMMA %s", self.state.current_gemma_state.code)
            self.main.show_error_message("No se puede iniciar terapia con falla activa")
            return False

        try:
            # Si NO viene de pausa, debe arrancar una sesión limpia.
            if self.state.current_phase != TreatmentPhase.PAUSED:
                self.prepare_new_treatment_session()

            # Comandos al hardware
            self.main._write_boolean_command("dialyModeOperationStart", True)
            self.main._write_boolean_command("dialyModeOperationStop", False)

            self.main.show_info_message("Terapia iniciada correctamente")
            # BiozUrea
            if self.bioz_urea_controller:
                try:
                    self.bioz_urea_controller.send_command("SRTB")
                    
                except Exception as e:
                    logger.warning(f"BiozUrea no respondió: {e}")

            return True

        except Exception as e:
            logger.error(f"Error al iniciar tratamiento: {e}")
            self.main.show_error_message("Error al iniciar tratamiento")
            return False
        
    def _setup_treatment_logger(self, is_resuming: bool = False):
        if is_resuming and getattr(self.main, 'treatment_logger', None) is not None:
            logger.info("Reanudando logger existente")
            return

        if getattr(self.main, 'treatment_logger', None):
            self.main.treatment_logger.close()
            self.main.treatment_logger = None

        try:
            LOG_DIRECTORY = str(get_runtime_data_path("logs", "tratamiento_hemodialisis"))
            self.main.treatment_logger = CsvLogger(
                log_directory=LOG_DIRECTORY,
                parameter_key_map=self.main.parameter_mapping
            )
            logger.info(f"Nuevo logger creado: {LOG_DIRECTORY}")
        except Exception as e:
            logger.error(f"Error creando logger: {e}")

    # ====================== PAUSE / STOP (mantengo limpios) ======================

    def pause_treatment(self):
        if self.therapy_start_time:
            seconds_passed = self.therapy_start_time.secsTo(QDateTime.currentDateTime())
            self.accumulated_therapy_seconds += seconds_passed
            self.therapy_start_time = None

        # Mostrar mensaje diferente si es por timeout o por botón
        if self.bypass_pause_sent:  # Se pausó por timeout en bypass
            self.main.show_operator_message("Terapia finalizada", level="warning", timeout_ms=8000)
            # NO apagar therapy_finished_by_time: mantenerla para UI
        else:  # Se pausó por botón
            self.main.show_info_message("Terapia en pausa")
            self.therapy_finished_by_time = False  # Limpiar UI flag (es pausa manual)

        if self.state.current_phase != TreatmentPhase.RUNNING:
            return False
        try:
            self.main._write_boolean_command("dialyModeOperationPause", True)
            return True
        except Exception as e:
            logger.error(f"Error al pausar: {e}")
            return False

    def close_therapy_records_on_timeout(self):
        """
        Cierra registros de terapia cuando el reloj llega a cero.
        Se ejecuta una sola vez (protegida por therapy_records_closed).
        La máquina permanece en pausa; no detiene cebado ni limpia pantalla KTV.
        """
        if self.therapy_records_closed:
            logger.debug("Registros de terapia ya cerrados, ignorando llamada duplicada")
            return

        self.therapy_records_closed = True

        # 1. Tomar tiempo transcurrido ANTES de limpiar contadores
        elapsed_seconds = self.get_elapsed_seconds()
        logger.info(f"Cerrando registros de terapia - Tiempo transcurrido: {elapsed_seconds}s")

        try:
            # 2. Finalizar dosis entregada y guardar reporte Kt/V
            if hasattr(self.main, 'ktv_controller') and self.main.ktv_controller:
                self.main.ktv_controller.finalize_delivered_dose()
                logger.info("KTV finalized_delivered_dose ejecutado")

            if hasattr(self.main, 'KTVScreen') and self.main.KTVScreen:
                self.main.KTVScreen.save_final_report()
                logger.info("KTV final report guardado")

            # 3. Abortar medición en curso (sin reset_screen_data)
            if hasattr(self.main, 'ktv_controller') and self.main.ktv_controller:
                # Abort sin emitir señal para mantener pantalla Kt/V visible
                self.main.ktv_controller.abort("Terapia cerrada por tiempo", emit_signal=False)
                logger.info("KTV abort ejecutado (sin signal)")

            # 4. Registrar sesión de tratamiento y limpiar current_treatment_start
            if hasattr(self.main, 'register_treatment_session'):
                self.main.register_treatment_session()
                logger.info("Sesión de tratamiento registrada")

            if hasattr(self.main, 'current_treatment_start'):
                self.main.current_treatment_start = None

            # 5. Cerrar treatment_logger
            if hasattr(self.main, 'treatment_logger') and self.main.treatment_logger:
                self.main.treatment_logger.close()
                self.main.treatment_logger = None
                logger.info("Treatment logger cerrado")

            # 6. Guardar NibpPressureHistory si tiene método de guardado
            if hasattr(self.main, 'nibp_pressure_history') and self.main.nibp_pressure_history:
                if hasattr(self.main.nibp_pressure_history, 'save'):
                    try:
                        self.main.nibp_pressure_history.save()
                        logger.info("NIBP pressure history guardado")
                    except Exception as e:
                        logger.warning(f"Error guardando NIBP history: {e}")
                else:
                    logger.debug("NibpPressureHistory sin método de guardado, se queda en memoria")

            # 7. TreatmentPhase NO cambia - hardware sigue en PAUSED
            logger.info("Registros de terapia cerrados - Hardware permanece en PAUSED")

        except Exception as e:
            logger.error(f"Error cerrando registros de terapia por timeout: {e}")

    def stop_treatment(self):
        """Detiene completamente el tratamiento (SIN parar el cebado)"""
        try:
            # Comandos al hardware: stop la terapia pero NO el cebado
            self.main._write_boolean_command("dialyModeOperationStop", True)
            self.main._write_boolean_command("dialyModeOperationStart", False)
            # Nota: No escribir dialyStopDialysisButt ni dialyStartDialysisButt
            # porque esos controlan el cebado, que debe permanecer independiente.

            if self.bioz_urea_controller:
                self.bioz_urea_controller.send_command("STOP")

            # Evita arrastre de tiempo entre terapias cuando el hardware
            # tarda en confirmar el cambio de estado.
            self._reset_session_counters(reset_total=True)
            self.bypass_pause_sent = False  # Resetear bandera de bypass
            self.therapy_finished_by_time = False  # Limpiar UI flag

            self.main.show_info_message("Terapia detenida...")
            logger.info("Tratamiento detenido y registrado correctamente")
            return True

        except Exception as e:
            logger.error(f"Error al detener tratamiento: {e}")
            self.main.show_error_message("Error al detener tratamiento")
            return False

    def end_therapy(self):
        """Finaliza completamente la terapia Y el cebado"""
        try:
            # Detiene terapia y cebado
            self.main._write_boolean_command("dialyModeOperationStop", True)
            self.main._write_boolean_command("dialyModeOperationStart", False)
            self.main._write_boolean_command("dialyStopDialysisButt", True)
            self.main._write_boolean_command("dialyStartDialysisButt", False)

            if self.bioz_urea_controller:
                self.bioz_urea_controller.send_command("STOP")

            # Limpia acumuladores
            self._reset_session_counters(reset_total=True)

            # Limpiar banderas
            self.therapy_finished_by_time = False
            self.bypass_pause_sent = False
            # NO limpiar therapy_records_closed aquí - solo se limpia en prepare_new_treatment_session

            # Cierra loggers
            if hasattr(self.main, 'treatment_logger') and self.main.treatment_logger:
                self.main.treatment_logger.close()
                self.main.treatment_logger = None
            if hasattr(self.main, 'csv_logger') and self.main.csv_logger:
                self.main.csv_logger.close()
                self.main.csv_logger = None

            self.main.show_info_message("Terapia finalizada")
            logger.info("Terapia finalizada completamente")
            return True

        except Exception as e:
            logger.error(f"Error al finalizar terapia: {e}")
            self.main.show_error_message("Error al finalizar terapia")
            return False

    # ====================== SINCRONIZACIÓN DE RELOJES ======================
    def start_therapy_timer(self):
        """Inicia o reinicia el timer de terapia cuando hardware confirma RUNNING"""
        if not self.therapy_start_time:
            self.therapy_start_time = QDateTime.currentDateTime()
            logger.info("Timer de terapia iniciado (hardware en RUNNING)")
        else:
            logger.info("Reanudando timer de terapia")

    def pause_therapy_timer(self):
        """Pausa el timer (llamado cuando hardware entra en 15)"""
        if self.therapy_start_time:
            seconds_passed = self.therapy_start_time.secsTo(QDateTime.currentDateTime())
            self.accumulated_therapy_seconds += seconds_passed
            self.therapy_start_time = None
            logger.info(f"Timer de terapia PAUSADO. Acumulado: {self.accumulated_therapy_seconds}s")
    
    def stop_therapy_timer(self):
        """Resetea completamente el timer de sesión cuando se detiene la terapia"""
        logger.info("Reset completo de timer de terapia (nueva sesión)")
        
        self._reset_session_counters(reset_total=True)

        # Limpiar KTV también, pero SOLO si registros no fueron ya cerrados por timeout
        if hasattr(self.main, 'KTVScreen') and self.main.KTVScreen:
            try:
                if not self.therapy_records_closed:
                    self.main.KTVScreen.save_final_report()
                if hasattr(self.main.KTVScreen, 'ktv_records'):
                    self.main.KTVScreen.ktv_records.clear()
                if hasattr(self.main.KTVScreen, 'ktv_points'):
                    self.main.KTVScreen.ktv_points.clear()
                if hasattr(self.main.KTVScreen, 'heit_points'):
                    self.main.KTVScreen.heit_points.clear()
            except Exception as e:
                logger.warning(f"Error limpiando KTV: {e}")
        print("si se ejecuto en Treatment_controller")

    def get_elapsed_seconds(self) -> int:
        """Elapsed de la terapia actual (no usa TimerManager)"""
        if not self.therapy_start_time:
            return self.accumulated_therapy_seconds

        now = QDateTime.currentDateTime()
        elapsed_this_session = self.therapy_start_time.secsTo(now)
        return self.accumulated_therapy_seconds + elapsed_this_session

    def get_elapsed_therapy_minutes(self) -> float:
        """Tiempo transcurrido de terapia en minutos para consumidores como Kt/V."""
        return self.get_elapsed_seconds() / 60.0

    def update_therapy_times(self):
        phase = self.state.current_phase
        status_code = int(self.main.current_values.get("primingProcessStatus", 0))

        # Fuera de terapia
        if phase not in (TreatmentPhase.RUNNING, TreatmentPhase.PAUSED):
            hours = int(self.main.current_values.get("heparineTherapyHours", 0))
            minutes = int(self.main.current_values.get("heparineTherapyMinutes", 0))
            self.total_therapy_seconds = self._get_programmed_total_seconds()
            
            remaining_str = f"{hours:02d}:{minutes:02d}:00"
            if hasattr(self.main, 'dialysis_screen') and self.main.dialysis_screen:
                self.main.dialysis_screen.update_therapy_times("00:00:00", remaining_str)
            if hasattr(self.main, 'update_remaining_time_header'):
                self.main.update_remaining_time_header(remaining_str)
            return

        # Terapia activa
        if self.total_therapy_seconds <= 0:
            self.total_therapy_seconds = self._get_programmed_total_seconds()

        current_elapsed = self.get_elapsed_seconds()
        remaining = max(0, self.total_therapy_seconds - current_elapsed)

        # Si tiempo llega a cero en RUNNING y estado es 14 (bypass), pausar una sola vez
        if self.total_therapy_seconds > 0 and remaining <= 0 and phase == TreatmentPhase.RUNNING and status_code == 14:
            if not self.bypass_pause_sent:
                logger.info("Tiempo de terapia completado - Pausando en bypass")
                # Establecer banderas ANTES de llamar pause_treatment() para que el aviso sea correcto
                self.bypass_pause_sent = True
                self.therapy_finished_by_time = True
                self.pause_treatment()
                # Cerrar registros de terapia UNA SOLA VEZ
                self.close_therapy_records_on_timeout()
            return

        if hasattr(self.main, 'dialysis_screen') and self.main.dialysis_screen:
            elapsed_str = f"{current_elapsed // 3600:02d}:{(current_elapsed % 3600) // 60:02d}:{current_elapsed % 60:02d}"
            remaining_str = f"{remaining // 3600:02d}:{(remaining % 3600) // 60:02d}:{remaining % 60:02d}"
            self.main.dialysis_screen.update_therapy_times(elapsed_str, remaining_str)
            if hasattr(self.main, 'update_remaining_time_header'):
                self.main.update_remaining_time_header(remaining_str)
