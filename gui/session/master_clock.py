from PySide6.QtCore import QDateTime

from core.state_manager import TreatmentPhase


class MasterClock:
    def __init__(self, window):
        self.window = window

    def prepare_clock(self):
        # Control de tiempo de terapia (global)
        self.window.therapy_start_time = None
        self.window.total_therapy_seconds = 0
        self.window.accumulated_therapy_seconds = 0

        self.window.current_treatment_start_date_time = None  # Variable para reporte de inicio/tratamiento
        self.window.navigation_buttons = {}  # nuevo

    def _master_timer_tick(self):
        """Timer Maestro Centralizado"""
        if self.window._timer_lock:
            return
        self.window._timer_lock = True
        try:
            now = QDateTime.currentDateTime()
            second_elapsed = self.window.last_second_update.msecsTo(now) >= 1000
            minute_elapsed = self.window.last_minute_update.secsTo(now) >= 60

            # Mantener vivo el monitoreo de alarmas aunque no lleguen tramas nuevas.
            self.window._sync_alarm_values_from_current_state()

            self.window.ktv_controller.on_master_tick()

            # ==================== LOGGERS ====================
            if self.window.state.current_phase == TreatmentPhase.RUNNING:
                self.window._log_treatment_current_data()  # Logger de tratamiento

            elif self.window.state.current_phase == TreatmentPhase.CLEANING:
                self.window._log_cleaning_current_data()  # Logger de limpieza

            elif self.window.state.current_phase == TreatmentPhase.PREPARING:
                self.window._log_current_data()  # Cebado / Priming (el general)

            self.window._update_gauges()

            if second_elapsed:
                self.window.update_connection_status()
                self.window.session_recorder.on_second()
                self.window.update_date_time()

                if self.window.state.current_phase in (
                    TreatmentPhase.RUNNING,
                    TreatmentPhase.PAUSED,
                    TreatmentPhase.IDLE,
                ):
                    self.window.treatment_controller.update_therapy_times()

                if self.window.state.current_phase == TreatmentPhase.RUNNING and hasattr(
                    self.window, "session_tracker"
                ):
                    uf_rem_l = (
                        self.window.dialysis_screen._uf_removed_liters()
                        if hasattr(self.window, "dialysis_screen")
                        else 0.0
                    )
                    self.window.session_tracker.on_therapy_tick(
                        self.window.current_values,
                        float(self.window.treatment_controller.get_elapsed_seconds()),
                        uf_removed_liters=uf_rem_l,
                    )

                self.window.nibp_coordinator.on_second()
                self.window.profile_coordinator.on_second()
                self.window.heparin_coordinator.on_second()

                # Actualizar encabezado durante la espera de 90 s después del llenado de filtro
                self.window._update_header_during_filter_fill()

                if self.window.screen_stack.currentWidget() == self.window.maintenance_screen:
                    self.window.timer_manager._update_maintenance_screen()

                self.window._refresh_navigation_bar()
                self.window.last_second_update = now

            if minute_elapsed:
                self.window.last_minute_update = now

        finally:
            self.window._timer_lock = False
