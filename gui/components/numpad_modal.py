# gui/components/numpad_modal.py
"""
Módulo que implementa un diálogo de teclado numérico modal y táctil.

Este módulo define la clase `NumpadDialog`, una ventana emergente diseñada
específicamente para dispositivos con pantalla táctil donde el uso de un
teclado físico no es posible o deseable. Permite al usuario ingresar valores
numéricos (enteros o decimales) de forma segura y controlada.

Características principales:
-----------------------------
- **Interfaz Táctil Optimizada**: Botones grandes, espaciados y de fácil
  pulsación para evitar errores de entrada.
- **Modalidad**: Se ejecuta como un diálogo modal (`QDialog.exec()`), bloqueando
  el resto de la interfaz hasta que el usuario acepte o cancele, asegurando
  el foco en la tarea de entrada de datos.
- **Sin Bordes del SO**: Utiliza `FramelessWindowHint` para integrarse
  visualmente con la estética de la aplicación HMI, eliminando barras de título
  del sistema operativo.
- **Soporte Decimal**: Permite la entrada de números decimales (punto flotante)
  con validación básica para evitar múltiples puntos.
- **Tipado Dinámico de Retorno**: El método `get_value()` devuelve inteligentemente
  un `int` o un `float` según lo que el usuario haya escrito, facilitando
  su uso con diferentes tipos de variables del sistema.
- **Estilo Visual**: Implementa un tema oscuro ("Dark Mode") consistente con
  el resto de la aplicación médica.

Clase principal:
----------------
- `NumpadDialog`: El widget del diálogo que contiene la lógica de entrada
  y la disposición visual.

Dependencias:
-------------
- `PySide6.QtWidgets`: Componentes básicos de UI.
- `PySide6.QtCore`: Flags de ventana y alineación.
- `PySide6.QtGui`: Fuentes.

Uso:
----
Generalmente se invoca desde un evento de clic en un campo editable:

    dialog = NumpadDialog(parent, initial_value="12.5", title="Flujo de Sangre")
    if dialog.exec():
        valor = dialog.get_value()
        # valor será int(12) o float(12.5) dependiendo de la entrada
"""


from PySide6.QtWidgets import (
    QDialog, QGridLayout, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout,QLabel
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from gui.components.floating_message import FloatingMessage
# from pyqtgraph import colors


class NumpadDialog(QDialog):
    """
    Diálogo modal con teclado numérico virtual.

    Proporciona una interfaz limpia para la entrada de números. Incluye un
    título descriptivo, una pantalla de visualización del valor actual,
    una cuadrícula de botones numéricos (0-9, punto, retroceso) y botones
    de acción (Aceptar/Cancelar).

    Args:
        parent (QWidget, optional): Widget padre del diálogo.
        initial_value (str, optional): Valor inicial a mostrar en la pantalla
                                       al abrir el diálogo. Por defecto "".
        title (str, optional): Título descriptivo que aparece en la cabecera
                               (ej. "Configurar Temperatura"). Por defecto "Ingrese Valor".

    Métodos:
        get_value() -> Union[int, float]: Retorna el valor ingresado convertido
                                          al tipo numérico apropiado. Retorna 0
                                          si la entrada está vacía o es inválida.
    """

    # ══════════════════════════════════════════════════════════════════════
    # DEFINICIÓN DE TEMAS
    # ══════════════════════════════════════════════════════════════════════
    THEMES = {
        "light": {
            "dialog_bg": "#ebebeb",
            "dialog_border": "#9ca3af",
            "title_bg": "#ebebeb",
            "title_color": "#1e293b",
            "display_bg": "#ffffff",
            "display_color": "#1e293b",
            "display_border": "#9ca3af",
            "button_bg": "#f3f4f6",
            "button_color": "#1e293b",
            "button_border": "#d1d5db",
            "button_hover": "#e5e7eb",
            "backspace_bg": "#fca5a5",
            "backspace_color": "#7f1d1d",
            "backspace_hover": "#f87171",
            "backspace_pressed": "#ef4444", 
        },
        "dark": {
            "dialog_bg": "#1e293b",
            "dialog_border": "#334155",
            "title_bg": "#0f172a",
            "title_color": "#ffffff",
            "display_bg": "#0f172a",
            "display_color": "#22d3ee",
            "display_border": "#475569",
            "button_bg": "#334155",
            "button_color": "#ffffff",
            "button_border": "#1e293b",
            "button_hover": "#475569",
            "backspace_bg": "#ef4444",
            "backspace_color": "#ffffff",
            "backspace_hover": "#dc2626",
            "backspace_pressed": "#b91c1c",  
        }
    }


    def __init__(self, parent=None, initial_value: str = "", title: str = "Ingrese Valor", theme: str = "light", allow_negative: bool = False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.theme = theme  # ← AGREGAR
        self.allow_negative = bool(allow_negative)
        colors = self.THEMES[theme]  # ← AGREGAR


        # Frameless + modal for full touch experience
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)

    
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['dialog_bg']};
                border: 2px solid {colors['dialog_border']};
                border-radius: 12px;
            }}
                QLabel {{ color: {colors['title_color']}; }}
        """)


        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # ── Título personalizado ──────────────────────────────────────────────────
        title_label = QLabel(title)  # Usa el parámetro title que pasas al __init__
        title_label.setAlignment(Qt.AlignCenter)
 
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {colors['title_color']};
                font-size: 24px;
                font-weight: bold;
                background-color: {colors['title_bg']};
                padding: 12px;
                border: 2px solid {colors['dialog_border']};
            }}
        """)

        main_layout.addWidget(title_label)

        # ── Display (read-only value preview) ────────────────────────────────────
        self.display = QLineEdit(initial_value)
        self.display.setFixedHeight(70)
        self.display.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.display.setReadOnly(True)
        self.display.setFont(QFont("Arial", 36, QFont.Bold))
        self.display.setStyleSheet(f"""
            QLineEdit {{
                font-size: 36px;
                font-family: "Arial";
                font-weight: bold;                background-color: {colors['display_bg']};
                color: {colors['display_color']};
                border: 2px solid {colors['display_border']};
                border-radius: 10px;
                padding: 0 15px;
            }}
        """)

        main_layout.addWidget(self.display)

        # ── Keypad Grid ──────────────────────────────────────────────────────────
        keypad_layout = QGridLayout()
        keypad_layout.setSpacing(12)

        if self.allow_negative:
            keys = [
                ('1', 0, 0), ('2', 0, 1), ('3', 0, 2),
                ('4', 1, 0), ('5', 1, 1), ('6', 1, 2),
                ('7', 2, 0), ('8', 2, 1), ('9', 2, 2),
                ('+/−', 3, 0), ('.', 3, 1), ('0', 3, 2), ('⌫', 3, 3)
            ]
        else:
            keys = [
                ('1', 0, 0), ('2', 0, 1), ('3', 0, 2),
                ('4', 1, 0), ('5', 1, 1), ('6', 1, 2),
                ('7', 2, 0), ('8', 2, 1), ('9', 2, 2),
                ('.', 3, 0), ('0', 3, 1), ('⌫', 3, 2)
            ]

        button_font = QFont("Arial", 32, QFont.Bold)

        for key, row, col in keys:
            btn = QPushButton(key)
            btn.setFixedSize(90, 90)
            btn.setFont(button_font)

            if key == '⌫':
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {colors['backspace_bg']};
                        color: {colors['backspace_color']};
                        border-radius: 12px;
                        border: none;
                    }}
                    QPushButton:hover {{ background-color: {colors['backspace_hover']}; }}
                    QPushButton:pressed {{ background-color: {colors['backspace_pressed']}; }}
                """)
                btn.clicked.connect(self._backspace)  # ← AGREGAR

            else:
                
                btn.setStyleSheet(f"""
                    QPushButton {{
                        font-size: 32px;
                        font-family: "Arial";
                        font-weight: bold;                                  
                        background-color: {colors['button_bg']};
                        color: {colors['button_color']};
                        border-radius: 12px;
                        border: 2px solid {colors['button_border']};
                    }}
                    QPushButton:hover {{ background-color: {colors['button_hover']}; }}
                    QPushButton:pressed {{ background-color: #22d3ee; border-color: #22d3ee; }}
                """)
                if key == '+/−':
                    btn.clicked.connect(self._toggle_sign)
                else:
                    btn.clicked.connect(lambda _, k=key: self._add_digit(k))


            keypad_layout.addWidget(btn, row, col)

        main_layout.addLayout(keypad_layout)

        # ── Action Buttons (Cancel / Accept) ─────────────────────────────────────
        action_layout = QHBoxLayout()
        action_layout.setSpacing(20)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setFixedHeight(70)
        cancel_btn.setFont(QFont("Arial", 24, QFont.Bold))
        cancel_btn.setStyleSheet("""
            QPushButton {
                font-size: 24px;
                font-family: "Arial";
                font-weight: bold;
                background-color: #64748b;
                color: #ffffff;
                border-radius: 12px;
                border: none;
            }
            QPushButton:hover { background-color: #475569; }
            QPushButton:pressed { background-color: #334155; }
        """)
        cancel_btn.clicked.connect(self.reject)
        action_layout.addWidget(cancel_btn)

        accept_btn = QPushButton("ACEPTAR")
        accept_btn.setFixedHeight(70)
        accept_btn.setFont(QFont("Arial", 24, QFont.Bold))
        accept_btn.setStyleSheet("""
            QPushButton {
                font-size: 24px;
                font-family: "Arial";
                font-weight: bold;
                background-color: #22c55e;
                color: #ffffff;
                border-radius: 12px;
                border: none;
            }
            QPushButton:hover { background-color: #16a34a; }
            QPushButton:pressed { background-color: #15803d; }
        """)
        accept_btn.clicked.connect(self.accept)
        action_layout.addWidget(accept_btn)

        main_layout.addLayout(action_layout)

    def _toggle_sign(self):
        """Alterna el signo cuando allow_negative es verdadero."""
        if not self.allow_negative:
            return
        current_text = self.display.text()
        if current_text.startswith("-"):
            self.display.setText(current_text[1:])
        else:
            self.display.setText("-" + current_text)

    def _add_digit(self, digit: str):
        """Append digit or decimal point to display."""
        if digit in ("+/−", "+/-", "-"):
            self._toggle_sign()
            return

        current_text = self.display.text()

        # Prevent multiple decimal points
        if digit == '.' and '.' in current_text:
            return

        # Replace leading zero with new digit (unless it's a decimal)
        if current_text == "0" and digit != ".":
            current_text = ""
        elif current_text == "-0" and digit != ".":
            current_text = "-"

        self.display.setText(current_text + digit)

    def _backspace(self):
        """Remove last character from display."""
        current_text = self.display.text()
        self.display.setText(current_text[:-1] if current_text else "")

    def get_value(self): # Ya no necesita tipo hint float
        """
        Return the entered value as float or int, depending on if it contains a decimal point.
        Returns 0 if empty or invalid.
        """
        text = self.display.text().strip()
        if not text or text in (".", "-", "-."):
            return 0 # Default to int 0 if empty/invalid

        try:
            # Si el texto contiene un punto, es un float
            if '.' in text:
                return float(text)
            # Si no contiene un punto, es un entero
            else:
                return int(text)
        except ValueError:
            return 0 # Default to int 0 if conversion fails

