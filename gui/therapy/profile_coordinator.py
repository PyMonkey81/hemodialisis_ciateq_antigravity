import logging
from PySide6.QtCore import QDateTime

from core.state_manager import TreatmentPhase
from logic.calculos import convertir_litros_h_a_ml_min
from logic.conductivity_profile import (
    ConductivityProfile,
    ProfileType,
    calculate_target_conductivity,
    save_profile,
    step_index_by_seconds,
    validate_profile,
)
from logic.uf_profile import (
    UFProfile,
    calculate_target_uf,
    save_profile as save_uf_profile,
    validate_profile as validate_uf_profile,
)

logger = logging.getLogger(__name__)


class ProfileCoordinator:
    def __init__(self, window):
        self.window = window

    def can_configure_conductivity_profile(self, allow_disable: bool = False) -> tuple[bool, str]:
        phase = self.window.state.current_phase
        if phase not in (TreatmentPhase.RUNNING, TreatmentPhase.PAUSED):
            return True, ""

        remaining_min = self.window.get_remaining_therapy_minutes()
        if remaining_min < 30.0 and not allow_disable:
            return (
                False,
                "No se puede configurar el perfil de conductividad cuando faltan menos de 30 minutos de terapia.",
            )

        return True, ""

    def is_conductivity_profile_active(self) -> bool:
        return bool(
            self.window.conductivity_profile.enabled
            and self.window.conductivity_profile.profile_type != ProfileType.NONE
        )

    def set_conductivity_profile(self, profile: ConductivityProfile, show_message: bool = False) -> bool:
        profile.therapy_duration_min = max(1, self.window.get_therapy_duration_minutes())

        if profile.enabled:
            can_change, msg = self.can_configure_conductivity_profile(allow_disable=False)
            if not can_change:
                if show_message:
                    self.window.show_warning_message(msg, 4500)
                return False

        ok, msg = validate_profile(profile)
        if not ok:
            if show_message:
                self.window.show_warning_message(msg, 4500)
            return False

        if not save_profile(profile):
            if show_message:
                self.window.show_error_message("No se pudo guardar el perfil de conductividad", 5000)
            return False

        self.window.conductivity_profile = profile
        self.window._last_profile_target = None
        self.window._last_profile_written = None
        self.window._last_profile_step_index = None
        self.window._last_profile_write_ts = 0
        self.window._last_profile_step_ts_s = 0

        if show_message:
            if self.is_conductivity_profile_active():
                self.window.show_success_message("Perfil de conductividad activado", 3500)
            else:
                self.window.show_info_message("Perfil de conductividad desactivado", 3500)

        if hasattr(self.window.therapy_config_screen, "_refresh_conductivity_profile_button"):
            self.window.therapy_config_screen._refresh_conductivity_profile_button()

        self._apply_conductivity_profile_from_state(log_forced=True)
        return True

    def disable_conductivity_profile(self, show_message: bool = False) -> bool:
        can_disable, msg = self.can_configure_conductivity_profile(allow_disable=True)
        if not can_disable:
            if show_message:
                self.window.show_warning_message(msg, 4500)
            return False

        disabled = ConductivityProfile.from_dict(self.window.conductivity_profile.to_dict())
        disabled.enabled = False
        disabled.profile_type = ProfileType.NONE

        if not save_profile(disabled):
            if show_message:
                self.window.show_error_message("No se pudo desactivar el perfil de conductividad", 5000)
            return False

        self.window.conductivity_profile = disabled
        self.window._last_profile_target = None
        self.window._last_profile_written = None
        self.window._last_profile_step_index = None
        self.window._last_profile_write_ts = 0
        self.window._last_profile_step_ts_s = 0

        if hasattr(self.window.therapy_config_screen, "_refresh_conductivity_profile_button"):
            self.window.therapy_config_screen._refresh_conductivity_profile_button()

        if show_message:
            self.window.show_info_message("Perfil de conductividad desactivado", 3500)
        return True

    def _apply_conductivity_profile_from_state(self, log_forced: bool = False):
        phase = self.window.state.current_phase
        if phase not in (TreatmentPhase.PREPARING, TreatmentPhase.RUNNING, TreatmentPhase.PAUSED):
            return

        if not self.is_conductivity_profile_active():
            return

        # El avance SOLO depende del reloj de terapia (RUNNING/PAUSED), nunca de
        # la UI (show/hide de pantallas) ni del muestreo serial.
        elapsed_seconds = 0
        if phase in (TreatmentPhase.RUNNING, TreatmentPhase.PAUSED):
            elapsed_seconds = int(self.window.treatment_controller.get_elapsed_seconds())
        elapsed_min = elapsed_seconds / 60.0

        # Usar duración real de terapia en curso, no el snapshot congelado en JSON
        therapy_duration_min = self.window.get_therapy_duration_minutes()
        
        target = calculate_target_conductivity(self.window.conductivity_profile, elapsed_min, therapy_duration_min=therapy_duration_min)
        if target is None:
            return

        target = round(float(target), 2)
        now = QDateTime.currentDateTime().toSecsSinceEpoch()

        if self.window.conductivity_profile.profile_type == ProfileType.STEP:
            # Periodo fijo de 30*60 s de terapia por escalón (ver step_index_by_seconds).
            idx = step_index_by_seconds(elapsed_seconds)
            if idx != self.window._last_profile_step_index or self.window._last_profile_written is None:
                dt_s = elapsed_seconds - self.window._last_profile_step_ts_s if self.window._last_profile_step_index is not None else 0
                self.window._write_setpoint("dialyCondControlSetPoint", target)
                self.window._last_profile_target = target
                self.window._last_profile_written = target
                self.window._last_profile_step_index = idx
                self.window._last_profile_write_ts = now
                self.window._last_profile_step_ts_s = elapsed_seconds
                logger.info(
                    "[PROFILE] step i=%s out=%.2f t_terapia_s=%s dt_s=%s",
                    idx,
                    target,
                    elapsed_seconds,
                    dt_s,
                )
        else:
            changed = self.window._last_profile_written is None or abs(target - self.window._last_profile_written) >= 0.01
            due = (now - self.window._last_profile_write_ts) >= 10
            if self.window._last_profile_written is None or (changed and due):
                self.window._write_setpoint("dialyCondControlSetPoint", target)
                self.window._last_profile_target = target
                self.window._last_profile_written = target
                self.window._last_profile_write_ts = now
                # Calcular progreso para logging
                progress = 0.0
                if therapy_duration_min > 0:
                    progress = min(1.0, elapsed_min / therapy_duration_min)
                logger.info(
                    "[PROFILE] mode=%s out=%.2f t_s=%.1f T_s=%.1f progress=%.1f%% start=%.2f end=%.2f",
                    self.window.conductivity_profile.profile_type.value,
                    target,
                    elapsed_min,
                    therapy_duration_min,
                    progress * 100.0,
                    self.window.conductivity_profile.start_conductivity,
                    self.window.conductivity_profile.end_conductivity,
                )

        if log_forced:
            logger.info(
                "Perfil conductividad aplicado: type=%s elapsed=%.2f target=%.2f",
                self.window.conductivity_profile.profile_type.value,
                elapsed_min,
                target,
            )
            return

        current_second = now
        if current_second % 10 == 0 and current_second != self.window._last_profile_log_second:
            self.window._last_profile_log_second = current_second
            logger.info(
                "Perfil conductividad tick: type=%s elapsed=%.2f target=%.2f",
                self.window.conductivity_profile.profile_type.value,
                elapsed_min,
                target,
            )

    # ────────────────────────────────────────────────
    #              Perfil de Ultrafiltración (UF)
    # ────────────────────────────────────────────────

    def can_configure_uf_profile(self, allow_disable: bool = False) -> tuple[bool, str]:
        phase = self.window.state.current_phase
        if phase not in (TreatmentPhase.RUNNING, TreatmentPhase.PAUSED):
            return True, ""

        remaining_min = self.window.get_remaining_therapy_minutes()
        if remaining_min < 30.0 and not allow_disable:
            return (
                False,
                "No se puede configurar el perfil de UF cuando faltan menos de 30 minutos de terapia.",
            )

        return True, ""

    def is_uf_profile_active(self) -> bool:
        return bool(
            self.window.uf_profile.enabled
            and self.window.uf_profile.profile_type != ProfileType.NONE
        )

    def set_uf_profile(self, profile: UFProfile, show_message: bool = False) -> bool:
        profile.therapy_duration_min = max(1, self.window.get_therapy_duration_minutes())

        if profile.enabled:
            can_change, msg = self.can_configure_uf_profile(allow_disable=False)
            if not can_change:
                if show_message:
                    self.window.show_warning_message(msg, 4500)
                return False

        ok, msg = validate_uf_profile(profile)
        if not ok:
            if show_message:
                self.window.show_warning_message(msg, 4500)
            return False

        if not save_uf_profile(profile):
            if show_message:
                self.window.show_error_message("No se pudo guardar el perfil de UF", 5000)
            return False

        self.window.uf_profile = profile
        self.window._last_uf_profile_target = None
        self.window._last_uf_profile_written = None
        self.window._last_uf_profile_step_index = None
        self.window._last_uf_profile_write_ts = 0
        self.window._last_uf_profile_step_ts_s = 0

        if show_message:
            if self.is_uf_profile_active():
                self.window.show_success_message("Perfil de UF activado", 3500)
            else:
                self.window.show_info_message("Perfil de UF desactivado", 3500)

        if hasattr(self.window.therapy_config_screen, "_refresh_uf_profile_button"):
            self.window.therapy_config_screen._refresh_uf_profile_button()

        self._apply_uf_profile_from_state(log_forced=True)
        return True

    def disable_uf_profile(self, show_message: bool = False) -> bool:
        can_disable, msg = self.can_configure_uf_profile(allow_disable=True)
        if not can_disable:
            if show_message:
                self.window.show_warning_message(msg, 4500)
            return False

        disabled = UFProfile.from_dict(self.window.uf_profile.to_dict())
        disabled.enabled = False
        disabled.profile_type = ProfileType.NONE

        if not save_uf_profile(disabled):
            if show_message:
                self.window.show_error_message("No se pudo desactivar el perfil de UF", 5000)
            return False

        self.window.uf_profile = disabled
        self.window._last_uf_profile_target = None
        self.window._last_uf_profile_written = None
        self.window._last_uf_profile_step_index = None
        self.window._last_uf_profile_write_ts = 0
        self.window._last_uf_profile_step_ts_s = 0

        if hasattr(self.window.therapy_config_screen, "_refresh_uf_profile_button"):
            self.window.therapy_config_screen._refresh_uf_profile_button()

        if show_message:
            self.window.show_info_message("Perfil de UF desactivado", 3500)
        return True

    def _apply_uf_profile_from_state(self, log_forced: bool = False):
        phase = self.window.state.current_phase
        if phase not in (TreatmentPhase.PREPARING, TreatmentPhase.RUNNING, TreatmentPhase.PAUSED):
            return

        if not self.is_uf_profile_active():
            return

        # El avance SOLO depende del reloj de terapia (RUNNING/PAUSED); show/hide
        # de pantallas y Cancelar no aplican ni reinician el perfil.
        elapsed_seconds = 0
        if phase in (TreatmentPhase.RUNNING, TreatmentPhase.PAUSED):
            elapsed_seconds = int(self.window.treatment_controller.get_elapsed_seconds())
        elapsed_min = elapsed_seconds / 60.0

        # Usar duración real de terapia en curso, no el snapshot congelado en JSON
        therapy_duration_min = self.window.get_therapy_duration_minutes()
        
        target_l_h = calculate_target_uf(self.window.uf_profile, elapsed_min, therapy_duration_min=therapy_duration_min)
        if target_l_h is None:
            return

        target_l_h = round(float(target_l_h), 2)
        ml_min = convertir_litros_h_a_ml_min(target_l_h)
        now = QDateTime.currentDateTime().toSecsSinceEpoch()

        def _write_uf_setpoint():
            self.window._write_setpoint("ultraFilterPumpSpeed", ml_min)
            # Mismo hold-off de 3 s que el numpad manual, para no pelear con el echo serial.
            if hasattr(self.window.therapy_config_screen, "write_hold_off"):
                self.window.therapy_config_screen.write_hold_off["ultraFilterPumpSpeed"] = (
                    QDateTime.currentMSecsSinceEpoch() + 3000
                )

        if self.window.uf_profile.profile_type == ProfileType.STEP:
            idx = step_index_by_seconds(elapsed_seconds)
            if idx != self.window._last_uf_profile_step_index or self.window._last_uf_profile_written is None:
                dt_s = elapsed_seconds - self.window._last_uf_profile_step_ts_s if self.window._last_uf_profile_step_index is not None else 0
                _write_uf_setpoint()
                self.window._last_uf_profile_target = target_l_h
                self.window._last_uf_profile_written = target_l_h
                self.window._last_uf_profile_step_index = idx
                self.window._last_uf_profile_write_ts = now
                self.window._last_uf_profile_step_ts_s = elapsed_seconds
                logger.info(
                    "[PROFILE-UF] mode=step i=%s out_Lh=%.2f out_mlmin=%.1f t_terapia_s=%s dt_s=%s",
                    idx,
                    target_l_h,
                    ml_min,
                    elapsed_seconds,
                    dt_s,
                )
        else:
            changed = self.window._last_uf_profile_written is None or abs(target_l_h - self.window._last_uf_profile_written) >= 0.01
            due = (now - self.window._last_uf_profile_write_ts) >= 10
            if self.window._last_uf_profile_written is None or (changed and due):
                _write_uf_setpoint()
                self.window._last_uf_profile_target = target_l_h
                self.window._last_uf_profile_written = target_l_h
                self.window._last_uf_profile_write_ts = now
                # Calcular progreso para logging
                progress = 0.0
                if therapy_duration_min > 0:
                    progress = min(1.0, elapsed_min / therapy_duration_min)
                logger.info(
                    "[PROFILE-UF] mode=%s out_Lh=%.2f out_mlmin=%.1f t_s=%.1f T_s=%.1f progress=%.1f%% start=%.2f end=%.2f",
                    self.window.uf_profile.profile_type.value,
                    target_l_h,
                    ml_min,
                    elapsed_min,
                    therapy_duration_min,
                    progress * 100.0,
                    self.window.uf_profile.start_uf,
                    self.window.uf_profile.end_uf,
                )

        if log_forced:
            logger.info(
                "Perfil UF aplicado: type=%s elapsed=%.2f target_Lh=%.2f",
                self.window.uf_profile.profile_type.value,
                elapsed_min,
                target_l_h,
            )
