from gui.theme_manager import ThemeManager
# gui/components/toggle_switch.py

"""
Módulo para un widget de interruptor tipo "toggle" animado y táctil.

Este módulo define la clase `ToggleSwitch`, un control de UI moderno y amigable
al tacto para representar estados binarios (encendido/apagado, sí/no).
Proporciona una retroalimentación visual clara mediante una animación suave
al cambiar de estado, mejorando la experiencia del usuario en interfaces HMI.

Características principales:
-----------------------------
- **Diseño Táctil**: Tamaño y estilo optimizados para ser fácilmente interactuable
  en pantallas táctiles, con un cursor de mano para indicar su interactividad.
- **Animación Suave**: Incorpora `QPropertyAnimation` y `QEasingCurve` para una
  transición visualmente agradable cuando el interruptor cambia de estado.
- **Feedback Visual Claro**: Cambia el color de fondo y la posición del círculo
  para indicar claramente el estado "on" (activado) o "off" (desactivado).
- **Altamente Configurable**: Permite personalizar el ancho, alto y los colores
  de fondo para los estados "on" y "off".
- **Control Programático**: El estado del interruptor puede ser modificado
  programáticamente mediante `setChecked()` y consultado con `is_checked()`.
- **Comunicación con Señales**: Emite una señal `toggled(bool)` cada vez que
  su estado cambia, facilitando la integración con la lógica de la aplicación.
  La señal envía un booleano (`True` para "on", `False` para "off").

Clase principal:
----------------
- `ToggleSwitch`: Un widget personalizado que implementa el interruptor tipo toggle.

Propiedades (para animación):
-----------------------------
- `circle_x` (float): Propiedad animable que controla la posición X del círculo
  interno del interruptor, utilizada por `QPropertyAnimation`.

Dependencias:
-------------
- `PySide6.QtWidgets.QWidget`: Clase base para widgets.
- `PySide6.QtCore`: Para `Qt`, `Property`, `QEasingCurve`, `QPropertyAnimation`, `Signal`.
- `PySide6.QtGui.QPainter`, `QColor`: Para el dibujo personalizado del widget.

Uso:
----
1.  **Instanciación**: Crear una instancia de `ToggleSwitch` en cualquier layout.
    Se pueden especificar `width`, `height`, `bg_color` y `active_color`.
2.  **Conexión de Señales**: Conectar la señal `toggled` a un slot que maneje
    el cambio de estado deseado en la aplicación.
    `my_toggle = ToggleSwitch()`
    `my_toggle.toggled.connect(self.handle_toggle_state)`
3.  **Control de Estado**: Usar `my_toggle.setChecked(True)` o `my_toggle.setChecked(False)`
    para cambiar el estado programáticamente. Usar `my_toggle.is_checked()` para
    consultar el estado actual.
"""


from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Property, QEasingCurve, QPropertyAnimation, Signal
from PySide6.QtGui import QPainter, QColor, QPen
import logging
logger = logging.getLogger(__name__)


class ToggleSwitch(QWidget):
    """
    Animated toggle switch widget (on/off) with smooth transition.
    Emits 'toggled' signal when state changes.
    Supports programmatic control via setChecked() and is_checked().
    """

    # Signal emitted when the toggle state changes (True = on, False = off)
    toggled = Signal(bool)

    def __init__(self,
                 parent=None,
                 width: int = 60,
                 height: int = 32,
                 bg_color: str = "#4b5563",       # Off background (gray)
                 active_color: str = "#22c55e"):  # On background (green)
        super().__init__(parent)

        self.setFixedSize(width, height)
        self.setCursor(Qt.PointingHandCursor)

        # Internal state
        self._is_checked = False
        self._bg_color_off = bg_color
        self._bg_color_on = active_color
        self._circle_color = "#ffffff"  # White circle

        # Animation setup
        self._circle_x = 4  # Initial left margin
        self.animation = QPropertyAnimation(self, b"circle_x", self)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.setDuration(300)
        try:
            ThemeManager.instance().theme_changed.connect(lambda _t: self.update())
        except Exception:
            pass  # 300ms smooth transition

    # Property for animation binding
    @Property(float)
    def circle_x(self):
        return self._circle_x

    @circle_x.setter
    def circle_x(self, value: float):
        self._circle_x = value
        self.update() 

    def mouseReleaseEvent(self, event):
        """Toggle state on left click/touch release."""
        if event.button() == Qt.LeftButton:
            self.toggle()
        super().mouseReleaseEvent(event)

    def toggle(self):
        """Toggle current state and start animation."""
        self.setChecked(not self._is_checked)

    def setChecked(self, checked: bool):
        """Programmatically set toggle state with animation."""
        if self._is_checked == checked:
            return

        self._is_checked = checked
        self.animation.stop()

        end_value = self.width() - self.height() + 4 if checked else 4
        self.animation.setEndValue(end_value)
        self.animation.start()

        self.toggled.emit(checked)
        self.update()

    def is_checked(self) -> bool:
        """Return current toggle state."""
        return self._is_checked

    def paintEvent(self, event):
        """Custom painting of background and animated circle."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. Background (rounded rect)
        tokens = ThemeManager.get_tokens()
        is_mono = bool(tokens.get("monochrome", False))
        if is_mono:
            current_bg = "#9CA3AF" if self._is_checked else "#E5E7EB"
            circle_color = "#111827" if self._is_checked else "#6B7280"
        else:
            current_bg = self._bg_color_on if self._is_checked else self._bg_color_off
            circle_color = self._circle_color

        painter.setPen(QPen(QColor("#6B7280" if is_mono else current_bg), 1) if is_mono else Qt.NoPen)
        painter.setBrush(QColor(current_bg))
        painter.drawRoundedRect(0, 0, self.width(), self.height(),
                                self.height() // 2, self.height() // 2)

        # 2. Circle (animated position)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(circle_color))
        circle_radius = self.height() - 8
        painter.drawEllipse(int(self._circle_x), 4, circle_radius, circle_radius)

        painter.end()