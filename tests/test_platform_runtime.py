"""Tests para utilities/platform_runtime.py - configuración multiplataforma y puertos."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Agregar el directorio raíz al path para imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utilities.platform_runtime import (
    get_runtime_config_dir,
    get_runtime_data_dir,
    get_runtime_data_path,
    sanitize_port_for_platform,
    is_linux,
    is_windows,
)


class TestSanitizePortForPlatform(unittest.TestCase):
    """Tests para sanitize_port_for_platform() - normalización de puertos."""

    def test_windows_port_unchanged_on_windows(self):
        """En Windows, COMn debe pasar sin cambios."""
        with patch("utilities.platform_runtime.is_linux", return_value=False):
            result = sanitize_port_for_platform("COM3")
            self.assertEqual(result, "COM3")

    def test_dev_port_unchanged_on_windows(self):
        """En Windows, /dev/ttyUSB0 debe pasar sin cambios."""
        with patch("utilities.platform_runtime.is_linux", return_value=False):
            result = sanitize_port_for_platform("/dev/ttyUSB0")
            self.assertEqual(result, "/dev/ttyUSB0")

    def test_auto_unchanged_on_windows(self):
        """En Windows, 'Auto' debe pasar sin cambios."""
        with patch("utilities.platform_runtime.is_linux", return_value=False):
            result = sanitize_port_for_platform("Auto")
            self.assertEqual(result, "Auto")

    def test_com_port_rejected_on_linux(self):
        """En Linux, COMn debe rechazarse y retornar 'Auto'."""
        with patch("utilities.platform_runtime.is_linux", return_value=True):
            with patch(
                "utilities.platform_runtime.feature_enabled", return_value=True
            ):
                result = sanitize_port_for_platform("COM3")
                self.assertEqual(result, "Auto")

    def test_dev_port_accepted_on_linux(self):
        """En Linux, /dev/* debe aceptarse."""
        with patch("utilities.platform_runtime.is_linux", return_value=True):
            with patch(
                "utilities.platform_runtime.feature_enabled", return_value=True
            ):
                result = sanitize_port_for_platform("/dev/ttyUSB0")
                self.assertEqual(result, "/dev/ttyUSB0")

    def test_auto_accepted_on_linux(self):
        """En Linux, 'Auto' debe aceptarse."""
        with patch("utilities.platform_runtime.is_linux", return_value=True):
            with patch(
                "utilities.platform_runtime.feature_enabled", return_value=True
            ):
                result = sanitize_port_for_platform("Auto")
                self.assertEqual(result, "Auto")

    def test_invalid_port_rejected_on_linux(self):
        """En Linux, puerto sin /dev/ (salvo 'Auto') debe rechazarse."""
        with patch("utilities.platform_runtime.is_linux", return_value=True):
            with patch(
                "utilities.platform_runtime.feature_enabled", return_value=True
            ):
                result = sanitize_port_for_platform("INVALID_PORT")
                self.assertEqual(result, "Auto")

    def test_sanitize_disabled_returns_original(self):
        """Si sanitize_linux_com_ports está deshabilitado, devuelve original."""
        with patch("utilities.platform_runtime.is_linux", return_value=True):
            with patch(
                "utilities.platform_runtime.feature_enabled", return_value=False
            ):
                result = sanitize_port_for_platform("COM3")
                self.assertEqual(result, "COM3")

    def test_none_port_defaults_to_auto(self):
        """Puerto None debe convertirse a 'Auto'."""
        with patch("utilities.platform_runtime.is_linux", return_value=False):
            result = sanitize_port_for_platform(None)
            self.assertEqual(result, "Auto")

    def test_empty_string_defaults_to_auto(self):
        """Cadena vacía debe convertirse a 'Auto'."""
        with patch("utilities.platform_runtime.is_linux", return_value=False):
            result = sanitize_port_for_platform("")
            self.assertEqual(result, "Auto")


class TestGetRuntimeConfigDirBasic(unittest.TestCase):
    """Tests básicos para get_runtime_config_dir() cuando no está frozen."""

    def test_ciateq_config_dir_when_set(self):
        """Debe usar CIATEQ_CONFIG_DIR cuando está definida y es escribible."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CIATEQ_CONFIG_DIR": tmpdir}, clear=False):
                result = get_runtime_config_dir()
                self.assertEqual(result, Path(tmpdir))

    def test_uses_repo_config_when_not_frozen_no_env(self):
        """Sin CIATEQ_CONFIG_DIR y sin frozen, debe usar repo config."""
        # Guardar valor actual de CIATEQ_CONFIG_DIR si existe
        old_val = os.environ.get("CIATEQ_CONFIG_DIR")
        try:
            # Limpiar la variable
            if "CIATEQ_CONFIG_DIR" in os.environ:
                del os.environ["CIATEQ_CONFIG_DIR"]
            
            # Si no está frozen, debe retornar repo config
            if not getattr(sys, "frozen", False):
                result = get_runtime_config_dir()
                expected = Path(__file__).resolve().parent.parent / "config"
                self.assertEqual(result, expected)
        finally:
            if old_val:
                os.environ["CIATEQ_CONFIG_DIR"] = old_val


class TestGetRuntimeDataDir(unittest.TestCase):
    """Tests para get_runtime_data_dir() y get_runtime_data_path()."""

    def test_ciateq_data_dir_when_set(self):
        """Debe usar CIATEQ_DATA_DIR cuando está definida y es escribible."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CIATEQ_DATA_DIR": tmpdir}, clear=False):
                result = get_runtime_data_dir()
                self.assertEqual(result, Path(tmpdir))

    def test_frozen_uses_executable_parent_and_not_dunder_file(self):
        """Un programa congelado usa la carpeta del ejecutable y no __file__."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_exe = Path(tmpdir) / "dist" / "hemodialisis.exe"
            fake_meipass = Path(tmpdir) / "_MEI12345"
            repo_root = Path(__file__).resolve().parent.parent

            with patch.dict(os.environ, {"CIATEQ_DATA_DIR": ""}, clear=False):
                with patch.object(sys, "frozen", True, create=True), patch.object(
                    sys, "executable", str(fake_exe)
                ), patch.object(sys, "_MEIPASS", str(fake_meipass), create=True):
                    result = get_runtime_data_dir()
                    self.assertEqual(result, fake_exe.resolve().parent)
                    self.assertNotEqual(result, repo_root)
                    self.assertNotEqual(result, fake_meipass.resolve())

                    log_path = get_runtime_data_path("var", "log", "hemodialisis.log")
                    self.assertEqual(
                        log_path,
                        fake_exe.resolve().parent / "var" / "log" / "hemodialisis.log",
                    )

    def test_frozen_falls_back_when_executable_dir_not_writable_windows(self):
        """Si la carpeta del ejecutable falla en Windows, usa %LOCALAPPDATA%/CIATEQ/Hemodialisis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_exe = Path(tmpdir) / "readonly" / "hemodialisis.exe"
            local_appdata = Path(tmpdir) / "LocalAppData"
            expected_fallback = local_appdata / "CIATEQ" / "Hemodialisis"

            def fake_ensure(path: Path):
                if path == fake_exe.resolve().parent:
                    return None
                path.mkdir(parents=True, exist_ok=True)
                return path

            with patch.dict(
                os.environ,
                {"CIATEQ_DATA_DIR": "", "LOCALAPPDATA": str(local_appdata)},
                clear=False,
            ):
                with patch.object(sys, "frozen", True, create=True), patch.object(
                    sys, "executable", str(fake_exe)
                ), patch("utilities.platform_runtime.is_windows", return_value=True), patch(
                    "utilities.platform_runtime._ensure_config_dir", side_effect=fake_ensure
                ):
                    result = get_runtime_data_dir()
                    self.assertEqual(result, expected_fallback)

    def test_uses_repo_root_when_not_frozen_no_env(self):
        """Sin CIATEQ_DATA_DIR y sin frozen, debe usar la raíz del repositorio."""
        with patch.dict(os.environ, {"CIATEQ_DATA_DIR": ""}, clear=False):
            with patch.object(sys, "frozen", False, create=True):
                result = get_runtime_data_dir()
                expected = Path(__file__).resolve().parent.parent
                self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()

