from gui.theme_manager import ThemeManager
# gui/components/led.py
"""
Módulo para un widget de indicador LED simple.

Este módulo define la clase `LED`, un componente de interfaz gráfica
diseñado para simular un indicador luminoso simple (LED) en paneles de control.
Su propósito es proporcionar una retroalimentación visual rápida y clara
del estado binario (encendido/apagado) de un sensor, actuador o condición del sistema.

Características principales:
-----------------------------
- **Visualización Clara**: Muestra un círculo verde cuando está "encendido"
  y rojo cuando está "apagado", siguiendo convenciones comunes de señalización.
- **Renderizado Personalizado**: Utiliza el sistema de pintura de Qt (`QPainter`)
  para dibujar el círculo, asegurando una apariencia nítida en cualquier
  resolución.
- **Ligero y Reutilizable**: Componente minimalista y de bajo consumo de recursos,
  fácil de integrar en diferentes partes de la interfaz de usuario.
- **Control de Estado Simple**: Se gestiona mediante el método `set_state()`,
  aceptando las cadenas 'on' o 'off'.

Clase principal:
----------------
- `LED`: Widget que encapsula la lógica de dibujo y gestión del estado
  del indicador LED.

Dependencias:
-------------
- `PySide6.QtWidgets.QWidget`: Clase base para widgets.
- `PySide6.QtCore.Qt`: Para constantes de Qt.
- `PySide6.QtGui.QPainter`, `QColor`: Para el dibujo personalizado.

Uso:
----
1.  **Instanciación**:
    `my_led = LED(parent_widget)`
2.  **Configuración de Estado**:
    `my_led.set_state('on')`  # El LED se encenderá (verde)
    `my_led.set_state('off')` # El LED se apagará (rojo)
3.  **Consulta de Estado**:
    `current_status = my_led.get_state()`  # Retorna 'on' o 'off'
"""


from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor


class LED(QWidget):
    """
    Widget de indicador LED circular simple.

    Muestra un círculo verde cuando su estado es 'on' y rojo cuando es 'off'.
    Utilizado para la visualización de estados en paneles de control y diagnóstico.

    Args:
        parent (QWidget, optional): Widget padre.
    """


    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(50, 50)

        # Internal state
        self._state = 'off'  # 'on' or 'off'

        # Colors (configurable if needed later)
        self._color_on = QColor(0, 255, 0)   # Green
        self._color_off = QColor(255, 0, 0)  # Red
        try:
            ThemeManager.instance().theme_changed.connect(lambda _t: self.update())
        except Exception:
            pass

    def set_state(self, state: str):
        """
        Set LED state ('on' or 'off') and trigger repaint if changed.
        """
        if state not in ('on', 'off'):
            return  # Invalid state → ignore silently

        if self._state != state:
            self._state = state
            self.update()  # Request repaint

    def get_state(self) -> str:
        """Return current LED state ('on' or 'off')."""
        return self._state

    def paintEvent(self, event):
        """Custom painting: draw colored circle with antialiasing."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Select color based on state and theme
        tokens = ThemeManager.get_tokens()
        if bool(tokens.get("monochrome", False)):
            # Encendido: gris oscuro (#374151 / #4B5563), Apagado: gris claro (#D1D5DB / #E5E7EB)
            color = QColor("#374151") if self._state == 'on' else QColor("#D1D5DB")
        else:
            color = self._color_on if self._state == 'on' else self._color_off

        # Draw filled circle (centered, 30px diameter)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(10, 10, 30, 30)  # Margen 10px para centrar

        painter.end()