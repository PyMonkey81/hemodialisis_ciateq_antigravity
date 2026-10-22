"""
Smoke test de renderizado e integridad de paintEvent para todas las pantallas y temas.

Lanza un subproceso por cada combinacion (pantalla, tema) para aislar posibles
fallos de segmentacion o 'Recursive repaint detected' sin afectar la sesion completa de pytest.
No requiere hardware ni abre puertos seriales.
"""

import os
import sys
import subprocess
import traceback
from typing import Tuple, List
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

THEMES: List[str] = [
    "Clínico Claro",
    "Escala de grises",
    "Modo Oscuro UCI",
    "Azul Biomédico",
    "Alto Contraste",
]

SCREENS: List[Tuple[str, str]] = [
    ("Inicio", "show_home_screen"),
    ("Diálisis", "show_dialysis_screen"),
    ("Tipo de Tratamiento", "show_treatment_mode_screen"),
    ("Configuración de terapia", "show_therapy_config_screen"),
    ("Perfil UF", "show_uf_profile_screen"),
    ("Perfil Na+", "show_conductivity_profile_screen"),
    ("Paciente", "show_patient_config_screen"),
    ("Heparina", "show_heparin_config_screen"),
    ("Kt/V", "show_ktv_screen"),
    ("Baumanómetro", "show_nibp_screen"),
    ("Historial NIBP", "show_nibp_history_screen"),
    ("Limpieza", "show_cleaning_screen"),
    ("Servicio (Opciones)", "show_options_screen"),
    ("Servicio (Parámetros)", "show_test_panel_screen"),
    ("Servicio (Bombas y válvulas)", "show_manual_mode_screen"),
    ("Servicio (Lazos)", "show_calibration_screen"),
    ("Servicio (Monitor de variables)", "show_real_time_var_screen"),
    ("Servicio (Puertos)", "show_config_comm_screen"),
    ("Servicio (Mantenimiento)", "show_maintenance_screen"),
    ("Servicio (Desinfección)", "show_cleanning_config_screen"),
    ("Modo manual", "show_manual_mode_screen"),
    ("Calibración", "show_calibration_screen"),
    ("Alarmas", "show_alarms_screen"),
    ("Configuración de alarmas", "show_alarm_config_limits_screen"),
    ("Alarmas de servicio técnico", "show_alarm_service_screen_config"),
    ("Historial", "show_history_screen"),
]


def _configure_qt_fontdir() -> None:
    candidates = []
    if os.name == "nt":
        win_dir = os.environ.get("WINDIR", r"C:\Windows")
        candidates.append(os.path.join(win_dir, "Fonts"))
    else:
        candidates.extend([
            "/usr/share/fonts",
            "/usr/local/share/fonts",
            "/usr/share/fonts/truetype/dejavu",
        ])

    for font_dir in candidates:
        if os.path.isdir(font_dir):
            os.environ.setdefault("QT_QPA_FONTDIR", font_dir)
            return


def run_child(method_name: str, theme: str, screen_name: str) -> None:
    """Ejecuta el ciclo de vida de la pantalla y el renderizado en un proceso hijo aislado."""
    from unittest.mock import MagicMock, patch

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    _configure_qt_fontdir()

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QObject, Signal

    app = QApplication.instance() or QApplication([sys.argv[0]])

    class MockHardware(QObject):
        data_received = Signal(str, float)
        connected_changed = Signal(bool)
        error_message = Signal(str)
        measurement_ready = Signal(dict)
        cuff_pressure = Signal(int)
        spo2_updated = Signal(int, int)
        error_cleared = Signal()

        def __init__(self, *args, **kwargs):
            super().__init__()
            self.is_connected = False
            self.CMD_CYAN_SOLID = "CMD_CYAN_SOLID"
            self.CMD_YELLOW_FLASH = "CMD_YELLOW_FLASH"
            self.CMD_GREEN_SOLID = "CMD_GREEN_SOLID"
            self.CMD_YELLOW_SOLID = "CMD_YELLOW_SOLID"
            self.CMD_OFF = "CMD_OFF"
            self.CMD_RED_SOLID = "CMD_RED_SOLID"

        def __getattr__(self, name):
            mock = MagicMock()
            setattr(self, name, mock)
            return mock

    with patch("gui.appMainHemodialysis.SerialCommunication", MockHardware), \
         patch("gui.appMainHemodialysis.BiozUreaController", MockHardware), \
         patch("gui.appMainHemodialysis.PatternConductivity", MockHardware), \
         patch("gui.appMainHemodialysis.MegaConductivitySensor", MockHardware), \
         patch("gui.appMainHemodialysis.LedBarController", MockHardware), \
         patch("gui.appMainHemodialysis.NibpParCommunication", MockHardware):

        from gui.appMainHemodialysis import HemodialysisHMI
        from gui.theme_manager import ThemeManager

        # 1. Crea la ventana real
        try:
            hmi = HemodialysisHMI()
        except Exception as e:
            sys.stderr.write(f"ERROR: Fallo al instanciar HemodialysisHMI para pantalla '{screen_name}': {e}\n")
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)

        # 2. Aplica el tema especificado
        try:
            ThemeManager.instance().apply_theme(theme, persist=False)
            app.processEvents()
        except Exception as e:
            sys.stderr.write(f"ERROR: Fallo al aplicar tema '{theme}' en pantalla '{screen_name}': {e}\n")
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)

        # 3. Muestra solo esa pantalla a 1920x1080
        if not hasattr(hmi, method_name):
            sys.stderr.write(f"ERROR: Metodo '{method_name}' no existe en HemodialysisHMI para pantalla '{screen_name}'\n")
            sys.exit(1)

        try:
            show_fn = getattr(hmi, method_name)
            show_fn()
        except Exception as e:
            sys.stderr.write(f"ERROR: Fallo al invocar '{method_name}' para pantalla '{screen_name}': {e}\n")
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)

        hmi.resize(1920, 1080)
        hmi.show()
        app.processEvents()

        # 4. Llama processEvents, grab() y un resize. grab() obliga el paintEvent
        try:
            app.processEvents()
            _ = hmi.grab()
            curr = hmi.screen_stack.currentWidget()
            if curr:
                _ = curr.grab()

            hmi.resize(1918, 1078)
            app.processEvents()
            _ = hmi.grab()

            hmi.resize(1920, 1080)
            app.processEvents()
            _ = hmi.grab()
            if curr:
                _ = curr.grab()
        except Exception as e:
            sys.stderr.write(f"ERROR: Fallo de pintura/resize en pantalla '{screen_name}': {e}\n")
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)

        # 5. Con la pantalla visible, cambia a Escala de grises y regresa a Clinico Claro
        try:
            ThemeManager.instance().apply_theme("Escala de grises", persist=False)
            app.processEvents()
            _ = hmi.grab()
            if curr:
                _ = curr.grab()

            ThemeManager.instance().apply_theme("Clínico Claro", persist=False)
            app.processEvents()
            _ = hmi.grab()
            if curr:
                _ = curr.grab()
        except Exception as e:
            sys.stderr.write(f"ERROR: Fallo en alternancia de tema para pantalla '{screen_name}': {e}\n")
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)

        # 6. Sale con codigo 0
        try:
            hmi.close()
            app.processEvents()
        except Exception:
            pass

        sys.exit(0)


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("screen_name,method_name", SCREENS)
def test_ui_paint_smoke(screen_name: str, method_name: str, theme: str) -> None:
    """
    Ejecuta cada combinacion de pantalla y tema en un subproceso aislado.
    Si el subproceso falla o se cuelga (>20 s), ese caso queda rojo sin tumbar pytest.
    """
    cmd = [
        sys.executable,
        os.path.abspath(__file__),
        "--child",
        method_name,
        theme,
        screen_name,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=20,
            cwd=PROJECT_ROOT,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"Pantalla '{screen_name}' con tema '{theme}' no respondio en 20 s (TimeoutExpired)")

    if proc.returncode != 0:
        err_msg = (
            f"Fallo en pantalla '{screen_name}' con tema '{theme}' (codigo de salida {proc.returncode}):\n"
            f"--- STDERR ---\n{proc.stderr}\n"
            f"--- STDOUT ---\n{proc.stdout}"
        )
        pytest.fail(err_msg)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        m_name = sys.argv[2]
        t_name = sys.argv[3]
        s_name = sys.argv[4] if len(sys.argv) > 4 else m_name
        run_child(m_name, t_name, s_name)
    else:
        # Permite ejecutar directamente 'python tests/test_ui_paint_smoke.py'
        sys.exit(pytest.main([__file__, "-v"]))
