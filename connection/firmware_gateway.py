import json
import logging

from core.variables_map import TAG_TO_ADDRESS, VARIABLES
from logic.calculos import (
    convertir_ciclos_a_flujo,
    convertir_flujo_a_ciclos,
    convertir_litros_h_a_ml_min,
    convertir_ml_min_a_litros_h,
)
from utilities.platform_runtime import get_runtime_config_path

logger = logging.getLogger(__name__)

THERAPY_CONFIG_PATH = get_runtime_config_path("therapy_config.json")
THERAPY_LOCAL_TAGS = {
    "heparineTherapyHours",
    "heparineTherapyMinutes",
    "heparineInfusionEnabled",
}
THERAPY_FIRMWARE_TAGS = {
    "heparineBolusQuantity",      # Vol. bolo heparina
    # "dialyHeparineBolusFlow",     # Flujo heparina 
    "heparineTherapyDosage",      # Dosis heparina
    "heparineAutoStopHours",      # Paro heparina (hh:mm)
    "heparineAutoStopMinutes",
    "dialyCondControlSetPoint",   # Conductividad
    "dialyTempControlSetPoint",   # Temperatura
    "balanceChamberSetTiming",    # Flujo dializante (UI en ml/min)
    "bloodFlowControlSetPoint",   # Flujo de sangre
    "ultraFilterPumpSpeed",       # Flujo UF (UI en L/h)
}
HEPARIN_DOSE_FIRMWARE_TAGS = {
    "heparineBolusQuantity",
    "heparineTherapyDosage",
    "heparineAutoStopHours",
    "heparineAutoStopMinutes",
}


class FirmwareGateway:
    def __init__(self, window):
        self.window = window

    def _write_setpoint(self, tag: str, value: float):
        if not self.window.serial_comm or not self.window.serial_comm.is_connected:
            logger.warning(f"No se puede escribir setpoint '{tag}': serial desconectado")
            return

        try:
            group, address = self._resolve_tag(tag)

            if group is None or address is None:
                logger.error(f"Tag double '{tag}' no encontrado en VARIABLES")
                return

            if not VARIABLES[group][address].get("rw", False):
                logger.warning(f"Tag '{tag}' es de solo lectura")
                return

            self.window.serial_comm.write_double(group, address, value)

            # Persistir en unidades de UI para mantener consistencia visual/configuración.
            persist_value = float(value)
            if tag == "balanceChamberSetTiming":
                persist_value = float(convertir_ciclos_a_flujo(value))
            elif tag == "ultraFilterPumpSpeed":
                persist_value = float(convertir_ml_min_a_litros_h(value))

            self._persist_therapy_config_tag(tag, persist_value)
            logger.info(f"SETPOINT [DBL]: {tag} = {value} (G:{hex(group)}, ID:{address})")

        except Exception as e:
            logger.error(f"Error escribiendo setpoint '{tag}': {e}")

    def _build_therapy_config_payload(self) -> dict:
        local_cfg = {
            tag: float(self.window.current_values.get(tag, 0.0) or 0.0)
            for tag in sorted(THERAPY_LOCAL_TAGS)
        }
        firmware_cfg = {
            tag: float(self.window.current_values.get(tag, 0.0) or 0.0)
            for tag in sorted(THERAPY_FIRMWARE_TAGS)
        }
        return {
            "schema_version": 1,
            "local": local_cfg,
            "firmware": firmware_cfg,
        }

    def _save_therapy_config_json(self):
        try:
            payload = self._build_therapy_config_payload()
            THERAPY_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            THERAPY_CONFIG_PATH.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("No se pudo guardar config de terapia JSON: %s", exc)

    def _persist_therapy_config_tag(self, tag: str, value: float):
        if tag not in THERAPY_LOCAL_TAGS and tag not in THERAPY_FIRMWARE_TAGS:
            return
        self.window.current_values[tag] = float(value)
        self._save_therapy_config_json()

    def _load_therapy_config_json(self):
        payload = None
        try:
            if THERAPY_CONFIG_PATH.exists():
                payload = json.loads(THERAPY_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("No se pudo leer %s: %s", THERAPY_CONFIG_PATH, exc)

        if not isinstance(payload, dict):
            # Crea el archivo con el estado actual (defaults) si no existe o está corrupto.
            self._save_therapy_config_json()
            self.window._therapy_config_loaded = True
            return

        local_cfg = payload.get("local", {}) if isinstance(payload.get("local"), dict) else {}
        firmware_cfg = payload.get("firmware", {}) if isinstance(payload.get("firmware"), dict) else {}

        for tag in THERAPY_LOCAL_TAGS:
            if tag in local_cfg:
                self.window.current_values[tag] = float(local_cfg[tag] or 0.0)

        for tag in THERAPY_FIRMWARE_TAGS:
            if tag in firmware_cfg:
                self.window.current_values[tag] = float(firmware_cfg[tag] or 0.0)

        self.window._therapy_config_loaded = True
        logger.info("Configuración de terapia cargada desde %s", THERAPY_CONFIG_PATH)

    def _to_firmware_setpoint_value(self, tag: str, user_value: float) -> float:
        """Convierte valor persistido (UI) al formato esperado por firmware."""
        if tag == "balanceChamberSetTiming":
            return float(convertir_flujo_a_ciclos(user_value))
        if tag == "ultraFilterPumpSpeed":
            return float(convertir_litros_h_a_ml_min(user_value))
        return float(user_value)

    def _apply_therapy_config_to_firmware(self, force: bool = False):
        if not self.window._therapy_config_loaded:
            return

        if self.window._therapy_config_applied_to_firmware and not force:
            return

        if not self.window.serial_comm or not self.window.serial_comm.is_connected:
            return

        heparin_enabled = bool(self.window.current_values.get("heparineInfusionEnabled", 1.0))
        for tag in sorted(THERAPY_FIRMWARE_TAGS):
            if not heparin_enabled and tag in HEPARIN_DOSE_FIRMWARE_TAGS:
                continue
            try:
                value = float(self.window.current_values.get(tag, 0.0) or 0.0)
                fw_value = self._to_firmware_setpoint_value(tag, value)
                self.window._write_setpoint(tag, fw_value)
            except Exception as exc:
                logger.warning("No se pudo aplicar setpoint de terapia %s: %s", tag, exc)

        self.window._therapy_config_applied_to_firmware = True
        logger.info("Configuración de terapia aplicada al firmware")

    def _write_boolean_command(self, tag: str, state: bool):
        if not self.window.serial_comm or not self.window.serial_comm.is_connected:
            logger.warning(f"No serial connection for boolean command: {tag}")
            return

        try:
            _, address = self._resolve_tag(tag)  # group no se usa en boolean

            if address is None:
                logger.error(f"Tag booleano '{tag}' no encontrado")
                return

            self.window.serial_comm.write_boolean(address, state)
            logger.info(f"COMANDO [BOOL]: {tag} = {state} (Addr: {address})")

        except Exception as e:
            logger.error(f"Error en write_boolean_command '{tag}': {e}")

    def _emit_pressure_alarm_limits(self, art_min, art_max, ven_min, ven_max, ptm_min, ptm_max):
        """Escribe los 6 límites de presión al dispositivo via write_double.
        art_min/max: límites arteriales
        ven_min/max: límites venosos
        ptm_min/max: límites de presión transmembrana (None si no está en pantalla)
        """
        pares = (
            ("artPresCircAlarmLoLimData", art_min),
            ("artPresCircAlarmHiLimData", art_max),
            ("venPresCircAlarmLoLimData", ven_min),
            ("venPresCircAlarmHiLimData", ven_max),
            ("membPressAlarmLoLimData", ptm_min),
            ("membPressAlarmHiLimData", ptm_max),
        )
        if not self.window.serial_comm or not self.window.serial_comm.is_connected:
            logger.warning("ALARMAS NO ENVIADAS: serial del control desconectado")
            return
        for tag, value in pares:
            if value is None:
                logger.info("OMITO alarma %s: valor None (fila no en pantalla)", tag)
                continue
            group, address = self._resolve_tag(tag)
            if group is None or address is None:
                logger.error("Tag de alarma no está en el mapa: %s", tag)
                continue
            self.window.serial_comm.write_double(group, address, float(value))
            logger.info("ESCRIBO alarma %s grupo %s id %s = %s", tag, hex(group), address, value)

    def _write_pressure_limits_on_connection(self):
        """Escribe límites de presión al conectar leyendo SOLO del cache.
        Si una fila no está guardada, NO la escribe."""
        if not self.window.serial_comm or not self.window.serial_comm.is_connected:
            return

        try:
            cache = self.window.config_manager._limits_cache

            if not cache:
                logger.info("Cache vacío: no hay límites guardados para escribir al conectar")
                return

            art_min, art_max = cache.get("bloodArteryPressureData", (None, None))
            ven_min, ven_max = cache.get("bloodVenousPressureData", (None, None))
            ptm_min, ptm_max = cache.get("CALC_PTM", (None, None))
            self._emit_pressure_alarm_limits(art_min, art_max, ven_min, ven_max, ptm_min, ptm_max)
        except Exception as e:
            logger.warning(f"Error escribiendo límites de presión al conectar: {e}")

    def _resolve_tag(self, tag: str) -> tuple[int | None, int | None]:
        """
        Resuelve un tag a (group, address) usando el mapa inverso.
        Mucho más rápido y limpio.
        """
        if not isinstance(getattr(self.window, '_tags_cache', None), dict):
            self.window._tags_cache = {}

        if tag in self.window._tags_cache:
            return self.window._tags_cache[tag]
        result = TAG_TO_ADDRESS.get(tag, (None, None))
        self.window._tags_cache[tag] = result
        return result
