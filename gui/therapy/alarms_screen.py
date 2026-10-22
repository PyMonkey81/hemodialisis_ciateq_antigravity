from gui.theme_manager import ThemeManager

# gui/therapy/alarms_screen.py
"""
Pantalla de visualización y configuración del sistema de alarmas.

Este módulo proporciona la interfaz de usuario para monitorear alarmas activas,
consultar un historial de eventos del sistema y configurar los límites de
advertencia y peligro para variables críticas.

Componentes principales:
------------------------
- `AlarmLimitsConfigDialog`: Un diálogo modal que permite al usuario ajustar
  los umbrales mínimos y máximos de las alarmas para varios parámetros
  fisiológicos y de máquina. Incluye funcionalidad para restaurar valores
  por defecto y un teclado numérico táctil.
- `AlarmsScreen`: La pantalla principal que muestra de forma dinámica las
  alarmas que se encuentran activas, su estado (reconocida o no) y un registro
  cronológico de todos los eventos del sistema, como la activación o normalización
  de alarmas, acciones del operador y mensajes informativos.

Funcionalidades clave:
----------------------
- **Visualización de Alarmas Activas:** Presenta una lista clara y con codificación
  de color de todas las alarmas que se encuentran en un estado activo, incluyendo
  su nivel de severidad y si han sido reconocidas por el operador.
- **Historial de Eventos:** Mantiene un registro persistente de todos los eventos
  importantes, incluyendo activaciones, normalizaciones y acciones del sistema.
- **Reconocimiento de Alarmas (Acknowledge):** Permite al operador silenciar el
  zumbador y marcar las alarmas activas como "reconocidas" sin desactivarlas,
  asegurando que se ha tomado conocimiento de la situación.
- **Configuración de Límites:** Proporciona una interfaz para ajustar los límites
  inferiores y superiores de las variables que disparan alarmas, garantizando
  la seguridad y adaptabilidad del sistema.
- **Sincronización:** Se integra con el `AlarmSystem` principal para recibir
  actualizaciones en tiempo real sobre el estado de las alarmas y eventos.

Dependencias:
-------------
- `PySide6`: Para la construcción de la interfaz gráfica.
- `gui.components.ui_components`: Componentes UI reutilizables como `ClickableLineEdit`.
- `gui.components.numpad_modal`: Diálogo para entrada numérica táctil.
- `gui.configuration.alarm_limits.AlarmLimitsManager`: Para la gestión persistente de los límites de alarma.

Uso:
----
La clase `AlarmsScreen` se instancia en el `HemodialysisHMI` principal y se
añade al `QStackedWidget`. Recibe instancias de `AlarmSystem` y `AlarmLimitsManager`
para su correcto funcionamiento.
"""

# gui/therapy/alarms_screen.py

import sys
import os
from xml.sax import handler 
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QFrame, QLineEdit, QSizePolicy,
    QPushButton, QScrollArea, QMessageBox, QDialog, QDialogButtonBox, QGroupBox,QFormLayout, QHBoxLayout
)
from PySide6.QtCore import Qt, QTime, Signal
from PySide6.QtGui import QFont, QDoubleValidator, QTextOption
from pyqtgraph import colors
from gui.components.ui_components import LabeledParameterWidget, ClickableLineEdit
from gui.components.numpad_modal import NumpadDialog
from gui.configuration.alarm_limits import AlarmLimitsManager
from gui.components.floating_message import FloatingMessage
from gui.components.floating_confirm import FloatingConfirmDialog
from typing import Dict
import json 



import logging
logger = logging.getLogger(__name__)

PATH_ALAMRS_LOG = "logs/alarms_log.json"  # Archivo para guardar el historial de eventos de alarmas

class AlarmsScreen(QWidget):
    """
    Pantalla dedicada para alarmas activas e historial de eventos.
    Maneja el reconocimiento (ACK) sin borrar alarmas persistentes.
    Estilo de "Equipo Médico" con fondos claros.
    """
    request_boolean_change = Signal(str, bool)    

    def __init__(self, parent=None, values_dict=None, alarm_system=None):
        super().__init__(parent)
      
        self.setStyleSheet("background: #F8F8FA; color: #333333; font-family: 'Segoe UI';")
        self.parent_window = parent
        self.current_values = values_dict if values_dict is not None else {}
        self.alarm_system = alarm_system

        # self.histroy_file = PATH_ALAMRS_LOG
        # self.max_history_entries = 1000  # Máximo número de eventos a guardar en el historial (puede ajustarse)
        # self.history_data = self._load_history_from_file()  # Cargar historial existente desde el archivo JSON
        # self._refresh_history_display()  # Mostrar el historial cargado al iniciar la pantalla

        self.history_file = "logs/alarm_history.json"
        self.max_history_entries = 1000
        self.history_data = self._load_history_from_file()
        

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)



        self.active_alarms: dict = {}
        self.setup_ui()
        self.apply_theme_styles()
        try:
            ThemeManager.instance().theme_changed.connect(lambda _t: self.apply_theme_styles())
        except Exception:
            pass
        self._refresh_history_display() # Mostrar lo cargado al iniciar

        if self.alarm_system:
            logger.info("AlarmsScreen: alarm_system found. Known alarm count: %s",
                        len(getattr(self.alarm_system, 'display_names', [])))
            self.alarm_system.alarm_changed.connect(self.on_alarm_changed)
            self.alarm_system.new_event.connect(self.on_new_event) # Conectar on_new_event
            # _sync_initial_state() se llamará al inicio, pero no en cada reconexión
            # Su lógica de 'acked' ahora se maneja en on_alarm_changed.
            self._sync_initial_state()
        else:
            logger.warning("Warning: alarm_system not available in AlarmsScreen")

        
    def _load_history_from_file(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
            except Exception as e:
                logger.error(f"Error cargando historial: {e}")
        return []

    def _refresh_history_display(self):
        """Puebla el QTextEdit con los datos cargados"""
        self.history_display.clear()
        for entry in self.history_data:
            if not isinstance(entry, dict):
                continue
            text = entry.get('text', '')
            value = entry.get('value', 0)
            level = entry.get('level', 'INFO')
            time_value = entry.get('time', '')
            self._append_to_history_visual(text, value, level, time_value)

    def setup_ui(self):
        layout = QVBoxLayout(self)
   
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5) # Reducido un poco el espaciado

        # Título
        self.title_label = QLabel("ALARMAS Y EVENTOS DEL SISTEMA")
        self.title_label.setStyleSheet("font-size: 42px; font-weight: bold; color: #E74C3C;") # Rojo fuerte
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setStyleSheet("background: #CCCCCC; max-height: 1px;") # Separador 
        layout.addWidget(sep1)

        # Sección Alarmas Activas
        self.lbl_active = QLabel("ALARMAS ACTIVAS")
        self.lbl_active.setStyleSheet("font-size: 32px; font-weight: bold; color: #3F88C5; margin-top: 15px;") # Azul profesional
        layout.addWidget(self.lbl_active)

        self.active_alarms_display = QTextEdit()
        self.active_alarms_display.setReadOnly(True)
        self.active_alarms_display.setStyleSheet("""
            QTextEdit {
                background: #FFFFFF; /* Blanco puro */
                color: #333333; /* Gris oscuro para el texto */
                font-family: Consolas, 'Courier New', monospace;
                font-size: 20px;
                border: 2px solid #D9534F; /* Borde rojo suave */
                border-radius: 8px;
                padding: 10px;
            }
            /* --- ESTILOS DE QSCROLLBAR PARA active_alarms_display --- */
            QTextEdit QScrollBar:vertical { /* Se aplica a la barra de scroll DENTRO de este QTextEdit */
                border: none;
                background: #e0e0e5;
                width: 34px;               /* <--- aquí cambias el ancho */
                margin: 0px 0px 0px 0px;
                border-radius: 14px;
            }
            QTextEdit QScrollBar::handle:vertical {
                background: #8a8a9c;
                min-height: 60px;
                border-radius: 14px;
            }
            QTextEdit QScrollBar::handle:vertical:hover {
                background: #6b6b7a;
            }
            QTextEdit QScrollBar::add-line:vertical, QTextEdit QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QTextEdit QScrollBar::add-page:vertical, QTextEdit QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        self.active_alarms_display.setMinimumHeight(220)
        layout.addWidget(self.active_alarms_display)

        # Botón Reconocer
        self.btn_ack_all = QPushButton("RECONOCER (SILENCIAR)")
        self.btn_ack_all.setFixedSize(320, 60)
        self.btn_ack_all.setStyleSheet("""
            QPushButton {
                background: #D9534F; /* Rojo suave */
                color: #ffffff;
                font-size: 22px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover { background: #C9302C; }
            QPushButton:pressed { background: #B22B29; }
            QPushButton:disabled { background: #CCCCCC; color: #999999; }
        """)
        self.btn_ack_all.clicked.connect(self.acknowledge_all_alarms)

        # Botón de Reset de Bombas
        self.btn_reset_pumps = QPushButton("RESET")
        self.btn_reset_pumps.setFixedSize(320, 60)
        self.btn_reset_pumps.setStyleSheet("""
            QPushButton {
                background: #FFC107; /* Amarillo */
                color: #333333; /* Texto oscuro para contraste */
                font-size: 22px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover { background: #E0A800; }
            QPushButton:pressed { background: #C69500; }
        """)
        self.btn_reset_pumps.clicked.connect(self.reset_pump_overpress_alarms) 

        # Botón de Configuración
        self.btn_config_limits = QPushButton("Configuración")
        self.btn_config_limits.setFixedSize(320, 60)
        self.btn_config_limits.setStyleSheet("""
            QPushButton {
                background: #3498DB; /* Azul Suave */
                color: #ffffff;
                font-size: 22px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover { background: #2980B9; }
            QPushButton:pressed { background: #1F6C8C; }
        """)
        if self.parent_window and hasattr(self.parent_window, 'show_alarm_config_limits_screen'):
            self.btn_config_limits.clicked.connect(self.parent_window.show_alarm_config_limits_screen)

        # Contenedor horizontal para alinear los 3 botones en una sola línea
        action_buttons_h_layout = QHBoxLayout()
        action_buttons_h_layout.addStretch()  # Empuja todo hacia la derecha
        action_buttons_h_layout.addWidget(self.btn_reset_pumps)
        action_buttons_h_layout.addWidget(self.btn_ack_all)
        action_buttons_h_layout.addWidget(self.btn_config_limits)  # Movido aquí junto a los otros dos
        
        layout.addLayout(action_buttons_h_layout)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("background: #CCCCCC; max-height: 1px;") # Separador sutil
        layout.addWidget(sep2)

        # Sección Historial
        self.lbl_history = QLabel("HISTORIAL DE EVENTOS")
        self.lbl_history.setStyleSheet("font-size: 26px; font-weight: bold; color: #3F88C5; margin-top: 15px;") # Azul profesional
        layout.addWidget(self.lbl_history)

        self.history_display = QTextEdit()
        self.history_display.setReadOnly(True)
        self.history_display.setUndoRedoEnabled(False)

        self.history_display.setLineWrapMode(QTextEdit.WidgetWidth)          # wrap al ancho del widget
        self.history_display.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)  # corta en espacios cuando pueda, si no → en cualquier 
        self.history_display.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.history_display.setStyleSheet("""
            QTextEdit {
                background: #F0F2F5; /* Fondo ligeramente gris para diferenciar del principal */
                color: #333333; /* Texto gris oscuro */
                font-family: Consolas, monospace;
                font-size: 17px;
                border: 1px solid #CCCCCC; /* Borde sutil */
                border-radius: 5px;
                padding: 8px;
            }
        """)

        scroll_area = QScrollArea()
        scroll_area.setWidget(self.history_display)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                border: none;
                background: #e0e0e5;
                width: 34px;               /* <--- aquí cambias el ancho */
                margin: 0px 0px 0px 0px;
                border-radius: 14px;
            }
            QScrollBar::handle:vertical {
                background: #8a8a9c;
                min-height: 60px;
                border-radius: 14px;
            }
            QScrollBar::handle:vertical:hover {
                background: #6b6b7a;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        scroll_area.setMinimumHeight(240) # Ajustado altura
        layout.addWidget(scroll_area)

        # Mensaje inicial
        self._update_active_alarms_display()
        
    def _sync_initial_state(self):
        """
        Sincroniza el estado inicial de la pantalla de alarmas al cargarse por primera vez.
        No se usa para reconexiones, ahí se depende de on_alarm_changed.
        """
        if not self.alarm_system:
            return

        current_time = QTime.currentTime().toString("hh:mm:ss")
        loaded_count = 0
        for i in range(self.alarm_system.alarm_count):
            if self.alarm_system.previous_states[i]: # Si AlarmSystem dice que está activa
                name = self.alarm_system.display_names[i]
                level = self.alarm_system.severity_levels[i]
                value = self.alarm_system.current_values[i] # Obtener el valor actual del AlarmSystem

                if name not in self.active_alarms:
                    self.active_alarms[name] = {
                        'value': value,
                        'level': level,
                        'time': current_time,
                        'acked': False # Siempre se inicia como NO reconocida
                    }
                    loaded_count += 1
                else:
                    # Actualizar valor y tiempo si ya estaba en la lista (pero sigue siendo 'acked: False')
                    self.active_alarms[name]['value'] = value
                    self.active_alarms[name]['time'] = current_time

        if loaded_count > 0:
            logger.info("AlarmsScreen: initial sync -> %s newly active alarms loaded", loaded_count)
        self._update_active_alarms_display()
        self.update_ack_button_state()

    def on_alarm_changed(self, idx, is_active, value, name, level, limits):
        """Maneja la señal cuando una alarma se activa o desactiva físicamente."""
        current_time = QTime.currentTime().toString("hh:mm:ss")

        if is_active:
            # Si la alarma se activa
            if name in self.active_alarms:
                
                self.active_alarms[name]['value'] = value
                self.active_alarms[name]['level'] = level
                self.active_alarms[name]['time'] = current_time
                self.active_alarms[name]['acked'] = False # IMPORTANTE: Resetea a NO reconocida
            else:
                # Es una alarma nueva o se había normalizado y ahora se activa de nuevo
                self.active_alarms[name] = {
                    'value': value,
                    'level': level,
                    'time': current_time,
                    'acked': False # Siempre se agrega como NO reconocida
                }
            self._append_to_history(f"ACTIVADA: {name}", value, level, current_time)

        else:            
            # La alarma se normalizó
            if name in self.active_alarms:
                del self.active_alarms[name] # Eliminar de la lista de activas
                self._append_to_history(f"NORMALIZADA: {name}", value, "info", current_time)

        self._update_active_alarms_display()
        self.update_ack_button_state()


    def on_new_event(self, event_msg, value, timestamp):
        """Maneja los eventos generales del AlarmSystem para el historial."""
        # Se asume que 'value' para eventos generales puede ser None o 0 si no es relevante.
        self._append_to_history(event_msg, value, "info", timestamp) 

    def acknowledge_all_alarms(self):
        """
        Marca todas las alarmas NO reconocidas actualmente como 'Reconocidas' (ACK).
        No las borra. Solo cambia su estado visual.
        """
        if not self.active_alarms:
            # QMessageBox.information(self, "Información", "No hay alarmas activas para reconocer.")
            
            self.show_info_message("No hay alarmas activas para reconocer.", 3000)
            return

        unacked_count = sum(1 for data in self.active_alarms.values() if not data['acked'])
        if unacked_count == 0:
            # QMessageBox.information(self, "Información", "Todas las alarmas activas ya están reconocidas.")
            self.show_info_message("Todas las alarmas activas ya están reconocidas.", 3000)
            return
        dialog = FloatingConfirmDialog(self)
        message = f"¿Estás seguro de reconocer {unacked_count} alarma(s) activa(s) y silenciar?"
        reply = dialog.show_confirm(message, accept_text="Sí, Reconocer", cancel_text="Cancelar")
        
        
        if reply == True:
            changed = False
            for name, data in self.active_alarms.items():
                if not data['acked']:
                    data['acked'] = True
                    changed = True   

            if changed:
                self._update_active_alarms_display()
                self.update_ack_button_state()

                # === NUEVA LÓGICA DE SILENCIO ===
                if self.parent_window and hasattr(self.parent_window, 'buzzer_silenced_by_user'):
                    self.parent_window.buzzer_silenced_by_user = True
                    if hasattr(self.parent_window, 'update_led_bar_state'):
                        self.parent_window.update_led_bar_state()   # ← fuerza envío inmediato

                self._append_to_history("Operador reconoció alarmas activas y silenció buzzer", 
                                      None, "info", QTime.currentTime().toString("hh:mm:ss"))
                
               
                self.show_info_message(f"{unacked_count} alarma(s) reconocida(s). Buzzer silenciado.", 4000)
        else:            
            self.show_info_message("Reconocimiento de alarmas cancelado.", 3000)

    def show_floating_message(self, text: str, timeout_ms: int = 3800):
        """Método genérico (recomendado)"""
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        
        self._floating_msg.show_floating_message(text, timeout_ms)

    # Métodos específicos (más semánticos)
    def show_success_message(self, text: str, timeout_ms: int = 4000):
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        self._floating_msg.show_success_message(text, timeout_ms)

    def show_info_message(self, text: str, timeout_ms: int = 3800):
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        self._floating_msg.show_info_message(text, timeout_ms)

    def show_warning_message(self, text: str, timeout_ms: int = 4500):
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        self._floating_msg.show_warning_message(text, timeout_ms)
    
    def show_error_message(self, text: str, timeout_ms: int = 5000):
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        self._floating_msg.show_error_message(text, timeout_ms)

    def reset_pump_overpress_alarms(self):
        """
        Envía una solicitud para resetear los estados de sobrepresión de las bombas
        de dializado y desaireación a False, utilizando el método on_user_boolean_command.
        """
        dialog = FloatingConfirmDialog(self)

        message = "¿Está seguro de querer resetear las alarmas de sobrepresión de bombas?"
        reply = dialog.show_confirm(message, accept_text="Sí, Restaurar", cancel_text="Cancelar")        


        if reply == True:
            logger.info("Solicitando reset de alarmas de sobrepresión de bombas: dialyDialyPumpOverPress y dialyDeaerPumpOverPress.")
            # Emitir la señal request_boolean_change para ambas variables
            self.on_user_boolean_command('dialyDialyPumpOverPress', False)
            self.on_user_boolean_command('dialyDeaerPumpOverPress', False)            
            self.show_info_message("Alarmas de sobrepresión de bombas reseteadas.", 2000)
            self._append_to_history("Operador solicitó reset de alarmas de sobrepresión de bombas",
                                    None, "info", QTime.currentTime().toString("hh:mm:ss"))
        else:
            self.show_info_message("Reset de alarmas de bombas cancelado.", 1500)

    def _update_active_alarms_display(self):
        """Regenera el HTML de la lista de alarmas activas con la nueva estética."""
        if not self.active_alarms:
            self.active_alarms_display.setHtml(
                '<div style="text-align:center; color:#607D8B; font-size:24px; margin-top:20px;">'
                'SISTEMA EN ÓPTIMAS CONDICIONES - SIN ALARMAS ACTIVAS</div>'
            )
            return

        html = ""
        # Ordenar: No reconocidas primero, luego por severidad 
        priority_map = {"rojo": 4, "naranja": 3, "amarillo": 2, "cian": 1, "info": 0}
        
        sorted_alarms = sorted(
            self.active_alarms.items(),
            key=lambda item: (
                not item[1]['acked'],  # Las False (no reconocidas) van primero
                priority_map.get(item[1]['level'], 0) # Luego por prioridad de severidad
            ),
            reverse=True # Para que el más grave o no reconocido esté arriba
        )

        for name, data in sorted_alarms:
            level = data['level']
            acked = data['acked']
            time_str = data['time']
            val = f"{data['value']:.1f}" if data['value'] is not None else "N/D" # N/D para No Disponible

            # Colores base para alarmas (no reconocidas)
            colors = {
                "rojo": "#E74C3C",    # Rojo fuerte
                "naranja": "#F39C12", # Naranja
                "amarillo": "#FBC02D",# Amarillo
                "cian": "#3498DB",    # Azul vibrante
                "info": "#607D8B"     # Gris azulado para info
            }
            base_color = colors.get(level, "#333333") # Default texto oscuro

            # Estilo visual diferente para ACK vs NO-ACK
            if acked:
                # Alarma Reconocida: Fondo claro, texto atenuado, borde sutil
                bg_style = "background-color: #E0E0E0;" # Gris claro
                status_icon = "✔ Reconocida"
                text_color = "#757575" # Gris medio, atenuado
                border_color = "#BDBDBD" # Borde gris más oscuro
            else:
                # Alarma NO Reconocida: Fondo ligeramente resaltado, texto vivo, borde fuerte
                bg_style = f"background-color: {base_color}1A;" # Un 10% de opacidad del color base
                status_icon = "⚠️ ACTIVA"
                text_color = base_color # Color vivo
                border_color = base_color # Borde con color de la alarma

            # Construcción de la tarjeta HTML para la alarma
            html += f"""
            <div style="border: 2px solid {border_color}; border-radius: 8px; margin-bottom: 8px; padding: 10px; {bg_style}">
                <table width="100%" style="border-collapse: collapse;">
                    <tr>
                        <td width="15%" style="color:{text_color}; font-weight:bold; font-size:18px; padding: 2px;">{time_str}</td>
                        <td width="55%" style="color:{text_color}; font-weight:bold; font-size:22px; padding: 2px;">{name}</td>
                        <td width="15%" style="color:#333333; font-size:22px; text-align:right; padding: 2px;">{val}</td>
                        <td width="15%" style="color:{text_color}; font-weight:bold; text-align:right; font-size:16px; padding: 2px;">{status_icon}</td>
                    </tr>
                </table>
            </div>
            """

        self.active_alarms_display.setHtml(html)



    def _append_to_history(self, text, value, level, time_str):
        # 1. Crear el objeto de la entrada
        entry = {
            "time": time_str,
            "text": text,
            "value": value,
            "level": level
        }
    
        # 2. Gestionar la lista en memoria (mantener los últimos 1000)
        self.history_data.append(entry)
        if len(self.history_data) > self.max_history_entries:
            self.history_data.pop(0) # Eliminar el más antiguo

        # 3. Guardar a archivo JSON
        try:
            history_dir = os.path.dirname(self.history_file)
            if history_dir:
                os.makedirs(history_dir, exist_ok=True)
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history_data, f, indent=4)
        except Exception as e:
            logger.error(f"Error guardando historial: {e}")

        # 4. Mostrar en pantalla (Visual)
        self._append_to_history_visual(text, value, level, time_str)

    def _append_to_history_visual(self, text, value, level, time_str):
        """Aquí mueves la lógica de 'self.history_display.append' que ya tenías"""
        if not hasattr(self, 'history_display') or self.history_display is None:
            return

        colors = {"rojo": "#E74C3C", "naranja": "#F39C12", "amarillo": "#FBC02D", "cian": "#3498DB", "info": "#607D8B"}
        color = colors.get(level, "#333333")
        val_str = f" [{value:.1f}]" if value is not None else ""

        self.history_display.append(
            f'<span style="color:#607D8B;">[{time_str}]</span> '
            f'<span style="color:{color}; font-weight:bold;">{text}{val_str}</span>'
        )
        scrollbar = self.history_display.verticalScrollBar()
        if scrollbar is not None:
            scrollbar.setValue(scrollbar.maximum())


    def update_ack_button_state(self):
        """Habilita/Deshabilita el botón de reconocimiento si hay alarmas no reconocidas."""
        if any(not data['acked'] for data in self.active_alarms.values()):
            self.btn_ack_all.setEnabled(True)
        else:
            self.btn_ack_all.setEnabled(False)
    

    def update_values(self, values_dict):
        """Método de compatibilidad. No usado directamente aquí."""
        # Puedes querer actualizar current_values si se usa en AlarmLimitsConfigDialog
        self.current_values = values_dict
        # Si la configuración de límites depende de estos valores, podrías tener que
        # refrescar la UI de configuración de límites si está abierta, pero eso es más complejo.

    def silence_buzzer_only(self):
        """
        Silencia el buzzer en HemodialysisHMI. Debería ser revisado o eliminado.
        """
        logger.warning("AlarmsScreen.silence_buzzer_only() llamado. Revisar si es necesario.")
        # if not self._last_buzzer_silence_state_sent: # estas variables no están definidas aquí
        #     self.command_queue.put(self.CMD_SILENCE)
        #     self._last_buzzer_silence_state_sent = True


    def reset_ui_state(self):
        """
        Limpia todas las alarmas activas mostradas y resetea el botón de reconocimiento.
        Útil cuando se pierde o restaura la conexión para tener un estado limpio.
        """
        self.active_alarms.clear() # Limpiar el diccionario de alarmas activas
        self._update_active_alarms_display() # Actualizar la pantalla (mostrar "SISTEMA NORMAL")
        self.update_ack_button_state() # Deshabilitar botón ACK
        logger.info("AlarmsScreen UI state reset.")

    def on_user_boolean_command(self, tag, state):
        self.request_boolean_change.emit(tag, state)
        print("confirmado")



    def showEvent(self, event):
        super().showEvent(event)
        self.apply_theme_styles()

    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        is_mono = bool(tokens.get("monochrome", False))
        is_dark = bool(tokens.get("is_dark", False))

        if is_mono:
            self.setStyleSheet(f"background: {tokens['bg_main']}; color: {tokens['text_primary']}; font-family: 'Segoe UI';")
            if hasattr(self, "title_label"):
                self.title_label.setStyleSheet("font-size: 42px; font-weight: bold; color: #4B5563; background: transparent;")
            if hasattr(self, "lbl_active"):
                self.lbl_active.setStyleSheet("font-size: 32px; font-weight: bold; color: #374151; margin-top: 15px; background: transparent;")
            if hasattr(self, "lbl_history"):
                self.lbl_history.setStyleSheet("font-size: 26px; font-weight: bold; color: #374151; margin-top: 15px; background: transparent;")
            if hasattr(self, "active_alarms_display"):
                self.active_alarms_display.setStyleSheet("""
                    background-color: #FFFFFF;
                    color: #374151;
                    font-size: 22px;
                    border: 2px solid #9CA3AF;
                    border-radius: 10px;
                    padding: 15px;
                """)
            if hasattr(self, "history_display"):
                self.history_display.setStyleSheet("""
                    background-color: #F8F9FA;
                    color: #374151;
                    font-size: 20px;
                    border: 1px solid #D1D5DB;
                    border-radius: 10px;
                    padding: 15px;
                """)
            btn_mono = """
                QPushButton {
                    font-size: 20px;
                    font-weight: bold;
                    background: #D9E0E8;
                    color: #374151;
                    border: 1px solid #C5CDD6;
                    border-radius: 10px;
                    padding: 8px;
                }
                QPushButton:hover { background: #C5CED6; }
                QPushButton:pressed { background: #B0B8C4; }
                QPushButton:disabled { background: #E5E7EB; color: #B0B8C2; border: 1px solid #D1D5DB; }
            """
            if hasattr(self, "btn_ack_all"):
                self.btn_ack_all.setStyleSheet(btn_mono)
            if hasattr(self, "btn_reset_pumps"):
                self.btn_reset_pumps.setStyleSheet(btn_mono)
            if hasattr(self, "btn_config_limits"):
                self.btn_config_limits.setStyleSheet(btn_mono)
        elif is_dark:
            self.setStyleSheet(f"background: {tokens['bg_main']}; color: {tokens['text_primary']}; font-family: 'Segoe UI';")
            if hasattr(self, "title_label"):
                self.title_label.setStyleSheet(f"font-size: 42px; font-weight: bold; color: {tokens.get('danger', '#ef4444')}; background: transparent;")
            if hasattr(self, "lbl_active"):
                self.lbl_active.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {tokens.get('primary', '#38bdf8')}; margin-top: 15px; background: transparent;")
            if hasattr(self, "lbl_history"):
                self.lbl_history.setStyleSheet(f"font-size: 26px; font-weight: bold; color: {tokens.get('primary', '#38bdf8')}; margin-top: 15px; background: transparent;")
            if hasattr(self, "active_alarms_display"):
                self.active_alarms_display.setStyleSheet(f"""
                    background-color: {tokens.get('bg_card', '#1E293B')};
                    color: {tokens.get('text_primary', '#F8FAFC')};
                    font-size: 22px;
                    border: 2px solid {tokens.get('border_card', '#334155')};
                    border-radius: 10px;
                    padding: 15px;
                """)
            if hasattr(self, "history_display"):
                self.history_display.setStyleSheet(f"""
                    background-color: {tokens.get('bg_card_alt', '#1E293B')};
                    color: {tokens.get('text_primary', '#F8FAFC')};
                    font-size: 20px;
                    border: 1px solid {tokens.get('border_card', '#334155')};
                    border-radius: 10px;
                    padding: 15px;
                """)
            btn_dark = f"""
                QPushButton {{
                    font-size: 20px;
                    font-weight: bold;
                    background: {tokens.get('primary', '#3b82f6')};
                    color: #FFFFFF;
                    border-radius: 10px;
                    padding: 8px;
                }}
                QPushButton:hover {{ background: {tokens.get('primary_hover', '#60a5fa')}; }}
                QPushButton:disabled {{ background: {tokens.get('btn_disabled_bg', '#334155')}; color: {tokens.get('btn_disabled_text', '#64748b')}; }}
            """
            if hasattr(self, "btn_ack_all"):
                self.btn_ack_all.setStyleSheet(btn_dark)
            if hasattr(self, "btn_reset_pumps"):
                self.btn_reset_pumps.setStyleSheet(btn_dark)
            if hasattr(self, "btn_config_limits"):
                self.btn_config_limits.setStyleSheet(btn_dark)
        else:
            self.setStyleSheet("background: #F8F8FA; color: #333333; font-family: 'Segoe UI';")
            if hasattr(self, "title_label"):
                self.title_label.setStyleSheet("font-size: 42px; font-weight: bold; color: #E74C3C;")
            if hasattr(self, "lbl_active"):
                self.lbl_active.setStyleSheet("font-size: 32px; font-weight: bold; color: #3F88C5; margin-top: 15px;")
            if hasattr(self, "lbl_history"):
                self.lbl_history.setStyleSheet("font-size: 26px; font-weight: bold; color: #3F88C5; margin-top: 15px;")
            if hasattr(self, "active_alarms_display"):
                self.active_alarms_display.setStyleSheet("""
                    background-color: #FFFFFF;
                    color: #333333;
                    font-size: 22px;
                    border: 2px solid #E74C3C;
                    border-radius: 10px;
                    padding: 15px;
                """)
            if hasattr(self, "history_display"):
                self.history_display.setStyleSheet("""
                    background-color: #F8F8F8;
                    color: #333333;
                    font-size: 20px;
                    border: 1px solid #DDDDDD;
                    border-radius: 10px;
                    padding: 15px;
                """)
            if hasattr(self, "btn_ack_all"):
                self.btn_ack_all.setStyleSheet("""
                    QPushButton {
                        font-size: 20px;
                        font-weight: bold;
                        background: #3b82f6;
                        color: white;
                        border-radius: 10px;
                        padding: 8px;
                    }
                    QPushButton:hover { background: #2563eb; }
                    QPushButton:disabled { background: #94a3b8; }
                """)
            if hasattr(self, "btn_reset_pumps"):
                self.btn_reset_pumps.setStyleSheet("""
                    QPushButton {
                        font-size: 22px;
                        font-weight: bold;
                        background: #facc15;
                        color: #1e293b;
                        border-radius: 10px;
                        padding: 8px;
                    }
                    QPushButton:hover { background: #eab308; }
                """)
            if hasattr(self, "btn_config_limits"):
                self.btn_config_limits.setStyleSheet("""
                    QPushButton {
                        font-size: 22px;
                        font-weight: bold;
                        background: #3b82f6;
                        color: white;
                        border-radius: 10px;
                        padding: 8px;
                    }
                    QPushButton:hover { background: #2563eb; }
                """)
