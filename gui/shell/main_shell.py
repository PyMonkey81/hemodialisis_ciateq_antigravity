import logging
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.nibp_pressure_history import NibpPressureHistory
from core.state_manager import TreatmentPhase
from core.therapy_session_tracker import TherapySessionTracker
from core.variables_map import VARIABLES
from gui.components.real_time_variables import RealTimeVariablesMonitor
from gui.configuration.alarm_screen_config import AlarmScreenConfig
from gui.configuration.alarm_screen_service_config import AlarmScreenServiceConfig
from gui.configuration.cleanning_config_screen import CleanningConfigScreen
from gui.service.calibration_screen import CalibrationScreen
from gui.service.cleaning_screen import CleaningScreen
from gui.service.comm_port_screen import CommPortScreen
from gui.service.history_screen import HistoryScreen
from gui.service.maintenance_screen import MaintenanceScreen
from gui.service.manual_mode_screen import ManualModeScreen
from gui.service.network_config_screen import NetworkConfigScreen
from gui.service.options_screen import OptionsScreen
from gui.service.test_panel_screen import TestPanelScreen
from gui.service.theme_config_screen import ThemeConfigScreen
from gui.theme_manager import ThemeManager
from gui.therapy.alarms_screen import AlarmsScreen
from gui.therapy.conductivity_profile_screen import ConductivityProfileScreen
from gui.therapy.dialysis_screenV2 import DialysisScreen
from gui.therapy.heparin_config_screenV2 import HeparinConfigScreen
from gui.therapy.ktv_screen import KTVScreen
from gui.therapy.main_screen import MainScreen
from gui.therapy.nibp_config_screen import NibpConfigScreen
from gui.therapy.nibp_history_screen import NibpChartScreen, NibpHistoryScreen
from gui.therapy.nibp_limits_screen import NibpLimitsScreen
from gui.therapy.patient_config_screen import PatientConfigScreen
from gui.therapy.therapy_config_screenV2 import TherapyConfigScreen
from gui.therapy.treatment_mode_screen import TreatmentModeScreen
from gui.therapy.uf_profile_screen import UFProfileScreen
from utilities.platform_runtime import safe_float, safe_int

logger = logging.getLogger(__name__)


class MainShell:
    def __init__(self, window):
        self.window = window

    def _build_header_label_style(self, background: str = "", is_process: bool = False) -> str:
        tokens = ThemeManager.get_tokens()
        is_mono = bool(tokens.get("monochrome", False))
        is_dark = bool(tokens.get("is_dark", False))

        if is_mono:
            if is_process:
                return """
                    QLabel {
                        background: #9CA3AF;
                        font-family: 'Segoe UI', Arial, sans-serif;
                        font-weight: bold;
                        font-size: 25px;
                        color: #111827;
                        border-radius: 8px;
                        border: 1px solid #6B7280;
                    }
                """
            else:
                return """
                    QLabel {
                        background: #D9E0E8;
                        font-family: 'Segoe UI', Arial, sans-serif;
                        font-weight: bold;
                        font-size: 25px;
                        color: #374151;
                        border-radius: 8px;
                        border: 1px solid #C5CDD6;
                    }
                """
        elif is_dark:
            border_c = tokens.get('border_card', '#334155')
            bg_c = tokens.get('bg_card_alt', '#1E293B')
            text_c = tokens.get('text_primary', '#F8FAFC')
            return f"""
                QLabel {{
                    background: {bg_c};
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-weight: bold;
                    font-size: 25px;
                    color: {text_c};
                    border-radius: 8px;
                    border: 1px solid {border_c};
                }}
            """
        else:
            return f"""
                QLabel {{
                    background: {background};
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-weight: bold;
                    font-size: 25px;
                    color: #ffffff;
                    border-radius: 8px;
                }}
            """

    def _apply_main_shell_theme(self, _theme_name: str = ""):
        """Actualiza dinámicamente los colores del contenedor principal, header, barra de navegación y tarjetas."""
        t = ThemeManager.get_tokens()
        bg_primary = t.get("bg_primary", "#FCFCFC")
        bg_header = t.get("bg_header", "#EBEBEB")
        bg_nav = t.get("bg_nav", "#FCFCFC")
        bg_card = t.get("bg_card", "#ffffff")
        text_primary = t.get("text_primary", "#0f172a")
        text_secondary = t.get("text_secondary", "#334155")
        border = t.get("border", "#cbd5e1")
        border_strong = t.get("border_strong", "#77787D")
        nav_btn_bg = t.get("nav_btn_bg", "#06298a")
        nav_btn_active = t.get("nav_btn_active", "#3b82f6")
        nav_btn_disabled = t.get("nav_btn_disabled", "#334155")
        header_pill = t.get("header_pill_bg", "#06298a")

        is_mono = bool(t.get("monochrome", False))
        is_dark = bool(t.get("is_dark", False))

        if is_mono:
            self.window.BTN_ENABLED_DEFAULT_STYLE = (
                "QPushButton { background: #D9E0E8; color: #374151; font-family: 'Segoe UI', Arial, sans-serif; "
                "font-weight: bold; font-size: 30px; border-radius: 10px; border: 1px solid #C5CDD6; }"
                "QPushButton:hover { background: #C5CED6; }"
                "QPushButton:pressed { background: #B0B8C4; }"
            )
            self.window.BTN_ACTIVE_STYLE = (
                "QPushButton { background: #9CA3AF; color: #111827; font-family: 'Segoe UI', Arial, sans-serif; "
                "font-weight: bold; font-size: 30px; border-radius: 10px; border: 1px solid #6B7280; }"
            )
            self.window.BTN_DISABLED_STYLE = (
                "QPushButton { background: #E5E7EB; color: #B0B8C2; font-family: 'Segoe UI', Arial, sans-serif; "
                "font-weight: bold; font-size: 30px; border-radius: 10px; }"
            )
            self.window.BTN_ENABLED_EXIT_STYLE = (
                "QPushButton { background: #D9E0E8; color: #374151; font-family: 'Segoe UI', Arial, sans-serif; "
                "font-weight: bold; font-size: 30px; border-radius: 10px; border: 1px solid #C5CDD6; }"
                "QPushButton:hover { background: #C5CED6; }"
                "QPushButton:pressed { background: #B0B8C4; }"
            )
            self.window.BTN_ENABLED_START_TREATMENT_STYLE = (
                "QPushButton { background: #D9E0E8; color: #374151; font-family: 'Segoe UI', Arial, sans-serif; "
                "font-weight: bold; font-size: 30px; border-radius: 10px; border: 1px solid #C5CDD6; }"
                "QPushButton:hover { background: #C5CED6; }"
                "QPushButton:pressed { background: #B0B8C4; }"
            )
        elif is_dark:
            self.window.BTN_ENABLED_DEFAULT_STYLE = (
                f"QPushButton {{ background: {nav_btn_bg}; color: #ffffff; font-family: 'Segoe UI', Arial, sans-serif; "
                f"font-weight: bold; font-size: 30px; border-radius: 10px; }}"
                f"QPushButton:pressed {{ background: {nav_btn_active}; }}"
            )
            self.window.BTN_ACTIVE_STYLE = (
                f"QPushButton {{ background: {nav_btn_active}; color: white; font-family: 'Segoe UI', Arial, sans-serif; "
                f"font-weight: bold; font-size: 30px; border-radius: 10px; border: 2px solid #93c5fd;}}"
                f"QPushButton:pressed {{ background: {nav_btn_bg}; }}"
            )
            self.window.BTN_DISABLED_STYLE = (
                f"QPushButton {{ background: {nav_btn_disabled}; color: #94a3b8; font-family: 'Segoe UI', Arial, sans-serif; "
                f"font-weight: bold; font-size: 30px; border-radius: 10px; }}"
            )
            self.window.BTN_ENABLED_EXIT_STYLE = (
                f"QPushButton {{ background: {t.get('danger', '#ef4444')}; color: #ffffff; font-family: 'Segoe UI', Arial, sans-serif; "
                f"font-weight: bold; font-size: 30px; border-radius: 10px; }}"
                f"QPushButton:pressed {{ background: #991b1b; }}"
            )
            self.window.BTN_ENABLED_START_TREATMENT_STYLE = (
                f"QPushButton {{ background: {t.get('success', '#10b981')}; color: #ffffff; font-family: 'Segoe UI', Arial, sans-serif; "
                f"border-radius: 8px; font-weight: bold; font-size: 30px; }}"
                f"QPushButton:pressed {{ background: #065f46; }}"
            )
        else:
            self.window.BTN_ENABLED_DEFAULT_STYLE = (
                f"QPushButton {{ background: {nav_btn_bg}; color: #ffffff; font-family: 'Segoe UI', Arial, sans-serif; "
                f"font-weight: bold; font-size: 30px; border-radius: 10px; }}"
                f"QPushButton:pressed {{ background: {nav_btn_active}; }}"
            )
            self.window.BTN_ACTIVE_STYLE = (
                f"QPushButton {{ background: {nav_btn_active}; color: white; font-family: 'Segoe UI', Arial, sans-serif; "
                f"font-weight: bold; font-size: 30px; border-radius: 10px; border: 2px solid #93c5fd;}}"
                f"QPushButton:pressed {{ background: {nav_btn_bg}; }}"
            )
            self.window.BTN_DISABLED_STYLE = (
                f"QPushButton {{ background: {nav_btn_disabled}; color: #94a3b8; font-family: 'Segoe UI', Arial, sans-serif; "
                f"font-weight: bold; font-size: 30px; border-radius: 10px; }}"
            )
            self.window.BTN_ENABLED_EXIT_STYLE = """
                QPushButton { background: #dc2626; color: #ffffff; font-family: 'Segoe UI', Arial, sans-serif; font-weight: bold; font-size: 30px; border-radius: 10px; }
                QPushButton:pressed { background: #b91c1c; }
            """
            self.window.BTN_ENABLED_START_TREATMENT_STYLE = f"""
                QPushButton {{ background: {t.get("success", "#16A34A")}; color: #ffffff; font-family: 'Segoe UI', Arial, sans-serif; border-radius: 8px; font-weight: bold; font-size: 30px;}}
                QPushButton:pressed {{ background: #15803d; }}
            """

        cw = self.window.centralWidget()
        if cw is not None:
            cw.setStyleSheet(f"QWidget#main_central_widget {{ background: {bg_primary}; }}")

        if hasattr(self.window, "header_container") and self.window.header_container is not None:
            self.window.header_container.setStyleSheet(f"background: {bg_header}; border-bottom: 1px solid {border};")

        logo_bg = "#F8FAFC" if bool(t.get("is_dark", False)) else "transparent"
        logo_border = f"1px solid {border}" if bool(t.get("is_dark", False)) else "none"
        logo_style = (
            f"QLabel, QPushButton {{ background-color: {logo_bg}; border: {logo_border}; "
            f"border-radius: 10px; padding: 4px 8px; }}"
        )
        for logo_attr in ("logo1", "logo2"):
            logo_lbl = getattr(self.window, logo_attr, None)
            if logo_lbl is not None:
                logo_lbl.setStyleSheet(logo_style)

        for lbl_attr in ("remaining_time_display", "date_time_label"):
            lbl = getattr(self.window, lbl_attr, None)
            if lbl is not None:
                lbl.setStyleSheet(self.window._build_header_label_style(header_pill, is_process=False))

        if hasattr(self.window, "current_process_status") and self.window.current_process_status is not None:
            self.window.current_process_status.setStyleSheet(self.window._build_header_label_style("#2bbd37", is_process=True))
        if hasattr(self.window, "status_label") and self.window.status_label is not None:
            self.window.refresh_alarms_label()
        if hasattr(self.window, "_update_navigation_bar"):
            self.window._update_navigation_bar()

        if hasattr(self.window, "nav_bar") and self.window.nav_bar is not None:
            self.window.nav_bar.setStyleSheet(f"background: {bg_nav}; border-top: 1px solid {border};")

        if hasattr(self.window, "screen_stack") and self.window.screen_stack is not None:
            self.window.screen_stack.setStyleSheet(f"""
                QStackedWidget#main_screen_stack, 
                QStackedWidget#main_screen_stack > QWidget {{
                    background-color: {bg_primary};
                }}
                QFrame#card, QFrame#graph_card, QGroupBox#card {{
                    background-color: {bg_card};
                    border: 2px solid {border};
                    border-radius: 14px;
                }}
                QLabel {{
                    color: {text_secondary};
                    background-color: transparent;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-size: 22px;
                }}
                QLabel#card_title {{
                    color: {text_primary};
                    font-size: 20px;
                    font-weight: bold;
                    background: transparent;
                    border: none;
                    border-bottom: 2px solid {border_strong};
                    padding-bottom: 8px;
                    margin-bottom: 8px;
                }}
                QLabel#val_large {{
                    color: #ef4444;
                    font-family: 'Consolas', monospace;
                    font-size: 52px;
                    font-weight: bold;
                }}
                QLabel#val_large_yellow {{
                    color: #eab308;
                    font-family: 'Consolas', monospace;
                    font-size: 52px;
                    font-weight: bold;
                }}
                QLabel#val_large_green {{
                    color: {t.get('val_green', '#15803d')};
                    font-family: 'Consolas', monospace;
                    font-size: 52px;
                    font-weight: bold;
                }}
                QLabel#val_large_cyan {{
                    color: {t.get('val_cyan', '#0369a1')};
                    font-family: 'Consolas', monospace;
                    font-size: 52px;
                    font-weight: bold;
                }}
                QPushButton {{
                    padding: 4px 10px;
                }}
            """)
            stack_palette = self.window.screen_stack.palette()
            stack_palette.setColor(self.window.screen_stack.backgroundRole(), QColor(bg_primary))
            self.window.screen_stack.setPalette(stack_palette)

        self.window._refresh_navigation_bar()

    def _apply_home_chrome(self, *_):
        """En Inicio oculta los indicadores del header (deja solo logos) y deja solo Resumen Terapia/Diálisis y Servicio en la barra."""
        on_home = (
            hasattr(self.window, "screen_stack")
            and hasattr(self.window, "_main_screen")
            and self.window.screen_stack.currentWidget() is self.window._main_screen
        )
        for attr in (
            "status_label",
            "current_process_status",
            "treatment_mode_selected",
            "remaining_time_display",
            "date_time_label",
        ):
            widget = getattr(self.window, attr, None)
            if widget is not None:
                widget.setVisible(not on_home)

        for text, btn in getattr(self.window, "navigation_buttons", {}).items():
            if btn is not None:
                if on_home:
                    btn.setVisible(text in ("Diálisis", "Resumen\nTerapia", "Servicio"))
                else:
                    btn.setVisible(True)

    def _on_treatment_mode_label_click(self):
        """Maneja el click en el label de tipo de tratamiento del header.
        Abre la pantalla de selección de tratamiento si está permitido según la fase actual."""
        if not self.window.serial_comm or not self.window.serial_comm.is_connected:
            return

        phase = self.window.state.current_phase

        # Permitir cambio solo en IDLE o PREPARING (cuando no está en cebado activo)
        if phase == TreatmentPhase.IDLE:
            self.window.show_treatment_mode_screen()
        elif phase == TreatmentPhase.PREPARING:
            status = int(self.window.current_values.get("primingProcessStatus", 0))
            if not self.window.hardware_mapper.is_preparing(status):
                # Solo si se detuvo el cebado
                self.window.show_treatment_mode_screen()

    def _update_treatment_mode_label_state(self):
        """Actualiza el estado (habilitado/deshabilitado) y estilo del label de tipo de tratamiento."""
        if not hasattr(self.window, "treatment_mode_selected") or self.window.treatment_mode_selected is None:
            return

        if not self.window.serial_comm or not self.window.serial_comm.is_connected:
            self.window.treatment_mode_selected.setEnabled(False)
            self.window.treatment_mode_selected.setStyleSheet(
                self.window._build_header_label_style("#6b7280", is_process=False)
            )
            return

        phase = self.window.state.current_phase
        can_change = False

        if phase == TreatmentPhase.IDLE:
            can_change = True
        elif phase == TreatmentPhase.PREPARING:
            status = int(self.window.current_values.get("primingProcessStatus", 0))
            if not self.window.hardware_mapper.is_preparing(status):
                can_change = True

        self.window.treatment_mode_selected.setEnabled(can_change)
        if can_change:
            self.window.treatment_mode_selected.setStyleSheet(
                self.window._build_header_label_style("#1d4ed8", is_process=False)
            )
        else:
            self.window.treatment_mode_selected.setStyleSheet(
                self.window._build_header_label_style("#6b7280", is_process=False)
            )

    def _get_current_screen_nav_text(self) -> str:
        """Devuelve el texto del botón de navegación correspondiente a la pantalla actual."""
        current = self.window.screen_stack.currentWidget()

        nav_buttons = getattr(self.window, "navigation_buttons", {}) or {}
        dialysis_nav_text = (
            "Diálisis"
            if ("Diálisis" in nav_buttons and "Resumen\nTerapia" not in nav_buttons)
            else "Resumen\nTerapia"
        )

        mapping = {
            self.window._main_screen: "Inicio",
            self.window.dialysis_screen: dialysis_nav_text,
            self.window.cleaning_screen: "Limpieza",
            self.window.options_screen: "Servicio",
            self.window.alarms_screen: "Alarmas",
            self.window.history_screen: "Historial",
            self.window.KTVScreen: dialysis_nav_text,                    # ← Importante
            self.window.patient_config_screen: dialysis_nav_text,
            self.window.therapy_config_screen: dialysis_nav_text,
            self.window.conductivity_profile_screen: dialysis_nav_text,
            self.window.uf_profile_screen: dialysis_nav_text,
            self.window.heparin_config_screen: dialysis_nav_text,
        }

        # Pantallas de servicio
        service_screens = {
            self.window.manual_mode_screen, self.window.test_panel_screen,
            self.window.calibration_screen, self.window.network_config_screen,
            self.window.comm_port_screen, self.window.maintenance_screen,
            self.window._cleanning_config_screen, self.window.alarm_service_screen_config,
            self.window.theme_config_screen
        }

        if current in mapping:
            return mapping[current]
        if current in service_screens:
            return "Servicio"

        return ""

    def _highlight_active_nav_button(self, active_button_text: str):
        """Resalta el botón activo y restaura el resto."""
        if not active_button_text:
            return

        for text, btn in self.window.navigation_buttons.items():
            if text == active_button_text:
                btn.setStyleSheet(self.window.BTN_ACTIVE_STYLE)
            elif text in ["Inicio", "Diálisis", "Resumen\nTerapia",
                          "Limpieza", "Servicio", "Alarmas", "Historial"]:
                # Solo restauramos estilo si el botón está habilitado
                if btn.isEnabled():
                    btn.setStyleSheet(self.window.BTN_ENABLED_DEFAULT_STYLE)

    def _refresh_navigation_bar(self):
        """Lógica centralizada y clara según especificación del usuario"""
        if not self.window.serial_comm or not self.window.serial_comm.is_connected:
            self.window._handle_disconnected_state()
            self.window._update_treatment_mode_label_state()
            return
        # status_code = int(self.window.current_values.get("primingProcessStatus", 0))
        temp_actual = safe_float(self.window.current_values.get("dialyTempIFProcessData", 0.0), 0.0)
        temp_set    = safe_float(self.window.current_values.get("dialyTempControlSetPoint", 0.0), 0.0)
        cond_actual = safe_float(self.window.current_values.get("dialyCondVariableData", 0.0), 0.0)
        cond_set    = safe_float(self.window.current_values.get("dialyCondControlSetPoint", 0.0), 0.0)

        # 2. Lógica de validación (Tolerancias)
        temp_ok = (temp_actual - temp_set <= 2.0) and (temp_set - temp_actual <= 5.0)
        cond_ok = abs(cond_actual - cond_set) <= 2.0

        phase = self.window.state.current_phase
        status_code = safe_int(self.window.current_values.get("primingProcessStatus", 0), 0)
        treatment_mode = safe_int(self.window.current_values.get("treatmentModeSelection", 0), 0)
        # 1. OBTENER TEXTO DE PANTALLA ACTUAL 
        current_nav_text = self.window._get_current_screen_nav_text()

        for text, btn in self.window.navigation_buttons.items():
            enabled = False

            # ==================== REGLAS POR BOTÓN ====================
            if text == "Servicio":
                enabled = True  # Siempre accesible (configuración, mantenimiento, etc.)

            elif text == "Alarmas":
                enabled = True

            elif text == "Historial":
                enabled = True

            elif text in ("Diálisis", "Resumen\nTerapia"):
                enabled = phase not in (TreatmentPhase.CLEANING,)

            elif text == "Limpieza":
                enabled = (treatment_mode == 3)

            elif text == "Inicio":
                enabled = phase in (TreatmentPhase.IDLE, TreatmentPhase.PREPARING)

            elif text == "Iniciar\nTratamiento":
                enabled = phase in (TreatmentPhase.READY, TreatmentPhase.PAUSED)

            # ==================== RESTRICCIONES POR ESTADO ====================
            if phase == TreatmentPhase.CLEANING:
                enabled = text in ["Limpieza", "Alarmas", "Historial", "Servicio"]

            elif phase == TreatmentPhase.RUNNING:
                enabled = text in ["Diálisis", "Resumen\nTerapia", "Alarmas", "Historial"]

            elif phase == TreatmentPhase.PAUSED:
                enabled = text in ["Diálisis", "Resumen\nTerapia", "Iniciar\nTratamiento", "Servicio",
                             "Alarmas", "Historial"]
                if text == "Iniciar\nTratamiento":
                    enabled = self.window._can_start_treatment()

            elif phase == TreatmentPhase.READY:
                enabled = text in ["Diálisis", "Resumen\nTerapia", "Iniciar\nTratamiento", "Servicio",
                             "Alarmas", "Historial"]
                if text == "Iniciar\nTratamiento":
                    # enabled = temp_ok and cond_ok
                    enabled = self.window._can_start_treatment()
                # Deshabilitamos explícitamente estos
                if text in ["Inicio", "Limpieza"]:
                    enabled = False

            elif phase == TreatmentPhase.PREPARING:
                status = int(self.window.current_values.get("primingProcessStatus", 0))
                if self.window.hardware_mapper.is_preparing(status):
                    # Durante cebado normal
                    enabled = text in ["Diálisis", "Resumen\nTerapia", "Alarmas", "Historial", "Servicio"]
                else:
                    # Cuando se detiene el priming
                    enabled = True

            elif phase == TreatmentPhase.IDLE:
                enabled = text in ["Diálisis", "Resumen\nTerapia", "Inicio",
                                 "Servicio", "Alarmas", "Historial"]
                if text == "Limpieza":
                    enabled = (treatment_mode == 3)

            # Aplicar estado
            btn.setEnabled(enabled)

            # ==================== ESTILOS ====================
            if enabled:
                if text == "Iniciar\nTratamiento":
                    if phase == TreatmentPhase.RUNNING:
                        btn.setStyleSheet(self.window.BTN_ACTIVE_STYLE)
                    elif phase == TreatmentPhase.PAUSED:
                        btn.setStyleSheet(self.window.BTN_ENABLED_START_TREATMENT_STYLE)
                    else:
                        btn.setStyleSheet(self.window.BTN_ENABLED_START_TREATMENT_STYLE)

                elif text == current_nav_text:
                    btn.setStyleSheet(self.window.BTN_ACTIVE_STYLE)
                else:
                    btn.setStyleSheet(self.window.BTN_ENABLED_DEFAULT_STYLE)
            else:
                btn.setStyleSheet(self.window.BTN_DISABLED_STYLE)

        # Actualizar texto del botón principal
        self.window._update_buttons_state()

        # Actualizar estado del label de tipo de tratamiento
        self.window._update_treatment_mode_label_state()

    def _handle_disconnected_state(self):
        """Estado sin conexión"""
        for text, btn in self.window.navigation_buttons.items():
            if text == "Servicio":
                btn.setEnabled(True)
                btn.setStyleSheet(self.window.BTN_ENABLED_DEFAULT_STYLE)
            else:
                btn.setEnabled(False)
                btn.setStyleSheet(self.window.BTN_DISABLED_STYLE)

    def _update_buttons_state(self):
        phase = self.window.state.current_phase
        btn = self.window.navigation_buttons.get("Iniciar\nTratamiento")
        if not btn:
            return

        if phase == TreatmentPhase.RUNNING:
            btn.setText("Tratamiento\nActivo")
            btn.setEnabled(False)
        elif phase == TreatmentPhase.PAUSED:
            btn.setText("Reanudar\nTratamiento")
            btn.setEnabled(self.window._can_start_treatment())
        elif phase == TreatmentPhase.READY:
            btn.setText("Iniciar\nTratamiento")
            btn.setEnabled(self.window._can_start_treatment())
        else:
            btn.setText("Iniciar\nTratamiento")
            btn.setEnabled(False)

    def _set_button_style(self, button: QPushButton, style_type: str):
        """Aplica estilos predefinidos a los botones"""
        if style_type == "start":
            button.setStyleSheet(self.window.BTN_ENABLED_START_TREATMENT_STYLE)
        elif style_type == "active":
            button.setStyleSheet(self.window.BTN_ACTIVE_STYLE)
        else:
            button.setStyleSheet(self.window.BTN_ENABLED_DEFAULT_STYLE)

    def update_date_time(self):
        self.window.date_time_label.setText(datetime.now().strftime("%d/%m/%Y \n %H:%M:%S"))

    def refresh_alarms_label(self):
        """
        Reutiliza status_label para mostrar conexión/estado/alarmas.
        """
        tokens = ThemeManager.get_tokens()
        is_mono = bool(tokens.get("monochrome", False))
        is_dark = bool(tokens.get("is_dark", False))

        if not self.window.serial_comm or not self.window.serial_comm.is_connected:
            self.window.status_label.setText("RECONECTANDO")
            if is_mono:
                self.window.status_label.setStyleSheet("""
                    QLabel { color: #374151; background: #D9E0E8; font-weight: bold; font-size: 20px; border-radius: 8px; border: 1px solid #C5CDD6; }
                """)
            elif is_dark:
                self.window.status_label.setStyleSheet(f"""
                    QLabel {{ color: #ffffff; background: {tokens.get('warning', '#f59e0b')}; font-weight: bold; font-size: 20px; border-radius: 8px; }}
                """)
            else:
                self.window.status_label.setStyleSheet("""
                    QLabel { color: #ffffff; background: #f39c12; font-weight: bold; font-size: 20px; border-radius: 8px; }
                """)
            return

        if getattr(self.window, "_connection_just_established_ticks", 0) > 0:
            self.window._connection_just_established_ticks -= 1
            self.window.status_label.setText("CONEXION\nESTABLECIDA")
            if is_mono:
                self.window.status_label.setStyleSheet("""
                    QLabel { color: #374151; background: #D9E0E8; font-weight: bold; font-size: 20px; border-radius: 8px; border: 1px solid #C5CDD6; }
                """)
            elif is_dark:
                self.window.status_label.setStyleSheet(f"""
                    QLabel {{ color: {tokens.get('text_primary', '#F8FAFC')}; background: {tokens.get('bg_card_alt', '#1E293B')}; font-weight: bold; font-size: 20px; border-radius: 8px; border: 1px solid {tokens.get('border_card', '#334155')}; }}
                """)
            else:
                self.window.status_label.setStyleSheet("""
                    QLabel { color: #ffffff; background: #0ea5e9; font-weight: bold; font-size: 20px; border-radius: 8px; }
                """)
            return

        if self.window._last_priming_status < 0 and not self.window.active_alarms:
            self.window.status_label.setText("MAQUINA\nCONECTADA")
            if is_mono:
                self.window.status_label.setStyleSheet("""
                    QLabel { color: #374151; background: #D9E0E8; font-weight: bold; font-size: 20px; border-radius: 8px; border: 1px solid #C5CDD6; }
                """)
            elif is_dark:
                self.window.status_label.setStyleSheet(f"""
                    QLabel {{ color: {tokens.get('text_primary', '#F8FAFC')}; background: {tokens.get('bg_card_alt', '#1E293B')}; font-weight: bold; font-size: 20px; border-radius: 8px; border: 1px solid {tokens.get('border_card', '#334155')}; }}
                """)
            else:
                self.window.status_label.setStyleSheet("""
                    QLabel { color: #ffffff; background: #0891b2; font-weight: bold; font-size: 20px; border-radius: 8px; }
                """)
            return

        if not self.window.active_alarms:
            self.window.status_label.setText("ESTADO: OK")
            if is_mono:
                # En Escala de grises ESTADO: OK deja el verde -> usa gris #D9E0E8 y texto #374151
                self.window.status_label.setStyleSheet("""
                    QLabel { color: #374151; background: #D9E0E8; font-weight: bold; font-size: 22px; border-radius: 8px; border: 1px solid #C5CDD6; }
                """)
            elif is_dark:
                self.window.status_label.setStyleSheet(f"""
                    QLabel {{ color: #ffffff; background: {tokens.get('success', '#10b981')}; font-weight: bold; font-size: 22px; border-radius: 8px; }}
                """)
            else:
                self.window.status_label.setStyleSheet("""
                    QLabel { color: #ffffff; background: #2bbd37; font-weight: bold; font-size: 22px; border-radius: 8px; }
                """)
            self.window._alarm_flash_toggle = False
            return

        # Orden de prioridad (rojo > naranja > amarillo > cian)
        priority_map = {"rojo": 4, "naranja": 3, "amarillo": 2, "cian": 1, "info": 0}
        top_alarm = max(self.window.active_alarms, key=lambda x: priority_map.get(x[2], 0))
        name, value, level = top_alarm

        short_label = name
        is_boolean = False

        for group in VARIABLES.values():
            if isinstance(group, dict):
                for info in group.values():
                    if info.get("name") == name:
                        short_label = info.get("label", name)
                        if info.get("type") == "bool":
                            is_boolean = True
                        break

        display_text = short_label.upper()
        if not is_boolean and value is not None and isinstance(value, (int, float)):
            display_text += f" {value:.1f}"

        color_map = {"rojo": "#dc2626", "naranja": "#f97316", "amarillo": "#eab308", "cian": "#06b6d4"}
        bg_color = color_map.get(level, "#1e293b")

        # Parpadeo entre mensaje genérico y detalle de la alarma activa.
        self.window._alarm_flash_toggle = not getattr(self.window, "_alarm_flash_toggle", False)
        flash_text = "ALARMA" if self.window._alarm_flash_toggle else display_text

        self.window.status_label.setText(flash_text)
        if is_mono:
            self.window.status_label.setStyleSheet("""
                QLabel { background: #9CA3AF; color: #111827; font-weight: bold; font-size: 22px; border-radius: 8px; border: 1px solid #6B7280; }
            """)
        else:
            self.window.status_label.setStyleSheet(f"""
                QLabel {{ background: {bg_color}; color: #ffffff; font-weight: bold; font-size: 22px; border-radius: 8px; }}
            """)

    def refresh_treatment_selected(self):
        short_mode_map = {
            0: "HD",
            1: "HDF",
            2: "UF",
            3: "Desinfección",
        }
        mode_code = int(self.window.current_values.get("treatmentModeSelection", 0))
        mode_text = short_mode_map.get(mode_code, "HD")
        self.window.treatment_mode_selected.setText(mode_text)
        self.window.treatment_mode_selected.setAlignment(Qt.AlignCenter)
        # El color y estado se actualizan en _update_treatment_mode_label_state()

    def update_remaining_time_header(self, remaining_str: str):
        if hasattr(self.window, "remaining_time_display") and self.window.remaining_time_display:
            self.window.remaining_time_display.setText(
                "<div style='text-align:center;'>"
                "<span style='font-size:25px;'>T. RESTANTE</span><br>"
                f"<span style='font-size:32px;'>{remaining_str}</span>"
                "</div>"
            )

    def setup_ui(self):
        from gui.appMainHemodialysis import ClickableTreatmentLabel, LogoButton, resource_path

        central_widget = QWidget()
        central_widget.setObjectName("main_central_widget")
        central_widget.setStyleSheet("QWidget#main_central_widget { background: #FCFCFC; }")
        self.window.setCentralWidget(central_widget)
        self.window.main_layout = QGridLayout(central_widget)
        self.window.main_layout.setSpacing(0)
        self.window.main_layout.setContentsMargins(0, 0, 0, 0)

        self.window.main_layout.setColumnStretch(0, 0)  # COLUMNA 0 → IZQUIERDA
        self.window.main_layout.setColumnStretch(1, 1)  # COLUMNA 1 → STACKED + NAV (parte 1/4)
        self.window.main_layout.setColumnStretch(2, 1)  # COLUMNA 2 → STACKED + NAV (parte 2/4)
        self.window.main_layout.setColumnStretch(3, 1)  # COLUMNA 3 → STACKED + NAV (parte 3/4)
        self.window.main_layout.setColumnStretch(4, 1)  # COLUMNA 4 → STACKED + NAV (parte 4/4)
        self.window.main_layout.setColumnStretch(5, 0)  # COLUMNA 5 → DERECHA

        # =========================================================================================
        #                                    MAIN STACKED
        # =========================================================================================
        # En gui/appMainHemodialysis.py -> setup_ui
        self.window.screen_stack = QStackedWidget()
        self.window.screen_stack.setObjectName("main_screen_stack")

        # ESTILO GLOBAL CENTRALIZADO
        self.window.screen_stack.setStyleSheet("""
            /* Asegura que el contenedor del stack y sus páginas sean claros */
            QStackedWidget#main_screen_stack, 
            QStackedWidget#main_screen_stack > QWidget {
                background-color: #FCFCFC;
            }

            /* Estilo de las Cards (se aplica a Frames y GroupBoxes con este ID) */
            QFrame#card, QFrame#graph_card, QGroupBox#card {
                background-color: #ffffff;
                border: 2px solid #cbd5e1;
                border-radius: 14px;
            }

            /* Etiquetas generales */
            QLabel {
                color: #334155;
                background-color: transparent;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 22px;
            }

            /* Título de la card con la línea debajo que pediste */
            QLabel#card_title {
                color: #0f172a;
                font-size: 20px;
                font-weight: bold;
                background: transparent;
                border: none;
                border-bottom: 2px solid #77787D;
                padding-bottom: 8px;
                margin-bottom: 8px;
            }

            /* Valores grandes con colores específicos */
            QLabel#val_large {
                color: #ef4444;
                font-family: 'Consolas', monospace;
                font-size: 52px;
                font-weight: bold;
            }
            QLabel#val_large_yellow {
                color: #eab308;
                font-family: 'Consolas', monospace;
                font-size: 52px;
                font-weight: bold;
            }
            QLabel#val_large_green {
                color: #15301E;
                font-family: 'Consolas', monospace;
                font-size: 52px;
                font-weight: bold;
            }
            QLabel#val_large_cyan {
                color: #0369a1;
                font-family: 'Consolas', monospace;
                font-size: 52px;
                font-weight: bold;
            }
    
            QPushButton {
                padding: 4px 10px;
            }
        """)

        self.window.screen_stack.setAutoFillBackground(True)
        stack_palette = self.window.screen_stack.palette()
        stack_palette.setColor(self.window.screen_stack.backgroundRole(), QColor("#FCFCFC"))
        self.window.screen_stack.setPalette(stack_palette)
        self.window._main_screen = MainScreen()
        self.window.screen_stack.addWidget(self.window._main_screen)
        self.window.main_layout.addWidget(self.window.screen_stack, 1, 1, 1, 4)
        # ==============================================2===========================================
        # ============================ Header (1920 × 177) ========================================
        # ==========================================================================================
        header_container = QWidget()
        self.window.header_container = header_container
        header_container.setFixedHeight(150)
        header_container.setStyleSheet("background: #EBEBEB;")

        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(8, 2, 8, 2)
        header_layout.setSpacing(8)

        # logo 1
        logo1 = LogoButton(
            icon_path=resource_path("resources/images/logo_ciateq__.png"),
            close_callback=self.window._show_exit_confirmation,
            screen_stack=self.window.screen_stack,
            parent=self.window,
        )
        logo1.setObjectName("header_logo_left")

        self.window._orig_pixmap_logo1 = QPixmap(resource_path("resources/images/logo_ciateq__.png")).scaled(
            180, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        self.window.logo1 = logo1
        header_layout.addWidget(logo1)
        header_layout.addStretch(1)

        self.window.status_label = QLabel("RECONECTANDO")
        self.window.status_label.setObjectName("header_status_label")
        self.window.status_label.setStyleSheet(self.window._build_header_label_style("#2bbd37"))

        self.window.current_process_status = QLabel("PROCESO: --")
        self.window.treatment_mode_selected = ClickableTreatmentLabel("HD")
        self.window.treatment_mode_selected.set_callback(self.window._on_treatment_mode_label_click)
        self.window.remaining_time_display = QLabel(
            "<div style='text-align:center;'>"
            "<span style='font-size:25px;'>T. RESTANTE</span><br>"
            "<span style='font-size:32px;'>00:00:00</span>"
            "</div>"
        )
        self.window.date_time_label = QLabel("25/12/2025 \n 14:37:22")

        self.window.current_process_status.setObjectName("header_process_label")
        self.window.treatment_mode_selected.setObjectName("header_treatment_label")
        self.window.remaining_time_display.setObjectName("header_remaining_label")
        self.window.date_time_label.setObjectName("header_datetime_label")

        self.window.current_process_status.setStyleSheet(
            self.window._build_header_label_style("#2bbd37", is_process=True)
        )
        self.window.treatment_mode_selected.setStyleSheet(
            self.window._build_header_label_style("#06298a", is_process=False)
        )
        self.window.remaining_time_display.setStyleSheet(
            self.window._build_header_label_style("#06298a", is_process=False)
        )
        self.window.date_time_label.setStyleSheet(
            self.window._build_header_label_style("#06298a", is_process=False)
        )

        header_pieces = [
            ("header_frame_status", self.window.status_label, 260),
            ("header_frame_process", self.window.current_process_status, 300),
            ("header_frame_treatment", self.window.treatment_mode_selected, 250),
            ("header_frame_remaining", self.window.remaining_time_display, 280),
            ("header_frame_datetime", self.window.date_time_label, 280),
        ]
        self.window.header_piece_frames = []
        for frame_name, lbl, piece_width in header_pieces:
            piece_frame = QFrame()
            piece_frame.setObjectName(frame_name)
            piece_frame.setFixedSize(piece_width, 120)
            piece_frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            piece_frame.setStyleSheet("QFrame { background: transparent; border: none; }")
            piece_layout = QVBoxLayout(piece_frame)
            piece_layout.setContentsMargins(0, 0, 0, 0)
            piece_layout.setSpacing(0)
            lbl.setFixedSize(piece_width, 120)
            lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            lbl.setAlignment(Qt.AlignCenter)
            piece_layout.addWidget(lbl)
            self.window.header_piece_frames.append(piece_frame)
            header_layout.addWidget(piece_frame)

        # header_layout.addStretch()

        # Logo 2
        logo2 = QLabel()
        logo2.setObjectName("header_logo_right")
        logo2.setAlignment(Qt.AlignCenter)
        self.window._orig_pixmap_logo2 = QPixmap(resource_path("resources/images/Logo_secihti_.png")).scaled(
            180, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        logo2.setPixmap(self.window._orig_pixmap_logo2)
        self.window.logo2 = logo2
        header_layout.addStretch(1)
        header_layout.addWidget(logo2)

        self.window.main_layout.addWidget(header_container, 0, 0, 1, 6)

        self.window._get_side_indicators().setup_ui()

        # ── Bottom navigation bar ────────────────────────
        self.window.nav_bar = QWidget()
        self.window.nav_bar.setFixedSize(1560, 150)
        self.window.nav_bar.setStyleSheet("background: #FCFCFC;")

        nav_layout = QHBoxLayout(self.window.nav_bar)
        nav_layout.setContentsMargins(40, 20, 40, 20)
        nav_layout.setSpacing(10)

        # Contenedor central para mantener los botones centrados
        central_nav_widget = QWidget()
        central_nav_layout = QHBoxLayout(central_nav_widget)
        central_nav_layout.setContentsMargins(0, 0, 0, 0)
        central_nav_layout.setSpacing(10)

        self.window.navigation_buttons = {}

        nav_items = [
            ("Inicio", "#06298a", self.window.show_home_screen),
            ("Resumen\nTerapia", "#06298a", self.window.show_dialysis_screen),
            ("Iniciar\nTratamiento", "#39ec21", self.window.start_treatment),
            ("Limpieza", "#06298a", self.window.show_cleaning_screen),
            ("Servicio", "#06298a", self.window.show_options_screen),
            ("Alarmas", "#06298a", self.window.show_alarms_screen),
            ("Historial", "#06298a", self.window.show_history_screen),
        ]

        for text, color, callback in nav_items:
            btn = QPushButton(text)
            btn.setFixedSize(200, 110)
            btn.clicked.connect(callback)
            central_nav_layout.addWidget(btn)
            self.window.navigation_buttons[text] = btn

        # Agregar stretches a los lados para centrar el contenedor
        nav_layout.addStretch()
        nav_layout.addWidget(central_nav_widget)
        nav_layout.addStretch()

        self.window.main_layout.addWidget(self.window.nav_bar, 2, 1, 1, 4)
        self.window.screen_stack.currentChanged.connect(self.window._apply_home_chrome)
        self.window._apply_home_chrome()

    def show_home_screen(self):
        self.window.screen_stack.setCurrentIndex(self.window.INDEX_HOME)
        self.window.right_content.hide()
        self.window.left_content.hide()
        self.window._highlight_active_nav_button("Inicio")

    def show_dialysis_screen(self):
        self.window.screen_stack.setCurrentWidget(self.window.dialysis_screen)
        if hasattr(self.window.dialysis_screen, "update_values"):
            self.window.dialysis_screen.update_values(self.window.current_values)
        self.window.left_content.show()
        self.window.right_content.show()
        self.window.navigation_buttons["Inicio"].setEnabled(True)
        self.window.navigation_buttons["Inicio"].setStyleSheet(self.window.BTN_ENABLED_DEFAULT_STYLE)  # NUEVO: usa el estilo de clase
        self.window._highlight_active_nav_button("Resumen\nTerapia")

    def show_treatment_mode_screen(self):
        self.window.screen_stack.setCurrentWidget(self.window.treatment_mode_screen)
        self.window.left_content.show()
        self.window.right_content.show()

    def show_cleaning_screen(self):
        self.window.screen_stack.setCurrentWidget(self.window.cleaning_screen)
        if hasattr(self.window.cleaning_screen, "update_values"):
            self.window.cleaning_screen.update_values(self.window.current_values)
        if hasattr(self.window.cleaning_screen, "reset_cleaning_mode_selection"):
            self.window.cleaning_screen.reset_cleaning_mode_selection(reset_display=True)
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Limpieza")

    def show_options_screen(self):
        self.window.screen_stack.setCurrentWidget(self.window.options_screen)
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Servicio")

    def show_theme_config_screen(self):
        self.window.screen_stack.setCurrentWidget(self.window.theme_config_screen)
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Servicio")

    def show_alarms_screen(self):
        self.window.screen_stack.setCurrentWidget(self.window.alarms_screen)
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Alarmas")

    def show_manual_mode_screen(self):
        self.window.screen_stack.setCurrentWidget(self.window.manual_mode_screen)
        if hasattr(self.window.manual_mode_screen, "update_values"):
            self.window.manual_mode_screen.update_values(self.window.current_values)
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Servicio")

    def show_test_panel_screen(self):
        self.window.screen_stack.setCurrentWidget(self.window.test_panel_screen)
        if hasattr(self.window.test_panel_screen, "update_values"):
            self.window.test_panel_screen.update_values(self.window.current_values)
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Servicio")

    def show_calibration_screen(self):
        self.window.screen_stack.setCurrentWidget(self.window.calibration_screen)
        if hasattr(self.window.calibration_screen, "update_values"):
            self.window.calibration_screen.update_values(self.window.current_values)
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Servicio")

    def show_network_config_screen(self):
        self.window.screen_stack.setCurrentWidget(self.window.network_config_screen)
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Servicio")

    def show_real_time_var_screen(self):
        self.window.screen_stack.setCurrentWidget(self.window.real_time_var)
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Servicio")

    def show_patient_config_screen(self):
        self.window.screen_stack.setCurrentWidget(self.window.patient_config_screen)
        if hasattr(self.window.patient_config_screen, "update_values"):
            self.window.patient_config_screen.update_values(self.window.current_values)
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Resumen\nTerapia")

    def show_therapy_config_screen(self):
        self.window.screen_stack.setCurrentWidget(self.window.therapy_config_screen)
        if hasattr(self.window.therapy_config_screen, "update_values"):
            self.window.therapy_config_screen.update_values(self.window.current_values)
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Resumen\nTerapia")

    def show_conductivity_profile_screen(self):
        can_open, msg = self.window.can_configure_conductivity_profile()
        if not can_open:
            self.window.show_warning_message(msg, 4500)
            return

        self.window.screen_stack.setCurrentWidget(self.window.conductivity_profile_screen)
        if hasattr(self.window.conductivity_profile_screen, "update_values"):
            self.window.conductivity_profile_screen.update_values(self.window.current_values)
        if hasattr(self.window.conductivity_profile_screen, "refresh_from_parent"):
            self.window.conductivity_profile_screen.refresh_from_parent()
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Resumen\nTerapia")

    def show_uf_profile_screen(self):
        can_open, msg = self.window.can_configure_uf_profile()
        if not can_open:
            self.window.show_warning_message(msg, 4500)
            return

        self.window.screen_stack.setCurrentWidget(self.window.uf_profile_screen)
        if hasattr(self.window.uf_profile_screen, "update_values"):
            self.window.uf_profile_screen.update_values(self.window.current_values)
        if hasattr(self.window.uf_profile_screen, "refresh_from_parent"):
            self.window.uf_profile_screen.refresh_from_parent()
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Resumen\nTerapia")

    def show_heparin_config_screen(self):
        self.window.screen_stack.setCurrentWidget(self.window.heparin_config_screen)
        if hasattr(self.window.heparin_config_screen, "update_values"):
            self.window.heparin_config_screen.update_values(self.window.current_values)
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Resumen\nTerapia")

    def show_config_comm_screen(self):
        self.window.screen_stack.setCurrentWidget(self.window.comm_port_screen)
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Servicio")

    def show_maintenance_screen(self):
        """Muestra la pantalla de mantenimiento y actualiza inmediatamente los valores"""
        self.window.screen_stack.setCurrentWidget(self.window.maintenance_screen)
        self.window.left_content.show()
        self.window.right_content.show()
        # self._update_maintenance_screen_immediately()
        self.window.timer_manager._update_maintenance_screen()
        self.window._highlight_active_nav_button("Servicio")

    def show_alarm_config_limits_screen(self):
        self.window.screen_stack.setCurrentWidget(self.window.alarm_config_limits_screen)
        self.window.alarm_config_limits_screen.refresh_ui()
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Alarmas")

    def show_alarm_service_screen_config(self):
        self.window.screen_stack.setCurrentWidget(self.window.alarm_service_screen_config)
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Servicio")

    def show_cleanning_config_screen(self):
        self.window.screen_stack.setCurrentWidget(self.window._cleanning_config_screen)
        self.window.left_content.show()
        self.window.right_content.show()
        if hasattr(self.window._cleanning_config_screen, '_load_config_for_display'):
            self.window._cleanning_config_screen._load_config_for_display()
            self.window._highlight_active_nav_button("Servicio")

    def show_history_screen(self):
        self.window.screen_stack.setCurrentWidget(self.window.history_screen)
        self.window.history_screen.refresh_data()
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Historial")

    def show_ktv_screen(self):
        self.window.screen_stack.setCurrentWidget(self.window.KTVScreen)
        # La actualización de valores en KTVScreen ahora es más granular
        # No se llama update_values aquí directamente para todos los current_values.
        # KTVScreen ya se actualiza a través del master_timer y las señales del ktv_controller.
        self.window.KTVScreen.update_patient_data(self.window.current_values)  # Función auxiliar para datos del paciente
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Resumen\nTerapia")

    def show_nibp_screen(self):
        # TEMPORAL: acceso desde el card de signos vitales de dialysis_screen.
        # Al abrir módulo: set_adult_mode() (cmd 24)
        self.window.nibp.set_adult_mode()
        self.window.screen_stack.setCurrentWidget(self.window.nibp_screen)
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Resumen\nTerapia")

    def show_nibp_history_screen(self):
        """Muestra la pantalla de Tomas del historial de presión arterial (sin borrar el historial)."""
        hours = safe_int(self.window.current_values.get("heparineTherapyHours", 0), 0)
        minutes = safe_int(self.window.current_values.get("heparineTherapyMinutes", 0), 0)
        self.window.nibp_history_screen.set_programmed_duration(hours, minutes)
        self.window.nibp_history_screen.update_from_history()
        self.window.screen_stack.setCurrentWidget(self.window.nibp_history_screen)
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Resumen\nTerapia")

    def show_nibp_chart_screen(self):
        """Muestra la pantalla de Gráfica de presión arterial (sin borrar el historial)."""
        hours = safe_int(self.window.current_values.get("heparineTherapyHours", 0), 0)
        minutes = safe_int(self.window.current_values.get("heparineTherapyMinutes", 0), 0)
        self.window.nibp_chart_screen.set_programmed_duration(hours, minutes)
        self.window.nibp_chart_screen.update_from_history()
        self.window.screen_stack.setCurrentWidget(self.window.nibp_chart_screen)
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Resumen\nTerapia")

    def show_nibp_limits_screen(self):
        """Muestra la pantalla de Límites de presión arterial."""
        self.window.nibp_limits_screen.load_limits_from_config()
        self.window.screen_stack.setCurrentWidget(self.window.nibp_limits_screen)
        self.window.left_content.show()
        self.window.right_content.show()
        self.window._highlight_active_nav_button("Resumen\nTerapia")

    def build_screens(self):
        # ====================== PANTALLAS ======================
        self.window.alarms_screen = AlarmsScreen(
            parent=self.window,
            values_dict=self.window.current_values,
            alarm_system=self.window.alarm_system,
        )
        self.window.alarms_screen.request_boolean_change.connect(
            self.window._write_boolean_command
        )  # Conexión: conecta la señal de pantalla con el método de escritura serial en main

        self.window.real_time_var = RealTimeVariablesMonitor(
            parent=self.window,
            values_dict=self.window.current_values,
            alarm_system=self.window.alarm_system,
        )

        # Pantalla de configuración para Operador
        self.window.alarm_config_limits_screen = AlarmScreenConfig(
            write_setpoint_callback=self.window._emit_pressure_alarm_limits,
            config_manager=self.window.config_manager,
            parent=self.window,
        )

        # Pantalla de configuración para Servicio Técnico
        self.window.alarm_service_screen_config = AlarmScreenServiceConfig(
            config_manager=self.window.config_manager,
            parent=self.window,
        )
        # # Therapy & service screens
        self.window.dialysis_screen = DialysisScreen(parent=self.window, values_dict=self.window.current_values)
        self.window.dialysis_screen.request_boolean_change.connect(self.window._write_boolean_command)

        self.window.treatment_mode_screen = TreatmentModeScreen(
            parent=self.window, values_dict=self.window.current_values
        )
        self.window.treatment_mode_screen.request_setpoint_change.connect(
            self.window._write_setpoint
        )  # Conexión: conecta la señal de pantalla con el método de escritura serial en main

        self.window.cleaning_screen = CleaningScreen(parent=self.window, values_dict=self.window.current_values)
        self.window.cleaning_screen.request_setpoint_change.connect(self.window._write_setpoint)
        self.window.cleaning_screen.request_boolean_change.connect(self.window._write_boolean_command)
        self.window.cleaning_screen.cleaning_active_changed.connect(self.window._handle_cleaning_status_change)

        self.window.cleaning_screen.cleaning_started_counting.connect(self.window._set_cleaning_start_time)

        self.window.cleaning_screen.cleaning_started_counting.connect(
            self.window.timer_manager.on_cleaning_started_counting
        )
        self.window.cleaning_screen.cleaning_stopped_counting.connect(
            self.window.timer_manager.on_cleaning_stopped_counting
        )
        self.window.options_screen = OptionsScreen(parent=self.window)

        # # Service sub-screens
        self.window.manual_mode_screen = ManualModeScreen(
            parent=self.window, values_dict=self.window.current_values
        )
        self.window.manual_mode_screen.request_setpoint_change.connect(self.window._write_setpoint)
        self.window.manual_mode_screen.request_boolean_change.connect(self.window._write_boolean_command)

        self.window.test_panel_screen = TestPanelScreen(
            parent=self.window, values_dict=self.window.current_values
        )
        self.window.test_panel_screen.request_setpoint_change.connect(
            self.window._write_setpoint
        )  # Conexión: conecta la señal de pantalla con el método de escritura serial en main

        self.window.calibration_screen = CalibrationScreen(
            parent=self.window, values_dict=self.window.current_values
        )
        self.window.calibration_screen.request_setpoint_change.connect(self.window._write_setpoint)
        self.window.calibration_screen.request_boolean_change.connect(self.window._write_boolean_command)

        self.window.network_config_screen = NetworkConfigScreen(parent=self.window)

        self.window.comm_port_screen = CommPortScreen(parent=self.window)
        self.window.comm_port_screen.config_changed.connect(self.window.handle_comm_config_change)
        self.window.nibp.connected_changed.connect(self.window.comm_port_screen.update_nibp_status)
        self.window.nibp.error_message.connect(self.window.comm_port_screen.update_nibp_error)

        self.window.nibp_screen = NibpConfigScreen(parent=self.window)
        self.window.nibp_screen.settings_applied.connect(self.window._on_nibp_settings_applied)
        self.window.nibp_screen.measure_now_requested.connect(self.window._on_nibp_measure_requested)
        self.window.nibp_screen.reset_requested.connect(self.window._on_nibp_reset_requested)
        self.window.nibp_screen.spo2_on_requested.connect(self.window.nibp.spo2_on)
        self.window.nibp_screen.spo2_off_requested.connect(self.window.nibp.spo2_off)
        self.window.nibp.connected_changed.connect(self.window.nibp_screen.update_connection)
        self.window.nibp.error_message.connect(self.window.nibp_screen.update_error)
        self.window.nibp.error_cleared.connect(self.window.nibp_screen.clear_error)
        self.window.nibp.measurement_ready.connect(self.window.nibp_screen.update_measurement)
        self.window.nibp.cuff_pressure.connect(self.window.nibp_screen.update_cuff)
        self.window.nibp.spo2_updated.connect(self.window.nibp_screen.update_spo2)
        self.window.nibp.measurement_ready.connect(self.window.dialysis_screen.update_nibp_measurement)
        self.window.nibp.spo2_updated.connect(self.window.dialysis_screen.update_spo2)

        # Conexiones para el historial de presión arterial
        self.window.nibp_screen.measure_now_requested.connect(self.window._on_nibp_measure_requested_for_history)
        self.window.nibp_screen.history_requested.connect(self.window.show_nibp_history_screen)
        self.window.nibp_screen.limits_requested.connect(self.window.show_nibp_limits_screen)
        self.window.nibp.measurement_ready.connect(self.window._on_nibp_measurement_ready_for_history)

        self.window.maintenance_screen = MaintenanceScreen(parent=self.window)  # PANTALLA NUEVA DE MANTENIMIENTO

        self.window._cleanning_config_screen = CleanningConfigScreen(parent=self.window)

        # # Therapy sub-screens
        self.window.patient_config_screen = PatientConfigScreen(parent=self.window)

        self.window.therapy_config_screen = TherapyConfigScreen(
            parent=self.window, values_dict=self.window.current_values
        )  # intanciar pasando los valores actuales (values_dict)
        self.window.therapy_config_screen.request_setpoint_change.connect(
            self.window._write_setpoint
        )  # Conexión: conecta la señal de pantalla con el método de escritura serial en main
        self.window.therapy_config_screen.request_boolean_change.connect(self.window._write_boolean_command)
        self.window.therapy_config_screen.valueChanged.connect(
            self.window.handleGlobalValueChange
        )  # Actualizar UI localmente

        self.window.conductivity_profile_screen = ConductivityProfileScreen(
            parent=self.window, values_dict=self.window.current_values
        )
        self.window.uf_profile_screen = UFProfileScreen(parent=self.window, values_dict=self.window.current_values)

        self.window.heparin_config_screen = HeparinConfigScreen(
            parent=self.window, values_dict=self.window.current_values
        )
        self.window.heparin_config_screen.request_setpoint_change.connect(self.window._write_setpoint)
        self.window.heparin_config_screen.request_boolean_change.connect(self.window._write_boolean_command)
        self.window.heparin_config_screen.valueChanged.connect(self.window.handleGlobalValueChange)
        self.window.heparin_config_screen.heparin_enabled_changed.connect(self.window.set_heparin_infusion_enabled)

        self.window.history_screen = HistoryScreen(parent=self.window)

        self.window.KTVScreen = KTVScreen(
            parent=self.window, values_dict=self.window.current_values
        )  # Pantalla de cálculo de Kt/V en tiempo real, con gráficos y todo el rollo.

        # === HISTORIAL DE PRESIÓN ARTERIAL NIBP Y RASTREADOR DE SESIÓN CLÍNICA ===
        self.window.nibp_pressure_history = NibpPressureHistory()
        self.window.nibp_history_screen = NibpHistoryScreen(
            parent=self.window, history=self.window.nibp_pressure_history
        )
        self.window.nibp_chart_screen = NibpChartScreen(
            parent=self.window, history=self.window.nibp_pressure_history
        )
        self.window.nibp_limits_screen = NibpLimitsScreen(
            parent=self.window, history=self.window.nibp_pressure_history
        )
        self.window._nibp_measure_is_manual = False  # Flag para marcar si la próxima medición es manual
        self.window._last_spo2_value = None
        self.window.session_tracker = TherapySessionTracker()
        self.window.nibp.spo2_updated.connect(self.window._on_spo2_updated_for_tracker)
        self.window.theme_config_screen = ThemeConfigScreen(parent=self.window)

        # Add all screens to stacked widget (order matters)
        self.window.screen_stack.addWidget(self.window._main_screen)                 # 0 - Home
        self.window.screen_stack.addWidget(self.window.dialysis_screen)              # 1   funciona
        self.window.screen_stack.addWidget(self.window.treatment_mode_screen)        # 2 funciona
        self.window.screen_stack.addWidget(self.window.cleaning_screen)              # 3
        self.window.screen_stack.addWidget(self.window.options_screen)               # 4
        self.window.screen_stack.addWidget(self.window.alarms_screen)                # 5
        self.window.screen_stack.addWidget(self.window.manual_mode_screen)           # 6
        self.window.screen_stack.addWidget(self.window.test_panel_screen)            # 7
        self.window.screen_stack.addWidget(self.window.calibration_screen)           # 8
        self.window.screen_stack.addWidget(self.window.network_config_screen)        # 9
        self.window.screen_stack.addWidget(self.window.real_time_var)                # 10
        self.window.screen_stack.addWidget(self.window.patient_config_screen)        # 11
        self.window.screen_stack.addWidget(self.window.therapy_config_screen)        # 12
        self.window.screen_stack.addWidget(self.window.heparin_config_screen)        # 13
        self.window.screen_stack.addWidget(self.window.conductivity_profile_screen)  # 14
        self.window.screen_stack.addWidget(self.window.uf_profile_screen)            # 14b
        self.window.screen_stack.addWidget(self.window.comm_port_screen)             # 15
        self.window.screen_stack.addWidget(self.window.maintenance_screen)           # 16
        self.window.screen_stack.addWidget(self.window.alarm_config_limits_screen)   # 17
        self.window.screen_stack.addWidget(self.window.alarm_service_screen_config)  # 18
        self.window.screen_stack.addWidget(self.window._cleanning_config_screen)     # 19
        self.window.screen_stack.addWidget(self.window.history_screen)               # 20
        self.window.screen_stack.addWidget(self.window.KTVScreen)                    # 21
        self.window.screen_stack.addWidget(self.window.nibp_screen)                  # 22
        self.window.screen_stack.addWidget(self.window.nibp_history_screen)          # 23
        self.window.screen_stack.addWidget(self.window.nibp_chart_screen)            # 23b
        self.window.screen_stack.addWidget(self.window.nibp_limits_screen)           # 23c
        self.window.screen_stack.addWidget(self.window.theme_config_screen)          # 24

        self.window.calibration_screen.valueChanged.connect(self.window.handleGlobalValueChange)
        self.window.manual_mode_screen.valueChanged.connect(self.window.handleGlobalValueChange)

    def start_shown(self):
        # self.master_timer.timeout.connect(self.KTVScreen.on_master_tick)
        self.window.ktv_controller.ktv_calculated.connect(
            self.window.KTVScreen.update_values
        )  # MODIFICADO: Para actualizar la UI de la pantalla KTV con los resultados
        self.window.ktv_controller.schedule_info_updated.connect(
            self.window.KTVScreen.update_schedule_display
        )  # MODIFICADO: Para actualizar la etiqueta de próxima medición
        self.window.ktv_controller.measurement_aborted.connect(
            lambda _reason: self.window.KTVScreen.reset_screen_data(preserve_frequency=True)
        )  # Limpiar UI si se aborta medición sin perder frecuencia seleccionada

        self.window.master_timer.timeout.connect(
            lambda: self.window.KTVScreen.update_patient_data(self.window.current_values)
        )

        self.window.comm_port_screen.emit_current_configurations()  # carga la configuracion de las puertos COM

        # Iniciar el Timer Maestro (único)
        self.window.master_timer.start()
        logger.info("Timer Maestro iniciado correctamente (intervalo 500ms)")
        QTimer.singleShot(
            800, self.window._sync_state_with_hardware
        )  # delay para sincronizar el estado de la maquina con la interfaz
        # Header update timers
        self.window.refresh_alarms_label()
        self.window.refresh_treatment_selected()
        self.window._update_treatment_mode_label_state()

        self.window.serial_comm.connect_port()
        self.window.serial_comm.start_reading()
        self.window._set_ui_connected_state(False)
        self.window.screen_stack.setCurrentIndex(self.window.INDEX_HOME)
        self.window.right_content.hide()
        self.window.left_content.hide()
        self.window.left_container.setStyleSheet("background: transparent")
        self.window.right_container.setStyleSheet("background: transparent")
        try:
            ThemeManager.instance().theme_changed.connect(self.window._apply_main_shell_theme)
            self.window._apply_main_shell_theme(ThemeManager.instance().current_theme_name)
        except Exception as e:
            logger.warning(f"No se pudo conectar ThemeManager al shell principal: {e}")
