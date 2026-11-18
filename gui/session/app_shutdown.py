import logging

from PySide6.QtWidgets import QApplication

from gui.components.floating_confirm import FloatingConfirmDialog

logger = logging.getLogger(__name__)


class AppShutdown:
    def __init__(self, window):
        self.window = window

    def on_del(self):
        logger.error("[INFO] Destructor called   stopping threads...")
        try:
            self.window.shutdown()
        except RuntimeError:
            # En destruccion de Qt, algunos objetos C++ ya no existen.
            pass
        except Exception as e:
            logger.error(f"[ERROR] shutdown() during __del__ failed: {e}")

    def shutdown(self):
        """Detención de hilos de comunicación de hardware con logs corregidos."""
        if getattr(self.window, "_shutdown_done", False) or getattr(self.window, "_shutting_down", False):
            return

        self.window._shutting_down = True
        logger.info("[INFO] Iniciando secuencia de apagado controlado de periféricos.")
        timer = getattr(self.window, 'master_timer', None)
        if timer is not None:
            try:
                if timer.isActive():
                    timer.stop()
                    logger.info("Timer Maestro detenido correctamente")
            except RuntimeError:
                logger.info("Timer Maestro ya destruido por Qt; se omite stop().")

        # SOLO GUARDAR
        timer_manager = getattr(self.window, 'timer_manager', None)
        if timer_manager is not None:
            try:
                timer_manager._save_power_on_hours()
                timer_manager._save_operation_hours()
                timer_manager._save_cleaning_hours()
            except Exception as e:
                logger.warning(f"[WARN] No se pudieron guardar horas del TimerManager durante shutdown: {e}")

        # Stop alarm system
        if hasattr(self.window, 'alarm_system') and self.window.alarm_system:
            try:
                self.window.alarm_system.stop()
            except Exception as e:
                logger.error(f"[ERROR] Failed to stop alarm system cleanly: {e}")
            self.window.alarm_system = None

        # Stop serial communication
        if hasattr(self.window, 'serial_comm') and self.window.serial_comm:
            try:
                self.window.serial_comm.stop()
            except Exception as e:
                logger.error(f"[ERROR] Failed to stop serial communication: {e}")
            self.window.serial_comm = None

        if hasattr(self.window, 'nibp') and self.window.nibp:
            try:
                self.window.nibp.stop()
            except Exception as e:
                logger.error(f"[ERROR] Failed to stop NIBP communication: {e}")
            self.window.nibp = None

        if hasattr(self.window, 'led_bar') and self.window.led_bar:
            try:
                self.window.led_bar.send_state(self.window.led_bar.CMD_OFF, silence_buzzer=True)
                # time.sleep(0.1)
                self.window.led_bar.stop()
            except Exception as e:
                logger.error(f"Error stopping LED bar: {e}")

        if hasattr(self.window, 'bioz_urea_controller') and self.window.bioz_urea_controller:
            try:
                self.window.bioz_urea_controller.stop()
            except Exception as e:
                logger.error(f"Error deteniendo el controlador de BioZ/Urea: {e}")

        if hasattr(self.window, 'pattern_sensor') and self.window.pattern_sensor:
            try:
                self.window.pattern_sensor.stop()
            except Exception as e:
                logger.error(f"Error deteniendo sensor patrón: {e}")

        if hasattr(self.window, 'mega_cond_sensor') and self.window.mega_cond_sensor:
            try:
                self.window.mega_cond_sensor.stop()
            except Exception as e:
                logger.error(f"Error deteniendo sensor Mega: {e}")

        logger.info("[INFO] Secuencia de apagado completo finalizada.")
        self.window._shutdown_done = True
        self.window._shutting_down = False

    def _show_exit_confirmation(self):
        """Muestra diálogo de confirmación para salir de la aplicación."""
        dialog = FloatingConfirmDialog(self.window)
        mensaje = "¿Desea salir de la aplicación?"
        reply = dialog.show_confirm(mensaje, accept_text="Sí", cancel_text="No")
        if reply:
            self.window.closeEvent(None)

    def closeEvent(self, event):
        self.window.end_dialysis_session()  # Cierra los loggers
        logger.error("[INFO] closeEvent → performing shutdown...")
        self.window.shutdown()  # shutdown ya guarda las horas
        self.window.unclean_close.mark_clean()
        # time.sleep(1.0)
        if event:
            event.accept()
        QApplication.quit()
