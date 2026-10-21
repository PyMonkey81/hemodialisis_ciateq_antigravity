import sys
import os

# ==============================================================================
# 1. CONFIGURACIÓN DE PLATAFORMA Y HiDPI (DEBE IR ANTES DE IMPORTAR PYSIDE6)
# ==============================================================================
IS_LINUX = sys.platform.startswith("linux")
IS_WINDOWS = sys.platform.startswith("win")

# En Linux (Wayland/X11/Ubuntu Server), removemos variables heredadas de Windows
if IS_LINUX:
    os.environ.pop("QT_SCALE_FACTOR", None)
    os.environ.pop("QT_AUTO_SCREEN_SCALE_FACTOR", None)
    os.environ.pop("QT_ENABLE_HIGHDPI_SCALING", None)
    # Evita parpadeos o fallos de renderizado en servidores sin compositor gráfico complejo
    os.environ["QT_QPA_PLATFORM"] = "wayland;xcb" 

import logging
from logging.handlers import RotatingFileHandler  
import datetime

from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QWidget, QGridLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QPalette, QColor

from gui import theme_manager
from gui.appMainHemodialysis import HemodialysisHMI
from gui.theme_manager import ThemeManager
from version import __version__
from utilities.platform_runtime import is_windows, load_platform_features

LOG_DIR = os.path.join(os.path.dirname(__file__), 'var', 'log')
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, 'hemodialisis.log')

max_log_size = 5 * 1024 * 1024  # 5 MB
backup_count = 2

handler = RotatingFileHandler(LOG_FILE, maxBytes=max_log_size, backupCount=backup_count, encoding='utf-8') 
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
handler.setFormatter(formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(handler)

logger = logging.getLogger(__name__)


def detect_screen_size() -> tuple[int, int]:
    """Detecta resolucion usando Qt; si no está disponible usa una resolución segura."""
    try:
        screen_instance = QGuiApplication.primaryScreen()
        if screen_instance is not None:
            geometry = screen_instance.availableGeometry()
            return geometry.width(), geometry.height()
    except Exception:
        pass

    return 1920, 1080

def unhandled_exception_handler(exc_type, exc_value, exc_traceback):
    if exc_type is KeyboardInterrupt:
        logger.info("KeyboardInterrupt recibido - cerrando aplicación de forma controlada")
        sys.exit(0)

    import traceback as tb
    error_message = "".join(tb.format_exception(exc_type, exc_value, exc_traceback))
    logger.critical(f"Unhandled exception:\n{error_message}")
    
    app = QApplication.instance()
    if app:
        QMessageBox.critical(
            None,
            "Critical System Error - CIATEQ A.C.",
            "La aplicación ha fallado de forma inesperada.\n\n"
            "Se cerrará por seguridad.\n\n"
            "Detalles del error:\n\n" + error_message[-1000:],
            QMessageBox.Close
        )
    sys.exit(1)

class ScaledHemodialysisHMI(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.DESIGN_WIDTH = 1920
        self.DESIGN_HEIGHT = 1080
        
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setStyleSheet("background: #000000;")
        
        # Widget HMI
        self.dialysis_hmi = HemodialysisHMI()
        
        # Contenedor con QGridLayout para centrado perfecto en Linux/Windows
        self.container = QWidget(self)
        self.container_layout = QGridLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.addWidget(self.dialysis_hmi, 0, 0, Qt.AlignCenter)
        
        self.setCentralWidget(self.container)
        self.showFullScreen()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.apply_scaling()

    def apply_scaling(self):
        screen_w = self.width()
        screen_h = self.height()

        scale_w = screen_w / self.DESIGN_WIDTH
        scale_h = screen_h / self.DESIGN_HEIGHT
        scale = min(scale_w, scale_h)

        new_width = int(self.DESIGN_WIDTH * scale)
        new_height = int(self.DESIGN_HEIGHT * scale)

        # Ajustamos el tamaño del HMI y dejamos que el QGridLayout de la ventana lo centre
        self.dialysis_hmi.setFixedSize(new_width, new_height)
        
        logger.info(f"OS: {sys.platform} | Escalado aplicado: {new_width}x{new_height} en pantalla {screen_w}x{screen_h}")


if __name__ == "__main__":
    sys.excepthook = unhandled_exception_handler

    # Sobrescribir la variable de entorno que impone Hyprland/Omarchy
    os.environ.pop("QT_STYLE_OVERRIDE", None)
    os.environ["QT_STYLE_OVERRIDE"] = "Fusion"


    platform_features = load_platform_features()
    logger.info("Platform: %s | Features: %s", sys.platform, platform_features)

    use_windows_legacy_prescale = is_windows() and platform_features.get("enable_windows_legacy_prescale", True)
    if use_windows_legacy_prescale:
        os.environ["QT_SCALE_FACTOR"] = "1.0"
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
        logger.info("HiDPI mode: Windows legacy prescale activo")
    else:
        logger.info("HiDPI mode: nativo de Qt/desktop (Linux detectado)")

    QApplication.setAttribute(Qt.AA_UseStyleSheetPropagationInWidgetStyles, True)
    
    if hasattr(Qt, 'HighDpiScaleFactorRoundingPolicy'):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    theme_manager = ThemeManager(app)

    try:
        main_window = ScaledHemodialysisHMI()
        main_window.showFullScreen()

        logger.info("=" * 80)
        logger.info("   CIATEQ A.C. - HEMODIALYSIS HMI STARTED")
        logger.info(f"   Platform: {sys.platform} | Resolution: 1920x1080 (design)")
        logger.info(f"   Windows legacy prescale: {use_windows_legacy_prescale}")
        logger.info("=" * 80)

        sys.exit(app.exec())

    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        QMessageBox.critical(None, "Error Fatal", str(e))
        sys.exit(1)