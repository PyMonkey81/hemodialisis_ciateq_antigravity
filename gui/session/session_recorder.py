import json
import logging
import os
from pathlib import Path

from PySide6.QtCore import QDateTime

from utilities.csv_logger import CsvLogger
from utilities.platform_runtime import get_runtime_data_path, safe_int
from utilities.therapy_report_generator import TherapyReportGenerator

logger = logging.getLogger(__name__)


class SessionRecorder:
    def __init__(self, window):
        self.window = window

    # ====================== MÉTODOS DE LOGGING ======================

    def _prepare_log_data(self, values_dict: dict) -> dict:
        """
        Prepara los datos para logging, aplicando formato especial 
        de 8 decimales para las variables del sensor patrón.
        """
        log_data = values_dict.copy()        
        high_precision_tags = ["patternCondSensor", "patternTempSensor", "patternCondRaw"]
        
        for tag in high_precision_tags:
            if tag in log_data:
                try:
                    value = float(log_data[tag])
                    log_data[tag] = round(value, 8)
                except (ValueError, TypeError):
                    log_data[tag] = 0.0
        return log_data

    def _log_current_data(self):
        if self.window.csv_logger:
            self.window.csv_logger.log_data(self._prepare_log_data(self.window.current_values))

    def _log_treatment_current_data(self):
        if self.window.treatment_logger:
            self.window.treatment_logger.log_data(self._prepare_log_data(self.window.current_values))

    def _start_cleaning_logger(self):
        """Inicia el logger CSV para sesión de limpieza"""
        if self.window.cleaning_logger:
            self.window.cleaning_logger.close()
        try:
            self.window.cleaning_logger = CsvLogger(
                log_directory=str(get_runtime_data_path("logs", "limpieza")),
                parameter_key_map=self.window.parameter_mapping
            )
            logger.info("Logger CSV de Limpieza iniciado")
        except Exception as e:
            logger.error(f"Error al inicializar sesión de logger para limpieza: {e}")
            self.window.cleaning_logger = None

    def _stop_cleaning_logger(self):
        if self.window.cleaning_logger:
            try:
                self.window.cleaning_logger.close()
                logger.info("Logger CSV de Limpieza cerrado exitosamente")
            except Exception as e:
                logger.error(f"Error al cerrar archivo logger de limpieza: {e}")
            self.window.cleaning_logger = None

    def _log_cleaning_current_data(self):
        if self.window.cleaning_logger:
            self.window.cleaning_logger.log_data(self._prepare_log_data(self.window.current_values))

    # ====================== HISTORIAL DE SESIONES ======================

    def _load_histories(self):
        """Carga los historiales desde JSON al iniciar"""
        historiales_dir = get_runtime_data_path("logs", "Historiales")
        historiales_dir.mkdir(parents=True, exist_ok=True)
        tratamientos_path = get_runtime_data_path("logs", "Historiales", "historial_tratamientos.json")
        limpieza_path = get_runtime_data_path("logs", "Historiales", "historial_limpieza.json")
        
        try:
            with open(tratamientos_path, 'r', encoding='utf-8') as f:
                self.window.treatment_history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.window.treatment_history = []
            
        try:
            with open(limpieza_path, 'r', encoding='utf-8') as f:
                self.window.cleaning_history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.window.cleaning_history = []

    def _save_history_to_file(self, file_path: str | Path, history_data: list, label: str):
        try:
            target_path = Path(file_path)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error escribiendo {label}: {e}")

    def _save_treatment_history(self):
        self._save_history_to_file(
            get_runtime_data_path("logs", "Historiales", "historial_tratamientos.json"),
            self.window.treatment_history,
            "historial_tratamientos",
        )

    def _save_cleaning_history(self):
        self._save_history_to_file(
            get_runtime_data_path("logs", "Historiales", "historial_limpieza.json"),
            self.window.cleaning_history,
            "historial_limpieza",
        )

    def _validate_session(self, start_time: QDateTime, end_time: QDateTime) -> bool:
        """Valida que la sesión sea lógica y no duplicada"""
        if start_time is None or end_time is None:
            logger.warning("Intento de registrar sesión sin tiempo de inicio o fin")
            return False

        if end_time < start_time:
            logger.error("Error: Hora de fin es anterior a hora de inicio")
            return False

        duration_seconds = start_time.secsTo(end_time)
        if duration_seconds < 60:  # Menos de 1 minuto
            logger.warning(f"Sesión muy corta ({duration_seconds} segundos). No se registrará.")
            return False

        return True

    def register_treatment_session(self):
        """Registra una sesión completa de tratamiento con validación"""
        if not self.window.current_treatment_start:
            return

        end_time = QDateTime.currentDateTime()
        
        # Validación de fechas
        if not self._validate_session(self.window.current_treatment_start, end_time):
            self.window.current_treatment_start = None
            logger.debug("Sesión de tratamiento descartada por validación")
            return

        duration_seconds = self.window.current_treatment_start.secsTo(end_time)
        # Preferir tiempo real activo de terapia (excluye pausas) si está disponible
        if hasattr(self.window, 'treatment_controller'):
            elapsed = self.window.treatment_controller.get_elapsed_seconds()
            if elapsed > 0:
                duration_seconds = elapsed
        duration_minutes = round(duration_seconds / 60)
        
        # Construir y respaldar el Reporte Clínico Integral (PDF + JSON + CSV)
        report_bundle = {}
        report_data = {}
        try:
            report_data = self.window.build_current_clinical_report(
                completion_status="Completada",
                start_time_str=self.window.current_treatment_start.toString("HH:mm:ss"),
                end_time_str=end_time.toString("HH:mm:ss"),
                override_elapsed_s=float(duration_seconds),
            )
            report_bundle = TherapyReportGenerator.save_session_report_bundle(report_data)
        except Exception as e:
            logger.error(f"Error guardando bundle de reporte clínico: {e}")

        p_info = report_data.get("patient", {}) if isinstance(report_data, dict) else {}
        rx_info = report_data.get("prescription", {}) if isinstance(report_data, dict) else {}
        ad_info = report_data.get("adequacy", {}) if isinstance(report_data, dict) else {}
        hemo_info = report_data.get("hemodynamics", {}) if isinstance(report_data, dict) else {}

        record = {
            "fecha": self.window.current_treatment_start.toString("yyyy-MM-dd"),
            "hora_inicio": self.window.current_treatment_start.toString("HH:mm:ss"),
            "hora_fin": end_time.toString("HH:mm:ss"),
            "patient_id": p_info.get("id", self.window.current_values.get("patient_id", "S/ID")),
            "paciente": p_info.get("name", self.window.current_values.get("patient_name", "Sin registrar")),
            "tipo_tratamiento": rx_info.get(
                "modality",
                self.window._treatment_map.get(int(self.window.current_values.get("treatmentModeSelection", 0)), "Hemodiálisis")
            ),
            "duracion_minutos": duration_minutes,
            "duracion_hhmm": f"{duration_minutes//60:02d}:{duration_minutes%60:02d}",
            "uf_meta_l": rx_info.get("uf_goal_liters", 0.0),
            "uf_lograda_l": rx_info.get("uf_achieved_liters", 0.0),
            "ktv_final": ad_info.get("ktv_final", 0.0),
            "sangre_procesada_l": ad_info.get("blood_processed_liters", 0.0),
            "pa_final": hemo_info.get("pa_final", "—"),
            "report_id": report_bundle.get("report_id", ""),
            "report_pdf_path": report_bundle.get("pdf_path", ""),
            "report_json_path": report_bundle.get("json_path", ""),
            "report_csv_path": report_bundle.get("csv_path", ""),
            "timestamp_registro": QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        }
        
        # Evitar duplicados cercanos (últimos 5 minutos)
        if self.window.treatment_history:
            last = self.window.treatment_history[-1]
            if last["fecha"] == record["fecha"] and last["hora_inicio"] == record["hora_inicio"]:
                logger.info("Sesión de tratamiento ya guardada de forma síncrona.")
                self.window.current_treatment_start = None
                return

        self.window.treatment_history.append(record)
        self._save_treatment_history()
        
        logger.info(f"✅ Tratamiento registrado: {record['fecha']} {record['hora_inicio']} ({record['duracion_hhmm']})")
        self.window.current_treatment_start = None

    def finish_cleaning_session(self, active_duration_seconds: float):
        """Método centralizado para finalizar limpieza con duración real"""
        logger.info(f"[CLEANING] Finalizando sesión con duración real: {active_duration_seconds:.1f} segundos")

        # *** CAMBIO CLAVE AQUÍ ***
        # Estas líneas se ELIMINAN porque TimerManager.on_cleaning_stopped_counting
        # ya ha procesado y acumulado esta duración cuando la señal
        # cleaning_stopped_counting fue emitida por CleaningScreen.
        # self.timer_manager.cleaning_hours += active_duration_seconds / 3600.0
        # self.timer_manager._save_cleaning_hours()
        logger.debug("Acumulación de cleaning_hours gestionada por TimerManager a través de señales.")
        # *** FIN CAMBIO CLAVE ***

        # Registrar en historial (esto sí es el propósito de este método)
        self.register_cleaning_session_with_duration(active_duration_seconds)

        self._stop_cleaning_logger()
        self.window.cleaning_start_time = None 

    def register_cleaning_session_with_duration(self, duration_seconds: float):
        """Registra sesión de limpieza usando duración real (no wall time)"""
        # ... (este método se mantiene igual)
        if duration_seconds < 1: # Un segundo mínimo para que el historial sea relevante
            logger.warning(f"Sesión de limpieza muy corta ({duration_seconds:.0f}s). No se registra en historial.")
            return

        duration_minutes = round(duration_seconds / 60)
        
        record = {
            "fecha": QDateTime.currentDateTime().toString("yyyy-MM-dd"),
            "hora_inicio": self.window.cleaning_start_time.toString("HH:mm:ss") if self.window.cleaning_start_time else "--:--",
            "hora_fin": QDateTime.currentDateTime().toString("HH:mm:ss"),
            "tipo_tratamiento": "Limpieza",
            "duracion_minutos": duration_minutes,
            "duracion_hhmm": f"{duration_minutes//60:02d}:{duration_minutes%60:02d}",
            "timestamp_registro": QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        }
        self.window.cleaning_start_time = None 
        self.window.cleaning_history.append(record)
        self._save_cleaning_history()

        logger.info(f"✅ Limpieza registrada en historial: {duration_minutes} minutos (duración real).")

    def register_cleaning_session(self):
        """Registra una sesión completa de limpieza"""
        if not self.window.cleaning_start_time:        # ← Cambiado a cleaning_start_time
            logger.warning("No hay sesión de limpieza activa para registrar.")
            return

        end_time = QDateTime.currentDateTime()
        
        if not self._validate_session(self.window.cleaning_start_time, end_time):
            self.window.cleaning_start_time = None
            return

        duration_seconds = self.window.cleaning_start_time.secsTo(end_time)
        duration_minutes = round(duration_seconds / 60)
        
        record = {
            "fecha": self.window.cleaning_start_time.toString("yyyy-MM-dd"),
            "hora_inicio": self.window.cleaning_start_time.toString("HH:mm:ss"),
            "hora_fin": end_time.toString("HH:mm:ss"),
            "tipo_tratamiento": "Limpieza",
            "duracion_minutos": duration_minutes,
            "duracion_hhmm": f"{duration_minutes//60:02d}:{duration_minutes%60:02d}",
            "timestamp_registro": QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        }
        
        # Evitar duplicados
        if self.window.cleaning_history:
            last = self.window.cleaning_history[-1]
            if last["fecha"] == record["fecha"] and last["hora_inicio"] == record["hora_inicio"]:
                logger.info("Sesión de limpieza duplicada ignorada.")
                self.window.cleaning_start_time = None
                return
        self.window.cleaning_history.append(record)
        self._save_cleaning_history()
        
        logger.info(f"✅ Limpieza registrada: {record['fecha']} {record['hora_inicio']} ({record['duracion_hhmm']})")

    # ====================== CIERRE ABRUPTO ======================

    def _get_clean_close_path(self) -> Path:
        custom_path = getattr(self.window, "_clean_close_file", None) or getattr(self, "clean_close_file", None)
        if custom_path is not None:
            return Path(custom_path)
        if os.environ.get("CIATEQ_DATA_DIR", "").strip():
            return get_runtime_data_path("cierre_limpio")
        cwd_file = Path("cierre_limpio")
        runtime_file = get_runtime_data_path("cierre_limpio")
        if cwd_file.exists():
            return cwd_file
        if Path.cwd().resolve() != runtime_file.parent.resolve():
            return cwd_file
        return runtime_file

    def mark_clean(self):
        try:
            clean_file = self._get_clean_close_path()
            clean_file.parent.mkdir(parents=True, exist_ok=True)
            clean_file.write_text("ok", encoding="utf-8")
        except Exception as e:
            logger.error(f"Error escribiendo archivo cierre_limpio: {e}")

    def _check_and_handle_unclean_close(self):
        if getattr(self.window, "_checked_unclean_close", False):
            return

        if not getattr(self.window, "serial_comm", None) or not self.window.serial_comm.is_connected:
            return

        status_code = safe_int(self.window.current_values.get("primingProcessStatus", 0), 0)
        if not (1 <= status_code <= 16):
            return

        self.window._checked_unclean_close = True
        clean_file = self._get_clean_close_path()

        if clean_file.exists():
            try:
                clean_file.unlink()
            except Exception as e:
                logger.error(f"Error borrando archivo cierre_limpio: {e}")
            return

        treatment_mode = safe_int(self.window.current_values.get("treatmentModeSelection", 0), 0)
        try:
            has_process_running = False
            if status_code in (14, 15) and treatment_mode != 3:
                has_process_running = True
                logger.warning(
                    f"Cierre no limpio detectado con terapia en progreso: primingProcessStatus={status_code}"
                )


            elif treatment_mode == 3 and status_code == 6:
                has_process_running = True
                logger.warning(
                    f"Cierre no limpio detectado con limpieza en progreso: treatmentModeSelection={treatment_mode}, primingProcessStatus={status_code}"
                )

            if has_process_running:
                msg = "La aplicación no cerró de forma limpia. Hay un proceso en curso y no se detuvo."
                logger.warning(f"Aviso: {msg}")
                self.window.show_operator_message(msg)
            else:
                logger.info(
                    f"Cierre no limpio detectado pero no hay proceso en curso (primingStatus={status_code}, mode={treatment_mode})"
                )
        except Exception as e:
            logger.error(f"Error manejando cierre abrupto: {e}")
