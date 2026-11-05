import logging

from core.state_manager import TreatmentPhase
from utilities.platform_runtime import (
    get_runtime_config_path,
    safe_int,
    safe_json_load,
)

logger = logging.getLogger(__name__)

NIBP_CONFIG_PATH = get_runtime_config_path("nibp_config.json")
NIBP_DEFAULT_CONFIG = {
    "enabled": False,
    "port": "Auto",
    "baudrate": 19200,
    "patient_mode": "adult",
    "method": 2,
    "start_pressure_mmhg": 160,
    "auto_during_therapy": False,
    "interval_min": 15,
    "spo2_enabled": False,
}
# Primera toma automática 30s después de RUNNING; luego cada interval_min minutos.
NIBP_AUTO_FIRST_MEASURE_DELAY_S = 30


class NibpCoordinator:
    def __init__(self, window):
        self.window = window

    def _apply_nibp_auto_spo2_for_phase(self, phase: TreatmentPhase):
        """RUNNING/PAUSED + spo2_enabled: mantiene el stream SpO2 (interval_min nunca dispara 31).

        No se apaga en PAUSED para no perder el clip/sensor; solo se apaga al salir
        de la sesión de terapia (IDLE/READY/etc.).
        """
        loaded = safe_json_load(NIBP_CONFIG_PATH, {})
        if not isinstance(loaded, dict):
            loaded = {}
        config = {**NIBP_DEFAULT_CONFIG, **loaded}
        auto_spo2_wanted = bool(config.get("spo2_enabled"))

        if not auto_spo2_wanted:
            return

        should_stream = phase in (TreatmentPhase.RUNNING, TreatmentPhase.PAUSED)
        if should_stream and not self.window._nibp_auto_spo2_active:
            self.window._nibp_auto_spo2_active = True
            self.window.nibp.spo2_on()
        elif not should_stream and self.window._nibp_auto_spo2_active:
            self.window._nibp_auto_spo2_active = False
            self.window.nibp.spo2_off()

    def _on_nibp_measure_requested(self):
        """Limpia SYS/DIA/MAP/FC y el error previo (NO toca SpO2, es un stream aparte) y dispara la toma."""
        self.window.nibp_screen.update_measurement(-1, -1, -1, -1)
        self.window.nibp_screen.clear_error()
        self.window.dialysis_screen.update_nibp_measurement(-1, -1, -1, -1)
        self.window._nibp_measuring = True
        self.window.nibp.start_measurement()

    def _check_nibp_auto_measurement(self):
        """Dispara PA automática con el reloj de terapia (no un QTimer propio de NibpConfigScreen).

        Primera toma NIBP_AUTO_FIRST_MEASURE_DELAY_S después de entrar a RUNNING;
        luego una cada interval_min minutos mientras siga en RUNNING.
        """
        if self.window.state.current_phase != TreatmentPhase.RUNNING:
            return

        loaded = safe_json_load(NIBP_CONFIG_PATH, {})
        if not isinstance(loaded, dict):
            loaded = {}
        config = {**NIBP_DEFAULT_CONFIG, **loaded}
        if not config.get("auto_during_therapy"):
            return

        interval_min = safe_int(config.get("interval_min", 15), 15)
        if interval_min <= 0:
            return

        elapsed_s = self.window.treatment_controller.get_elapsed_seconds()
        if elapsed_s < NIBP_AUTO_FIRST_MEASURE_DELAY_S:
            return

        interval_s = interval_min * 60
        current_index = (elapsed_s - NIBP_AUTO_FIRST_MEASURE_DELAY_S) // interval_s
        if current_index == self.window._nibp_auto_last_interval_index or self.window._nibp_measuring:
            return

        self.window._nibp_auto_last_interval_index = current_index
        self.window._on_nibp_measure_requested()

    def _load_nibp_config_and_apply(self):
        """Carga config/nibp_config.json y aplica update_config; enabled=False no abre puerto."""
        loaded = safe_json_load(NIBP_CONFIG_PATH, {})
        if not isinstance(loaded, dict):
            loaded = {}
        config = {**NIBP_DEFAULT_CONFIG, **loaded}
        self.window.nibp.update_config(config.get("port", "Auto"), config.get("enabled", False))

    def _on_nibp_connected_changed(self, connected: bool, port: str):
        logger.info(f"[NIBP] connected_changed: conectado={connected} | puerto={port} | NIBP2020 UP")

    def _on_nibp_error_message(self, error_code: str, error_text: str):
        logger.warning(f"[NIBP] {error_code}: {error_text}")
        self.window._nibp_measuring = False

    def _on_nibp_measurement_ready(self, sys_mmhg: int, dia_mmhg: int, map_mmhg: int, hr_bpm: int):
        logger.info(f"[NIBP] Medición lista: SYS={sys_mmhg} DIA={dia_mmhg} MAP={map_mmhg} HR={hr_bpm}")
        self.window._nibp_measuring = False

    def _on_nibp_measure_requested_for_history(self):
        """Se llama cuando se presiona "Medir ahora": marca la próxima medición como manual."""
        self.window._nibp_measure_is_manual = True

    def _on_nibp_measurement_ready_for_history(self, sys_mmhg: int, dia_mmhg: int, map_mmhg: int, hr_bpm: int):
        """Registra la medición en el historial (validación ya hecha por measurement_ready)."""
        # Validar que sea una medición válida (sys, dia, hr >= 0)
        if sys_mmhg < 0 or dia_mmhg < 0 or hr_bpm < 0:
            return
        
        # Calcular elapsed_s (tiempo desde inicio de RUNNING)
        elapsed_s = None
        if self.window.state.current_phase == TreatmentPhase.RUNNING:
            elapsed_s = self.window.treatment_controller.current_elapsed
        
        # Determinar origen (manual o auto)
        origen = "manual" if self.window._nibp_measure_is_manual else "auto"
        self.window._nibp_measure_is_manual = False  # Reset para la próxima medición
        
        # Agregar al historial con último SpO2 válido si existe
        self.window.nibp_pressure_history.add_measurement(
            sys=sys_mmhg,
            dia=dia_mmhg,
            map_mmhg=map_mmhg,
            hr=hr_bpm,
            elapsed_s=elapsed_s,
            spo2=getattr(self.window, "_last_spo2_value", None),
            origen=origen
        )
        if hasattr(self.window, "nibp_history_screen"):
            self.window.nibp_history_screen.update_from_history()
        if hasattr(self.window, "nibp_chart_screen"):
            self.window.nibp_chart_screen.update_from_history()
        if hasattr(self.window, "session_tracker"):
            uf_rem_l = self.window.dialysis_screen._uf_removed_liters() if hasattr(self.window, "dialysis_screen") else 0.0
            self.window.session_tracker.on_nibp_measurement(
                sys_mmhg=sys_mmhg,
                dia_mmhg=dia_mmhg,
                map_mmhg=map_mmhg,
                hr_bpm=hr_bpm,
                origen=origen,
                current_values=self.window.current_values,
                elapsed_s=elapsed_s,
                uf_removed_liters=uf_rem_l,
            )
        logger.info(f"[NIBP History] Medición registrada: origen={origen}, elapsed_s={elapsed_s}, spo2={getattr(self.window, '_last_spo2_value', None)}")

    def _on_nibp_settings_applied(self, config: dict):
        """Aplica patient_mode/method/start_pressure/spo2 al módulo; el ciclo queda en manual (otro ticket)."""
        # patient_mode siempre es "adult" en esta entrega (UI + default NIBP)
        self.window.nibp.set_adult_mode()

        self.window.nibp.set_method(int(config.get("method", 2)))
        self.window.nibp.set_start_pressure_mmhg(int(config.get("start_pressure_mmhg", 160)))
        self.window.nibp.set_cycle_minutes(None)  # siempre manual en esta entrega

        if config.get("spo2_enabled"):
            self.window.nibp.spo2_on()
        else:
            self.window.nibp.spo2_off()

        logger.info(f"[NIBP] Configuración clínica aplicada: {config}")

    def _on_nibp_reset_requested(self):
        """Reset manual del módulo NIBP solicitado por el usuario."""
        self.window.nibp.software_reset()
