# gui/components/floating_message.py

import time
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import QTimer, Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QGuiApplication


class FloatingMessage(QLabel):
    """Mensaje flotante estilo Toast/Notification con diferentes tipos"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        # self.setAttribute(Qt.WA_TranslucentBackground)

        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide_message)
        self._animation = None
        self._supports_opacity_animation = QGuiApplication.platformName() not in {
            "wayland", "offscreen", "minimal"
        }
        self._last_message_key = None
        self._last_message_ts = 0

    def _show_message(self, text: str, timeout_ms: int, bg_color: str, border_color: str, emoji: str = ""):
        """Método interno para mostrar mensaje con estilo personalizado"""
        now_ms = int(time.monotonic() * 1000)
        message_key = f"{text}|{bg_color}|{border_color}|{emoji}"
        if self._last_message_key == message_key and abs(now_ms - self._last_message_ts) < 2500:
            return

        self._last_message_key = message_key
        self._last_message_ts = now_ms

        full_text = f"{emoji}  {text}" if emoji else text
        self.setText(full_text)
        
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: #ffffff;
                border: 3px solid {border_color};
                border-radius: 18px;
                padding: 22px 35px;
                font-size: 32px;
                font-weight: bold;
            }}
        """)
        
        self.adjustSize()
        # self.setFixedWidth(min(self.width() + 60, 880))
        self.setFixedWidth(1000)
        

      

        # self.move(x, y)
        if self.parent():
            # Obtener el punto 0,0 del padre en coordenadas de la pantalla global
            global_pos = self.parent().mapToGlobal(self.parent().rect().topLeft())
            
            x = global_pos.x() + (self.parent().width() - self.width()) // 2
            y = global_pos.y() + (self.parent().height() - self.height()) // 2 - 80
            self.move(x, y)
        self.show()
        self.fade_in()

        self.timer.start(timeout_ms)

    def show_success_message(self, text: str, timeout_ms: int = 4000):
        """Mensaje de éxito (verde)"""
        self._show_message(
            text, 
            timeout_ms,
            bg_color="rgba(16, 185, 129, 0.96)",   # Emerald
            border_color="#10b981",
            emoji="✅"
        )

    def show_info_message(self, text: str, timeout_ms: int = 3800):
        """Mensaje informativo (azul)"""
        self._show_message(
            text, 
            timeout_ms,
            bg_color="#1a3561",
            border_color="#1a3561",
            emoji="ℹ️"
        )

    def show_warning_message(self, text: str, timeout_ms: int = 4500):
        """Mensaje de advertencia (naranja)"""
        self._show_message(
            text, 
            timeout_ms,
            bg_color="rgba(245, 158, 11, 0.96)",   # Amber
            border_color="#f59e0b",
            emoji="⚠️"
        )
    def show_error_message(self, text: str, timeout_ms: int = 10000):
        """❌ Error (Rojo)"""
        self._show_message(text, timeout_ms, 
                          bg_color="rgba(239, 68, 68, 0.96)", 
                          border_color="#ef4444", 
                          emoji="❌")

    def show_floating_message(self, text: str, timeout_ms: int = 3800):
        """Método genérico (azul por defecto)"""
        self.show_info_message(text, timeout_ms)

    def fade_in(self):
        if not self._supports_opacity_animation:
            return

        self.setWindowOpacity(0.0)
        self._animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._animation.setDuration(280)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.InOutQuad)
        self._animation.start()

    def hide_message(self):
        if not self._supports_opacity_animation:
            self.hide()
            return

        if self._animation is not None:
            self._animation.stop()

        self._animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._animation.setDuration(350)
        self._animation.setStartValue(1.0)
        self._animation.setEndValue(0.0)
        self._animation.setEasingCurve(QEasingCurve.InOutQuad)
        self._animation.finished.connect(self.hide)
        self._animation.start()


