import logging
from PySide6.QtCore import QDateTime, QTimer

from gui.components.floating_message import FloatingMessage

logger = logging.getLogger(__name__)


class OperatorAlerts:
    def __init__(self, window):
        self.window = window

    def begin_operator_alert(self, level: str = "warning"):
        if any(alarm_level == "rojo" for _, _, alarm_level in self.window.active_alarms):
            logger.info("Aviso de operador omitido: hay una alarma roja activa")
            return

        if self.window._operator_alert_active:
            logger.info("Aviso de operador ya activo")
            return

        command_by_level = {
            "warning": self.window.led_bar.CMD_YELLOW_FLASH,
            "error": self.window.led_bar.CMD_RED_SOLID,
            "info": self.window.led_bar.CMD_CYAN_SOLID,
        }
        cmd = command_by_level.get(level, self.window.led_bar.CMD_YELLOW_FLASH)
        self.window._operator_alert_active = True
        self.window._operator_alert_cmd = cmd
        self.window.led_bar.send_state(cmd, silence_buzzer=False)
        logger.info("Aviso de operador iniciado: %s", level)

    def end_operator_alert(self):
        if not self.window._operator_alert_active:
            return

        self.window._operator_alert_active = False
        self.window._operator_alert_cmd = None
        logger.info("Aviso de operador finalizado")
        self.window.update_led_bar_state()

    def update_led_bar_state(self):
        """Actualiza el estado de la barra LED según las alarmas activas"""
        if not hasattr(self.window, 'led_bar') or self.window.led_bar is None:
            return  # Evita error si aún no se ha creado o ya se cerró

        if any(level == "rojo" for _, _, level in self.window.active_alarms):
            self.window.led_bar.send_state(
                self.window.led_bar.CMD_RED_SOLID,
                silence_buzzer=self.window.buzzer_silenced_by_user,
            )
            return

        if getattr(self.window, "_operator_alert_active", False):
            if self.window._operator_alert_cmd:
                self.window.led_bar.send_state(self.window._operator_alert_cmd, silence_buzzer=False)
            return

        if not self.window.serial_comm or not self.window.serial_comm.is_connected:
            self.window.led_bar.send_state(self.window.led_bar.CMD_CYAN_SOLID, silence_buzzer=False)
            return

        if self.window.active_alarms:
            priority_map = {"rojo": 4, "naranja": 3, "amarillo": 2, "cian": 1}
            top_alarm = max(self.window.active_alarms, key=lambda x: priority_map.get(x[2], 0))
            level = top_alarm[2]

            if level == "rojo":
                cmd = self.window.led_bar.CMD_RED_SOLID
            elif level == "naranja":
                cmd = self.window.led_bar.CMD_YELLOW_FLASH
            elif level == "amarillo":
                cmd = self.window.led_bar.CMD_YELLOW_SOLID
            else:  # cian o default
                cmd = self.window.led_bar.CMD_CYAN_SOLID

            silence = self.window.buzzer_silenced_by_user
            self.window.led_bar.send_state(cmd, silence_buzzer=silence)
        else:
            self.window.led_bar.send_state(self.window.led_bar.CMD_GREEN_SOLID, silence_buzzer=False)

    def show_operator_message(self, text: str, level: str = "info", timeout_ms: int = 4000):
        """
        Muestra un mensaje al operador con:
        - Mensaje flotante
        - LED + Buzzer temporal
        - Restauración automática del estado de alarma (si existe)
        """
        if not self._can_show_operator_toast(text, level):
            return

        # Guardar estado actual de alarmas antes de modificar
        had_active_alarms = len(self.window.active_alarms) > 0
        previous_cmd = None

        if had_active_alarms:
            # Guardamos el comando actual de alarma para restaurarlo después
            priority_map = {"rojo": 4, "naranja": 3, "amarillo": 2, "cian": 1}
            top_alarm = max(self.window.active_alarms, key=lambda x: priority_map.get(x[2], 0))
            level_alarm = top_alarm[2]

            if level_alarm == "rojo":
                previous_cmd = self.window.led_bar.CMD_RED_SOLID
            elif level_alarm == "naranja":
                previous_cmd = self.window.led_bar.CMD_YELLOW_FLASH
            elif level_alarm == "amarillo":
                previous_cmd = self.window.led_bar.CMD_YELLOW_SOLID
            else:
                previous_cmd = self.window.led_bar.CMD_CYAN_SOLID

        # Determinar comando y estilo según el nivel del mensaje
        if level == "success":
            self._get_or_create_floating_msg().show_success_message(text, timeout_ms)
            cmd = getattr(self.window.led_bar, 'CMD_GREEN_SOLID', None)
        elif level == "warning":
            self._get_or_create_floating_msg().show_warning_message(text, timeout_ms)
            cmd = getattr(self.window.led_bar, 'CMD_YELLOW_FLASH', None)
        elif level == "error":
            self._get_or_create_floating_msg().show_error_message(text, timeout_ms)
            cmd = getattr(self.window.led_bar, 'CMD_RED_SOLID', None)
        else:  # info
            self._get_or_create_floating_msg().show_info_message(text, timeout_ms)
            cmd = getattr(self.window.led_bar, 'CMD_CYAN_SOLID', None)

        # Enviar comando al LED Bar + Buzzer activo
        if hasattr(self.window, 'led_bar') and self.window.led_bar and cmd:
            self.window.led_bar.send_state(cmd, silence_buzzer=False)

        # Restaurar estado de alarma después del timeout
        def restore_alarm_state():
            if hasattr(self.window, 'led_bar') and self.window.led_bar:
                if had_active_alarms and previous_cmd:
                    self.window.led_bar.send_state(previous_cmd, 
                                          silence_buzzer=self.window.buzzer_silenced_by_user)
                else:
                    # No había alarma → volver a verde o estado normal
                    self.window.led_bar.send_state(self.window.led_bar.CMD_GREEN_SOLID, 
                                          silence_buzzer=False)
            self.window.update_led_bar_state()  # Forzar sincronización con sistema de alarmas

        QTimer.singleShot(timeout_ms, restore_alarm_state)

    def _can_show_operator_toast(self, text: str, level: str) -> bool:
        now_ms = QDateTime.currentMSecsSinceEpoch()
        dedupe_key = f"{level}:{text}"
        if (
            getattr(self.window, "_last_operator_message_key", None) == dedupe_key
            and now_ms - getattr(self.window, "_last_operator_message_ts", 0) < 4000
        ):
            logger.debug("Toast de operador suprimido por reentrancia: %s", dedupe_key)
            return False
        self.window._last_operator_message_key = dedupe_key
        self.window._last_operator_message_ts = now_ms
        return True

    def _get_or_create_floating_msg(self) -> FloatingMessage:
        """Helper para evitar la duplicación de instanciación del widget de mensajes"""
        if not hasattr(self.window, '_floating_msg') or self.window._floating_msg is None:
            self.window._floating_msg = FloatingMessage(self.window)
        return self.window._floating_msg

    def show_floating_message(self, text: str, timeout_ms: int = 3800):
        self._get_or_create_floating_msg().show_floating_message(text, timeout_ms)

    def show_success_message(self, text: str, timeout_ms: int = 4000):
        if self._can_show_operator_toast(text, "success"):
            self._get_or_create_floating_msg().show_success_message(text, timeout_ms)

    def show_info_message(self, text: str, timeout_ms: int = 3800):
        if self._can_show_operator_toast(text, "info"):
            self._get_or_create_floating_msg().show_info_message(text, timeout_ms)

    def show_warning_message(self, text: str, timeout_ms: int = 4500):
        if self._can_show_operator_toast(text, "warning"):
            self._get_or_create_floating_msg().show_warning_message(text, timeout_ms)
    
    def show_error_message(self, text: str, timeout_ms: int = 5000):
        if self._can_show_operator_toast(text, "error"):
            self._get_or_create_floating_msg().show_error_message(text, timeout_ms)
