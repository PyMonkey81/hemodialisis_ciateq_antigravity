import logging

from PySide6.QtCore import QDateTime

from core.state_manager import TreatmentPhase

logger = logging.getLogger(__name__)


class CleaningSession:
    def __init__(self, window):
        self.window = window

    def _on_cleaning_started(self):
        logger.info("Limpieza INICIADA")
        self.window.is_cleaning_in_progress = True
        self.window.ktv_controller.abort("Limpieza iniciada")  # Abortar Kt/V si limpieza empieza

    def _on_cleaning_finished(self):
        logger.info("Limpieza FINALIZADA")
        self.window.is_cleaning_in_progress = False

    def _handle_cleaning_status_change(self, is_cleaning_active: bool):
        logger.info(f"[CLEANING] Señal recibida → Activo: {is_cleaning_active}")

        if is_cleaning_active:
            self.window.state.set_phase(TreatmentPhase.CLEANING, "Inicio de limpieza")
            # La hora de inicio de historial debe fijarse en el primer tramo ACTIVO real
            # (cuando CleaningScreen emite cleaning_started_counting al entrar a estado 6).
            self.window.cleaning_start_time = None
            self.window._start_cleaning_logger()
        else:
            self.window.state.set_phase(TreatmentPhase.IDLE, "Fin de limpieza")
            self.window._stop_cleaning_logger()
            # self.cleaning_start_time = None # Esto se reinicia al finalizar, lo cual es correcto.
            #                                # Sin embargo, lo mantendremos para el registro en el historial
            #                                # y luego lo estableceremos a None en el método de registro.

    def _set_cleaning_start_time(self):
        """Se llama exactamente cuando el cronómetro entra al estado 6"""
        if self.window.cleaning_start_time is None:
            self.window.cleaning_start_time = QDateTime.currentDateTime()
            logger.info("Hora de inicio de limpieza (primer tramo activo) registrada para el historial.")
        else:
            logger.debug(
                "Se ignoró una nueva marca de inicio de limpieza para conservar la hora original de la sesión."
            )

    def pause_cleaning_timer(self):
        """Llamado desde CleaningScreen"""
        if hasattr(self.window, 'timer_manager'):
            self.window.timer_manager.pause_cleaning_timer()

    def resume_cleaning_timer(self):
        """Llamado desde CleaningScreen"""
        if hasattr(self.window, 'timer_manager'):
            self.window.timer_manager.resume_cleaning_timer()
