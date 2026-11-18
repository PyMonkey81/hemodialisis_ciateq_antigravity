import logging

from utilities.csv_logger import CsvLogger
from utilities.platform_runtime import get_runtime_data_path

logger = logging.getLogger(__name__)


class PrimingFlow:
    def __init__(self, window):
        self.window = window

    def start_priming(self):
        """
        Inicia el proceso de cebado (priming / enjuague).
        - Verifica conexión serial
        - Cierra logger anterior si existe
        - Inicia nuevo logging CSV
        - Envía comandos booleanos al controlador
        - Muestra feedback al usuario
        """
        # 1. Verificar conexión serial
        if not self.window.serial_comm or not self.window.serial_comm.is_connected:
            self.window.show_warning_message("No hay conexión serial.\nCebado no iniciado.", 3000)
            logger.warning("Intento de iniciar cebado sin conexión serial")
            return

        # 2. Cerrar logger anterior si ya existe (evita duplicados/corrupción)
        if self.window.csv_logger:
            logger.info("Cerrando logger anterior antes de nuevo cebado")
            self.window.csv_logger.close()
            self.window.csv_logger = None

        # 3. Definir directorio de logs (puedes cambiar la ruta si quieres)
        LOG_DIRECTORY = str(get_runtime_data_path("logs", "hemodialysis_cebado"))  # Se crea automáticamente si no existe

        # 4. Crear e iniciar el nuevo logger CSV
        try:
            self.window.csv_logger = CsvLogger(
                log_directory=LOG_DIRECTORY,
                parameter_key_map=self.window.parameter_mapping,
            )
            logger.info("Logger CSV iniciado correctamente para cebado")
        except Exception as e:
            logger.error(f"Error al crear logger CSV para cebado: {e}")

            self.window.show_error_message(
                f"Error crítico:\nNo se pudo iniciar el registro de datos:\n{str(e)}", 4000
            )
            return

        # 5. Enviar comandos al controlador
        try:
            self.window._write_boolean_command("dialyStartDialysisButt", True)
            self.window._write_boolean_command("dialyStopDialysisButt", False)

            logger.info("Comandos de cebado enviados: Start=True, Stop=False")
        except Exception as e:
            logger.error(f"Error enviando comandos de cebado: {e}")
            self.window.show_error_message(f"Error al enviar comandos de cebado:\n{str(e)}", 4000)

        self.window.show_success_message("Cebado iniciado", 3000)

        self.window.show_dialysis_screen()

    def stop_priming(self):
        try:
            self.window._write_boolean_command("dialyStopDialysisButt", True)
            self.window._write_boolean_command("dialyStartDialysisButt", False)

            logger.info("Comandos de cebado enviados: Start=True, Stop=False")
            self.window.show_info_message("Cebado detenido...", 3000)
        except Exception as e:
            logger.error(f"Error enviando comandos de cebado: {e}")
            self.window.show_warning_message(
                "Cebado detenido, pero hubo problema al enviar comandos al controlador.", 4000
            )

        # Cerrar logger de cebado al detener
        if self.window.csv_logger:
            self.window.csv_logger.close()
            self.window.csv_logger = None
            logger.info("Logger de cebado cerrado al detener cebado")
