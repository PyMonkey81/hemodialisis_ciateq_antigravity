import logging

logger = logging.getLogger(__name__)


class ActiveAlarms:
    def __init__(self, window):
        self.window = window

    def handleGlobalValueChange(self, tag: str, value: float):
        self.window.current_values[tag] = value  # Actualiza el valor global
        logger.debug("[GLOBAL] Valor actualizado: %s = %s", tag, value)

        # Sincroniza cambios locales (pantallas de configuración) con alarmas.
        if self.window.alarm_system:
            self.window.alarm_system.update_value_by_tag(tag, value)

        current_widget = self.window.screen_stack.currentWidget()
        if hasattr(current_widget, "update_values"):
            current_widget.update_values(self.window.current_values)

    def update_alarm_system_monitor_config(self):
        """
        Llamado al cambiar la configuración de monitoreo en la pantalla de servicio.
        """
        logger.info("Actualizando configuración del sistema de alarmas desde HMI (Recarga Solicitada).")
        # 1. Limpieza forzada de la interfaz
        self.window.active_alarms.clear()
        if hasattr(self.window, 'alarms_screen') and self.window.alarms_screen:
            self.window.alarms_screen.reset_ui_state()

        # 2. Recargar motor de alarmas
        self.window.alarm_system.reload_configuration()

        # 3. Refrescar interfaz visual
        self.window.refresh_alarms_label()
        self.window.update_led_bar_state()

    def handle_alarm(self, idx, active, value, name, level, limits):
        found_idx = -1  # buscar si la alarma ya está en la lista de alarmas activas
        for i, (alarm_name, _, _) in enumerate(self.window.active_alarms):
            if alarm_name == name:
                found_idx = i
                break

        if active:
            if found_idx == -1:
                # Es una alarma NUEVA que se acaba de activar -> añadir
                self.window.active_alarms.append((name, value, level))
                self.window.buzzer_silenced_by_user = False  # Resetear silencio por NUEVA alarma
                if hasattr(self.window, "session_tracker"):
                    el_s = (
                        float(self.window.treatment_controller.get_elapsed_seconds())
                        if hasattr(self.window, "treatment_controller")
                        else 0.0
                    )
                    self.window.session_tracker.record_alarm(
                        f"{name} ({value:.1f})", elapsed_s=el_s, severity=level
                    )
            else:
                # La alarma ya estaba activa, solo actualizar su estado (valor/nivel)
                self.window.active_alarms[found_idx] = (name, value, level)
        else:
            if found_idx != -1:
                # La alarma se normalizó -> eliminar de la lista de activas
                self.window.active_alarms.pop(found_idx)

        # Si no quedan alarmas activas, resetear el silencio del buzzer
        if not self.window.active_alarms:
            self.window.buzzer_silenced_by_user = False

        self.window.refresh_alarms_label()
        self.window.update_led_bar_state()

    def _sync_alarm_values_from_current_state(self):
        """
        Empuja periódicamente al AlarmSystem los valores actuales para todos los
        tags de alarma habilitados. Esto desacopla el monitoreo del ritmo serial.
        """
        if not self.window.alarm_system:
            return

        for tag in self.window.alarm_system.tags:
            if tag in self.window.current_values:
                self.window.alarm_system.update_value_by_tag(tag, self.window.current_values.get(tag, 0.0))
