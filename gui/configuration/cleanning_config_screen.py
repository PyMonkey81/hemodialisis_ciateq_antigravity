from gui.theme_manager import ThemeManager
# # gui/configuration/cleanning_config_screen.py
# gui/configuration/cleanning_config_screen.py


# gui/configuration/cleanning_config_screen.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy, QButtonGroup, QPushButton, QFrame
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt, Signal
import time
import logging
import json
from utilities.platform_runtime import get_runtime_config_path

from gui.components.floating_message import FloatingMessage # Asumo que esta clase está disponible
from gui.components.time_numpad_modal import TimeNumpadDialog
from gui.components.ui_components import ClickableLineEdit
from gui.components.numpad_modal import NumpadDialog # Asegúrate que NumpadDialog esté disponible

logger = logging.getLogger(__name__)

# Definimos la ruta del archivo de configuración
CONFIG_FILE_PATH = get_runtime_config_path("cleaning_config.json")

class CleanningConfigScreen(QWidget):
    request_setpoint_change = Signal(str, float)
    request_boolean_change = Signal(str, bool) 

    def __init__(self, parent=None, values_dict=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_values = values_dict if values_dict is not None else {}
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAutoFillBackground(True)
        
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor("#f8f8f8"))
        self.setPalette(palette)

        self.pending_mode_change_deadline = None
        self.command_mode_value = 0.0 # Guardará el modo actual (0.0 o 1.0)
        self.current_mode_tag = "DesinftectionMode" # Valor por defecto, se actualizará al seleccionar un modo

        self.init_ui()
        # Se llama a _load_config_for_display() al inicializar la pantalla
        # para que siempre muestre el último modo y tiempo activo al abrirla.
        self._load_config_for_display()
        self.apply_theme_styles()
        try:
            ThemeManager.instance().theme_changed.connect(lambda _t: self.apply_theme_styles())
        except Exception:
            pass 

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        self.title_label = QLabel("Configuración de Desinfección")
        self.title_label.setStyleSheet("color: #0f172a; font-size: 28px; font-weight: bold;")
        self.title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.title_label)

        _line = QFrame()
        _line.setFrameShape(QFrame.HLine)
        _line.setStyleSheet("background: #d3d3d3; max-height: 2px;")
        main_layout.addWidget(_line)

        # === Frame para modos ===
        self.mode_frame = QFrame()
        self.mode_frame.setStyleSheet("background: #fcfcfc; border-radius: 10px; padding: 20px; border: 1px solid #e5e5e5;")
        mode_layout = QVBoxLayout(self.mode_frame)
        mode_layout.setSpacing(20)

        self.lbl_mode = QLabel("Seleccione tipo de desinfección predeterminado")
        self.lbl_mode.setStyleSheet("font-size: 24px; font-weight: bold; color: #000000; border: none;")
        mode_layout.addWidget(self.lbl_mode)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(20)

        self._short_chemical_desinfection = QPushButton("Desinfección Química Corta")
        self._long_chemical_desinfection = QPushButton("Desinfección Química Larga")

        self.btn_mode_group = QButtonGroup(self)
        self.btn_mode_group.setExclusive(True)

        btn_mode_info = [
            (self._short_chemical_desinfection, "DesinftectionMode", 0.0),
            (self._long_chemical_desinfection, "DesinftectionMode", 1.0),
        ]

        self.style_mode_unchecked = """
            QPushButton {
                background: #3b82f6; color: #ffffff; font-size: 22px; font-weight: bold;
                border-radius: 12px; padding: 15px 25px; border: 2px solid #2563eb;
            }
            QPushButton:hover { background: #60a5fa; }
        """
        self.style_mode_checked = """
            QPushButton {
                background: #22c55e; color: #ffffff; font-size: 22px; font-weight: bold;
                border-radius: 12px; padding: 15px 25px; border: 2px solid #16a34a;
            }
        """

        for btn, tag, value in btn_mode_info:
            btn.setStyleSheet(self.style_mode_unchecked) 
            btn.setCheckable(True)
            btn.toggled.connect(lambda checked, b=btn, t=tag, v=value:
                                self._on_mode_toggled(b, t, v, checked))
            buttons_layout.addWidget(btn)
            self.btn_mode_group.addButton(btn)

        mode_layout.addLayout(buttons_layout)
        main_layout.addWidget(self.mode_frame)

        # === Input de Tiempo ===
        self.lbl_time = QLabel("Tiempo de desinfección (hh:mm):") 
        self.lbl_time.setStyleSheet("color: #0f172a; font-size: 20px; font-weight: bold;")
        main_layout.addWidget(self.lbl_time)

        # ClickableLineEdit para el tiempo
        self.desinfection_time_input = ClickableLineEdit("00:00")
        self.desinfection_time_input.setStyleSheet("color: #0f172a; font-size: 24px; padding: 10px; border: 1px solid #ccc; border-radius: 5px; background: #FFFFFF;")
        self.desinfection_time_input.setAlignment(Qt.AlignCenter)
        self.desinfection_time_input.setReadOnly(True)
        self.desinfection_time_input.clicked.connect(
            lambda: self.open_time_numpad(
                self.desinfection_time_input,
                title="Tiempo de Desinfección"
            )
         )
        main_layout.addWidget(self.desinfection_time_input)

        # === Input de Temperatura ===
        self.lbl_temperature = QLabel("Temperatura (°C):")
        self.lbl_temperature.setStyleSheet("color: #0f172a; font-size: 20px; font-weight: bold;")
        main_layout.addWidget(self.lbl_temperature)

        self._desinfection_temp_input = ClickableLineEdit("0.0")
        self._desinfection_temp_input.setStyleSheet("color: #0f172a; font-size: 24px; padding: 10px; border: 1px solid #ccc; border-radius: 5px; background: #FFFFFF;")
        self._desinfection_temp_input.setAlignment(Qt.AlignCenter)
        self._desinfection_temp_input.setReadOnly(True)
        self._desinfection_temp_input.clicked.connect(
            # Corregida la llamada: ahora pasa el widget y el título
            lambda: self.open_numpad(
                self._desinfection_temp_input,
                title="Temperatura de Desinfección (°C)",
            )
        )
        main_layout.addWidget(self._desinfection_temp_input)


        # ==========imput de flujo camara de balance=========
        self.lbl_balance_chamber_flow = QLabel("Flujo de Cámara (ml/min)")
        self.lbl_balance_chamber_flow.setStyleSheet("color: #0f172a; font-size: 20px; font-weight: bold;")
        main_layout.addWidget(self.lbl_balance_chamber_flow)

        self._flow_bchamber = ClickableLineEdit("0.0")
        self._flow_bchamber.setStyleSheet("color: #0f172a; font-size: 24px; padding: 10px; border: 1px solid #ccc; border-radius: 5px; background: #FFFFFF;")
        self._flow_bchamber.setAlignment(Qt.AlignCenter)
        self._flow_bchamber.setReadOnly(True)
        self._flow_bchamber.clicked.connect(
            lambda: self.open_numpad(
                self._flow_bchamber,
                title="Flujo para desinfección (ml/min)"
            )
        )
        main_layout.addWidget(self._flow_bchamber)

        main_layout.addStretch(1)

        # === Botón Guardar ===
        self.save_button = QPushButton("Guardar Configuración")
        self.save_button.setStyleSheet("QPushButton { background: #06298a; color: #ffffff; font-size: 24px; padding: 15px; border-radius: 8px; font-weight: bold; }")
        self.save_button.clicked.connect(self.save_configuration)
        main_layout.addWidget(self.save_button)

        self.setLayout(main_layout)

    def _load_config_for_display(self):
        """
        Carga la configuración de los modos desde el JSON y actualiza la UI.
        Se llama al iniciar la pantalla de configuración.
        """
        config_data = {}
        if CONFIG_FILE_PATH.exists():
            try:
                with CONFIG_FILE_PATH.open('r', encoding='utf-8') as f:
                    config_data = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Archivo JSON de configuración corrupto: {CONFIG_FILE_PATH}. Se usará configuración por defecto.")
                config_data = {} # Resetear a vacío si está corrupto
            except Exception as e:
                logger.error(f"Error al leer configuración del JSON {CONFIG_FILE_PATH}: {e}")

        # Obtener el último modo activo o usar uno por defecto
        last_active_mode_value = config_data.get("last_active_mode_value", 0.0) # Por defecto, modo corto

        # Simular el clic en el botón correspondiente para cargar sus valores
        if last_active_mode_value == 0.0:
            self._short_chemical_desinfection.setChecked(True)
        elif last_active_mode_value == 1.0:
            self._long_chemical_desinfection.setChecked(True)
        else: # Si el valor no es válido, por defecto el corto
             self._short_chemical_desinfection.setChecked(True)

    def _on_mode_toggled(self, button: QPushButton, tag: str, value: float, checked: bool):
        if checked:
            button.setStyleSheet(self.style_mode_checked)
            self.command_mode_value = value
            self.current_mode_tag = tag 
            # Cargar el tiempo y la temperatura específica para el modo seleccionado
            self._display_mode_parameters(value)
        else:
            button.setStyleSheet(self.style_mode_unchecked)

    def _display_mode_parameters(self, mode_value: float):
        """Carga el tiempo y temperatura guardados para el mode_value y los muestra en los ClickableLineEdit."""
        config_data = {}
        if CONFIG_FILE_PATH.exists():
            try:
                with CONFIG_FILE_PATH.open('r', encoding='utf-8') as f:
                    config_data = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Archivo JSON de configuración corrupto: {CONFIG_FILE_PATH}. Usando valores por defecto para mostrar tiempo y temperatura.")
            except Exception as e:
                logger.error(f"Error al leer configuración para display de tiempo y temperatura: {e}")
        
        # Obtener la configuración específica para el modo
        modes_config = config_data.get("modes", {})
        # Valores por defecto para tiempo y temperatura
        mode_specific_config = modes_config.get(str(mode_value), {
            "time_hours": 0, "time_minutes": 15, "mode_temp": 37.0 # Default temp
        })
        
        hours = mode_specific_config.get("time_hours", 0)
        minutes = mode_specific_config.get("time_minutes", 15)
        temperature = mode_specific_config.get("mode_temp", 37.0) # Obtener la temperatura
        _flow_balance_chamber = mode_specific_config.get("mode_flow", 100.0)

        self.desinfection_time_input.setText(f"{hours:02d}:{minutes:02d}")
        self._desinfection_temp_input.setText(f"{temperature:.1f}") # Mostrar temperatura con un decimal
        self._flow_bchamber.setText(f"{_flow_balance_chamber:.1f}") # mostrar flujo con un decimal


    def save_configuration(self):
        # 1. Validar si se seleccionó un modo
        if not hasattr(self, 'current_mode_tag'):
            logger.warning("No se ha seleccionado ningún modo para guardar.")
            self.show_warning_message("Seleccione un modo de desinfección", 3000)
            return

        # 2. Obtener horas y minutos del ClickableLineEdit
        time_str = self.desinfection_time_input.text() 
        temp_str = self._desinfection_temp_input.text()
        flow_str = self._flow_bchamber.text()
        try:
            hours, minutes = map(int, time_str.split(':'))
        except ValueError:
            hours, minutes = 0, 0
            logger.error("Error al parsear el tiempo del ClickableLineEdit")
            self.show_error_message("Error al leer el tiempo, revise formato", 2000)
            return
        
        # 3. Obtener la temperatura y manejar errores de conversión
        try:
            temp = float(temp_str) # CORRECCIÓN: Usar float() para la temperatura
        except ValueError:
            temp = 0.0 # Valor por defecto o manejar error
            logger.error(f"Error al parsear la temperatura '{temp_str}'. Se usará 0.0.")
            self.show_error_message("Error al leer la temperatura, revise formato", 2000)
            return
        
        try:
            flow = float(flow_str)
        except ValueError:
            flow = 0.0
            logger.error(f"Error al parsear el flujo '{flow_str}'. Se usará 0.0.")
            self.show_error_message("Error al leer el flujo, revise formato",2000)

        # 4. Leer la configuración existente (o inicializar con valores por defecto si no existe o está incompleta)
        current_config = {
            "modes": {}, # Aseguramos que 'modes' siempre sea un diccionario vacío por defecto
            "last_active_mode_value": 0.0,
            "last_active_mode_tag": "DesinftectionMode"
        }
        
        if CONFIG_FILE_PATH.exists():
            try:
                with CONFIG_FILE_PATH.open('r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    current_config.update(loaded_data)
                    
                    if not isinstance(current_config.get("modes"), dict):
                        current_config["modes"] = {}

            except json.JSONDecodeError:
                logger.error(f"El archivo JSON de configuración {CONFIG_FILE_PATH} está corrupto. Se recreará con los valores actuales.")
                self.show_warning_message("Archivo de configuración corrupto, se recreará.", 4000)
            except Exception as e:
                logger.error(f"Error inesperado al leer JSON existente {CONFIG_FILE_PATH}: {e}")
                self.show_error_message(f"Error al leer configuración: {e}", 4000)
        
        # 5. Actualizar la configuración del modo actual
        mode_name = "Corta" if self.command_mode_value == 0.0 else "Larga"
        current_config["modes"][str(self.command_mode_value)] = {
            "time_hours": hours,
            "time_minutes": minutes,
            "mode_name": mode_name,
            "mode_temp": temp,# AÑADIDO: Guardar la 
            "mode_flow": flow,
        }
        
        # 6. Actualizar cuál fue el último modo activo
        current_config["last_active_mode_value"] = self.command_mode_value
        current_config["last_active_mode_tag"] = self.current_mode_tag

        # 7. Guardar la configuración completa en el archivo JSON
        try:
            CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

            with CONFIG_FILE_PATH.open('w', encoding='utf-8') as json_file:
                json.dump(current_config, json_file, indent=4, ensure_ascii=False)
            logger.info(f"Configuración guardada en JSON: {current_config}")
            self.show_success_message("Configuración guardada exitosamente", 2000)
        except Exception as e:
            logger.error(f"Error al guardar la configuración en JSON: {e}")
            self.show_error_message(f"Error al guardar: {e}", 3000)

    def open_time_numpad(self, time_widget, title: str = "Config. Tiempo"):
        # Se ha simplificado la firma al no usar tag_hours, tag_minutes, timer_id
        current_text = time_widget.text() if time_widget.text() else "00:00"

        dialog = TimeNumpadDialog(self, initial_hh_mm="", title=title) # Pasar el tiempo actual para editar

        if dialog.exec():
            hours, minutes = dialog.get_hours_minutes()
            time_widget.setText(f"{hours:02d}:{minutes:02d}")
            logger.debug(f"Tiempo actualizado en la pantalla: {hours:02d}:{minutes:02d}")
            
    
    def open_numpad(self, input_widget: ClickableLineEdit, title: str):
        # Tomar el valor actual del widget como valor inicial
        current_value_text = input_widget.text()
        dialog = NumpadDialog(self, initial_value="", title=title)
        if dialog.exec():
            new_value = dialog.get_value()
            if new_value is not None:
                try:
                    float_val = float(new_value)
                    input_widget.setText(f"{float_val:.1f}") # Formatear a un decimal para consistencia
                    logger.debug(f"Temperatura actualizada en la pantalla: {float_val:.1f}")
                except ValueError:
                    logger.error(f"Valor '{new_value}' no es un número válido para temperatura.")
                    self.show_warning_message("Valor de temperatura inválido", 2000)

    # Métodos show_floating_message, show_success_message, etc.
    def show_floating_message(self, text: str, timeout_ms: int = 3800):
        """Método genérico (recomendado)"""
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        
        self._floating_msg.show_floating_message(text, timeout_ms)

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



    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        is_mono = bool(tokens.get("monochrome", False))
        is_dark = bool(tokens.get("is_dark", False))

        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(tokens['bg_main']))
        self.setPalette(palette)
        self.setStyleSheet(f"background-color: {tokens['bg_main']};")

        if is_mono:
            if hasattr(self, "title_label"):
                self.title_label.setStyleSheet("color: #4B5563; font-size: 28px; font-weight: bold; background: transparent;")
            if hasattr(self, "mode_frame"):
                self.mode_frame.setStyleSheet("background: #FFFFFF; border-radius: 10px; padding: 20px; border: 1px solid #D1D5DB;")
            lbl_css = "color: #374151; font-size: 20px; font-weight: bold; background: transparent;"
            inp_css = "color: #374151; font-size: 24px; padding: 10px; border: 2px solid #C5CDD6; border-radius: 5px; background: #F8F9FA;"
            self.style_mode_unchecked = """
                QPushButton {
                    background: #D9E0E8; color: #374151; font-size: 22px; font-weight: bold;
                    border-radius: 12px; padding: 15px 25px; border: 2px solid #C5CDD6;
                }
                QPushButton:hover { background: #C5CED6; }
            """
            self.style_mode_checked = """
                QPushButton {
                    background: #9CA3AF; color: #111827; font-size: 22px; font-weight: bold;
                    border-radius: 12px; padding: 15px 25px; border: 2px solid #6B7280;
                }
            """
            save_css = """
                QPushButton { background: #D9E0E8; color: #374151; font-size: 24px; padding: 15px; border-radius: 8px; font-weight: bold; border: 2px solid #C5CDD6; }
                QPushButton:hover { background: #C5CED6; }
                QPushButton:pressed { background: #B0B8C4; }
            """

        elif is_dark:
            if hasattr(self, "title_label"):
                self.title_label.setStyleSheet(f"color: {tokens.get('text_primary', '#F8FAFC')}; font-size: 28px; font-weight: bold; background: transparent;")
            if hasattr(self, "mode_frame"):
                self.mode_frame.setStyleSheet(f"background: {tokens.get('bg_card', '#1E293B')}; border-radius: 10px; padding: 20px; border: 1px solid {tokens.get('border_card', '#334155')};")
            lbl_css = f"color: {tokens.get('text_primary', '#F8FAFC')}; font-size: 20px; font-weight: bold; background: transparent;"
            inp_css = f"color: {tokens.get('text_primary', '#F8FAFC')}; font-size: 24px; padding: 10px; border: 2px solid {tokens.get('border_input', '#334155')}; border-radius: 5px; background: {tokens.get('bg_input', '#1E293B')};"
            self.style_mode_unchecked = f"""
                QPushButton {{
                    background: {tokens.get('bg_card_alt', '#1E293B')}; color: {tokens.get('text_secondary', '#94A3B8')}; font-size: 22px; font-weight: bold;
                    border-radius: 12px; padding: 15px 25px; border: 2px solid {tokens.get('border_card', '#334155')};
                }}
                QPushButton:hover {{ background: {tokens.get('border_card', '#334155')}; }}
            """
            self.style_mode_checked = f"""
                QPushButton {{
                    background: {tokens.get('primary', '#38BDF8')}; color: #ffffff; font-size: 22px; font-weight: bold;
                    border-radius: 12px; padding: 15px 25px; border: 2px solid {tokens.get('primary_hover', '#0284C7')};
                }}
            """
            save_css = f"""
                QPushButton {{ background: {tokens.get('primary', '#38BDF8')}; color: #ffffff; font-size: 24px; padding: 15px; border-radius: 8px; font-weight: bold; }}
                QPushButton:hover {{ background: {tokens.get('primary_hover', '#0284C7')}; }}
            """

        else:
            if hasattr(self, "title_label"):
                self.title_label.setStyleSheet("color: #0f172a; font-size: 28px; font-weight: bold; background: transparent;")
            if hasattr(self, "mode_frame"):
                self.mode_frame.setStyleSheet("background: #fcfcfc; border-radius: 10px; padding: 20px; border: 1px solid #e5e5e5;")
            lbl_css = "color: #0f172a; font-size: 20px; font-weight: bold; background: transparent;"
            inp_css = "color: #0f172a; font-size: 24px; padding: 10px; border: 1px solid #ccc; border-radius: 5px; background: #FFFFFF;"
            self.style_mode_unchecked = """
                QPushButton {
                    background: #3b82f6; color: #ffffff; font-size: 22px; font-weight: bold;
                    border-radius: 12px; padding: 15px 25px; border: 2px solid #2563eb;
                }
                QPushButton:hover { background: #60a5fa; }
            """
            self.style_mode_checked = """
                QPushButton {
                    background: #22c55e; color: #ffffff; font-size: 22px; font-weight: bold;
                    border-radius: 12px; padding: 15px 25px; border: 2px solid #16a34a;
                }
            """
            save_css = """
                QPushButton { background: #06298a; color: #ffffff; font-size: 24px; padding: 15px; border-radius: 8px; font-weight: bold; }
                QPushButton:hover { background: #1e293b; }
            """

        if hasattr(self, "lbl_mode"):
            self.lbl_mode.setStyleSheet(lbl_css)
        if hasattr(self, "lbl_time"):
            self.lbl_time.setStyleSheet(lbl_css)
        if hasattr(self, "lbl_temperature"):
            self.lbl_temperature.setStyleSheet(lbl_css)
        if hasattr(self, "lbl_balance_chamber_flow"):
            self.lbl_balance_chamber_flow.setStyleSheet(lbl_css)

        for inp in (getattr(self, "desinfection_time_input", None), getattr(self, "_desinfection_temp_input", None), getattr(self, "_flow_bchamber", None)):
            if inp:
                inp.setStyleSheet(inp_css)

        if hasattr(self, "save_button"):
            self.save_button.setStyleSheet(save_css)

        for btn in (getattr(self, "_short_chemical_desinfection", None), getattr(self, "_long_chemical_desinfection", None)):
            if btn:
                btn.setStyleSheet(self.style_mode_checked if btn.isChecked() else self.style_mode_unchecked)
