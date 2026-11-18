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

    def update_connection_status(self):
        """
        Actualiza el estado de la conexión en la UI y maneja la habilitación/deshabilitación
        de elementos según el estado de la conexión.
        """
        current_is_connected = self.window.serial_comm and self.window.serial_comm.is_connected
        if current_is_connected != self.window._is_connected_prev_state:
            self.window._sync_state_with_hardware()
            self.window._set_ui_connected_state(current_is_connected)
            if current_is_connected:
                self.window._connection_just_established_ticks = 3
                self.window._write_pressure_limits_on_connection()

        self.window._is_connected_prev_state = current_is_connected
        current_widget = self.window.screen_stack.currentWidget()
        if hasattr(current_widget, "update_values"):
            current_widget.update_values(self.window.current_values)

        self.window.refresh_alarms_label()
        self.window.update_led_bar_state()
