from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QPushButton

from core.state_manager import TreatmentPhase
from core.variables_map import VARIABLES
from gui.theme_manager import ThemeManager
from utilities.platform_runtime import safe_float, safe_int


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

        for lbl_attr in ("treatment_mode_selected", "remaining_time_display", "date_time_label"):
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

    def _get_current_screen_nav_text(self) -> str:
        """Devuelve el texto del botón de navegación correspondiente a la pantalla actual."""
        current = self.window.screen_stack.currentWidget()

        mapping = {
            self.window._main_screen: "Inicio",
            self.window.dialysis_screen: "Resumen\nTerapia",
            self.window.treatment_mode_screen: "Tipo de\nTratamiento",
            self.window.cleaning_screen: "Limpieza",
            self.window.options_screen: "Servicio",
            self.window.alarms_screen: "Alarmas",
            self.window.history_screen: "Historial",
            self.window.KTVScreen: "Resumen\nTerapia",                    # ← Importante
            self.window.patient_config_screen: "Resumen\nTerapia",
            self.window.therapy_config_screen: "Resumen\nTerapia",
            self.window.conductivity_profile_screen: "Resumen\nTerapia",
            self.window.uf_profile_screen: "Resumen\nTerapia",
            self.window.heparin_config_screen: "Resumen\nTerapia",
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
            elif text in ["Inicio", "Resumen\nTerapia", "Tipo de\nTratamiento",
                          "Limpieza", "Servicio", "Alarmas", "Historial"]:
                # Solo restauramos estilo si el botón está habilitado
                if btn.isEnabled():
                    btn.setStyleSheet(self.window.BTN_ENABLED_DEFAULT_STYLE)

    def _refresh_navigation_bar(self):
        """Lógica centralizada y clara según especificación del usuario"""
        if not self.window.serial_comm or not self.window.serial_comm.is_connected:
            self.window._handle_disconnected_state()
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

            elif text == "Resumen\nTerapia":
                enabled = phase not in (TreatmentPhase.CLEANING,)

            elif text == "Limpieza":
                enabled = (treatment_mode == 3)

            elif text == "Tipo de\nTratamiento":
                enabled = phase in (TreatmentPhase.IDLE, TreatmentPhase.PREPARING)

            elif text == "Inicio":
                enabled = phase in (TreatmentPhase.IDLE, TreatmentPhase.PREPARING)

            elif text == "Iniciar\nTratamiento":
                enabled = phase in (TreatmentPhase.READY, TreatmentPhase.PAUSED)

            # ==================== RESTRICCIONES POR ESTADO ====================
            if phase == TreatmentPhase.CLEANING:
                enabled = text in ["Limpieza", "Alarmas", "Historial", "Servicio"]

            elif phase == TreatmentPhase.RUNNING:
                enabled = text in ["Resumen\nTerapia", "Alarmas", "Historial"]

            elif phase == TreatmentPhase.PAUSED:
                enabled = text in ["Resumen\nTerapia", "Iniciar\nTratamiento", "Servicio",
                             "Alarmas", "Historial"]

            elif phase == TreatmentPhase.READY:
                enabled = text in ["Resumen\nTerapia", "Iniciar\nTratamiento", "Servicio",
                             "Alarmas", "Historial"]
                if text == "Iniciar\nTratamiento":
                    # enabled = temp_ok and cond_ok
                    enabled = self.window._can_start_treatment()
                # Deshabilitamos explícitamente estos
                if text in ["Inicio", "Tipo de\nTratamiento", "Limpieza"]:
                    enabled = False

            elif phase == TreatmentPhase.PREPARING:
                status = int(self.window.current_values.get("primingProcessStatus", 0))
                if self.window.hardware_mapper.is_preparing(status):
                    # Durante cebado normal
                    enabled = text in ["Resumen\nTerapia", "Alarmas", "Historial", "Servicio"]
                else:
                    # Cuando se detiene el priming
                    enabled = True

            elif phase == TreatmentPhase.IDLE:
                enabled = text in ["Resumen\nTerapia", "Tipo de\nTratamiento", "Inicio",
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
            btn.setEnabled(True)
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
        self.window.treatment_mode_selected.setStyleSheet(
            self.window._build_header_label_style("#1d4ed8", is_process=False)
        )

    def update_remaining_time_header(self, remaining_str: str):
        if hasattr(self.window, "remaining_time_display") and self.window.remaining_time_display:
            self.window.remaining_time_display.setText(
                "<div style='text-align:center;'>"
                "<span style='font-size:25px;'>T. RESTANTE</span><br>"
                f"<span style='font-size:32px;'>{remaining_str}</span>"
                "</div>"
            )
