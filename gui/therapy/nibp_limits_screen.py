# gui/therapy/nibp_limits_screen.py
"""
Pantalla y lógica de límites de presión arterial (NIBP) estilo Dialog+.

Tres filas, cada una con límite inferior y superior:
  - Sistólica, mmHg: Arranque 70 y 200. Inferior [50, 200], Superior [70, 245], inferior <= superior.
  - Diastólica, mmHg: Arranque 40 y 130. Inferior [40, 130], Superior [40, 220], inferior <= superior.
  - Ritmo, 1/min: Arranque 50 y 140. Inferior [40, 140], Superior [50, 200], inferior <= superior.

Se guardan en config/nibp_config.json y se pueden editar a mano.
Incluye el botón "Adaptación valor límite individual" a partir de la última toma válida del historial.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QLabel,
    QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from core.nibp_pressure_history import NibpPressureHistory, NibpPressureMeasurement
from gui.components.floating_confirm import FloatingConfirmDialog
from gui.components.numpad_modal import NumpadDialog
from gui.components.ui_components import ClickableLineEdit
from gui.theme_manager import ThemeManager
from utilities.platform_runtime import get_runtime_config_path, safe_int, safe_json_load

logger = logging.getLogger(__name__)

NIBP_CONFIG_FILE = get_runtime_config_path("nibp_config.json")

NIBP_LIMIT_SPECS: Dict[str, Dict[str, Any]] = {
    "sys": {
        "label": "Sistólica",
        "unit": "mmHg",
        "default_min": 70,
        "default_max": 200,
        "min_bounds": (50, 200),
        "max_bounds": (70, 245),
        "key_min": "sys_min",
        "key_max": "sys_max",
    },
    "dia": {
        "label": "Diastólica",
        "unit": "mmHg",
        "default_min": 40,
        "default_max": 130,
        "min_bounds": (40, 130),
        "max_bounds": (40, 220),
        "key_min": "dia_min",
        "key_max": "dia_max",
    },
    "hr": {
        "label": "Ritmo",
        "unit": "1/min",
        "default_min": 50,
        "default_max": 140,
        "min_bounds": (40, 140),
        "max_bounds": (50, 200),
        "key_min": "hr_min",
        "key_max": "hr_max",
    },
}

DEFAULT_NIBP_LIMITS: Dict[str, int] = {
    "sys_min": 70,
    "sys_max": 200,
    "dia_min": 40,
    "dia_max": 130,
    "hr_min": 50,
    "hr_max": 140,
}

NO_VALID_MEASUREMENT_MSG = "No hay una toma válida para adaptar los límites."


def clamp_parameter_limits(
    param: str,
    low_val: int,
    high_val: int,
    edited_side: Optional[str] = None,
    strict_less: bool = False,
) -> Tuple[int, int]:
    """
    Recorta (inferior, superior) de un parámetro ('sys', 'dia', 'hr') a sus topes
    absolutos y garantiza inferior <= superior (o inferior < superior si strict_less=True).
    """
    spec = NIBP_LIMIT_SPECS[param]
    low_min, low_max = spec["min_bounds"]
    high_min, high_max = spec["max_bounds"]

    low = max(low_min, min(low_max, int(round(low_val))))
    high = max(high_min, min(high_max, int(round(high_val))))

    if strict_less:
        if low >= high:
            if edited_side == "min":
                low = max(low_min, min(low_max, high - 1))
            elif edited_side == "max":
                high = max(high_min, min(high_max, low + 1))
            else:
                if high < high_max:
                    high = max(high_min, min(high_max, low + 1))
                if low >= high:
                    low = max(low_min, min(low_max, high - 1))
    else:
        if low > high:
            if edited_side == "min":
                low = max(low_min, min(low_max, high))
            elif edited_side == "max":
                high = max(high_min, min(high_max, low))
            else:
                low = max(low_min, min(low_max, high))

    return low, high


def adapt_single_parameter(param: str, measured_val: int) -> Tuple[int, int]:
    """
    Calcula (inferior, superior) adaptados para un parámetro ('sys', 'dia', 'hr'):
      - Ventana normal: valor - 30 y valor + 30.
      - Si el valor ya está a 15 o menos de su tope absoluto (low_min o high_max),
        la ventana de ese parámetro es de 10, no de 30.
      - Recorta a los topes permitidos y conserva inferior < superior.
    """
    spec = NIBP_LIMIT_SPECS[param]
    low_min, _low_max = spec["min_bounds"]
    _high_min, high_max = spec["max_bounds"]

    val = int(round(measured_val))
    if (val - low_min) <= 15 or (high_max - val) <= 15:
        window = 10
    else:
        window = 30

    raw_low = val - window
    raw_high = val + window
    return clamp_parameter_limits(param, raw_low, raw_high, strict_less=True)


def compute_adapted_limits_from_measurement(measurement: NibpPressureMeasurement) -> Dict[str, int]:
    """Calcula los 6 límites individuales a partir de una toma válida."""
    sys_min, sys_max = adapt_single_parameter("sys", measurement.sys)
    dia_min, dia_max = adapt_single_parameter("dia", measurement.dia)
    hr_min, hr_max = adapt_single_parameter("hr", measurement.hr)
    return {
        "sys_min": sys_min,
        "sys_max": sys_max,
        "dia_min": dia_min,
        "dia_max": dia_max,
        "hr_min": hr_min,
        "hr_max": hr_max,
    }


def get_last_valid_measurement(history: Optional[NibpPressureHistory]) -> Optional[NibpPressureMeasurement]:
    """Retorna únicamente la última toma válida del historial, o None si no hay."""
    if history is None or not hasattr(history, "get_all_measurements"):
        return None
    measurements = history.get_all_measurements()
    for m in reversed(measurements):
        if (
            getattr(m, "sys", -1) is not None
            and getattr(m, "dia", -1) is not None
            and getattr(m, "hr", -1) is not None
            and m.sys >= 0
            and m.dia >= 0
            and m.hr >= 0
        ):
            return m
    return None


def load_nibp_limits(config_path: Optional[Path] = None) -> Dict[str, int]:
    """Carga y valida los límites de presión desde nibp_config.json."""
    path = config_path or NIBP_CONFIG_FILE
    loaded = safe_json_load(path, {})
    if not isinstance(loaded, dict):
        loaded = {}

    nested = loaded.get("limits") if isinstance(loaded.get("limits"), dict) else {}

    result: Dict[str, int] = {}
    for param, spec in NIBP_LIMIT_SPECS.items():
        k_min = spec["key_min"]
        k_max = spec["key_max"]
        raw_min = loaded.get(k_min, nested.get(k_min, spec["default_min"]))
        raw_max = loaded.get(k_max, nested.get(k_max, spec["default_max"]))
        c_min, c_max = clamp_parameter_limits(
            param,
            safe_int(raw_min, spec["default_min"]),
            safe_int(raw_max, spec["default_max"]),
        )
        result[k_min] = c_min
        result[k_max] = c_max

    return result


def save_nibp_limits(limits: Dict[str, int], config_path: Optional[Path] = None) -> Dict[str, int]:
    """Guarda los límites validados en nibp_config.json preservando el resto de claves."""
    path = config_path or NIBP_CONFIG_FILE
    loaded = safe_json_load(path, {})
    if not isinstance(loaded, dict):
        loaded = {}

    validated: Dict[str, int] = {}
    for param, spec in NIBP_LIMIT_SPECS.items():
        k_min = spec["key_min"]
        k_max = spec["key_max"]
        c_min, c_max = clamp_parameter_limits(
            param,
            safe_int(limits.get(k_min, spec["default_min"]), spec["default_min"]),
            safe_int(limits.get(k_max, spec["default_max"]), spec["default_max"]),
        )
        validated[k_min] = c_min
        validated[k_max] = c_max
        loaded[k_min] = c_min
        loaded[k_max] = c_max

    loaded["limits"] = dict(validated)

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(loaded, f, indent=4, ensure_ascii=False)
        logger.info(f"[NIBP Limits] Límites guardados en {path}: {validated}")
    except Exception as e:
        logger.error(f"[NIBP Limits] Error guardando límites en {path}: {e}")

    return validated


class NibpLimitsScreen(QWidget):
    """
    Pantalla de configuración de límites de presión arterial (Sistólica, Diastólica, Ritmo)
    con edición manual y botón "Adaptación valor límite individual".
    """

    limits_changed = Signal(dict)
    close_requested = Signal()

    def __init__(
        self,
        parent=None,
        history: Optional[NibpPressureHistory] = None,
        config_path: Optional[Path] = None,
    ):
        super().__init__(parent if isinstance(parent, QWidget) else None)
        self.parent_window = parent
        self.history = history if history is not None else NibpPressureHistory()
        self.config_path = config_path or NIBP_CONFIG_FILE
        self._limits: Dict[str, int] = load_nibp_limits(self.config_path)
        self._pending_adapted_limits: Optional[Dict[str, int]] = None

        self.setObjectName("NibpLimitsScreen")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.setup_background()
        self.setup_ui()
        self._apply_limits_to_ui(self._limits)
        try:
            ThemeManager.instance().theme_changed.connect(self._on_theme_changed)
        except Exception:
            pass

    def setup_background(self):
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), QColor("#f8fafc"))
        self.setPalette(p)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        dpi = max(self.logicalDpiX() / 96.0, 1.0)
        margen = int(16 * dpi)
        main_layout.setContentsMargins(margen, margen, margen, margen)
        main_layout.setSpacing(14)

        # ─── ENCABEZADO ───────────────────────────────────────────────
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        self.lbl_title = QLabel("Límites de Presión Arterial")
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()

        self.btn_close = QPushButton("Cerrar")
        self.btn_close.clicked.connect(self.on_close_clicked)
        header_layout.addWidget(self.btn_close)
        main_layout.addLayout(header_layout)

        # ─── TARJETA DE TRES FILAS (INFERIOR Y SUPERIOR) ──────────────
        self.card_frame = QFrame()
        self.card_frame.setObjectName("card")
        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(18)

        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(18)

        self.lbl_col_param = QLabel("Parámetro")
        self.lbl_col_min = QLabel("Inferior")
        self.lbl_col_min.setAlignment(Qt.AlignCenter)
        self.lbl_col_max = QLabel("Superior")
        self.lbl_col_max.setAlignment(Qt.AlignCenter)
        self.lbl_col_range = QLabel("Rango permitido")

        grid.addWidget(self.lbl_col_param, 0, 0)
        grid.addWidget(self.lbl_col_min, 0, 1)
        grid.addWidget(self.lbl_col_max, 0, 2)
        grid.addWidget(self.lbl_col_range, 0, 3)

        self._row_labels: list[QLabel] = []
        self._range_labels: list[QLabel] = []
        self.inputs: Dict[str, ClickableLineEdit] = {}

        rows_spec = [
            ("sys", "Sistólica, mmHg", "Inferior: 50–200 | Superior: 70–245"),
            ("dia", "Diastólica, mmHg", "Inferior: 40–130 | Superior: 40–220"),
            ("hr", "Ritmo, 1/min", "Inferior: 40–140 | Superior: 50–200"),
        ]

        for row_idx, (param, row_title, range_hint) in enumerate(rows_spec, start=1):
            lbl_param = QLabel(row_title)
            self._row_labels.append(lbl_param)
            grid.addWidget(lbl_param, row_idx, 0)

            k_min = f"{param}_min"
            k_max = f"{param}_max"

            inp_min = ClickableLineEdit(str(self._limits[k_min]))
            inp_min.setFixedSize(140, 52)
            inp_min.setAlignment(Qt.AlignCenter)
            inp_min.setReadOnly(True)
            inp_min.clicked.connect(lambda p=param, s="min": self._on_edit_limit_clicked(p, s))
            self.inputs[k_min] = inp_min
            grid.addWidget(inp_min, row_idx, 1, alignment=Qt.AlignCenter)

            inp_max = ClickableLineEdit(str(self._limits[k_max]))
            inp_max.setFixedSize(140, 52)
            inp_max.setAlignment(Qt.AlignCenter)
            inp_max.setReadOnly(True)
            inp_max.clicked.connect(lambda p=param, s="max": self._on_edit_limit_clicked(p, s))
            self.inputs[k_max] = inp_max
            grid.addWidget(inp_max, row_idx, 2, alignment=Qt.AlignCenter)

            lbl_range = QLabel(range_hint)
            self._range_labels.append(lbl_range)
            grid.addWidget(lbl_range, row_idx, 3)

        self.input_sys_min = self.inputs["sys_min"]
        self.input_sys_max = self.inputs["sys_max"]
        self.input_dia_min = self.inputs["dia_min"]
        self.input_dia_max = self.inputs["dia_max"]
        self.input_hr_min = self.inputs["hr_min"]
        self.input_hr_max = self.inputs["hr_max"]

        card_layout.addLayout(grid)

        # ─── FILA DE ACCIÓN: ADAPTACIÓN INDIVIDUAL ────────────────────
        actions_row = QHBoxLayout()
        actions_row.setSpacing(16)

        self.btn_adapt = QPushButton("Adaptación valor límite individual")
        self.btn_adapt.clicked.connect(self.on_adapt_clicked)
        actions_row.addWidget(self.btn_adapt)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        actions_row.addWidget(self.lbl_status, stretch=1)

        card_layout.addLayout(actions_row)

        # ─── PANEL DE CONFIRMACIÓN DE ADAPTACIÓN (SI SE USA SIN MODAL) ─
        self.confirm_frame = QFrame()
        self.confirm_frame.setObjectName("confirm_card")
        confirm_layout = QHBoxLayout(self.confirm_frame)
        confirm_layout.setContentsMargins(16, 12, 16, 12)
        confirm_layout.setSpacing(14)

        self.lbl_preview = QLabel("")
        self.lbl_preview.setWordWrap(True)
        confirm_layout.addWidget(self.lbl_preview, stretch=1)

        self.btn_accept_adapt = QPushButton("Aceptar")
        self.btn_accept_adapt.clicked.connect(self.accept_adaptation)
        confirm_layout.addWidget(self.btn_accept_adapt)

        self.btn_cancel_adapt = QPushButton("Cancelar")
        self.btn_cancel_adapt.clicked.connect(self.cancel_adaptation)
        confirm_layout.addWidget(self.btn_cancel_adapt)

        self.confirm_frame.hide()
        card_layout.addWidget(self.confirm_frame)

        card_layout.addStretch()
        main_layout.addWidget(self.card_frame, stretch=1)

        self._apply_theme_styles()

    def _on_theme_changed(self, _theme_name: str):
        self.setup_background()
        self._apply_theme_styles()

    def _apply_theme_styles(self):
        bg_primary = "#f8fafc"
        bg_card = "#ffffff"
        bg_input = "#f8fafc"
        text_primary = "#0f172a"
        text_secondary = "#334155"
        text_muted = "#64748b"
        border = "#cbd5e1"
        border_strong = "#64748b"
        accent = "#2563eb"
        btn_primary_bg = "#06298a"

        self.setStyleSheet(f"""
            QWidget#NibpLimitsScreen {{ background-color: {bg_primary}; }}
            QFrame#card {{
                background-color: {bg_card};
                border: 1px solid {border};
                border-radius: 12px;
            }}
            QFrame#confirm_card {{
                background-color: #eff6ff;
                border: 2px solid {accent};
                border-radius: 10px;
            }}
        """)

        self.lbl_title.setStyleSheet(
            f"font-size: 28px; font-weight: bold; color: {text_primary}; background: transparent;"
        )
        self.btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: #64748b;
                color: #ffffff;
                font-size: 20px;
                font-weight: bold;
                padding: 10px 24px;
                border-radius: 8px;
                border: 1px solid {border};
            }}
            QPushButton:hover {{ background-color: {accent}; color: #ffffff; }}
        """)

        header_lbl_style = f"font-size: 20px; font-weight: bold; color: {text_secondary}; background: transparent;"
        for lbl in (self.lbl_col_param, self.lbl_col_min, self.lbl_col_max, self.lbl_col_range):
            lbl.setStyleSheet(header_lbl_style)

        for lbl in self._row_labels:
            lbl.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {text_primary}; background: transparent;")

        for lbl in self._range_labels:
            lbl.setStyleSheet(f"font-size: 16px; color: {text_muted}; background: transparent;")

        input_style = f"""
            ClickableLineEdit {{
                font-family: Consolas, "Courier New", monospace;
                font-size: 24px;
                font-weight: bold;
                color: {text_primary};
                background: {bg_input};
                border: 2px solid {border_strong};
                border-radius: 8px;
                padding: 4px;
            }}
            ClickableLineEdit:focus {{
                border: 2px solid {accent};
                background: {bg_card};
            }}
        """
        for inp in self.inputs.values():
            inp.setStyleSheet(input_style)

        self.btn_adapt.setStyleSheet(f"""
            QPushButton {{
                background-color: {btn_primary_bg};
                color: #ffffff;
                font-size: 20px;
                font-weight: bold;
                padding: 12px 24px;
                border-radius: 10px;
                min-height: 54px;
            }}
            QPushButton:hover {{ background-color: {accent}; }}
        """)
        self.btn_accept_adapt.setStyleSheet("""
            QPushButton {
                background-color: #16a34a;
                color: #ffffff;
                font-size: 18px;
                font-weight: bold;
                padding: 10px 22px;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #15803d; }
        """)
        self.btn_cancel_adapt.setStyleSheet("""
            QPushButton {
                background-color: #64748b;
                color: #ffffff;
                font-size: 18px;
                font-weight: bold;
                padding: 10px 22px;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #475569; }
        """)
        self.lbl_status.setStyleSheet(f"font-size: 18px; font-weight: 600; color: #b91c1c; background: transparent;")
        self.lbl_preview.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {text_primary}; background: transparent;")

    def _apply_limits_to_ui(self, limits: Dict[str, int]):
        for key, inp in self.inputs.items():
            if key in limits:
                inp.setText(str(int(limits[key])))

    def load_limits_from_config(self) -> Dict[str, int]:
        """Recarga los límites desde nibp_config.json y actualiza los campos."""
        self._limits = load_nibp_limits(self.config_path)
        self._pending_adapted_limits = None
        self.confirm_frame.hide()
        self.lbl_status.setText("")
        self._apply_limits_to_ui(self._limits)
        return dict(self._limits)

    def get_current_limits(self) -> Dict[str, int]:
        """Retorna los límites actualmente guardados/activos."""
        return dict(self._limits)

    def set_limit_value(self, param: str, side: str, new_value: int) -> Tuple[int, int]:
        """
        Edita manualmente un límite ('sys', 'dia', 'hr'; side='min' o 'max'),
        recorta a los topes permitidos conservando inferior <= superior y guarda en nibp_config.json.
        """
        spec = NIBP_LIMIT_SPECS[param]
        k_min = spec["key_min"]
        k_max = spec["key_max"]

        cur_min = self._limits.get(k_min, spec["default_min"])
        cur_max = self._limits.get(k_max, spec["default_max"])

        if side == "min":
            cur_min = int(round(new_value))
            low_min, low_max = spec["min_bounds"]
            cur_min = max(low_min, min(min(low_max, cur_max), cur_min))
        else:
            cur_max = int(round(new_value))
            high_min, high_max = spec["max_bounds"]
            cur_max = max(max(high_min, cur_min), min(high_max, cur_max))

        c_min, c_max = clamp_parameter_limits(param, cur_min, cur_max, edited_side=side)
        self._limits[k_min] = c_min
        self._limits[k_max] = c_max

        self._apply_limits_to_ui(self._limits)
        self._limits = save_nibp_limits(self._limits, self.config_path)
        self.limits_changed.emit(dict(self._limits))
        if self.parent_window and hasattr(self.parent_window, "nibp_history_screen"):
            self.parent_window.nibp_history_screen.update_from_history()
        return c_min, c_max

    def _on_edit_limit_clicked(self, param: str, side: str):
        spec = NIBP_LIMIT_SPECS[param]
        side_label = "Inferior" if side == "min" else "Superior"
        title = f"{spec['label']} {side_label} ({spec['unit']})"
        dialog = NumpadDialog(self, initial_value="", title=title)
        if dialog.exec():
            val_str = dialog.get_value()
            if val_str is not None:
                try:
                    val = int(round(float(val_str)))
                    self.set_limit_value(param, side, val)
                except (TypeError, ValueError):
                    pass

    def on_adapt_clicked(self, auto_confirm: Optional[bool] = None) -> Optional[Dict[str, int]]:
        """
        Calcula los 6 límites adaptados a partir de la última toma válida del historial.
        - Si no hay toma válida, no cambia nada y avisa:
          "No hay una toma válida para adaptar los límites."
        - Si hay toma válida, muestra los 6 números y no los guarda hasta que acepten.
          Si cancelan, no cambia nada.
        """
        last_m = get_last_valid_measurement(self.history)
        if last_m is None:
            self._pending_adapted_limits = None
            self.confirm_frame.hide()
            self.lbl_status.setText(NO_VALID_MEASUREMENT_MSG)
            if self.parent_window and hasattr(self.parent_window, "show_warning_message"):
                self.parent_window.show_warning_message(NO_VALID_MEASUREMENT_MSG, 4000)
            return None

        self.lbl_status.setText("")
        adapted = compute_adapted_limits_from_measurement(last_m)
        self._pending_adapted_limits = dict(adapted)

        # Mostrar los 6 números en pantalla y en el diálogo de confirmación
        self._apply_limits_to_ui(adapted)
        preview_text = (
            f"Sistólica: {adapted['sys_min']} – {adapted['sys_max']} mmHg   |   "
            f"Diastólica: {adapted['dia_min']} – {adapted['dia_max']} mmHg   |   "
            f"Ritmo: {adapted['hr_min']} – {adapted['hr_max']} 1/min"
        )
        self.lbl_preview.setText(preview_text)
        self.confirm_frame.show()

        if auto_confirm is True:
            self.accept_adaptation()
            return dict(self._limits)
        if auto_confirm is False:
            self.cancel_adaptation()
            return dict(self._limits)

        return dict(adapted)

    def accept_adaptation(self) -> Dict[str, int]:
        """Acepta y guarda en nibp_config.json los 6 números adaptados mostrados."""
        if self._pending_adapted_limits is not None:
            self._limits = save_nibp_limits(self._pending_adapted_limits, self.config_path)
            self._pending_adapted_limits = None
            self.confirm_frame.hide()
            self._apply_limits_to_ui(self._limits)
            self.limits_changed.emit(dict(self._limits))
            if self.parent_window and hasattr(self.parent_window, "nibp_history_screen"):
                self.parent_window.nibp_history_screen.update_from_history()
        return dict(self._limits)

    def cancel_adaptation(self) -> Dict[str, int]:
        """Cancela la adaptación y restaura los límites anteriores sin guardar cambios."""
        self._pending_adapted_limits = None
        self.confirm_frame.hide()
        self._apply_limits_to_ui(self._limits)
        return dict(self._limits)

    def on_close_clicked(self):
        """Cancela cualquier adaptación pendiente sin confirmar y regresa al baumanómetro."""
        if self._pending_adapted_limits is not None:
            self.cancel_adaptation()
        self.close_requested.emit()
        if self.parent_window and hasattr(self.parent_window, "show_nibp_screen"):
            self.parent_window.show_nibp_screen()
