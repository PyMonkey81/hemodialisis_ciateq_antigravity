# core/alarm_config_manager.py
from PySide6.QtCore import QSettings
from typing import List, Tuple, Dict, Set
import json

from core.variables_map import VARIABLES
import logging
logger = logging.getLogger(__name__)


class AlarmConfigManager:
    """
    Gestor central de configuración de alarmas usando QSettings.
    - enabled_tags: Qué variables están activadas para monitoreo (Servicio Técnico)
    - limits: Límite inferior y superior por tag (Operador)
    - severity: Nivel de alarma por tag (Operador)
    
    Los límites se guardan en memoria (diccionario) para evitar perder datos
    al releer QSettings.
    """
    def __init__(self, organization: str = "HemodialisisApp", app_name: str = "AlarmSystem"):
        self.settings = QSettings(organization, app_name)

        # Claves
        self.KEY_ENABLED = "alarms/enabled_tags"
        self.KEY_LIMITS = "alarms/limits"      # dict: tag -> [min, max]
        self.KEY_SEVERITY = "alarms/severity"  # dict: tag -> "cian" | "naranja" | "amarillo" | "rojo"
        
        # Diccionario en memoria para límites: tag -> [min, max]
        # Se carga una sola vez al inicializar
        self._limits_cache: Dict[str, list] = {}
        self._load_limits_from_settings()

    def _load_limits_from_settings(self):
        """Carga los límites desde QSettings (puede ser dict viejo o JSON nuevo).
        Si es diccionario, lo copia directamente.
        Si es JSON string, lo parsea.
        Si es vacío o inválido, deja el cache vacío.
        No rellena con valores del mapa."""
        try:
            raw = self.settings.value(self.KEY_LIMITS, "")
            
            if isinstance(raw, dict):
                # QSettings devolvió un diccionario (formato viejo)
                self._limits_cache = dict(raw)
            elif isinstance(raw, str) and raw.strip():
                # QSettings devolvió un string, intentar parsear JSON
                loaded = json.loads(raw)
                self._limits_cache = dict(loaded) if isinstance(loaded, dict) else {}
            else:
                # Vacío o no es dict ni string
                self._limits_cache = {}
                
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning(f"Error cargando límites de QSettings: {e}, cache vacío")
            self._limits_cache = {}

    # ====================== Métodos para obtener valores por defecto del VARIABLES_MAP ======================
    def _get_default_info_from_variables_map(self, tag: str) -> dict:
        """Helper para buscar la info de una variable en VARIABLES_MAP."""
        for group in VARIABLES.values():
            for info in group.values():
                if info.get("tag") == tag:
                    return info
        return {} # Devuelve diccionario vacío si no se encuentra

    def get_default_limits_from_variables_map(self, tag: str) -> Tuple[float, float]:
        """Devuelve los límites por defecto de VARIABLES_MAP o un fallback."""
        info = self._get_default_info_from_variables_map(tag)
        limits_from_map = info.get("limites")
        if limits_from_map and isinstance(limits_from_map, (list, tuple)) and len(limits_from_map) == 2:
            try:
                return float(limits_from_map[0]), float(limits_from_map[1])
            except ValueError:
                pass # Si los valores en el mapa no son válidos, usar fallback
        return 0.0, 100.0 # Fallback general si no hay límites en el mapa o son inválidos

    def get_default_severity_from_variables_map(self, tag: str) -> str:
        """Devuelve la severidad por defecto de VARIABLES_MAP o un fallback."""
        info = self._get_default_info_from_variables_map(tag)
        severity_from_map = info.get("nivel")
        if severity_from_map and isinstance(severity_from_map, str):
            return severity_from_map
        return "cian" # Fallback general si no hay nivel en el mapa
    
    def get_parameter_name(self, tag: str) -> str:
        """Devuelve el nombre legible del parámetro para mostrar en mensajes."""
        info = self._get_default_info_from_variables_map(tag)
        name = info.get("name", info.get("label", tag))
        unit = info.get("unit", "")
        if unit:
            return f"{name} ({unit})"
        return name
    
    # ====================== ENABLED TAGS (Servicio Técnico) ======================
    def get_enabled_tags(self) -> List[str]:
        """Devuelve lista de tags habilitados"""
        tags = self.settings.value(self.KEY_ENABLED, [])
        if isinstance(tags, str):          # Seguridad por posible bug en listas de 1 elemento en algunos sistemas
            tags = [tags]
        return tags if isinstance(tags, list) else []

    def set_enabled_tags(self, tags: List[str]):
        """Guarda la lista completa de tags habilitados"""
        self.settings.setValue(self.KEY_ENABLED, tags)
        self.settings.sync()   # Fuerza guardar inmediatamente

    def is_enabled(self, tag: str) -> bool:
        return tag in self.get_enabled_tags()

    def set_enabled(self, tag: str, enabled: bool):
        """Activa o desactiva una sola variable"""
        current = set(self.get_enabled_tags())
        if enabled:
            current.add(tag)
        else:
            current.discard(tag)
        self.set_enabled_tags(sorted(list(current)))

    # ====================== LIMITS (Operador) ======================
    def get_limits(self, tag: str) -> Tuple[float, float]:
        """Devuelve (min, max). Lee primero del diccionario en memoria.
        Si no existe en memoria → usa defaults de VARIABLES_MAP."""
        if tag in self._limits_cache:
            try:
                minv, maxv = self._limits_cache[tag]
                return float(minv), float(maxv)
            except (ValueError, TypeError):
                pass  # Si el formato es incorrecto, ignorar y usar el default
        
        return self.get_default_limits_from_variables_map(tag) 

    def set_limits(self, tag: str, min_val: float, max_val: float):
        """Guarda límites en memoria y en QSettings como JSON.
        Actualiza el diccionario en memoria, luego serializa a JSON."""
        # Actualizar el diccionario en memoria
        self._limits_cache[tag] = [float(min_val), float(max_val)]
        
        # Guardar como JSON en QSettings
        limits_json_str = json.dumps(self._limits_cache)
        self.settings.setValue(self.KEY_LIMITS, limits_json_str)
        self.settings.sync()
    # ====================== SEVERITY ======================
    def get_severity(self, tag: str) -> str:
        severity_dict_raw = self.settings.value(self.KEY_SEVERITY, {})
        # QSettings puede devolver QVariant, convertimos a dict si es necesario
        severity_dict = dict(severity_dict_raw) if isinstance(severity_dict_raw, dict) else {}
        
        return severity_dict.get(tag, self.get_default_severity_from_variables_map(tag)) # Usa el default del mapa



    def set_severity(self, tag: str, level: str):
        severity_dict_raw = self.settings.value(self.KEY_SEVERITY, {})
        # QSettings puede devolver QVariant, convertimos a dict si es necesario
        severity_dict = dict(severity_dict_raw) if isinstance(severity_dict_raw, dict) else {}

        severity_dict[tag] = level
        self.settings.setValue(self.KEY_SEVERITY, severity_dict)
        self.settings.sync()

    # ====================== UTILIDADES ======================
    
    def get_all_enabled_with_config(self) -> List[Dict]:
        """Devuelve lista de tags habilitados con sus límites y severidad actuales"""
        enabled = self.get_enabled_tags()
        result = []
        for tag in enabled:
            result.append({
                "tag": tag,
                "limits": self.get_limits(tag),
                "severity": self.get_severity(tag)
            })
        return result

    # Método para guardar explícitamente (si es necesario)
    def save_config(self):
        """Fuerza la escritura de todos los cambios pendientes a disco."""
        self.settings.sync()
