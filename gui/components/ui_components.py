from gui.theme_manager import ThemeManager
# gui/components/ui_components.py
"""
Módulo que contiene componentes de interfaz de usuario (UI) reutilizables
diseñados para la Interfaz Hombre-Máquina (HMI) de la máquina de hemodiálisis.

Estos componentes están optimizados para la interacción táctil y la presentación
clara de información, siguiendo un diseño cohesivo y las necesidades de seguridad
y usabilidad de un dispositivo médico.

Componentes principales:
-------------------------
- `ToggleBox`: Un widget compacto que combina una etiqueta y un `ToggleSwitch`
  para activar/desactivar funciones con un solo toque.
- `DoubleToggleBox`: Un widget que agrupa dos `ToggleBox`s para controlar
  pares de funcionalidades relacionadas (ej. habilitar y modo de un lazo de control).
- `ClickableLineEdit`: Una `QLineEdit` de solo lectura que emite una señal
  `clicked` al ser tocada, ideal para disparar teclados virtuales (numpads, QWERTY).
- `LabeledParameterWidget`: Un widget compuesto que muestra un parámetro
  con su etiqueta, valor y unidades. Puede ser editable (dispara numpad)
  o de solo lectura.
- `LabeledTimeInput`: Un widget compuesto similar al anterior, pero especializado
  para la entrada y visualización de tiempos en formato HH:MM, también con
  capacidad de disparar un teclado numérico de tiempo.
- `show_dark_message`: Una función auxiliar para mostrar mensajes modales
  (`QMessageBox`) con un estilo oscuro consistente, útil para alertas y
  confirmaciones.

Funcionalidades clave:
----------------------
- **Optimización Táctil**: Todos los componentes de entrada están diseñados
  para ser usados con teclados virtuales, mejorando la seguridad (no se usa
  teclado físico) y la usabilidad en pantallas táctiles.
- **Coherencia Visual**: Mantienen un estilo visual uniforme con la estética
  general de la HMI.
- **Reusabilidad**: Diseñados para ser fácilmente reutilizables en diferentes
  pantallas de la aplicación, promoviendo la consistencia del código y la UI.
- **Manejo de Señales**: Utilizan el sistema de señales/slots de PySide6 para
  comunicarse con otros componentes y la lógica de la aplicación.
"""


from PySide6.QtWidgets import (
    QLineEdit, QSizePolicy, QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QMessageBox
from gui.components.ToggleSwitch import ToggleSwitch
import logging
logger = logging.getLogger(__name__)


class ToggleBox(QFrame):
    """
    Componente reutilizable que combina una etiqueta y un `ToggleSwitch`.

    Ideal para presentar una opción de activación/desactivación de forma compacta
    y visualmente atractiva. Muestra una etiqueta descriptiva y permite al usuario
    cambiar el estado de un interruptor con un toque.

    Args:
        label (str): Texto descriptivo que se mostrará junto al interruptor.
        parent (QWidget, optional): El widget padre de este componente.

    Atributos:
        toggle (ToggleSwitch): La instancia del interruptor `ToggleSwitch` que
                               gestiona el estado ON/OFF. Se puede acceder a sus
                               señales (`toggled`) para conectar la lógica de la aplicación.
    """

    def __init__(self, label, parent=None):
        super().__init__(parent)

        self.setStyleSheet("""
            QFrame {
                background-color: #fcfcfc;
                border-radius: 8px;
                border: 1px solid #334155;
            }
        """)
        self.setFixedHeight(80)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        lbl_info = QLabel(f"<b>{label}</b>")
        lbl_info.setStyleSheet("color: #000000; font-size: 18px; border:none; background: transparent;")
        lbl_info.setAlignment(Qt.AlignLeft | Qt.AlignCenter)

        self.toggle = ToggleSwitch(width=60, height=30)

        layout.addWidget(lbl_info)
        layout.addStretch()
        layout.addWidget(self.toggle)
        



class DoubleToggleBox(QFrame):
    """
    Componente reutilizable que agrupa dos `ToggleSwitch`s con sus respectivas etiquetas.

    Útil para controlar dos funcionalidades relacionadas en un espacio compacto,
    como la habilitación de un lazo de control y su modo de operación (manual/automático).

    Args:
        label1_text (str): Texto para la etiqueta del primer interruptor.
        label2_text (str): Texto para la etiqueta del segundo interruptor.
        parent (QWidget, optional): El widget padre de este componente.

    Atributos:
        toggle1 (ToggleSwitch): La instancia del primer interruptor `ToggleSwitch`.
        toggle2 (ToggleSwitch): La instancia del segundo interruptor `ToggleSwitch`.
    """
    def __init__(self, label1_text, label2_text, parent=None):
        super().__init__(parent)

        self.setStyleSheet("""
            QFrame {
                background-color: #f0f4f8; /* Un fondo ligeramente diferente para destacar */
                border-radius: 8px;
                border: 1px solid #334155;
            }
        """)
        self.setFixedHeight(120) # Ajusta la altura si es necesario para acomodar dos filas

        # Layout principal de la DoubleToggleBox (vertical)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5) # Menos espacio vertical entre las filas

        # --- Primera Fila: Label 1 y Toggle 1 ---
        row1_layout = QHBoxLayout()
        self.lbl1 = QLabel(f"<b>{label1_text}</b>")
        self.lbl1.setStyleSheet("color: #000000; font-size: 16px; border:none; background: transparent;")
        self.lbl1.setAlignment(Qt.AlignLeft | Qt.AlignCenter)
        self.toggle1 = ToggleSwitch(width=60, height=30) # Almacenar como atributo

        row1_layout.addWidget(self.lbl1)
        row1_layout.addStretch()
        row1_layout.addWidget(self.toggle1)
        main_layout.addLayout(row1_layout)

        # --- Segunda Fila: Label 2 y Toggle 2 ---
        row2_layout = QHBoxLayout()
        self.lbl2 = QLabel(f"<b>{label2_text}</b>")
        self.lbl2.setStyleSheet("color: #000000; font-size: 16px; border:none; background: transparent;")
        self.lbl2.setAlignment(Qt.AlignLeft | Qt.AlignCenter)
        self.toggle2 = ToggleSwitch(width=60, height=30) # Almacenar como atributo

        row2_layout.addWidget(self.lbl2)
        row2_layout.addStretch()
        row2_layout.addWidget(self.toggle2)
        main_layout.addLayout(row2_layout)

        self.apply_theme_styles()
        try:
            ThemeManager.instance().theme_changed.connect(lambda _t: self.apply_theme_styles())
        except Exception:
            pass

    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        is_mono = bool(tokens.get("monochrome", False))
        is_dark = bool(tokens.get("is_dark", False))
        if is_mono:
            self.setStyleSheet("""
                QFrame {
                    background-color: #FFFFFF;
                    border-radius: 8px;
                    border: 1px solid #D1D5DB;
                }
            """)
            lbl_css = "color: #374151; font-size: 16px; border:none; background: transparent;"
        elif is_dark:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {tokens.get('bg_card', '#1E293B')};
                    border-radius: 8px;
                    border: 1px solid {tokens.get('border_card', '#334155')};
                }}
            """)
            lbl_css = f"color: {tokens.get('text_primary', '#F8FAFC')}; font-size: 16px; border:none; background: transparent;"
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #f0f4f8;
                    border-radius: 8px;
                    border: 1px solid #334155;
                }
            """)
            lbl_css = "color: #000000; font-size: 16px; border:none; background: transparent;"

        if hasattr(self, "lbl1"):
            self.lbl1.setStyleSheet(lbl_css)
        if hasattr(self, "lbl2"):
            self.lbl2.setStyleSheet(lbl_css)





class ClickableLineEdit(QLineEdit):
    """
    Una subclase de QLineEdit que es de solo lectura y emite una señal `clicked`
    cuando se pulsa con el ratón o se toca.

    Esta implementación es fundamental para interfaces táctiles de grado médico,
    donde la entrada manual directa de texto puede ser insegura o propensa a errores.
    Al ser de solo lectura, la entrada de valores se delega a teclados virtuales
    (como un `NumpadDialog`), que se disparan mediante la señal `clicked`.

    Señales:
        clicked: Emitida cuando el QLineEdit es pulsado (clic izquierdo del ratón
                 o toque en pantalla táctil).
    """

    clicked = Signal()

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setReadOnly(True)  # Force keypad input (medical safety)
        self.setCursor(Qt.PointingHandCursor)  # Visual cue (touch-friendly)

    def mousePressEvent(self, event):
        """Emit clicked signal on left mouse/touch press."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)






class LabeledParameterWidget(QWidget):
    """
    Un widget compuesto y reutilizable para la visualización y/o entrada
    de un parámetro numérico con una etiqueta descriptiva y unidades.

    Métodos:
        set_value(value): Actualiza el valor mostrado, aplicando un formato
                          numérico consistente (1 o 2 decimales según el valor).
        get_value() -> str: Retorna el texto actual del valor mostrado.
    """

    
    request_numpad = Signal(str, object, str)

    def __init__(self,
                 label_text: str, # label_text: str,
                 tag: str = None, #               tag: str = None,
                 value: str = "",
                 units: str = "",
                 numpad_title: str = "",
                 is_editable: bool = True,
                 parent=None):
        super().__init__(parent)

        
        indicator_style = "color: #22d3ee; font-size: 26px; font-weight: bold; border: 2px solid #000000; border-radius: 5px; padding: 2px;"
        input_style = """
            background: #FFFFE5; color: #000000; font-size: 26px; font-weight: bold;
            border: 2px solid #000000; border-radius: 5px; padding: 4px;
        """

        # self.setFixedHeight(100)  # Consistent touch target size
        self._tag = tag
        self._numpad_title = numpad_title or label_text

        # Container frame
        self.frame = QFrame(self)
        self.frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.frame)

        # Inner layout
        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(1)

        # Header label (description + units)
        header_text = f"{label_text} ({units})" if units else label_text
        self.header_label = QLabel(header_text)
        self.header_label.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.header_label.setStyleSheet("""
            background: transparent;
            border: none;
            color: #333333;
            font-weight: bold;
            font-size: 18px;
        """)

        # Value widget (editable or read-only)
        if is_editable:
            self.value_widget = ClickableLineEdit(value)
            self.value_widget.setStyleSheet(input_style)
            self.value_widget.setMinimumWidth(80)
            self.value_widget.setFixedHeight(40)
            self.value_widget.setAlignment(Qt.AlignCenter)
            self.value_widget.clicked.connect(self._emit_numpad_request)
        else:
            self.value_widget = QLabel(value)
            self.value_widget.setStyleSheet(indicator_style)      
            self.value_widget.setMinimumWidth(80)
            self.value_widget.setFixedHeight(40)
            self.value_widget.setAlignment(Qt.AlignCenter)

        frame_layout.addWidget(self.header_label)
        frame_layout.addWidget(self.value_widget)

        self.is_editable = is_editable
        self.apply_theme_styles()
        try:
            ThemeManager.instance().theme_changed.connect(lambda _t: self.apply_theme_styles())
        except Exception:
            pass

    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens()
        is_mono = bool(tokens.get("monochrome", False))
        is_dark = bool(tokens.get("is_dark", False))
        if is_mono:
            inp_style = (
                "background: #F8F9FA; color: #374151; font-size: 26px; font-weight: bold; "
                "border: 2px solid #C5CDD6; border-radius: 5px; padding: 4px;"
            )
            ind_style = (
                "color: #374151; font-size: 26px; font-weight: bold; "
                "border: 2px solid #C5CDD6; border-radius: 5px; padding: 2px; background: #FFFFFF;"
            )
            hdr_style = "background: transparent; border: none; color: #4B5563; font-weight: bold; font-size: 18px;"
        elif is_dark:
            inp_style = f"background: {tokens.get('bg_input', '#1E293B')}; color: {tokens.get('text_primary', '#F8FAFC')}; font-size: 26px; font-weight: bold; border: 2px solid {tokens.get('border_input', '#334155')}; border-radius: 5px; padding: 4px;"
            ind_style = f"color: {tokens.get('primary', '#38BDF8')}; font-size: 26px; font-weight: bold; border: 2px solid {tokens.get('border_card', '#334155')}; border-radius: 5px; padding: 2px; background: {tokens.get('bg_card_alt', '#1E293B')};"
            hdr_style = f"background: transparent; border: none; color: {tokens.get('text_secondary', '#94A3B8')}; font-weight: bold; font-size: 18px;"
        else:
            inp_style = "background: #FFFFE5; color: #000000; font-size: 26px; font-weight: bold; border: 2px solid #000000; border-radius: 5px; padding: 4px;"
            ind_style = "color: #22d3ee; font-size: 26px; font-weight: bold; border: 2px solid #000000; border-radius: 5px; padding: 2px;"
            hdr_style = "background: transparent; border: none; color: #333333; font-weight: bold; font-size: 18px;"

        self.header_label.setStyleSheet(hdr_style)
        if getattr(self, "is_editable", False):
            self.value_widget.setStyleSheet(inp_style)
        else:
            self.value_widget.setStyleSheet(ind_style)
    def _emit_numpad_request(self):
        """Internal handler to emit numpad request signal."""
        self.request_numpad.emit(self._tag, self, self._numpad_title)

    def set_value(self, value):
        """Update displayed value with safe formatting."""
        try:
            if isinstance(value, (int, float)):
                # Consistent medical formatting: 1 decimal if >=10, 2 if <10
                display_text = f"{value:.1f}" if value >= 10 else f"{value:.2f}"
            else:
                display_text = str(value)

            if isinstance(self.value_widget, QLineEdit):
                self.value_widget.setText(display_text)
            elif isinstance(self.value_widget, QLabel):
                self.value_widget.setText(display_text)

        except Exception as e:
            print(f"[ERROR] Failed to set value in LabeledParameterWidget: {e}")
            fallback = "ERR"
            if isinstance(self.value_widget, QLineEdit):
                self.value_widget.setText(fallback)
            elif isinstance(self.value_widget, QLabel):
                self.value_widget.setText(fallback)

    def get_value(self) -> str:
        """Return current text value."""
        if isinstance(self.value_widget, QLineEdit):
            return self.value_widget.text()
        elif isinstance(self.value_widget, QLabel):
            return self.value_widget.text()
        return ""


class LabeledTimeInput(QWidget):
    """
    Un widget compuesto y reutilizable para la visualización y/o entrada
    de valores de tiempo en formato HH:MM, con una etiqueta descriptiva.
    Métodos:
        set_time_value(hours, minutes): Actualiza el tiempo mostrado a "HH:MM".
        get_time_value() -> str: Retorna el texto actual del tiempo como "HH:MM".
        get_hours_minutes() -> tuple[int, int]: Parsea el tiempo mostrado y lo retorna como `(horas, minutos)`.
    """
    request_time_numpad = Signal(object, str, str, str, str)

    def __init__(self,
                 label_text: str,
                 initial_hh_mm: str = "00:00",
                 tag_hours: str = None,
                 tag_minutes: str = None,
                 local_timer_id: str = None,
                 numpad_title: str = "",
                 is_editable: bool = True,
                 parent=None):
        super().__init__(parent)

        # self.setFixedHeight(90)
        self._tag_hours = tag_hours
        self._tag_minutes = tag_minutes
        self._local_timer_id = local_timer_id
        self._numpad_title = numpad_title or label_text

        indicator_style = "color: #22d3ee; font-size: 26px; font-weight: bold; border: 2px solid #000000; border-radius: 5px; padding: 2px;"
        input_style = """
            background: #FFFFE5; color: #000000; font-size: 26px; font-weight: bold;
            border: 2px solid #000000; border-radius: 5px; padding: 4px;
        """

        # Container frame
        self.frame = QFrame(self)
        self.frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.frame)

        # Inner layout
        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(1)

        # Header label
        self.header_label = QLabel(label_text)
        self.header_label.setAlignment(Qt.AlignCenter)
        self.header_label.setStyleSheet("""
            background: transparent;
            border: none;
            color: #333333;
            font-weight: bold;
            font-size: 20px;
        """)

        # Clickable time display
        if is_editable:
            self.time_display = ClickableLineEdit(initial_hh_mm)
            self.time_display.setStyleSheet(input_style)
            self.time_display.setReadOnly(True)
            self.time_display.setMinimumWidth(80)
            self.time_display.setFixedHeight(40)
            self.time_display.setAlignment(Qt.AlignCenter)
            self.time_display.clicked.connect(self._emit_time_numpad_request)
        else:
            self.time_display = QLabel(initial_hh_mm)
            self.time_display.setStyleSheet(indicator_style)
            self.time_display.setMinimumWidth(80)
            self.time_display.setFixedHeight(40)
            self.time_display.setAlignment(Qt.AlignCenter)
            

        frame_layout.addWidget(self.header_label)
        self.is_editable = is_editable
        frame_layout.addWidget(self.time_display)
        self.apply_theme_styles()
        try:
            ThemeManager.instance().theme_changed.connect(lambda _t: self.apply_theme_styles())
        except Exception:
            pass

    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        is_mono = bool(tokens.get("monochrome", False))
        is_dark = bool(tokens.get("is_dark", False))
        if is_mono:
            self.setStyleSheet("""
                QFrame {
                    background-color: #FFFFFF;
                    border-radius: 8px;
                    border: 1px solid #D1D5DB;
                }
            """)
            lbl_css = "color: #374151; font-size: 16px; border:none; background: transparent;"
        elif is_dark:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {tokens.get('bg_card', '#1E293B')};
                    border-radius: 8px;
                    border: 1px solid {tokens.get('border_card', '#334155')};
                }}
            """)
            lbl_css = f"color: {tokens.get('text_primary', '#F8FAFC')}; font-size: 16px; border:none; background: transparent;"
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #f0f4f8;
                    border-radius: 8px;
                    border: 1px solid #334155;
                }
            """)
            lbl_css = "color: #000000; font-size: 16px; border:none; background: transparent;"

        if hasattr(self, "lbl1"):
            self.lbl1.setStyleSheet(lbl_css)
        if hasattr(self, "lbl2"):
            self.lbl2.setStyleSheet(lbl_css)

    def _emit_time_numpad_request(self):
        """Internal handler to emit time numpad request signal."""
        self.request_time_numpad.emit(
            self,
            self._tag_hours,
            self._tag_minutes,
            self._local_timer_id,
            self._numpad_title
        )

    def set_time_value(self, hours: int, minutes: int):
        """Update displayed time in HH:MM format."""
        self.time_display.setText(f"{hours:02d}:{minutes:02d}")

    def get_time_value(self) -> str:
        """Return current displayed time as HH:MM string."""
        return self.time_display.text()

    def get_hours_minutes(self) -> tuple[int, int]:
        """Parse displayed time into (hours, minutes)."""
        try:
            h_str, m_str = self.time_display.text().split(':')
            return int(h_str), int(m_str)
        except ValueError:
            print(f"[ERROR] Invalid time format in LabeledTimeInput: {self.time_display.text()}")
#             return 0, 0




    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        is_mono = bool(tokens.get("monochrome", False))
        is_dark = bool(tokens.get("is_dark", False))

        if is_mono:
            inp_style = (
                "background: #F8F9FA; color: #374151; font-size: 26px; font-weight: bold; "
                "border: 2px solid #C5CDD6; border-radius: 5px; padding: 4px;"
            )
            ind_style = (
                "color: #374151; font-size: 26px; font-weight: bold; "
                "border: 2px solid #C5CDD6; border-radius: 5px; padding: 2px; background: #FFFFFF;"
            )
            hdr_style = "background: transparent; border: none; color: #4B5563; font-weight: bold; font-size: 20px;"
        elif is_dark:
            inp_style = f"background: {tokens.get('bg_input', '#1E293B')}; color: {tokens.get('text_primary', '#F8FAFC')}; font-size: 26px; font-weight: bold; border: 2px solid {tokens.get('border_input', '#334155')}; border-radius: 5px; padding: 4px;"
            ind_style = f"color: {tokens.get('primary', '#38BDF8')}; font-size: 26px; font-weight: bold; border: 2px solid {tokens.get('border_card', '#334155')}; border-radius: 5px; padding: 2px; background: {tokens.get('bg_card_alt', '#1E293B')};"
            hdr_style = f"background: transparent; border: none; color: {tokens.get('text_secondary', '#94A3B8')}; font-weight: bold; font-size: 20px;"
        else:
            inp_style = (
                "background: #FFFFE5; color: #000000; font-size: 26px; font-weight: bold; "
                "border: 2px solid #000000; border-radius: 5px; padding: 4px;"
            )
            ind_style = "color: #22d3ee; font-size: 26px; font-weight: bold; border: 2px solid #000000; border-radius: 5px; padding: 2px;"
            hdr_style = "background: transparent; border: none; color: #333333; font-weight: bold; font-size: 20px;"

        if hasattr(self, "header_label"):
            self.header_label.setStyleSheet(hdr_style)
        if hasattr(self, "time_display"):
            if self.is_editable:
                self.time_display.setStyleSheet(inp_style)
            else:
                self.time_display.setStyleSheet(ind_style)


def show_dark_message(parent, title: str, text: str, icon=QMessageBox.Information, buttons=QMessageBox.Ok):
    """
    Muestra un diálogo de mensaje (`QMessageBox`) con un estilo oscuro consistente.

    Esta función estiliza el `QMessageBox` para que coincida con la estética
    general de la HMI, asegurando que los mensajes del sistema sean visualmente
    coherentes. Es útil para mostrar alertas, advertencias, errores o
    información al usuario.

    Args:
        parent (QWidget): El widget padre del `QMessageBox`.
        title (str): El título del cuadro de mensaje.
        text (str): El contenido principal del mensaje.
        icon (QMessageBox.Icon, optional): El icono a mostrar en el mensaje
            (ej. `QMessageBox.Information`, `QMessageBox.Warning`, `QMessageBox.Critical`).
            Por defecto: `QMessageBox.Information`.
        buttons (QMessageBox.StandardButtons, optional): Los botones a mostrar
            en el mensaje (ej. `QMessageBox.Ok`, `QMessageBox.Yes | QMessageBox.No`).
            Por defecto: `QMessageBox.Ok`.

    Returns:
        int: El valor del botón que el usuario ha pulsado
             (ej. `QMessageBox.Ok`, `QMessageBox.Yes`).
    """
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(icon)
    msg.setStandardButtons(buttons)
    msg.setDefaultButton(QMessageBox.Ok if buttons & QMessageBox.Ok else QMessageBox.Yes)

    msg.setStyleSheet("""
        QMessageBox {
            background-color: #2b2b2b;
        }
        QLabel {
            color: #ffffff;
            background-color: #2b2b2b;
            padding: 10px;
            min-width: 350px;
        }
        QPushButton {
            background-color: #4CAF50;
            color: #ffffff;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            min-width: 100px;
            font-weight: bold;
        }
        QPushButton:hover { background-color: #45a049; }
        QPushButton:pressed { background-color: #3e8e41; }
    """)

    return msg.exec()