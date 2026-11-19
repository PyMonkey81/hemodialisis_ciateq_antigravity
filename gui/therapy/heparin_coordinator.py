import logging
import time

from core.state_manager import TreatmentPhase
from gui.therapy.heparin_config_screenV2 import (
    HEPARIN_AUTO_STOP_HOURS_TAG,
    HEPARIN_AUTO_STOP_MINUTES_TAG,
)
from logic.heparin_time import clamp_heparin_time, was_clamped
from utilities.platform_runtime import safe_int

logger = logging.getLogger(__name__)


class HeparinCoordinator:
    def __init__(self, window):
        self.window = window

    def arm_session(self):
        self.window._heparin_auto_stop_latched = False
        self.window._heparin_running_clamped = False
        self.window._heparin_infusion_forced_stop_latched = False

    def _validate_and_clamp_heparin_auto_stop_time(self):
        """
        Valida y ajusta el tiempo de paro automático de heparina según la regla clínica.
        
        Si el tiempo guardado excede el máximo permitido:
        - Lo recorta al máximo
        - Persiste heparineAutoStopHours, heparineAutoStopMinutes
        - Recalcula y persiste heparineTherapyDosage
        - Envía los valores al firmware via _write_setpoint (paso 2)
        - Marca los tags para ignorar lecturas durante 3s (paso 3)
        - Actualiza la pantalla de heparina (si existe)
        - Muestra un aviso
        
        Al terminar, loguea el estado en los tres sitios para verificar sincronía:
        1. Tags del padre (appMainHemodialysis.current_values)
        2. Tags de la pantalla (HeparinConfigScreen.current_values)
        3. Texto del widget (input_heparin_auto_stop)
        """
        # Si la infusión de heparina está deshabilitada, no hacer nada
        heparin_enabled = bool(self.window.current_values.get("heparineInfusionEnabled", 1.0))
        if not heparin_enabled:
            logger.info("[HEPARIN-VALIDATION] Infusión deshabilitada, omitiendo validación")
            return

        try:
            # Obtener tiempos actuales guardados
            auto_h = int(self.window.current_values.get("heparineAutoStopHours", 0) or 0)
            auto_m = int(self.window.current_values.get("heparineAutoStopMinutes", 0) or 0)
            
            # Calcular tiempo de referencia usando siempre la duración programada de la terapia (NO restante)
            # Máximo = max(0, minutos programados de terapia - 30)
            therapy_h = int(self.window.current_values.get("heparineTherapyHours", 0) or 0)
            therapy_m = int(self.window.current_values.get("heparineTherapyMinutes", 0) or 0)
            programmed_minutes = (therapy_h * 60) + therapy_m
            ref_min = max(0, programmed_minutes)
            
            # Validar y recortar
            if was_clamped(auto_h, auto_m, ref_min):
                clamped_h, clamped_m = clamp_heparin_time(auto_h, auto_m, ref_min)
                
                logger.warning(
                    f"[HEPARIN-VALIDATION] Tiempo {auto_h:02d}:{auto_m:02d} "
                    f"excede máximo {clamped_h:02d}:{clamped_m:02d}. Acotando."
                )
                
                # Paso 1: Escribe heparineAutoStopHours y heparineAutoStopMinutes en current_values
                self.window.current_values["heparineAutoStopHours"] = float(clamped_h)
                self.window.current_values["heparineAutoStopMinutes"] = float(clamped_m)
                
                # Persistir en la base de datos/configuración local
                self.window._persist_therapy_config_tag("heparineAutoStopHours", float(clamped_h))
                self.window._persist_therapy_config_tag("heparineAutoStopMinutes", float(clamped_m))
                
                # Recalcular dosis con el tiempo recortado
                time_hours = clamped_h + (clamped_m / 60.0)
                flow_ml_per_h = self._get_heparin_flow_ml_per_h()
                dosage_ml = round(time_hours * flow_ml_per_h, 2)
                
                self.window.current_values["heparineTherapyDosage"] = dosage_ml
                self.window._persist_therapy_config_tag("heparineTherapyDosage", dosage_ml)
                
                # Actualizar pantalla de heparina si existe
                if (hasattr(self.window, 'heparin_config_screen') and 
                    self.window.heparin_config_screen is not None):
                    self.window.heparin_config_screen.input_heparin_auto_stop.setText(
                        f"{clamped_h:02d}:{clamped_m:02d}"
                    )
                    self.window.heparin_config_screen.current_values["heparineAutoStopHours"] = float(clamped_h)
                    self.window.heparin_config_screen.current_values["heparineAutoStopMinutes"] = float(clamped_m)
                    self.window.heparin_config_screen.current_values["heparineTherapyDosage"] = dosage_ml
                
                # Paso 3: Marcar estos tags para ignorar lecturas durante 3 segundos
                # (evita que la lectura vieja del firmware pise el nuevo valor)
                ignore_until = time.time() + 3.0
                self.window.ignore_tags_until["heparineAutoStopHours"] = ignore_until
                self.window.ignore_tags_until["heparineAutoStopMinutes"] = ignore_until
                self.window.ignore_tags_until["heparineTherapyDosage"] = ignore_until
                logger.info(f"[HEPARIN-VALIDATION] Bloqueando lecturas de heparina durante 3s")

                # Paso 2: Enviar los valores recortados al firmware mediante _write_setpoint
                # (mismo camino que usa el numpad de Tiempo Heparina)
                logger.info("[HEPARIN-VALIDATION] Enviando valores recortados al firmware...")
                self.window._write_setpoint("heparineAutoStopHours", float(clamped_h))
                self.window._write_setpoint("heparineAutoStopMinutes", float(clamped_m))
                self.window._write_setpoint("heparineTherapyDosage", dosage_ml)
                
                # Log de verificación
                padre_h = int(self.window.current_values.get("heparineAutoStopHours", 0) or 0)
                padre_m = int(self.window.current_values.get("heparineAutoStopMinutes", 0) or 0)
                padre_dosage = float(self.window.current_values.get("heparineTherapyDosage", 0.0) or 0.0)
                
                pantalla_h = pantalla_m = pantalla_dosage = None
                widget_text = None
                
                if (hasattr(self.window, 'heparin_config_screen') and 
                    self.window.heparin_config_screen is not None):
                    pantalla_h = int(self.window.heparin_config_screen.current_values.get(
                        "heparineAutoStopHours", 0) or 0)
                    pantalla_m = int(self.window.heparin_config_screen.current_values.get(
                        "heparineAutoStopMinutes", 0) or 0)
                    pantalla_dosage = float(self.window.heparin_config_screen.current_values.get(
                        "heparineTherapyDosage", 0.0) or 0.0)
                    widget_text = self.window.heparin_config_screen.input_heparin_auto_stop.text()
                
                sync_ok = (
                    padre_h == clamped_h and
                    padre_m == clamped_m and
                    padre_dosage == dosage_ml and
                    (pantalla_h is None or (pantalla_h == clamped_h and pantalla_m == clamped_m and pantalla_dosage == dosage_ml)) and
                    (widget_text is None or widget_text == f"{clamped_h:02d}:{clamped_m:02d}")
                )
                
                logger.info(
                    f"[HEPARIN-SYNC] Padre: {padre_h:02d}:{padre_m:02d} dosage={padre_dosage:.2f}ml | "
                    f"Pantalla: {pantalla_h:02d}:{pantalla_m:02d} dosage={pantalla_dosage:.2f}ml | "
                    f"Widget: '{widget_text}' | "
                    f"Sincronizado: {sync_ok}"
                )
                
                if not sync_ok:
                    logger.error(
                        f"[HEPARIN-SYNC-ERROR] Inconsistencia detectada después del recorte. "
                        f"Esperado: {clamped_h:02d}:{clamped_m:02d} dosage={dosage_ml:.2f}ml"
                    )
                
                # Mostrar aviso
                self.window.show_catalog_message("HEP_TIEMPO_LIMITADO", horas=clamped_h, minutos=clamped_m)
        
        except Exception as e:
            logger.error(f"Error validando tiempo de heparina: {e}", exc_info=True)

    def _apply_heparin_auto_trim_on_running(self):
        """
        Al entrar a RUNNING, recorta UNA SOLA VEZ el tiempo de heparina si es necesario.
        Si heparineInfusionEnabled es 0, no hace nada.
        """
        heparin_enabled = bool(self.window.current_values.get("heparineInfusionEnabled", 1.0))
        if not heparin_enabled:
            logger.info("[HEPARIN-TRIM-RUNNING] Infusión deshabilitada, omitiendo recorte")
            return

        try:
            therapy_h = int(self.window.current_values.get("heparineTherapyHours", 0) or 0)
            therapy_m = int(self.window.current_values.get("heparineTherapyMinutes", 0) or 0)
            programmed_minutes = (therapy_h * 60) + therapy_m

            auto_h = int(self.window.current_values.get("heparineAutoStopHours", 0) or 0)
            auto_m = int(self.window.current_values.get("heparineAutoStopMinutes", 0) or 0)
            auto_minutes = (auto_h * 60) + auto_m

            max_heparin_minutes = max(0, programmed_minutes - 30)

            if auto_minutes > max_heparin_minutes:
                trimmed_h = max_heparin_minutes // 60
                trimmed_m = max_heparin_minutes % 60

                logger.info(
                    f"[HEPARIN-TRIM-RUNNING] Terapia: {therapy_h:02d}:{therapy_m:02d} ({programmed_minutes} min) | "
                    f"Heparina original: {auto_h:02d}:{auto_m:02d} ({auto_minutes} min) | "
                    f"Máximo permitido: {trimmed_h:02d}:{trimmed_m:02d} ({max_heparin_minutes} min) | "
                    f"Recortando..."
                )

                self.window.current_values["heparineAutoStopHours"] = float(trimmed_h)
                self.window.current_values["heparineAutoStopMinutes"] = float(trimmed_m)

                self.window._persist_therapy_config_tag("heparineAutoStopHours", float(trimmed_h))
                self.window._persist_therapy_config_tag("heparineAutoStopMinutes", float(trimmed_m))

                time_hours = trimmed_h + (trimmed_m / 60.0)
                flow_ml_per_h = self._get_heparin_flow_ml_per_h()
                dosage_ml = round(time_hours * flow_ml_per_h, 2)

                self.window.current_values["heparineTherapyDosage"] = dosage_ml
                self.window._persist_therapy_config_tag("heparineTherapyDosage", dosage_ml)

                ignore_until = time.time() + 3.0
                self.window.ignore_tags_until["heparineAutoStopHours"] = ignore_until
                self.window.ignore_tags_until["heparineAutoStopMinutes"] = ignore_until
                self.window.ignore_tags_until["heparineTherapyDosage"] = ignore_until
                logger.info("[HEPARIN-TRIM-RUNNING] Bloqueando lecturas durante 3s")

                logger.info("[HEPARIN-TRIM-RUNNING] Enviando valores recortados al firmware...")
                self.window._write_setpoint("heparineAutoStopHours", float(trimmed_h))
                self.window._write_setpoint("heparineAutoStopMinutes", float(trimmed_m))
                self.window._write_setpoint("heparineTherapyDosage", dosage_ml)

                if (
                    hasattr(self.window, 'heparin_config_screen')
                    and self.window.heparin_config_screen is not None
                ):
                    self.window.heparin_config_screen.input_heparin_auto_stop.setText(
                        f"{trimmed_h:02d}:{trimmed_m:02d}"
                    )
                    self.window.heparin_config_screen.current_values["heparineAutoStopHours"] = float(trimmed_h)
                    self.window.heparin_config_screen.current_values["heparineAutoStopMinutes"] = float(trimmed_m)
                    self.window.heparin_config_screen.current_values["heparineTherapyDosage"] = dosage_ml

                msg = (
                    f"Heparina recortada a {trimmed_h:02d}:{trimmed_m:02d} al iniciar terapia. "
                    "No se infunde en los últimos 30 minutos."
                )
                self.window.show_warning_message(msg, 5000)
            else:
                logger.info(
                    f"[HEPARIN-TRIM-RUNNING] Heparina {auto_h:02d}:{auto_m:02d} ({auto_minutes} min) "
                    f"está dentro del límite ({max_heparin_minutes} min). No se modifica."
                )
        except Exception as e:
            logger.error(f"Error recortando tiempo de heparina al iniciar RUNNING: {e}", exc_info=True)

    def _get_heparin_flow_ml_per_h(self) -> float:
        """Obtiene el flujo de heparina en ml/h desde current_values."""
        try:
            raw = self.window.current_values.get("heparineTherapyFlow")
            if raw is None and hasattr(self.window, "heparin_config_screen") and self.window.heparin_config_screen is not None:
                screen_vals = getattr(self.window.heparin_config_screen, "current_values", None)
                if isinstance(screen_vals, dict):
                    raw = screen_vals.get("heparineTherapyFlow")
            if raw is not None:
                return float(raw)
        except (AttributeError, TypeError, ValueError):
            pass
        
        # Default a 1.0 ml/h si no se puede obtener
        return 1.0

    def _coerce_heparin_auto_stop_seconds(self) -> int:
        cfg_hours = safe_int(self.window.current_values.get(HEPARIN_AUTO_STOP_HOURS_TAG, 0), 0)
        cfg_minutes = safe_int(self.window.current_values.get(HEPARIN_AUTO_STOP_MINUTES_TAG, 0), 0)
        requested_seconds = max(0, (cfg_hours * 3600) + (cfg_minutes * 60))

        therapy_hours = safe_int(self.window.current_values.get("heparineTherapyHours", 0), 0)
        therapy_minutes = safe_int(self.window.current_values.get("heparineTherapyMinutes", 0), 0)
        therapy_seconds = max(0, (therapy_hours * 3600) + (therapy_minutes * 60))

        # La heparina debe parar, como máximo, cuando falten 30 minutos de terapia.
        max_allowed_seconds = max(0, therapy_seconds - 1800)
        effective_seconds = min(requested_seconds, max_allowed_seconds)

        return effective_seconds

    def _update_heparin_auto_stop_timer(self):
        phase = self.window.state.current_phase

        if phase in (TreatmentPhase.IDLE, TreatmentPhase.READY, TreatmentPhase.PREPARING):
            self.window._heparin_auto_stop_latched = False
            return

        if phase != TreatmentPhase.RUNNING:
            return

        # Si la infusión de heparina está deshabilitada, no hacer nada
        heparin_enabled = bool(self.window.current_values.get("heparineInfusionEnabled", 1.0))
        if not heparin_enabled:
            self.window._heparin_auto_stop_latched = False
            return

        auto_stop_seconds = self._coerce_heparin_auto_stop_seconds()
        if auto_stop_seconds <= 0:
            return

        elapsed_seconds = int(self.window.treatment_controller.get_elapsed_seconds())

        if elapsed_seconds >= auto_stop_seconds and not self.window._heparin_auto_stop_latched:
            logger.info(
                "Auto-paro de heparina por tiempo alcanzado (%ss >= %ss)",
                elapsed_seconds,
                auto_stop_seconds,
            )
            self.window._write_boolean_command("heparinePumpsStopButton", True)
            self.window._heparin_auto_stop_latched = True
            self.window.show_catalog_message("HEP_PARO_AUTO")

    def set_heparin_infusion_enabled(self, enabled: bool):
        """Habilita/deshabilita la infusión automática de heparina (checkbox de terapia)."""
        self.window.current_values["heparineInfusionEnabled"] = 1.0 if enabled else 0.0
        self.window._persist_therapy_config_tag("heparineInfusionEnabled", 1.0 if enabled else 0.0)
        self._update_heparin_infusion_enable_guard()
        if hasattr(self.window, "heparin_config_screen") and hasattr(self.window.heparin_config_screen, "update_values"):
            self.window.heparin_config_screen.update_values(self.window.current_values)

    def _update_heparin_infusion_enable_guard(self):
        """Mantiene la bomba de heparina parada en RUNNING mientras el check esté OFF."""
        phase = self.window.state.current_phase
        enabled = bool(self.window.current_values.get("heparineInfusionEnabled", 1.0))

        if phase != TreatmentPhase.RUNNING:
            self.window._heparin_infusion_forced_stop_latched = False
            return

        if enabled:
            if self.window._heparin_infusion_forced_stop_latched:
                # self._write_boolean_command("heparinePumpsStopButton", False)
                self.window._heparin_infusion_forced_stop_latched = False
            return

        if not self.window._heparin_infusion_forced_stop_latched:
            self.window._write_setpoint("heparineTherapyFlow", 0.0)
            # self._write_boolean_command("heparinePumpsStopButton", True)
            self.window._heparin_infusion_forced_stop_latched = True
            logger.info("[HEPARIN] disabled")

    def on_second(self):
        self._update_heparin_auto_stop_timer()
        self._update_heparin_infusion_enable_guard()

    def _validate_heparin_on_therapy_time_change(self, new_total_seconds: float) -> bool:
        """
        Valida un cambio de duración de terapia mientras está RUNNING o PAUSED.
        Retorna True si es válido, False si debe rechazarse.
        """
        controller = getattr(self.window, "treatment_controller", None)
        if getattr(controller, "therapy_records_closed", False):
            msg = "La terapia ya está en bypass. No se puede modificar la duración."
            self.window.show_warning_message(msg, 4000)
            logger.warning("[THERAPY-TIME-CHANGE] Rechazado: therapy_records_closed activa")
            return False

        elapsed_sec = controller.get_elapsed_seconds() if controller else 0
        if new_total_seconds <= elapsed_sec:
            msg = "El tiempo debe ser mayor al ya transcurrido."
            self.window.show_warning_message(msg, 4000)
            logger.warning(
                f"[THERAPY-TIME-CHANGE] Rechazado: nuevo total {new_total_seconds}s <= transcurrido {elapsed_sec}s"
            )
            return False

        heparin_enabled = bool(self.window.current_values.get("heparineInfusionEnabled", 1.0))
        if not heparin_enabled:
            logger.info("[THERAPY-TIME-CHANGE] Infusión deshabilitada, sin validación heparina")
            return True

        try:
            remaining_real_sec = new_total_seconds - elapsed_sec
            remaining_real_min = remaining_real_sec / 60.0

            hep_h = int(self.window.current_values.get("heparineAutoStopHours", 0) or 0)
            hep_m = int(self.window.current_values.get("heparineAutoStopMinutes", 0) or 0)
            hep_total_min = (hep_h * 60) + hep_m

            max_hep_min = max(0, remaining_real_min - 30)

            if hep_total_min > max_hep_min:
                msg = (
                    f"Tiempo de heparina ({hep_h:02d}:{hep_m:02d}) excede el máximo "
                    f"permitido ({int(max_hep_min // 60):02d}:{int(max_hep_min % 60):02d}) "
                    "para esta duración de terapia."
                )
                self.window.show_warning_message(msg, 5000)
                logger.warning(
                    f"[THERAPY-TIME-CHANGE] Rechazado: heparina {hep_total_min}min > máximo {max_hep_min}min"
                )
                return False

            logger.info(
                f"[THERAPY-TIME-CHANGE] Validación OK: heparina {hep_total_min}min <= máximo {max_hep_min}min"
            )
            return True
        except Exception as e:
            logger.error(f"[THERAPY-TIME-CHANGE] Error validando heparina: {e}", exc_info=True)
            return False

    def write_local_setpoint(self, tag: str, value: float):
        if tag in ("heparineTherapyHours", "heparineTherapyMinutes"):
            in_running_or_paused = (
                self.window.state.current_phase in (TreatmentPhase.RUNNING, TreatmentPhase.PAUSED)
            )
            if in_running_or_paused:
                if tag == "heparineTherapyHours":
                    new_h = int(value)
                    new_m = int(self.window.current_values.get("heparineTherapyMinutes", 0) or 0)
                else:
                    new_h = int(self.window.current_values.get("heparineTherapyHours", 0) or 0)
                    new_m = int(value)
                new_total_seconds = (new_h * 60 + new_m) * 60

                if not self._validate_heparin_on_therapy_time_change(new_total_seconds):
                    return False

                self.window.current_values[tag] = float(value)
                self.window._persist_therapy_config_tag(tag, float(value))
                self.window.treatment_controller.total_therapy_seconds = new_total_seconds
                self.window._update_therapy_time_displays()
                logger.info(
                    f"[THERAPY-TIME] set_min={new_h * 60 + new_m} remaining={new_h:02d}:{new_m:02d}:00 source=running_or_paused"
                )
                return True

        self.window.current_values[tag] = float(value)
        self.window._persist_therapy_config_tag(tag, float(value))

        # Detectar cambio de tiempo de terapia y actualizar displays
        if tag in ("heparineTherapyHours", "heparineTherapyMinutes"):
            hours = int(self.window.current_values.get("heparineTherapyHours", 0))
            minutes = int(self.window.current_values.get("heparineTherapyMinutes", 0))
            total_min = (hours * 60) + minutes

            # Si no está RUNNING, puede cambiar el total de terapia
            if self.window.state.current_phase not in (TreatmentPhase.RUNNING, TreatmentPhase.PAUSED):
                self.window.treatment_controller.total_therapy_seconds = total_min * 60

            # Actualizar displays inmediatamente
            self.window._update_therapy_time_displays()

            # Validar y acotar el tiempo de heparina si es necesario (excepto en limpieza)
            is_cleaning = (
                getattr(getattr(self.window, "state", None), "current_phase", None) == TreatmentPhase.CLEANING
                or safe_int(self.window.current_values.get("treatmentModeSelection", 0), 0) == 3
            )
            if not is_cleaning:
                self.window._validate_and_clamp_heparin_auto_stop_time()

            logger.info(f"[THERAPY-TIME] set_min={total_min} remaining={hours:02d}:{minutes:02d}:00 source=config")

        logger.info(f"SETPOINT [LOCAL]: {tag} = {value}")
        return
