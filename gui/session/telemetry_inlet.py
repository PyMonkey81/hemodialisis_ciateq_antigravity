import logging
import time
from collections import deque

from PySide6.QtCore import QDateTime, QTimer

from core.state_manager import TreatmentPhase
from gui.theme_manager import ThemeManager
from logic.calculos import (
    convertir_ciclos_a_flujo,
    convertir_ml_min_a_litros_h,
)
from utilities.platform_runtime import safe_int

logger = logging.getLogger(__name__)

LOCAL_SETPOINT_TAGS = {
    "heparineTherapyHours",
    "heparineTherapyMinutes",
}


class TelemetryInlet:
    def __init__(self, window):
        self.window = window

    def update_value(self, tag: str, value: float):
        # Estos setpoints son locales de UI y no deben ser pisados por telemetría.
        # Solo deben cambiar por acción explícita del usuario.
        if tag in LOCAL_SETPOINT_TAGS:
            logger.debug("Ignorando actualización externa de setpoint local: %s=%s", tag, value)
            return

        # Verificar si este tag debe ser ignorado hasta cierto tiempo (para evitar que la
        # lectura vieja del firmware pise valores recién enviados)
        if tag in self.window.ignore_tags_until:
            if time.time() < self.window.ignore_tags_until[tag]:
                logger.debug(f"[HEPARIN-SYNC] Ignorando lectura de {tag}={value} (bloqueado hasta reconf. firmware)")
                return
            else:
                del self.window.ignore_tags_until[tag]

        # 1. Pre-procesamiento y conversión de unidades ANTES de guardar o enviar a alarmas
        if tag == "dialyCondControlOutput":
            value = value / 5.0

        elif tag == "ultraFilterPumpSpeed":
            try:
                # Convertimos directamente el 'value' entrante (ml/min -> L/h)
                value = convertir_ml_min_a_litros_h(value)
            except Exception as e:
                logger.error(f"Error converting UF flow: {e}")

        elif tag == "balanceChamberSetTiming":
            try:
                # Convertimos directamente el 'value' entrante (ciclos -> ml/min)
                value = convertir_ciclos_a_flujo(value)
            except Exception as e:
                logger.error(f"Error converting CB flow: {e}")

        # Calcular promedio de temperatura SOLO PARA DISPLAY (incluso si el valor no cambió)
        if tag == "dialyTempIFProcessData":
            if not hasattr(self.window, "temp_readings") or self.window.temp_readings is None:
                self.window.temp_readings = deque()
            current_time = time.monotonic()
            self.window.temp_readings.append((current_time, value))
            while self.window.temp_readings and (current_time - self.window.temp_readings[0][0]) > 3.0:
                self.window.temp_readings.popleft()
            if self.window.temp_readings:
                self.window.dialyTempIFProcessData_avg = (
                    sum(v for _, v in self.window.temp_readings) / len(self.window.temp_readings)
                )
            else:
                self.window.dialyTempIFProcessData_avg = value

        # Evita trabajo redundante cuando el valor entrante no cambia.
        previous_value = self.window.current_values.get(tag)
        if previous_value == value:
            return

        # 2. Actualizar el valor centralizado (Ya convertido de manera segura)
        self.window.current_values[tag] = value

        # Actualizar sistema de alarmas si existe
        if self.window.alarm_system:
            self.window.alarm_system.update_value_by_tag(tag, value)

        # Manejo del tratamiento seleccionado
        if tag == "treatmentModeSelection":
            self.window.refresh_treatment_selected()  # Llama al nuevo método para actualizar el label
            self.window._update_treatment_mode_label_state()
            try:
                status_code = safe_int(self.window.current_values.get("primingProcessStatus", 0), 0)
                treatment_mode = safe_int(value, 0)
                if hasattr(self.window, "hardware_mapper") and self.window.hardware_mapper is not None:
                    new_phase = self.window.hardware_mapper.get_phase(status_code, treatment_mode)
                    display_text = self.window.hardware_mapper.get_display_text(status_code, treatment_mode)
                    if hasattr(self.window, "current_process_status") and self.window.current_process_status is not None:
                        self.window.current_process_status.setText(display_text)
                    if (
                        hasattr(self.window, "state")
                        and self.window.state is not None
                        and new_phase != self.window.state.current_phase
                    ):
                        self.window.state.set_phase(new_phase, f"Hardware → {display_text}")
                        self.window._refresh_navigation_bar()
            except Exception as e:
                logger.warning(f"Error sincronizando estado al cambiar modo de tratamiento: {e}")

        # Verificar si se completó el bolo pendiente o si se agotó la heparina cuando llega heparineCurrentDosage
        if tag == "heparineCurrentDosage":
            if hasattr(self.window, "heparin_config_screen") and self.window.heparin_config_screen is not None:
                if (
                    hasattr(self.window.heparin_config_screen, "current_values")
                    and isinstance(self.window.heparin_config_screen.current_values, dict)
                ):
                    self.window.heparin_config_screen.current_values[tag] = value
                self.window.heparin_config_screen._check_pending_bolus_completed()
                self.window.heparin_config_screen._check_heparin_depletion()

        # ────────────────────────────────────────────────────────────────
        # Manejo de primingProcessStatus (estado del proceso + horas de operación)
        # ────────────────────────────────────────────────────────────────
        if tag == "primingProcessStatus":
            try:
                status_code = int(value)
            except (TypeError, ValueError):
                logger.warning("primingProcessStatus inválido recibido: %r", value)
                return

            if status_code != self.window._last_priming_status:
                logger.info(f"Cambio de estado hardware: {self.window._last_priming_status} → {status_code}")
                self.window._last_priming_status = status_code

                if not hasattr(self.window, "current_process_status") or self.window.current_process_status is None:
                    logger.warning("current_process_status no está inicializado; ignorando cambio de estado hardware.")
                    return

                if not hasattr(self.window, "state") or self.window.state is None:
                    logger.warning("state no está inicializado; ignorando cambio de estado hardware.")
                    return

                if not hasattr(self.window, "hardware_mapper") or self.window.hardware_mapper is None:
                    logger.warning("hardware_mapper no está inicializado; ignorando cambio de estado hardware.")
                    return

                treatment_mode = int(self.window.current_values.get("treatmentModeSelection", 0))

                # === NUEVA LÓGICA ===
                new_phase = self.window.hardware_mapper.get_phase(status_code, treatment_mode)
                display_text = self.window.hardware_mapper.get_display_text(status_code, treatment_mode)

                self.window.current_process_status.setText(display_text)
                self.window._update_header_during_filter_fill()

                old_phase = self.window.state.current_phase  # ← Guardamos siempre el estado anterior

                # Cambiar fase + acciones solo si realmente cambió
                if new_phase != old_phase:
                    if not (old_phase == TreatmentPhase.CLEANING and new_phase != TreatmentPhase.CLEANING):
                        reason = f"Hardware → {display_text}"
                        self.window.state.set_phase(new_phase, reason)
                        if hasattr(self.window, "screen_state_manager") and self.window.screen_state_manager is not None:
                            self.window.screen_state_manager.update_all_screens(new_phase)

                        # === CONTROL DEL TIMER DE TERAPIA SEGÚN HARDWARE ===
                        treatment_controller = getattr(self.window, 'treatment_controller', None)
                        if treatment_controller is not None:
                            if new_phase == TreatmentPhase.RUNNING:
                                treatment_controller.start_therapy_timer()

                                if not self.window.current_treatment_start:
                                    self.window.current_treatment_start = QDateTime.currentDateTime()
                                # Logger: nueva sesión o reanudación
                                is_resuming = (old_phase == TreatmentPhase.PAUSED)
                                treatment_controller._setup_treatment_logger(is_resuming)

                            elif new_phase == TreatmentPhase.PAUSED:
                                treatment_controller.pause_therapy_timer()
                            elif new_phase == TreatmentPhase.READY and old_phase in (
                                TreatmentPhase.RUNNING,
                                TreatmentPhase.PAUSED,
                            ):
                                # Si el hardware vuelve a READY sin pasar por IDLE,
                                # se limpia la sesión previa para evitar arrastre de tiempo.
                                treatment_controller.prepare_new_treatment_session()
                                self.window.current_treatment_start = None

                # === REGISTRO DE HISTORIAL AL FINALIZAR TRATAMIENTO ===
                if new_phase == TreatmentPhase.IDLE and old_phase in (
                    TreatmentPhase.RUNNING,
                    TreatmentPhase.PAUSED,
                    TreatmentPhase.READY,
                    TreatmentPhase.PREPARING,
                ):
                    logger.info("Hardware confirmó fin de tratamiento → Registrando historial")
                    if hasattr(self.window, 'register_treatment_session'):
                        self.window.register_treatment_session()
                        logger.debug("Historial de tratamiento registrado")

                    # Cerrar logger
                    if hasattr(self.window, 'treatment_logger') and self.window.treatment_logger:
                        self.window.treatment_logger.close()
                        self.window.treatment_logger = None

                    treatment_controller = getattr(self.window, 'treatment_controller', None)
                    if treatment_controller is not None:
                        treatment_controller.stop_therapy_timer()
                        logger.debug("Timer de terapia detenido tras transición a IDLE")

                # Sincronizar timers del TimerManager
                timer_manager = getattr(self.window, 'timer_manager', None)
                if timer_manager is not None:
                    timer_manager.sync_with_hardware(status_code)

                # Mensaje especial para colocar filtro
                if status_code == 7 and self.window._last_status_prompt != 7:
                    # Usar QTimer.singleShot para no anidar diálogo dentro de lectura serial
                    QTimer.singleShot(0, self.window._show_filter_fill_dialog_main)
                    self.window._last_status_prompt = 7
                elif status_code != 7:
                    self.window._last_status_prompt = None

                # ==================== COLORES ====================
                tokens = ThemeManager.get_tokens()
                is_mono = bool(tokens.get("monochrome", False))
                is_dark = bool(tokens.get("is_dark", False))

                if is_mono:
                    self.window.current_process_status.setStyleSheet("""
                        QLabel {
                            color: #111827;
                            background: #9CA3AF;
                            font-weight: bold;
                            font-size: 25px;
                            border-radius: 10px;
                            border: 1px solid #6B7280;
                        }
                    """)
                elif is_dark:
                    if status_code in [15, 16]:
                        c_bg = tokens.get('danger', '#ef4444')
                        c_text = '#ffffff'
                    elif status_code in [6, 7, 13, 14]:
                        c_bg = tokens.get('success', '#10b981')
                        c_text = '#ffffff'
                    else:
                        c_bg = tokens.get('bg_card_alt', '#1E293B')
                        c_text = tokens.get('text_primary', '#F8FAFC')
                    self.window.current_process_status.setStyleSheet(f"""
                        QLabel {{
                            color: {c_text};
                            background: {c_bg};
                            font-weight: bold;
                            font-size: 25px;
                            border-radius: 10px;
                            border: 1px solid {tokens.get('border_card', '#334155')};
                        }}
                    """)
                else:
                    if status_code in [6, 7, 13]:
                        color = "#2bbd37"
                    elif status_code in [1, 2, 3, 4, 5, 8]:
                        color = "#06298a"
                    elif status_code == 14:
                        color = "#2bbd37"
                    elif status_code in [15, 16]:
                        color = "#ef4444"
                    else:
                        color = "#C6E3E6"

                    self.window.current_process_status.setStyleSheet(f"""
                        QLabel {{
                            color: #ffffff;
                            background: {color};
                            font-weight: bold;
                            font-size: 25px;
                            border-radius: 10px;
                        }}
                    """)

    def _get_temperature_display_value(self):
        """Retorna el promedio de temperatura de los últimos 3 segundos para display.
        El promedio se calcula una sola vez en update_value().
        Mantiene el valor raw en current_values para alarmas y perfiles."""
        if getattr(self.window, "temp_readings", None):
            return self.window.dialyTempIFProcessData_avg
        return self.window.current_values.get("dialyTempIFProcessData", 0.0)
