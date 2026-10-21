# gui/therapy/nibp_config_screen.py

"""
Pantalla clínica de configuración y lectura del baumanómetro PAR NIBP2020 UP.


"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QLabel,
    QComboBox, QCheckBox, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer
import json
import logging

from gui.components.floating_confirm import FloatingConfirmDialog
from gui.theme_manager import ThemeManager
from utilities.platform_runtime import get_runtime_config_path, safe_json_load

logger = logging.getLogger(__name__)

NIBP_CONFIG_FILE = get_runtime_config_path("nibp_config.json")
NIBP_DEFAULT_CONFIG = {
    "enabled": False,
    "port": "Auto",
    "baudrate": 19200,
    "patient_mode": "adult",
    "method": 2,
    "start_pressure_mmhg": 160,
    "auto_during_therapy": False,
    "interval_min": 15,
    "spo2_enabled": False,
}

METHOD_LABELS = {
    1: "1 - Deflación",
    2: "2 - IMT (inflado)",
    3: "3 - Deflación adaptativa",
}
START_PRESSURE_OPTIONS_MMHG = [80, 100, 120, 140, 160, 180, 200, 220, 240, 280]
INTERVAL_OPTIONS_MIN = [5, 10, 15, 30, 60]
_CARD_FIXED_WIDTH = 507
_CARD_ROW0_MIN_HEIGHT = 200
_CARD_ROW1_MIN_HEIGHT = 260
_SPO2_STATUS_TEXTS = ("Sensor desconectado", "Sin dedo", "Sin pulso", "Buscando…", "Señal débil", "OK", "-----")
_SPO2_STATUS_WIDTH = max(len(text) for text in _SPO2_STATUS_TEXTS)


class NibpConfigScreen(QWidget):
    """Pantalla de configuración clínica del NIBP2020 UP (sin manejo de puerto/enable)."""

    settings_applied = Signal(dict)
    measure_now_requested = Signal()
    reset_requested = Signal()
    history_requested = Signal()
    spo2_on_requested = Signal()
    spo2_off_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self._config = self._load_config()

        self.setObjectName("NibpConfigScreen")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.setup_ui()
        self._apply_config_to_ui()
        try:
            ThemeManager.instance().theme_changed.connect(self._on_theme_changed)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------
    def _load_config(self) -> dict:
        loaded = safe_json_load(NIBP_CONFIG_FILE, {})
        if not isinstance(loaded, dict):
            loaded = {}
        return {**NIBP_DEFAULT_CONFIG, **loaded}

    def _save_config(self):
        NIBP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with NIBP_CONFIG_FILE.open("w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
            logger.info(f"[NIBP] Configuración clínica guardada en {NIBP_CONFIG_FILE}")
        except Exception as e:
            logger.error(f"[NIBP] Error guardando configuración clínica: {e}")

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(7, 7, 7, 7)
        main_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        self.lbl_main_title = QLabel("Baumanómetro PAR NIBP2020 UP")
        header_layout.addWidget(self.lbl_main_title)
        header_layout.addStretch()

        self.btn_close = QPushButton("Cerrar")
        self.btn_close.clicked.connect(self._on_close_clicked)
        header_layout.addWidget(self.btn_close)
        main_layout.addLayout(header_layout)

        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setContentsMargins(7, 7, 7, 7)

        self._card_titles = []
        self._value_labels = []
        self._hint_labels = []

        # ─── CARD 1: LECTURA ACTUAL ───────────────────────────────────────
        reading_card, reading_layout = self._make_card("Lectura actual", _CARD_ROW0_MIN_HEIGHT, fixed_width=False)

        values_row = QHBoxLayout()
        values_row.setSpacing(20)
        self.lbl_sys = self._make_value_label("SYS", "—")
        self.lbl_dia = self._make_value_label("DIA", "—")
        self.lbl_map = self._make_value_label("MAP", "—")
        self.lbl_hr = self._make_value_label("FC", "—")
        for lbl in (self.lbl_sys, self.lbl_dia, self.lbl_map, self.lbl_hr):
            values_row.addWidget(lbl)
        values_row.addStretch()
        reading_layout.addLayout(values_row)

        inf_row = QHBoxLayout()
        inf_row.setSpacing(20)

        self.lbl_cuff = QLabel("Manguito: — mmHg")
        inf_row.addWidget(self.lbl_cuff)

        self.lbl_status = QLabel("Desconectado")
        inf_row.addWidget(self.lbl_status)
        reading_layout.addLayout(inf_row)

        self.lbl_nibp_error = QLabel("")
        self.lbl_nibp_error.setWordWrap(True)
        reading_layout.addWidget(self.lbl_nibp_error)

        hint_label = QLabel("Colocar el manguito en el brazo contrario a la fístula.")
        self._hint_labels.append(hint_label)
        reading_layout.addWidget(hint_label)
        reading_layout.addStretch()

        grid.addWidget(reading_card, 0, 0, 1, 2)

        # ─── CARD 2: MÉTODO ───────────────────────────────────────────────
        method_card, method_layout = self._make_card("Método", _CARD_ROW0_MIN_HEIGHT)

        self.cmb_method = QComboBox()
        for code, label in METHOD_LABELS.items():
            self.cmb_method.addItem(label, code)
        method_layout.addWidget(self.cmb_method)
        method_layout.addStretch()

        grid.addWidget(method_card, 0, 2, 1, 1)

        # ─── CARD 4: PRESIÓN DE ARRANQUE ──────────────────────────────────
        pressure_card, pressure_layout = self._make_card("Presión de arranque", _CARD_ROW1_MIN_HEIGHT)

        self.cmb_start_pressure = QComboBox()
        for pressure in START_PRESSURE_OPTIONS_MMHG:
            self.cmb_start_pressure.addItem(f"{pressure} mmHg", pressure)
        pressure_layout.addWidget(self.cmb_start_pressure)
        pressure_layout.addStretch()

        grid.addWidget(pressure_card, 1, 0, 1, 1)

        # ─── CARD 5: AUTOMÁTICA (solo persistir)
        # ESTA CONFIGURACION APLICA PARA MEDICION DE PRESIÓN ARTERIAL AUTOMÁTICA DURANTE LA TERAPIA Y MEDICION SPo2 AUTOMÁTICA
        auto_card, auto_layout = self._make_card("Configuración", _CARD_ROW1_MIN_HEIGHT)

        self.chk_auto = QCheckBox("Medición automática durante la terapia")
        auto_layout.addWidget(self.chk_auto)

        interval_row = QHBoxLayout()
        interval_row.setSpacing(10)
        self.lbl_interval = QLabel("Intervalo:")
        self.cmb_interval = QComboBox()
        for minutes in INTERVAL_OPTIONS_MIN:
            self.cmb_interval.addItem(f"{minutes} min", minutes)
        interval_row.addWidget(self.lbl_interval)
        interval_row.addWidget(self.cmb_interval)
        interval_row.addStretch()
        auto_layout.addLayout(interval_row)

        auto_hint = QLabel("Se activará cuando la terapia esté en RUNNING.")
        auto_hint.setWordWrap(True)
        self._hint_labels.append(auto_hint)
        auto_layout.addWidget(auto_hint)
        auto_layout.addStretch()

        grid.addWidget(auto_card, 1, 1, 1, 1)

        # ─── CARD 6: SPo2 (solo checkbox + lectura, sin botones) ──────────
        spo2_card, spo2_layout = self._make_card("SpO2", _CARD_ROW1_MIN_HEIGHT)

        self.chk_spo2 = QCheckBox("SpO2")
        self.chk_spo2.toggled.connect(self._on_chk_spo2_toggled)
        spo2_layout.addWidget(self.chk_spo2)

        self.lbl_spo2_value = self._make_value_label("SpO2", "----")
        self.lbl_spo2_value.setFixedWidth(150)
        spo2_layout.addWidget(self.lbl_spo2_value)

        self.lbl_spo2_status = self._make_value_label("Estado SpO2", "-----".ljust(_SPO2_STATUS_WIDTH))
        self.lbl_spo2_status.setFixedWidth(320)
        spo2_layout.addWidget(self.lbl_spo2_status)
        spo2_layout.addStretch()

        grid.addWidget(spo2_card, 1, 2, 1, 1)

        # ─── CARD 7: ACCIONES (grid único sin huecos) ─────────────────────
        actions_card, actions_layout = self._make_card("Acciones", _CARD_ROW0_MIN_HEIGHT, fixed_width=False)

        # Grid: Fila 0 (Medir ahora, Aplicar, Reset), Fila 1 (Historial)
        buttons_grid = QGridLayout()
        buttons_grid.setSpacing(10)
        buttons_grid.setContentsMargins(0, 0, 0, 0)

        self.btn_measure_now = QPushButton("Medir\n ahora")
        self.btn_measure_now.clicked.connect(self.measure_now_requested.emit)

        self.btn_apply = QPushButton("Aplicar")
        self.btn_apply.clicked.connect(self._on_apply_clicked)

        self.btn_reset = QPushButton("Reset\n módulo")
        self.btn_reset.clicked.connect(self._on_reset_clicked)

        self.btn_history = QPushButton("Historial")
        self.btn_history.clicked.connect(self.history_requested.emit)

        # Fila 0: botones en columnas 0, 1, 2
        buttons_grid.addWidget(self.btn_measure_now, 0, 0)
        buttons_grid.addWidget(self.btn_apply, 0, 1)
        buttons_grid.addWidget(self.btn_reset, 0, 2)

        # Fila 1: Historial en columna 0
        buttons_grid.addWidget(self.btn_history, 0, 3)

        actions_layout.addLayout(buttons_grid)

        grid.addWidget(actions_card, 2, 0, 1, 2)

        grid.setRowStretch(0, 0)
        grid.setRowStretch(1, 0)
        grid.setRowStretch(2, 0)

        main_layout.addLayout(grid)
        main_layout.addStretch()

        self._apply_theme_styles()

    def _on_theme_changed(self, _theme_name: str):
        self._apply_theme_styles()

    def _apply_theme_styles(self):
        t = ThemeManager.get_tokens()
        bg_primary = t.get("bg_primary", "#FCFCFC")
        bg_card = t.get("bg_card", "#ffffff")
        bg_input = t.get("bg_input", "#ffffff")
        text_primary = t.get("text_primary", "#0f172a")
        text_secondary = t.get("text_secondary", "#475569")
        text_muted = t.get("text_muted", "#64748b")
        border = t.get("border", "#cbd5e1")
        border_strong = t.get("border_strong", "#94a3b8")
        accent = t.get("accent", "#2563eb")
        btn_bg = t.get("btn_primary_bg", "#06298a")
        btn_hover = t.get("btn_primary_hover", "#1e293b")

        self.setStyleSheet(f"""
            QWidget#NibpConfigScreen {{ background-color: {bg_primary}; }}
            QFrame#card {{
                background-color: {bg_card};
                border: 1px solid {border};
                border-radius: 14px;
            }}
        """)
        self.lbl_main_title.setStyleSheet(
            f"font-size: 28px; font-weight: bold; color: {text_primary}; background: transparent;"
        )
        self.btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('btn_secondary_bg', '#64748b')};
                color: {t.get('btn_secondary_text', '#ffffff')};
                font-size: 20px;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 8px;
                border: 1px solid {border};
            }}
            QPushButton:hover {{ background-color: {accent}; color: #ffffff; }}
        """)

        combo_style = f"""
            QComboBox {{
                font-size: 22px;
                min-width: 200px;
                color: {text_primary};
                background-color: {bg_input};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 6px 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {bg_card};
                color: {text_primary};
                selection-background-color: {accent};
                selection-color: #ffffff;
                border: 1px solid {border};
            }}
        """
        for cmb in (self.cmb_method, self.cmb_start_pressure, self.cmb_interval):
            cmb.setStyleSheet(combo_style)

        chk_style = f"""
            QCheckBox {{ color: {text_primary}; font-size: 20px; background: transparent; }}
            QCheckBox::indicator {{ width: 28px; height: 28px; border: 2px solid {border_strong}; border-radius: 4px; background: {bg_input}; }}
            QCheckBox::indicator:checked {{ background-color: {accent}; border-color: {accent}; }}
        """
        for chk in (self.chk_auto, self.chk_spo2):
            chk.setStyleSheet(chk_style)

        btn_style = f"""
            QPushButton {{
                background-color: {btn_bg};
                color: #ffffff;
                font-size: 22px;
                font-weight: bold;
                padding: 12px 28px;
                border-radius: 10px;
                min-height: 70px;
            }}
            QPushButton:hover {{ background-color: {btn_hover}; }}
            QPushButton:pressed {{ background-color: {accent}; }}
            QPushButton:disabled {{ background-color: {border}; color: {text_muted}; }}
        """
        for btn in (self.btn_measure_now, self.btn_apply, self.btn_reset, self.btn_history):
            btn.setStyleSheet(btn_style)

        for title_lbl in self._card_titles:
            title_lbl.setStyleSheet(
                f"font-size: 20px; font-weight: bold; color: {text_primary}; background: transparent;"
                f"padding-bottom: 6px; border: none; border-bottom: 1px solid {border};"
            )
        for val_lbl in self._value_labels:
            val_lbl.setStyleSheet(f"font-size: 26px; font-weight: bold; color: {text_primary};")
        for h_lbl in self._hint_labels:
            h_lbl.setStyleSheet(f"font-size: 16px; color: {text_muted};")

        self.lbl_cuff.setStyleSheet(f"font-size: 22px; color: {text_primary};")
        self.lbl_status.setStyleSheet(f"font-size: 20px; color: {text_secondary};")
        self.lbl_nibp_error.setStyleSheet(f"font-size: 16px; color: {t.get('danger', '#b91c1c')};")
        self.lbl_interval.setStyleSheet(f"font-size: 22px; color: {text_primary};")

    def _make_card(self, title_text: str, min_height: int, fixed_width: bool = True):
        """Card con patrón uniforme: título (con raya via QSS) + widgets añadidos directo al layout del card."""
        card = QFrame()
        card.setObjectName("card")
        card.setMinimumHeight(min_height)
        if fixed_width:
            card.setMinimumWidth(_CARD_FIXED_WIDTH)
            card.setMaximumWidth(_CARD_FIXED_WIDTH)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(7)

        title = QLabel(title_text)
        title.setObjectName("card_title")
        title.setMinimumHeight(28)
        self._card_titles.append(title)
        card_layout.addWidget(title)

        return card, card_layout

    def _make_value_label(self, name: str, value: str) -> QLabel:
        label = QLabel(f"{name}: {value}")
        self._value_labels.append(label)
        return label

    # ------------------------------------------------------------------
    # Config <-> UI
    # ------------------------------------------------------------------
    def _apply_config_to_ui(self):
        method = self._config.get("method", 2)
        index = self.cmb_method.findData(method)
        self.cmb_method.setCurrentIndex(index if index >= 0 else 1)

        start_pressure = self._config.get("start_pressure_mmhg", 160)
        index = self.cmb_start_pressure.findData(start_pressure)
        self.cmb_start_pressure.setCurrentIndex(index if index >= 0 else 0)

        self.chk_auto.setChecked(bool(self._config.get("auto_during_therapy", False)))

        interval = self._config.get("interval_min", 15)
        index = self.cmb_interval.findData(interval)
        self.cmb_interval.setCurrentIndex(index if index >= 0 else 0)

        self.chk_spo2.setChecked(bool(self._config.get("spo2_enabled", False)))

    def _on_apply_clicked(self):
        # NO cambia enabled/port: eso solo lo edita CommPortScreen.
        # patient_mode siempre es "adult" (forzado internamente)
        
        # Mostrar diálogo de confirmación
        dialog = FloatingConfirmDialog(self.parent_window if self.parent_window else self)
        title = "Aplicar configuración del baumanómetro"
        message = (
            "Se enviarán al módulo el método, la presión de arranque,\n"
            "el intervalo y el estado de SpO2.\n"
            "¿Aplica estos parámetros?"
        )
        result = dialog.show_confirm(message, accept_text="Aplicar", cancel_text="Cancelar")
        
        if not result:
            # Usuario canceló: no guardar configuración ni emitir señal
            logger.info("[NIBP] Aplicación de configuración cancelada por usuario")
            return
        
        # Usuario confirmó: guardar y emitir
        self._config["patient_mode"] = "adult"
        self._config["method"] = self.cmb_method.currentData()
        self._config["start_pressure_mmhg"] = self.cmb_start_pressure.currentData()
        self._config["auto_during_therapy"] = self.chk_auto.isChecked()
        self._config["interval_min"] = self.cmb_interval.currentData()
        self._config["spo2_enabled"] = self.chk_spo2.isChecked()

        self._save_config()
        self.settings_applied.emit(dict(self._config))

    def _on_reset_clicked(self):
        # Mostrar diálogo de confirmación antes de resetear el módulo
        dialog = FloatingConfirmDialog(self.parent_window if self.parent_window else self)
        title = "Reiniciar módulo de presión"
        message = (
            "Se reiniciará el baumanómetro. Si hay una medición\n"
            "en curso se cancelará. ¿Continúa?"
        )
        result = dialog.show_confirm(message, accept_text="Reiniciar", cancel_text="Cancelar")
        
        if result:
            # Usuario confirmó reset
            logger.info("[NIBP] Reset del módulo solicitado por usuario")
            
            # Poner las mediciones en "—"
            self.lbl_sys.setText("SYS: —")
            self.lbl_dia.setText("DIA: —")
            self.lbl_map.setText("MAP: —")
            self.lbl_hr.setText("FC: —")
            
            # Dejar el error visible (no limpiar aquí)
            # Deshabilitar "Medir ahora" durante el reset
            self.btn_measure_now.setEnabled(False)
            
            # Emitir señal de reset
            self.reset_requested.emit()
            
            # Habilitar botón a los 3s (después de que el módulo complete el reset)
            QTimer.singleShot(3000, self.clear_error)
        else:
            # Usuario canceló
            logger.info("[NIBP] Reset del módulo cancelado por usuario")

    def _on_chk_spo2_toggled(self, checked: bool):
        self._config["spo2_enabled"] = checked
        self._save_config()
        if checked:
            self.spo2_on_requested.emit()
        else:
            self.spo2_off_requested.emit()

    def _on_close_clicked(self):
        if self.parent_window and hasattr(self.parent_window, "show_dialysis_screen"):
            self.parent_window.show_dialysis_screen()

    # ------------------------------------------------------------------
    # Slots públicos (conectados por el composition root a NibpParCommunication)
    # ------------------------------------------------------------------
    def update_connection(self, connected: bool, port: str):
        self.lbl_status.setText(f"Conectado ({port})" if connected else "Desconectado")
        if connected:
            self.lbl_nibp_error.setText("")

    def _mark_connected_if_needed(self):
        # El módulo no siempre reporta connected_changed antes de la primera trama; si
        # ya llegan datos, el puerto está evidentemente abierto.
        if self.lbl_status.text() == "Desconectado":
            self.lbl_status.setText("Conectado")

    def update_error(self, error_code: str, error_text: str):
        # NO pisar "Conectado": el error de medición va en una línea aparte.
        self.lbl_nibp_error.setText(f"Error {error_code}: {error_text}")
        # Deshabilitar "Medir ahora" SOLO si es M15 con "fallo repetido"
        # (contador llegó a 3 y se detuvo el reintento automático)
        if error_code == "M15" and "fallo repetido" in error_text:
            self.btn_measure_now.setEnabled(False)
        else:
            # M10, M07, etc.: el botón queda habilitado (operador puede lanzar otra toma)
            self.btn_measure_now.setEnabled(True)

    def clear_error(self):
        self.lbl_nibp_error.setText("")
        # Habilitar "Medir ahora" cuando se limpia el error
        self.btn_measure_now.setEnabled(True)

    def update_measurement(self, sys_mmhg: int, dia_mmhg: int, map_mmhg: int, hr_bpm: int):
        # Mostrar SYS/DIA/MAP/FC solo si los CUATRO son >= 0. Si alguno < 0, mostrar "—" en los cuatro.
        all_valid = all(v >= 0 for v in [sys_mmhg, dia_mmhg, map_mmhg, hr_bpm])
        
        if all_valid:
            self._mark_connected_if_needed()
            self.lbl_sys.setText(f"SYS: {sys_mmhg}")
            self.lbl_dia.setText(f"DIA: {dia_mmhg}")
            self.lbl_map.setText(f"MAP: {map_mmhg}")
            self.lbl_hr.setText(f"FC: {hr_bpm}")
        else:
            self.lbl_sys.setText("SYS: —")
            self.lbl_dia.setText("DIA: —")
            self.lbl_map.setText("MAP: —")
            self.lbl_hr.setText("FC: —")

    def update_cuff(self, mmhg: int, caution: int, status: int):
        self._mark_connected_if_needed()
        self.lbl_cuff.setText(f"Manguito: {mmhg} mmHg")

    def update_spo2(self, data):
        if not data:
            self.lbl_spo2_value.setText("SpO2: ----")
            self.lbl_spo2_status.setText(f"Estado SpO2: {'-----'.ljust(_SPO2_STATUS_WIDTH)}")
            return

        self._mark_connected_if_needed()
        value = data.get("spo2")
        self.lbl_spo2_value.setText(f"SpO2: {value} %" if value is not None else "SpO2: ----")

        if data.get("sensor_off"):
            status_text = "Sensor desconectado"
        elif data.get("no_finger"):
            status_text = "Sin dedo"
        elif data.get("no_pulse"):
            status_text = "Sin pulso"
        elif data.get("searching"):
            status_text = "Buscando…"
        elif data.get("signal_weak"):
            status_text = "Señal débil"
        elif value is None:
            status_text = "-----"
        else:
            status_text = "OK"
        self.lbl_spo2_status.setText(f"Estado SpO2: {status_text.ljust(_SPO2_STATUS_WIDTH)}")
