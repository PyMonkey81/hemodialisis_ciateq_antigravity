from utilities.platform_runtime import safe_int


class ScreenRouter:
    def __init__(self, window):
        self.window = window

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
