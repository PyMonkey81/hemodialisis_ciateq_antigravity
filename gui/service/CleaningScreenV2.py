from gui.theme_manager import ThemeManager
from enum import Enum, auto
import logging
import json
import os
from utilities.platform_runtime import get_runtime_config_path

from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QProgressBar, QVBoxLayout, QHBoxLayout,
    QSizePolicy, QFrame
)
from PySide6.QtCore import Qt, QTimer, QElapsedTimer, Signal

from logic.calculos import convertir_flujo_a_ciclos
from gui.components.floating_confirm import FloatingConfirmDialog
from core.state_manager import TreatmentPhase

logger = logging.getLogger(__name__)

CONFIG_FILE_PATH = get_runtime_config_path("cleaning_config.json")

DEFAULT_CONFIG = {
    "modes": {
        "0.0": {
            "time_hours": 0,
            "time_minutes": 15,
            "mode_temp": 35.0,
            "mode_flow": 100.0
        },
        "1.0": {
            "time_hours": 0,
            "time_minutes": 30,
            "mode_temp": 40.0,
            "mode_flow": 120.0
        }
    }
}


class CleaningStep(Enum):
    IDLE = auto()
    PREPARING = auto()
    ACTIVE = auto()
    PAUSED = auto()
    FINISHED = auto()
    ABORTED = auto()


class CleaningScreenV2(QWidget):
    request_setpoint_change = Signal(str, float)
    request_boolean_change = Signal(str, bool)
    cleaning_started_counting = Signal()
    cleaning_stopped_counting = Signal()
    cleaning_phase_changed = Signal(CleaningStep)

    def __init__(self, parent=None, values_dict=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_values = values_dict or {}

        CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.config_data = self._load_config()

        self.step = CleaningStep.IDLE
        self.selected_mode = None
        self.total_time_seconds = 0
        self.remaining_time_seconds = 0
        self.active_duration_seconds = 0.0
        self._active_timer = QElapsedTimer()
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(1000)
        self._progress_timer.timeout.connect(self._on_progress_tick)

        self._mid_pause_done = False
        self._awaiting_line_change = False

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background: #0f172a;")

        self._build_ui()
        self._update_ui_state()
        self.apply_theme_styles()
        try:
            ThemeManager.instance().theme_changed.connect(lambda _t: self.apply_theme_styles())
        except Exception:
            pass

    def _load_config(self):
        if not os.path.exists(CONFIG_FILE_PATH):
            try:
                with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_CONFIG, f, indent=4)
            except Exception as e:
                logger.error(f"No se pudo crear config de limpieza: {e}")
                return DEFAULT_CONFIG

        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            for key, default_mode in DEFAULT_CONFIG["modes"].items():
                config_data.setdefault("modes", {}).setdefault(key, default_mode)

            with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)

            return config_data
        except Exception as e:
            logger.error(f"Error leyendo config de limpieza: {e}")
            return DEFAULT_CONFIG

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(24)

        self.title_label = QLabel("Limpieza / Desinfección")


        self.title_label.setAlignment(Qt.AlignCenter)


        main_layout.addWidget(self.title_label)

        self.phase_label = QLabel("Seleccione modo para iniciar")
        self.phase_label.setAlignment(Qt.AlignCenter)
        self.phase_label.setStyleSheet("color: #94a3b8; font-size: 30px; font-weight: bold;")
        main_layout.addWidget(self.phase_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(1)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("0% - 0/0 seg")
        self.progress_bar.setFixedHeight(54)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background: #1e293b; color: #ffffff; border-radius: 10px; }"
            "QProgressBar::chunk { background: #3b82f6; border-radius: 10px; }"
        )
        main_layout.addWidget(self.progress_bar)

        self.time_label = QLabel("Tiempo configurado: --:--")
        self.temp_label = QLabel("Temperatura: -- °C")
        self.flow_label = QLabel("Flujo: -- ml/min")
        for label in (self.time_label, self.temp_label, self.flow_label):
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color: #cbd5e1; font-size: 26px; font-weight: bold;")
            main_layout.addWidget(label)

        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setSpacing(16)

        self.btn_short = QPushButton("Química Corta")
        self.btn_long = QPushButton("Química Larga")
        for btn in (self.btn_short, self.btn_long):
            btn.setCheckable(True)
            btn.setFixedHeight(80)
            btn.setStyleSheet(self._button_style_blue())

        self.btn_short.clicked.connect(lambda: self._select_mode(0.0))
        self.btn_long.clicked.connect(lambda: self._select_mode(1.0))
        button_layout.addWidget(self.btn_short)
        button_layout.addWidget(self.btn_long)
        main_layout.addWidget(button_frame)

        action_frame = QFrame()
        action_layout = QHBoxLayout(action_frame)
        action_layout.setSpacing(16)

        self.start_button = QPushButton("Iniciar")
        self.start_button.clicked.connect(self.start_cleaning)
        self.stop_button = QPushButton("Detener")
        self.stop_button.clicked.connect(self.abort_cleaning)
        for btn in (self.start_button, self.stop_button):
            btn.setFixedSize(260, 100)
            btn.setStyleSheet(self._button_style_action(btn.text()))

        action_layout.addWidget(self.start_button)
        action_layout.addWidget(self.stop_button)
        main_layout.addWidget(action_frame)

    def _button_style_blue(self):
        tokens = ThemeManager.get_tokens()
        if bool(tokens.get("monochrome", False)):
            return (
                "QPushButton { background: #D9E0E8; color: #374151; font-size: 22px; font-weight: bold;"
                " border-radius: 14px; padding: 12px; border: 2px solid #C5CDD6; }"
                "QPushButton:checked { background: #9CA3AF; color: #111827; border: 2px solid #6B7280; font-weight: bold; }"
                "QPushButton:hover { background: #C5CED6; }"
                "QPushButton:disabled { background: #E5E7EB; color: #B0B8C2; border: 1px solid #D1D5DB; }"
            )
        elif bool(tokens.get("is_dark", False)):
            return (
                f"QPushButton {{ background: {tokens.get('bg_card_alt', '#1E293B')}; color: {tokens.get('text_primary', '#F8FAFC')}; font-size: 22px; font-weight: bold;"
                f" border-radius: 14px; padding: 12px; border: 2px solid {tokens.get('border_card', '#334155')}; }}"
                f"QPushButton:checked {{ background: {tokens.get('primary', '#38BDF8')}; color: #FFFFFF; border: 2px solid {tokens.get('primary_hover', '#0284C7')}; }}"
                f"QPushButton:hover {{ background: {tokens.get('border_card', '#334155')}; }}"
                f"QPushButton:disabled {{ background: {tokens.get('btn_disabled_bg', '#334155')}; color: {tokens.get('btn_disabled_text', '#64748b')}; }}"
            )
        return (
            "QPushButton { background: #2563eb; color: #ffffff; font-size: 22px; font-weight: bold;"
            " border-radius: 14px; padding: 12px; }"
            "QPushButton:checked { background: #22c55e; }"
            "QPushButton:hover { background: #3b82f6; }"
        )

    def _button_style_action(self, label: str):
        tokens = ThemeManager.get_tokens()
        if bool(tokens.get("monochrome", False)):
            return (
                "QPushButton { background: #D9E0E8; color: #374151; font-size: 28px; font-weight: bold;"
                " border-radius: 16px; border: 2px solid #C5CDD6; }"
                "QPushButton:hover { background: #C5CED6; }"
                "QPushButton:pressed { background: #B0B8C4; }"
                "QPushButton:disabled { background: #E5E7EB; color: #B0B8C2; border: 1px solid #D1D5DB; }"
            )
        elif bool(tokens.get("is_dark", False)):
            color = tokens.get("success", "#10b981") if label == "Iniciar" else tokens.get("danger", "#ef4444")
            return (
                f"QPushButton {{ background: {color}; color: #ffffff; font-size: 28px; font-weight: bold;"
                " border-radius: 16px; }"
                "QPushButton:hover { opacity: 0.92; }"
                f"QPushButton:disabled {{ background: {tokens.get('btn_disabled_bg', '#334155')}; color: {tokens.get('btn_disabled_text', '#64748b')}; }}"
            )
        if label == "Iniciar":
            color = "#047857"
        else:
            color = "#dc2626"
        return (
            f"QPushButton {{ background: {color}; color: #ffffff; font-size: 28px; font-weight: bold;"
            " border-radius: 16px; }"
            "QPushButton:hover { opacity: 0.92; }"
        )

    def _update_ui_state(self):
        self.phase_label.setText(self._step_text())
        self.progress_bar.setMaximum(self.total_time_seconds or 1)
        self.progress_bar.setValue(self.total_time_seconds - self.remaining_time_seconds if self.total_time_seconds else 0)
        self.progress_bar.setFormat(f"{self._progress_percentage()}% - {self.total_time_seconds - self.remaining_time_seconds}/{self.total_time_seconds} seg")

        self.start_button.setEnabled(self.step in (CleaningStep.IDLE, CleaningStep.PAUSED) and self.selected_mode is not None)
        self.stop_button.setEnabled(self.step in (CleaningStep.PREPARING, CleaningStep.ACTIVE, CleaningStep.PAUSED))
        self.btn_short.setEnabled(self.step == CleaningStep.IDLE)
        self.btn_long.setEnabled(self.step == CleaningStep.IDLE)

    def _step_text(self) -> str:
        return {
            CleaningStep.IDLE: "Seleccione modo para iniciar",
            CleaningStep.PREPARING: "Preparando limpieza...",
            CleaningStep.ACTIVE: "Limpieza en curso",
            CleaningStep.PAUSED: "Limpieza en pausa",
            CleaningStep.FINISHED: "Limpieza completada",
            CleaningStep.ABORTED: "Limpieza detenida"
        }.get(self.step, "Estado desconocido")

    def _progress_percentage(self) -> int:
        if not self.total_time_seconds:
            return 0
        elapsed = self.total_time_seconds - self.remaining_time_seconds
        return int((elapsed / self.total_time_seconds) * 100)

    def _select_mode(self, mode_value: float):
        if self.step not in (CleaningStep.IDLE, CleaningStep.FINISHED, CleaningStep.ABORTED):
            self._warning("No se puede cambiar de modo durante la limpieza")
            return
        self.selected_mode = mode_value
        self._apply_mode_config(mode_value)
        self._update_ui_state()

    def _apply_mode_config(self, mode_value: float):
        mode_key = str(mode_value)
        mode_config = self.config_data.get("modes", {}).get(mode_key, DEFAULT_CONFIG["modes"][mode_key])
        hours = mode_config.get("time_hours", 0)
        minutes = mode_config.get("time_minutes", 0)
        temp = mode_config.get("mode_temp", 0.0)
        flow = mode_config.get("mode_flow", 0.0)

        self.total_time_seconds = (hours * 3600) + (minutes * 60)
        self.remaining_time_seconds = self.total_time_seconds
        self.time_label.setText(f"Tiempo configurado: {hours:02d}:{minutes:02d}")
        self.temp_label.setText(f"Temperatura: {temp:.1f} °C")
        self.flow_label.setText(f"Flujo: {flow:.1f} ml/min")

        self.request_setpoint_change.emit("heparineTherapyHours", float(hours))
        self.request_setpoint_change.emit("heparineTherapyMinutes", float(minutes))
        self.request_setpoint_change.emit("dialyTempControlSetPoint", float(temp))
        try:
            self.request_setpoint_change.emit("balanceChamberSetTiming", float(convertir_flujo_a_ciclos(flow)))
        except Exception as e:
            logger.error(f"Error al convertir flujo de limpieza: {e}")

    def start_cleaning(self):
        if self.selected_mode is None:
            self._warning("Seleccione un modo antes de iniciar")
            return

        if self.step == CleaningStep.ACTIVE:
            self._warning("La limpieza ya está en curso")
            return

        self._set_step(CleaningStep.PREPARING, "Inicio de limpieza")
        self._request_hardware_start()
        self._update_ui_state()

    def _request_hardware_start(self):
        self.request_setpoint_change.emit("treatmentModeSelection", 3.0)
        self.request_boolean_change.emit("dialyStartDialysisButt", True)
        self.request_boolean_change.emit("dialyStopDialysisButt", False)

    def on_hardware_status(self, status_code: int):
        if self.step != CleaningStep.PREPARING:
            return
        if status_code == 6:
            self._set_step(CleaningStep.ACTIVE, "Hardware listo para desinfección")
            self._begin_active_phase()

    def _begin_active_phase(self):
        if not self._active_timer.isValid():
            self._active_timer.start()
        else:
            self._active_timer.restart()

        self.cleaning_started_counting.emit()
        self._progress_timer.start()
        self._update_ui_state()

    def _on_progress_tick(self):
        if self.step != CleaningStep.ACTIVE:
            return

        if self.remaining_time_seconds > 0:
            self.remaining_time_seconds -= 1
            self._update_ui_state()
            if not self._mid_pause_done and self.remaining_time_seconds <= self.total_time_seconds // 2:
                self._pause_for_line_change()
        else:
            self._finish_cleaning()

    def _pause_for_line_change(self):
        self._accumulate_active_duration()
        self.cleaning_stopped_counting.emit()
        self._set_step(CleaningStep.PAUSED, "Pausa por cambio de línea")
        self._progress_timer.stop()
        self.request_boolean_change.emit("dialyStartDialysisButt", False)
        self.request_boolean_change.emit("dialyStopDialysisButt", True)
        self._mid_pause_done = True
        self._await_line_change_confirmation()

    def _await_line_change_confirmation(self):
        self._awaiting_line_change = True
        dialog = FloatingConfirmDialog(
            title="Cambio de línea",
            message="Cambie la línea y presione Continuar para reanudar o Detener para cancelar.",
            confirm_text="Continuar",
            cancel_text="Detener",
            parent=self
        )
        result = dialog.exec()
        self._awaiting_line_change = False
        if result:
            self._resume_cleaning()
        else:
            self.abort_cleaning()

    def _resume_cleaning(self):
        self._set_step(CleaningStep.PREPARING, "Reanudando limpieza")
        self.request_boolean_change.emit("dialyStartDialysisButt", True)
        self.request_boolean_change.emit("dialyStopDialysisButt", False)

    def _finish_cleaning(self):
        self._accumulate_active_duration()
        self.cleaning_stopped_counting.emit()
        self._progress_timer.stop()
        self.request_boolean_change.emit("dialyStartDialysisButt", False)
        self.request_boolean_change.emit("dialyStopDialysisButt", True)
        self._set_step(CleaningStep.FINISHED, "Limpieza completada")
        self._finalize_cleaning()

    def abort_cleaning(self):
        if self.step not in (CleaningStep.PREPARING, CleaningStep.ACTIVE, CleaningStep.PAUSED):
            return
        self._accumulate_active_duration()
        self.cleaning_stopped_counting.emit()
        self._progress_timer.stop()
        self.request_boolean_change.emit("dialyStartDialysisButt", False)
        self.request_boolean_change.emit("dialyStopDialysisButt", True)
        self._set_step(CleaningStep.ABORTED, "Limpieza detenida")
        self._finalize_cleaning()

    def _accumulate_active_duration(self):
        if self._active_timer.isValid():
            self.active_duration_seconds += self._active_timer.elapsed() / 1000.0
            self._active_timer.restart()
            logger.debug(f"Duración activa acumulada: {self.active_duration_seconds:.2f}s")

    def _finalize_cleaning(self):
        if hasattr(self.parent_window, "finish_cleaning_session"):
            self.parent_window.finish_cleaning_session(self.active_duration_seconds)
        self._update_ui_state()

    def _set_step(self, step: CleaningStep, reason: str = ""):
        if self.step == step:
            return
        logger.info(f"[CleaningScreenV2] {self.step.name} -> {step.name} | {reason}")
        self.step = step
        self.cleaning_phase_changed.emit(step)
        self._update_ui_state()

    def _warning(self, message: str):
        if hasattr(self.parent_window, "show_warning_message"):
            self.parent_window.show_warning_message(message, 3000)
        else:
            logger.warning(message)

    def set_current_values(self, values: dict):
        self.current_values = values

    def reset(self):
        self._progress_timer.stop()
        self._active_timer = QElapsedTimer()
        self.step = CleaningStep.IDLE
        self.selected_mode = None
        self.total_time_seconds = 0
        self.remaining_time_seconds = 0
        self.active_duration_seconds = 0.0
        self._mid_pause_done = False
        self._awaiting_line_change = False
        self.btn_short.setChecked(False)
        self.btn_long.setChecked(False)
        self._update_ui_state()


    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        is_mono = bool(tokens.get("monochrome", False))
        is_dark = bool(tokens.get("is_dark", False))

        if is_mono:
            self.setStyleSheet(f"background: {tokens['bg_main']};")
            if hasattr(self, "title_label"):
                self.title_label.setStyleSheet("color: #4B5563; font-size: 48px; font-weight: bold; background: transparent;")
            if hasattr(self, "phase_label"):
                self.phase_label.setStyleSheet("color: #374151; font-size: 30px; font-weight: bold; background: transparent;")
            if hasattr(self, "progress_bar"):
                self.progress_bar.setStyleSheet(
                    "QProgressBar { background: #E5E7EB; color: #111827; border-radius: 10px; border: 1px solid #D1D5DB; font-size: 20px; font-weight: bold; text-align: center; }"
                    "QProgressBar::chunk { background: #9CA3AF; border-radius: 10px; }"
                )
            for lbl in (getattr(self, "time_label", None), getattr(self, "temp_label", None), getattr(self, "flow_label", None)):
                if lbl:
                    lbl.setStyleSheet("color: #374151; font-size: 26px; font-weight: bold; background: transparent;")
        elif is_dark:
            self.setStyleSheet(f"background: {tokens['bg_main']};")
            if hasattr(self, "title_label"):
                self.title_label.setStyleSheet(f"color: {tokens.get('text_primary', '#F8FAFC')}; font-size: 48px; font-weight: bold; background: transparent;")
            if hasattr(self, "phase_label"):
                self.phase_label.setStyleSheet(f"color: {tokens.get('text_secondary', '#94A3B8')}; font-size: 30px; font-weight: bold; background: transparent;")
            if hasattr(self, "progress_bar"):
                self.progress_bar.setStyleSheet(
                    f"QProgressBar {{ background: {tokens.get('bg_card_alt', '#1E293B')}; color: {tokens.get('text_primary', '#F8FAFC')}; border-radius: 10px; border: 1px solid {tokens.get('border_card', '#334155')}; font-size: 20px; font-weight: bold; text-align: center; }}"
                    f"QProgressBar::chunk {{ background: {tokens.get('primary', '#38BDF8')}; border-radius: 10px; }}"
                )
            for lbl in (getattr(self, "time_label", None), getattr(self, "temp_label", None), getattr(self, "flow_label", None)):
                if lbl:
                    lbl.setStyleSheet(f"color: {tokens.get('text_primary', '#F8FAFC')}; font-size: 26px; font-weight: bold; background: transparent;")
        else:
            self.setStyleSheet("background: #0f172a;")
            if hasattr(self, "title_label"):
                self.title_label.setStyleSheet("color: #cbd5e1; font-size: 48px; font-weight: bold; background: transparent;")
            if hasattr(self, "phase_label"):
                self.phase_label.setStyleSheet("color: #94a3b8; font-size: 30px; font-weight: bold; background: transparent;")
            if hasattr(self, "progress_bar"):
                self.progress_bar.setStyleSheet(
                    "QProgressBar { background: #1e293b; color: #ffffff; border-radius: 10px; text-align: center; }"
                    "QProgressBar::chunk { background: #3b82f6; border-radius: 10px; }"
                )
            for lbl in (getattr(self, "time_label", None), getattr(self, "temp_label", None), getattr(self, "flow_label", None)):
                if lbl:
                    lbl.setStyleSheet("color: #cbd5e1; font-size: 26px; font-weight: bold; background: transparent;")

        if hasattr(self, "btn_short"):
            self.btn_short.setStyleSheet(self._button_style_blue())
        if hasattr(self, "btn_long"):
            self.btn_long.setStyleSheet(self._button_style_blue())
        if hasattr(self, "start_button"):
            self.start_button.setStyleSheet(self._button_style_action("Iniciar"))
        if hasattr(self, "stop_button"):
            self.stop_button.setStyleSheet(self._button_style_action("Detener"))
