# core/alarms.py


import threading
import time
from typing import List, Tuple, Optional

from PySide6.QtCore import QObject, Signal

from core.alarm_config_manager import AlarmConfigManager
import logging
logger = logging.getLogger(__name__)


try:
    from core.variables_map import VARIABLES
except ImportError:
    VARIABLES = {0x01: {}, 0x02: {}}


class AlarmSystem(QObject):
    """
    Sistema de Monitorización y Gestión de Alarmas.
    Ahora usa AlarmConfigManager (QSettings) para obtener solo las variables habilitadas
    por el Servicio Técnico.
    """

    alarm_changed = Signal(int, bool, float, str, str, object)   # index, is_active, value, name, level, limits
    new_event = Signal(str, float, str)                         # message, value, timestamp

    def __init__(
        self,
        config_manager: Optional[AlarmConfigManager] = None,
        parent=None
    ):
        super().__init__(parent)

        self.config_manager = config_manager or AlarmConfigManager()

        # Atributos para la configuración de alarmas
        self.tags: List[str] = []
        self.display_names: List[str] = []
        self.types: List[str] = []              # "double" o "bool"
        self.boolean_triggers: List[bool] = []  # True = alarm on value != 0, False = alarm on value == 0
        self.severity_levels: List[str] = []
        self.previous_emitted_levels: List[str] = []
        self.alarm_count = 0

        # Atributos para el estado en tiempo de ejecución
        self.current_values: List[float] = []
        self.previous_states: List[bool] = []
        self.event_history: List[Tuple[str, float, str]] = []

        self.lock = threading.Lock()
        self.monitor_thread: Optional[threading.Thread] = None
        self.running = False

        # Cargar la configuración inicial
        self._rebuild_internal_config()
        if self.alarm_count == 0:
            logger.warning("AlarmSystem: No hay variables de alarma habilitadas al inicio.")

    def _find_variable_info(self, tag: str) -> dict:
        """Busca información de una variable en el mapa VARIABLES"""
        for group in VARIABLES.values():
            for info in group.values():
                if info.get("tag") == tag:
                    return info
        # Fallback si no se encuentra
        return {"name": tag, "type": "numeric", "boolean_trigger": True} # Default si no está en VARIABLES

    def _rebuild_internal_config(self):
        """
        Reconstruye la configuración interna del AlarmSystem a partir del config_manager y VARIABLES_MAP.
        Esto se llama en __init__ y en reload_configuration.
        """
        new_tags = self.config_manager.get_enabled_tags()
        
        self.tags = new_tags
        self.alarm_count = len(self.tags)

        self.display_names = []
        self.types = []
        self.boolean_triggers = []
        self.severity_levels = []

        for tag in self.tags:
            info = self._find_variable_info(tag)

            self.display_names.append(info.get("name", tag))
            
            var_type_from_map = info.get("type", "double") # Asumir 'double' si no se especifica.
            self.types.append(var_type_from_map)
            
            # Lógica para boolean_triggers: si es tipo 'bool', trigger es True (activa en 1.0) por defecto.
            # Puedes añadir un campo 'boolean_active_on_false' en VARIABLES_MAP si necesitas invertir esto.
            if var_type_from_map == "bool":
                # Caso especial: dialyWaterTankFull se activa cuando el tanque NO está lleno (valor == 0.0)
                if tag == "dialyWaterTankFull":
                    self.boolean_triggers.append(False) # Activa si valor == 0.0 (tanque vacío/falta de agua)
                else:
                    self.boolean_triggers.append(True) # Activa si valor != 0.0 (es decir, 1.0)
            else:
                self.boolean_triggers.append(False) # No se usa para numéricas, es un placeholder.
            
            # La severidad siempre se obtiene del config_manager (que ya usa defaults de VARIABLES_MAP)
            self.severity_levels.append(self.config_manager.get_severity(tag))

        # Trackea el último nivel emitido para poder refrescar UI si cambia en caliente.
        self.previous_emitted_levels = list(self.severity_levels)

        # Reiniciar el estado de valores y estados previos para la nueva configuración
        self.current_values = [
            1.0 if tag == "dialyWaterTankFull" else 0.0 for tag in self.tags
        ]
        self.previous_states = [False] * self.alarm_count
        # event_history se mantiene, es un log.


    def update_value_by_index(self, index: int, value: float) -> None:
        """Actualiza el valor de una alarma por índice (thread-safe)"""
        if 0 <= index < self.alarm_count:
            with self.lock:
                self.current_values[index] = value

    def update_value_by_tag(self, tag: str, value: float) -> None:
        """Actualiza valor usando el tag (útil para comunicación serial/PLC)"""
        try:
            # Asegurarse de que el tag esté en la lista actual de tags monitoreados
            if tag in self.tags:
                index = self.tags.index(tag)
                self.update_value_by_index(index, value)
        except ValueError:
            pass  # Tag no está en las alarmas habilitadas → ignorar silenciosamente

    def _monitoring_loop(self) -> None:
        """Bucle de monitoreo en hilo separado"""
        while self.running:
            # Capturar los valores actuales y la configuración para minimizar el tiempo de bloqueo
            with self.lock:
                snapshot_values = list(self.current_values)
                # No es necesario tomar un snapshot de tags, types, etc.,
                # porque reload_configuration lo maneja deteniendo y reiniciando el bucle.
                # Sin embargo, los límites y severidades se leen directamente del config_manager
                # en cada iteración, lo cual es correcto para cambios en caliente.

            for i in range(self.alarm_count):
                value = snapshot_values[i]
                tag = self.tags[i]
                alarm_type = self.types[i] # "double" o "bool"

                # Obtener configuración actual (siempre fresca desde QSettings/VARIABLES_MAP)
                min_val, max_val = self.config_manager.get_limits(tag)
                level = self.config_manager.get_severity(tag)
                self.severity_levels[i] = level

                is_active = False # Inicializar

                # Determinar si la alarma debe estar activa
                if alarm_type == "double": # <-- CORRECCIÓN: Usar "double" para numéricas
                    is_active = (value < min_val) or (value > max_val)
                elif alarm_type == "bool": # <-- CORRECCIÓN: Usar "bool" para booleanas
                    condition = (value != 0.0)
                    is_active = condition if self.boolean_triggers[i] else not condition
                # else: Si hubiera otros tipos no alarmables o no definidos, simplemente is_active = False

                # Detectar cambio de estado
                if is_active != self.previous_states[i]:
                    self.previous_states[i] = is_active
                    self.previous_emitted_levels[i] = level

                    current_time = time.strftime("%H:%M:%S")
                    status_text = "ACTIVADA" if is_active else "DESACTIVADA"
                    # Mensaje personalizado para falta de agua
                    display_text = "FALTA AGUA" if tag == "dialyWaterTankFull" else self.display_names[i]
                    event_msg = f"{status_text} - {display_text}"

                    with self.lock: # Proteger el acceso al historial
                        self.event_history.append((event_msg, value, current_time))

                    # Emitir señales (seguro para GUI)
                    self.new_event.emit(event_msg, value, current_time)
                    self.alarm_changed.emit(
                        i,
                        is_active,
                        value,
                        self.display_names[i],
                        level,
                        (min_val, max_val)
                    )
                elif is_active and level != self.previous_emitted_levels[i]:
                    # Permite refrescar el color/prioridad en UI cuando cambia la severidad
                    # sin esperar a que la alarma se active/desactive físicamente.
                    self.previous_emitted_levels[i] = level
                    self.alarm_changed.emit(
                        i,
                        True,
                        value,
                        self.display_names[i],
                        level,
                        (min_val, max_val)
                    )
                elif not is_active:
                    # Mantener el baseline coherente para futuros cambios de severidad.
                    self.previous_emitted_levels[i] = level

            time.sleep(0.5)  # Intervalo de chequeo (puedes hacerlo configurable)

    def start_monitoring(self) -> None:
        """Inicia el hilo de monitoreo"""
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitor_thread.start()
            print(f"[INFO] AlarmSystem iniciado con {self.alarm_count} alarmas habilitadas.")

    def stop(self) -> None:
        """Detiene el hilo de monitoreo de forma segura"""
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
        self.monitor_thread = None
        print("[INFO] AlarmSystem detenido.")

    def reset(self) -> None:
        """Reinicia estado en tiempo de ejecución (manteniendo configuración)"""
        with self.lock:
            self.current_values = [
                1.0 if tag == "dialyWaterTankFull" else 0.0 for tag in self.tags
            ]
            self.previous_states = [False] * self.alarm_count
            self.event_history.clear()

    def reload_configuration(self):
        """
        Recarga la configuración de alarmas habilitadas desde config_manager
        y reinicia el monitoreo si estaba activo.
        """
        was_running = self.running
        if was_running:
            self.stop() # Detener el hilo actual

        with self.lock: # Proteger la reconstrucción interna
            self._rebuild_internal_config()
        
        print(f"[INFO] AlarmSystem reconstruido con {self.alarm_count} variables habilitadas.")

        if was_running:
            self.start_monitoring() # Reiniciar con la nueva configuración

    def get_history(self) -> List[Tuple[str, float, str]]:
        """Devuelve copia del historial de eventos"""
        with self.lock:
            return self.event_history.copy()


