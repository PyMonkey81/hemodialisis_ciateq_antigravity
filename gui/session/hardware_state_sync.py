import logging

from core.state_manager import TreatmentPhase
from utilities.platform_runtime import safe_int

logger = logging.getLogger(__name__)


class HardwareStateSync:
    def __init__(self, window):
        self.window = window

    def _sync_state_with_hardware(self):
        return sync_state_with_hardware(self.window)


def sync_state_with_hardware(window):
    """Sincroniza el estado interno con el estado real del hardware (fuente de verdad)"""
    if not hasattr(window, "current_values"):
        return

    status_code = safe_int(window.current_values.get("primingProcessStatus", 0), 0)
    treatment_mode = safe_int(window.current_values.get("treatmentModeSelection", 0), 0)
    reason = "Sincronización automática con hardware"

    logger.info(f"Sincronizando estado - Status: {status_code}, Mode: {treatment_mode}")

    mapper = getattr(window, "hardware_mapper", None)
    if mapper is not None:
        target_phase = mapper.get_phase(status_code, treatment_mode)
        if target_phase == TreatmentPhase.CLEANING:
            window.state.set_phase(TreatmentPhase.CLEANING, reason)
            if hasattr(window, "current_process_status") and window.current_process_status is not None:
                window.current_process_status.setText(mapper.get_display_text(status_code, treatment_mode))
            if hasattr(window, "screen_state_manager") and window.screen_state_manager is not None:
                window.screen_state_manager.update_all_screens(TreatmentPhase.CLEANING)
            window._refresh_navigation_bar()
            return
        elif target_phase == TreatmentPhase.IDLE and status_code not in (1, 16):
            window.state.set_phase(TreatmentPhase.IDLE, "Sincronización inicial - Sin actividad")
        else:
            window.state.set_phase(target_phase, reason)
        if hasattr(window, "screen_state_manager") and window.screen_state_manager is not None:
            window.screen_state_manager.update_all_screens(target_phase)
        return

    # Modo Limpieza (sin mapper)
    if treatment_mode == 3:
        if status_code == 6:  # Infusión = limpieza activa
            window.state.set_phase(TreatmentPhase.CLEANING, reason)
            if hasattr(window, "screen_state_manager") and window.screen_state_manager is not None:
                window.screen_state_manager.update_all_screens(TreatmentPhase.CLEANING)
            window._refresh_navigation_bar()
        elif status_code in [2, 3, 4, 5]:
            window.state.set_phase(TreatmentPhase.PREPARING, reason)
            if hasattr(window, "screen_state_manager") and window.screen_state_manager is not None:
                window.screen_state_manager.update_all_screens(TreatmentPhase.PREPARING)
        else:
            window.state.reset_to_idle(reason)
        return

    if status_code == 13:
        window.state.set_phase(TreatmentPhase.READY, reason)
        window.screen_state_manager.update_all_screens(TreatmentPhase.READY)
    elif status_code == 14:
        window.state.set_phase(TreatmentPhase.RUNNING, reason)
        window.screen_state_manager.update_all_screens(TreatmentPhase.RUNNING)
    elif status_code == 15:
        window.state.set_phase(TreatmentPhase.PAUSED, reason)
        window.screen_state_manager.update_all_screens(TreatmentPhase.PAUSED)
    elif status_code in [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]:
        window.state.set_phase(TreatmentPhase.PREPARING, reason)
        window.screen_state_manager.update_all_screens(TreatmentPhase.PREPARING)
    else:
        window.state.set_phase(TreatmentPhase.IDLE, "Sincronización inicial - Sin actividad")
        window.screen_state_manager.update_all_screens(TreatmentPhase.IDLE)
