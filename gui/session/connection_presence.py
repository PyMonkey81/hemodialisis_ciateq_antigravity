import logging

logger = logging.getLogger(__name__)


class ConnectionPresence:
    def __init__(self, window):
        self.window = window

    def _set_ui_connected_state(self, is_connected: bool):
        """
        Manages the overall UI state based on connection status.
        Protege al usuario si está en pantallas de configuración.
        """
        # --- NUEVA LÓGICA DE PROTECCIÓN ---
        current_widget = self.window.screen_stack.currentWidget()
        # Definimos las pantallas donde NO queremos que el sistema nos saque automáticamente
        service_screens = [
            self.window.comm_port_screen,
            self.window.options_screen,
            self.window.maintenance_screen,
            self.window.network_config_screen,
            self.window.theme_config_screen,
        ]
        is_in_service_area = current_widget in service_screens
        # ----------------------------------

        if is_connected:
            logger.info("Enabling UI elements for connected state.")

            # Reaplica configuración persistida al reconectar firmware.
            self.window._apply_therapy_config_to_firmware(force=True)

            if hasattr(self.window, 'alarm_system') and self.window.alarm_system:
                self.window.alarm_system.reset()
            self.window.active_alarms.clear()

            if hasattr(self.window, 'alarms_screen') and self.window.alarms_screen:
                self.window.alarms_screen.reset_ui_state()

            self.window.refresh_treatment_selected()
            self.window._update_treatment_mode_label_state()

            # Solo mandamos al Home si NO estamos en área de servicio
            if not is_in_service_area:
                self.window.show_home_screen()
            else:
                logger.info("Manteniendo pantalla de servicio tras conexión.")

        else:  # ESTADO DESCONECTADO
            logger.warning("Disabling UI elements for disconnected state.")

            if hasattr(self.window, 'alarm_system') and self.window.alarm_system:
                self.window.alarm_system.reset()
            self.window.active_alarms.clear()

            if hasattr(self.window, 'alarms_screen') and self.window.alarms_screen:
                self.window.alarms_screen.reset_ui_state()

            self.window._update_treatment_mode_label_state()

            if not is_in_service_area:
                self.window.show_home_screen()
            else:
                logger.info("Manteniendo pantalla de servicio tras desconexión (permitiendo configuración).")
