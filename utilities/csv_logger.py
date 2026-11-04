#utilities/csv_logger.py
"""
Clase para registrar datos de monitorización en un archivo CSV.

Esta clase facilita el registro de datos de monitorización en serie temporal,
como lecturas de sensores o variables del sistema, en un formato CSV estructurado.
Gestiona la creación del archivo, la escritura de la cabecera y la adición de
filas de datos con marcas de tiempo. Su diseño flexible permite mapear claves
internas a nombres de columnas legibles.

Características principales:
-------------------------
- **Automatización de Archivos**: Crea automáticamente el directorio de logs
  si no existe y genera nombres de archivo únicos basados en la fecha y hora
  (`YYYYMMDD_HHMMSS`) para evitar sobrescrituras.
- **Mapeo de Parámetros**: Utiliza un diccionario `parameter_key_map` para
  definir qué variables del diccionario de valores actuales se deben registrar
  y cómo se deben nombrar las columnas en el archivo CSV.
- **Registro de Tiempo Real**: Añade una marca de tiempo precisa (con milisegundos)
  a cada fila de datos, facilitando el análisis cronológico de los eventos.
- **Persistencia Inmediata**: Fuerza la escritura de los datos al disco de forma
  inmediata (`file.flush()`) después de cada registro, minimizando el riesgo
  de pérdida de datos en caso de un fallo inesperado.
- **Manejo Básico de Errores**: Incluye mensajes informativos y de error para
  problemas de apertura o escritura del archivo.

Uso:
----
1.  **Instanciación**: Crear una instancia de `CsvLogger` especificando el
    directorio donde se guardarán los logs y un diccionario de mapeo de parámetros.
2.  **Registro de Datos**: Llamar al método `log_data()` periódicamente,
    pasándole un diccionario con los valores actuales a registrar.
3.  **Cierre**: Llamar al método `close()` cuando ya no se necesite registrar
    más datos (ej. al finalizar una sesión o al cerrar la aplicación) para
    asegurar que el archivo se cierre correctamente.

Ejemplo de `parameter_key_map`:
    `{ "dialyLinePresProcessData": "Presion_Linea", "dialyTempIFProcessData": "Temperatura_EF" }`

"""

import csv
import os
from datetime import datetime
import logging
import time
logger = logging.getLogger(__name__)

import os
import csv
import logging
import threading
import queue
from datetime import datetime
from pathlib import Path
from utilities.platform_runtime import get_runtime_data_path

logger = logging.getLogger(__name__)

class CsvLogger:
    """
    Clase para registrar datos de monitorización en un archivo CSV.
    Optimizada con un hilo en segundo plano (Thread) para evitar congelamientos en la GUI.
    """
    def __init__(self, log_directory: str, parameter_key_map: dict, flush_every_rows: int = 10, flush_interval_sec: float = 1.0):
        log_dir_path = Path(log_directory)
        if not log_dir_path.is_absolute():
            log_dir_path = get_runtime_data_path(log_dir_path)
        log_dir_path.mkdir(parents=True, exist_ok=True)
        self.log_directory = str(log_dir_path)
        self.parameter_key_map = parameter_key_map
        self.flush_every_rows = max(1, int(flush_every_rows))
        self.flush_interval_sec = max(0.2, float(flush_interval_sec))

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.file_path = os.path.join(
            self.log_directory,
            f"hemodialysis_log_{timestamp_str}.csv"
        )

        self.file = None
        self.csv_writer = None
        
        # 1. Creamos una cola para comunicación segura entre hilos
        self.data_queue = queue.Queue(maxsize=2000)
        self.is_running = True
        self._rows_since_flush = 0
        self._last_flush_time = time.monotonic()
        self._dropped_rows = 0

        self._open_file_and_write_header()

        # 2. Iniciamos el hilo que se encargará exclusivamente de escribir en el disco
        self.writer_thread = threading.Thread(target=self._write_loop, daemon=True)
        self.writer_thread.start()

    def _open_file_and_write_header(self):
        try:
            self.file = open(self.file_path, 'w', newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.file)

            headers = ['Timestamp'] + list(self.parameter_key_map.values())
            self.csv_writer.writerow(headers)
            self.file.flush() # Escribimos la cabecera inmediatamente
            logger.info(f"CSV Logger: Archivo '{self.file_path}' creado.")            
        except IOError as e:            
            logger.error(f"CSV Logger Error al crear archivo: {e}")

    def log_data(self, current_values: dict):
        """
        Llamado por la interfaz gráfica. No escribe en disco, solo pone en la cola.
        """
        if not self.is_running:
            return

        try:
            row_data = [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            for cv_key in self.parameter_key_map.keys():
                value = current_values.get(cv_key, 'N/A')
                row_data.append(value)
            
            # 3. Metemos los datos en la cola sin bloquear la interfaz.
            try:
                self.data_queue.put_nowait(row_data)
            except queue.Full:
                self._dropped_rows += 1
                if self._dropped_rows % 100 == 1:
                    logger.warning("CSV Logger: cola llena, filas descartadas=%d", self._dropped_rows)
        except Exception as e:
            logger.error(f"CSV Logger Error al encolar datos: {e}")

    def _write_loop(self):
        """
        Bucle que corre en un hilo secundario. Espera datos de la cola y los escribe.
        """
        while self.is_running or not self.data_queue.empty():
            try:
                # Espera hasta 1 segundo por nuevos datos
                row_data = self.data_queue.get(timeout=1.0)

                if self.csv_writer is None or self.file is None or self.file.closed:
                    self.data_queue.task_done()
                    continue

                self.csv_writer.writerow(row_data)
                self._rows_since_flush += 1
                now = time.monotonic()
                if self._rows_since_flush >= self.flush_every_rows or (now - self._last_flush_time) >= self.flush_interval_sec:
                    self.file.flush()
                    self._rows_since_flush = 0
                    self._last_flush_time = now

                self.data_queue.task_done()
            except queue.Empty:
                # Es normal que salte por timeout si no hay datos nuevos, continúa el bucle
                continue
            except Exception as e:
                logger.error(f"CSV Logger Error en escritura en hilo: {e}")

    def close(self):
        """
        Detiene el hilo secundario y cierra el archivo limpiamente.
        """
        logger.info(f"CSV Logger: Cerrando archivo '{self.file_path}'...")
        self.is_running = False # Señal para detener el bucle

        # Esperamos a que el hilo termine de escribir los últimos datos
        if getattr(self, 'writer_thread', None) and self.writer_thread.is_alive():
            self.writer_thread.join(timeout=3.0)

        if getattr(self, 'file', None) is not None and not self.file.closed:
            try:
                self.file.flush()
            except Exception:
                pass
            try:
                self.file.close()
            except Exception:
                pass
            logger.info("CSV Logger: Archivo cerrado correctamente.")

