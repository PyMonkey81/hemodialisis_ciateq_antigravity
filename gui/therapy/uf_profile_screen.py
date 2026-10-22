from __future__ import annotations

import math

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from core.state_manager import TreatmentPhase
from gui.theme_manager import ThemeManager
from logic.uf_profile import ProfileType, UFProfile


class _SelectableSlider(QSlider):
    """Vertical slider whose value only changes via external setValue(); touch/mouse only select it."""

    def __init__(self, index: int, on_select, parent=None):
        super().__init__(Qt.Vertical, parent)
        self._index = index
        self._on_select = on_select
        self.setFocusPolicy(Qt.NoFocus)

    def mousePressEvent(self, event):
        self._on_select(self._index)
        event.accept()

    def mouseMoveEvent(self, event):
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()

    def wheelEvent(self, event):
        event.ignore()

    def keyPressEvent(self, event):
        event.ignore()

    def event(self, event):
        if event.type() in (QEvent.TouchBegin, QEvent.TouchUpdate, QEvent.TouchEnd):
            if event.type() == QEvent.TouchBegin:
                self._on_select(self._index)
            event.accept()
            return True
        return super().event(event)


class UFProfileScreen(QWidget):
    profile_saved = Signal()

    def __init__(self, parent=None, values_dict=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_values = values_dict if values_dict is not None else {}
        self._phase = TreatmentPhase.IDLE
        self._selected_index = 0
        self._slider_values = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self._setup_ui()

    def _setup_ui(self):
        baseline = ThemeManager.get_therapy_config_baseline() or {}
        colors = baseline.get("colors", {})

        self.style_primary_btn = """
            QPushButton {
                background: %s;
                color: #ffffff;
                font-weight: bold;
                font-size: 20px;
                border-radius: 12px;
                border: 3px solid %s;
                min-height: 56px;
                padding: 6px 12px;
            }
            QPushButton:pressed {
                background: #334155;
            }
        """ % (colors.get("button_enabled_bg", "#39ec21"), colors.get("button_border", "#1e293b"))

        self.style_secondary_btn = """
            QPushButton {
                background: #0f172a;
                color: #ffffff;
                font-weight: bold;
                font-size: 18px;
                border-radius: 12px;
                border: 2px solid #1e293b;
                min-height: 52px;
                padding: 6px 12px;
            }
            QPushButton:pressed {
                background: #334155;
            }
        """

        self.style_toggle_btn = """
            QPushButton {
                background: #f1f5f9;
                color: #0f172a;
                font-weight: 600;
                font-size: 18px;
                border-radius: 10px;
                border: 2px solid #94a3b8;
                min-height: 52px;
                padding: 8px 10px;
            }
            QPushButton:checked {
                background: #0f766e;
                color: #ffffff;
                border: 2px solid #134e4a;
            }
            QPushButton:pressed {
                background: #115e59;
                color: #ffffff;
            }
        """

        card_style = """
            QFrame#Card {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 14px;
            }
        """

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(18)

        self.lbl_screen = QLabel("Perfil UF")
        self.lbl_screen.setStyleSheet("font-size: 26px; font-weight: bold; color: #1e3a8a;")
        self.lbl_screen.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.lbl_screen)
        
        self.lbl_therapy_time = QLabel("Tiempo de terapia: 00:00 (0 min)")
        self.lbl_therapy_time.setStyleSheet("font-size: 22px; font-weight: 600; color: #1e3a8a;")
        self.lbl_therapy_time.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.lbl_therapy_time)

        self.top_card = self._build_top_card(card_style)
        main_layout.addWidget(self.top_card)

        self.main_card = self._build_main_card(card_style)
        main_layout.addWidget(self.main_card)

        self._setup_modes()
        self._set_selected_slider(0)
        self._slider_values = [self._get_uf_setpoint()] * 6
        for idx, slider in enumerate(self.slider_widgets):
            slider.setValue(int(round(self._slider_values[idx] * 100.0)))
        self._update_selected_value_label()
        self.refresh_from_parent()
        self.apply_theme_styles()
        try:
            ThemeManager.instance().theme_changed.connect(lambda _t: self.apply_theme_styles())
        except Exception:
            pass

    def _build_top_card(self, card_style: str) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setStyleSheet(card_style)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(18)

        self.lbl_selected_value = QLabel("0.00 L/h")
        self.lbl_selected_value.setStyleSheet(
            "font-size: 30px; font-weight: bold; color: #0f172a;"
        )
        self.lbl_selected_value.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.lbl_selected_value, 1)

        self.btn_accept = QPushButton("Aceptar")
        self.btn_accept.setStyleSheet(self.style_primary_btn)
        self.btn_accept.clicked.connect(self._on_save_profile)
        card_layout.addWidget(self.btn_accept)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setStyleSheet(self.style_secondary_btn)
        self.btn_cancel.clicked.connect(self._on_cancel_profile)
        card_layout.addWidget(self.btn_cancel)

        self.btn_save = self.btn_accept
        self.btn_back = self.btn_cancel
        return card

    def _build_main_card(self, card_style: str) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setStyleSheet(card_style)
        main_layout = QHBoxLayout(card)
        main_layout.setContentsMargins(20, 18, 20, 18)
        main_layout.setSpacing(18)

        left_panel = QVBoxLayout()
        left_panel.setSpacing(18)
        left_panel.setContentsMargins(0, 0, 0, 0)

        self.btn_plus = QPushButton("+")
        self.btn_plus.setFixedWidth(90)
        self.btn_plus.setMinimumHeight(90)
        self.btn_plus.setStyleSheet(
            "QPushButton { background: #0f172a; color: #ffffff; font-size: 42px; font-weight: bold; border-radius: 14px; }"
            "QPushButton:pressed { background: #334155; }"
        )
        self.btn_plus.clicked.connect(self._on_plus_clicked)

        self.btn_minus = QPushButton("-")
        self.btn_minus.setFixedWidth(90)
        self.btn_minus.setMinimumHeight(90)
        self.btn_minus.setStyleSheet(
            "QPushButton { background: #0f172a; color: #ffffff; font-size: 42px; font-weight: bold; border-radius: 14px; }"
            "QPushButton:pressed { background: #334155; }"
        )
        self.btn_minus.clicked.connect(self._on_minus_clicked)

        self.btn_adjust = QPushButton("Ajuste")
        self.btn_adjust.setFixedWidth(90)
        self.btn_adjust.setMinimumHeight(90)
        self.btn_adjust.setStyleSheet(
            "QPushButton { background: #0f766e; color: #ffffff; font-size: 18px; font-weight: bold; border-radius: 12px; }"
            "QPushButton:pressed { background: #115e59; }"
        )
        self.btn_adjust.clicked.connect(self._on_adjust_clicked)

        left_panel.addStretch(1)
        left_panel.addWidget(self.btn_plus)
        left_panel.addWidget(self.btn_minus)
        left_panel.addSpacing(10)
        left_panel.addWidget(self.btn_adjust)
        left_panel.addStretch(1)

        main_layout.addLayout(left_panel)

        self.slider_frame = QFrame()
        self.slider_frame.setStyleSheet("background: transparent;")
        self.slider_layout = QHBoxLayout(self.slider_frame)
        self.slider_layout.setSpacing(8)
        self.slider_layout.setContentsMargins(8, 8, 8, 8)

        self.slider_widgets = []
        self.slider_labels = []
        for index in range(6):
            column = QVBoxLayout()
            column.setSpacing(10)
            slider = _SelectableSlider(index, self._set_selected_slider)
            slider.setRange(0, 200)
            slider.setSingleStep(1)
            slider.setPageStep(1)
            slider.setTickPosition(QSlider.NoTicks)
            slider.setMinimumHeight(220)
            slider.setMinimumWidth(78)
            slider.setStyleSheet(self._slider_style(False))

            label = QLabel(f"{index + 1}")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 12px; color: #475569; font-weight: 600;")
            label.setMinimumHeight(30)

            column.addWidget(slider, 1, Qt.AlignHCenter)
            column.addWidget(label)
            self.slider_layout.addLayout(column)
            self.slider_widgets.append(slider)
            self.slider_labels.append(label)

        main_layout.addWidget(self.slider_frame, 1)

        self.type_button_group = QButtonGroup(self)
        self.type_button_group.setExclusive(True)

        mode_panel = QVBoxLayout()
        mode_panel.setSpacing(12)
        mode_panel.setContentsMargins(0, 0, 0, 0)

        self.btn_type_none = QPushButton("Sin\nperfil")
        self.btn_type_linear = QPushButton("Lineal")
        self.btn_type_exp = QPushButton("Exp")
        self.btn_type_step = QPushButton("Escalón")

        for btn in [self.btn_type_none, self.btn_type_linear, self.btn_type_exp, self.btn_type_step]:
            btn.setCheckable(True)
            btn.setStyleSheet(self.style_toggle_btn)
            self.type_button_group.addButton(btn)
            mode_panel.addWidget(btn)

        self.btn_type_none.setChecked(True)
        main_layout.addLayout(mode_panel)

        return card

    def _slider_style(self, selected: bool) -> str:
        tokens = ThemeManager.get_tokens()
        is_mono = bool(tokens.get("monochrome", False))
        is_dark = bool(tokens.get("is_dark", False))
        if is_mono:
            # "El relleno de la barra pasa a gris medio y el contorno a gris."
            accent = "#9CA3AF" if selected else "#B0B8C4"
            empty = "#E5E7EB"
            border = "#6B7280" if selected else "#D1D5DB"
        elif is_dark:
            accent = tokens.get("primary", "#38BDF8") if selected else tokens.get("primary_hover", "#0284C7")
            empty = tokens.get("bg_card_alt", "#1E293B")
            border = tokens.get("primary", "#38BDF8") if selected else tokens.get("border_card", "#334155")
        else:
            accent = "#14b8a6" if selected else "#2dd4bf"
            empty = "#dfe7ee"
            border = "#0f766e" if selected else "#cbd5e1"

        return (
            "QSlider { background: transparent; min-height: 220px; }"
            "QSlider::groove:vertical { background: transparent; width: 42px; border-radius: 7px; }"
            "QSlider::sub-page:vertical { background: %s; border-radius: 2px; }"
            "QSlider::add-page:vertical { background: %s; border-radius: 2px; }"
            "QSlider::handle:vertical { background: transparent; width: 0px; height: 0px; border: none; }"
            "QSlider { border: %s solid %s; border-radius: 14px; padding: 2px; }"
        ) % (empty, accent, "3px" if selected else "2px", border)

    def _setup_modes(self):
        self.type_button_group.buttonToggled.connect(self._on_profile_type_changed)

    def _selected_type(self) -> ProfileType:
        if self.btn_type_linear.isChecked():
            return ProfileType.LINEAR
        if self.btn_type_step.isChecked():
            return ProfileType.STEP
        if self.btn_type_exp.isChecked():
            return ProfileType.CUSTOM
        return ProfileType.NONE

    def _set_selected_slider(self, index: int):
        self._selected_index = max(0, min(5, index))
        for i, slider in enumerate(self.slider_widgets):
            slider.setStyleSheet(self._slider_style(i == self._selected_index))
        self._update_selected_value_label()

    def _on_plus_clicked(self):
        if not self.slider_widgets:
            return
        idx = self._selected_index
        next_value = self._clamp_value(self._slider_values[idx] + 0.05)
        self._slider_values[idx] = next_value
        self.slider_widgets[idx].blockSignals(True)
        self.slider_widgets[idx].setValue(int(round(next_value * 100.0)))
        self.slider_widgets[idx].blockSignals(False)
        self._update_selected_value_label()

    def _on_minus_clicked(self):
        if not self.slider_widgets:
            return
        idx = self._selected_index
        next_value = self._clamp_value(self._slider_values[idx] - 0.05)
        self._slider_values[idx] = next_value
        self.slider_widgets[idx].blockSignals(True)
        self.slider_widgets[idx].setValue(int(round(next_value * 100.0)))
        self.slider_widgets[idx].blockSignals(False)
        self._update_selected_value_label()

    def _update_selected_value_label(self):
        value = self._slider_values[self._selected_index]
        self.lbl_selected_value.setText(f"{value:.2f} L/h")
        self._update_slider_numeric_labels()

    def _update_slider_numeric_labels(self):
        for idx, label in enumerate(self.slider_labels):
            value = self._slider_values[idx] if idx < len(self._slider_values) else 0.0
            label.setText(f"{idx + 1}\n{value:.2f}")

    def _on_profile_type_changed(self):
        self._update_selected_value_label()

    def _get_uf_setpoint(self) -> float:
        """Obtiene el flujo UF actual en L/h (ultraFilterPumpSpeed, ya persistido en L/h)."""
        try:
            value = self.current_values.get("ultraFilterPumpSpeed")
            if value is not None:
                return self._clamp_value(float(value))
        except (TypeError, ValueError):
            pass

        return 0.0

    def _clamp_value(self, value: float) -> float:
        return max(0.0, min(2.0, float(value)))

    def _on_cancel_profile(self):
        self.refresh_from_parent()
        self.apply_theme_styles()
        try:
            ThemeManager.instance().theme_changed.connect(lambda _t: self.apply_theme_styles())
        except Exception:
            pass
        self._on_back()

    def _on_back(self):
        if self.parent_window and hasattr(self.parent_window, "show_therapy_config_screen"):
            self.parent_window.show_therapy_config_screen()

    def _on_save_profile(self):
        profile_type = self._selected_type()
        therapy_duration_min = self._therapy_duration_min_from_values()

        values = self._slider_values[:]
        profile = UFProfile(
            enabled=(profile_type != ProfileType.NONE),
            profile_type=profile_type,
            therapy_duration_min=therapy_duration_min,
            start_uf=float(values[0]),
            end_uf=float(values[-1]),
            step_high=float(max(values[0], values[-1])),
            step_low=float(min(values[0], values[-1])),
            step_change_at_percent=50.0,
            points=[float(v) for v in values],
        )

        if self.parent_window and hasattr(self.parent_window, "set_uf_profile"):
            ok = self.parent_window.set_uf_profile(profile, show_message=True)
            if ok:
                self.profile_saved.emit()
                self._on_back()

    def _therapy_duration_min_from_values(self) -> int:
        hours = int(self.current_values.get("heparineTherapyHours", 0) or 0)
        minutes = int(self.current_values.get("heparineTherapyMinutes", 0) or 0)
        return max(1, (hours * 60) + minutes)

    def refresh_from_parent(self):
        self._update_therapy_time_label()

        if not self.parent_window or not hasattr(self.parent_window, "uf_profile"):
            setpoint = self._get_uf_setpoint()
            self._slider_values = [setpoint] * 6
            self.btn_type_none.setChecked(True)
            for idx, slider in enumerate(self.slider_widgets):
                slider.setValue(int(round(self._slider_values[idx] * 100.0)))
            self._set_selected_slider(self._selected_index)
            self._update_selected_value_label()
            return

        profile: UFProfile = self.parent_window.uf_profile

        if not profile.enabled or profile.profile_type == ProfileType.NONE:
            self.btn_type_none.setChecked(True)
            setpoint = self._get_uf_setpoint()
            self._slider_values = [setpoint] * 6
        elif getattr(profile, "points", None) and len(profile.points) == 6:
            if profile.profile_type == ProfileType.LINEAR:
                self.btn_type_linear.setChecked(True)
            elif profile.profile_type == ProfileType.STEP:
                self.btn_type_step.setChecked(True)
            else:
                self.btn_type_exp.setChecked(True)
            self._slider_values = [self._clamp_value(float(v)) for v in profile.points]
        elif profile.profile_type == ProfileType.LINEAR:
            self.btn_type_linear.setChecked(True)
            self._slider_values = self._generate_linear_profile_from_values(
                float(profile.start_uf), float(profile.end_uf)
            )
        elif profile.profile_type == ProfileType.STEP:
            self.btn_type_step.setChecked(True)
            high = float(profile.step_high if profile.step_high else profile.start_uf)
            low = float(profile.step_low if profile.step_low else profile.end_uf)
            self._slider_values = self._generate_step_from_ends(high, low)
        else:
            self.btn_type_exp.setChecked(True)
            self._slider_values = self._generate_exp_profile_from_values(
                float(profile.start_uf), float(profile.end_uf)
            )

        for idx, slider in enumerate(self.slider_widgets):
            slider.setValue(int(round(self._slider_values[idx] * 100.0)))

        self._set_selected_slider(self._selected_index)
        self._update_selected_value_label()

    def _generate_linear_profile_from_values(self, start: float, end: float):
        values = []
        for i in range(6):
            progress = i / 5.0
            values.append(start + (end - start) * progress)
        return [self._clamp_value(v) for v in values]

    def _generate_exp_profile_from_values(self, start: float, end: float):
        return self._calculate_decay_curve(start, end)

    def _update_therapy_time_label(self):
        hours = int(self.current_values.get("heparineTherapyHours", 0) or 0)
        minutes = int(self.current_values.get("heparineTherapyMinutes", 0) or 0)
        total_min = (hours * 60) + minutes
        self.lbl_therapy_time.setText(f"Tiempo de terapia: {hours:02d}:{minutes:02d} ({total_min} min)")

    def update_values(self, new_values: dict):
        self.current_values = new_values
        self._update_therapy_time_label()

    def update_state(self, phase: TreatmentPhase):
        self._phase = phase
        disabled = phase in (TreatmentPhase.CLEANING, TreatmentPhase.ERROR)

        for widget in [
            self.btn_accept,
            self.btn_cancel,
            self.btn_plus,
            self.btn_minus,
            self.btn_adjust,
            self.btn_type_none,
            self.btn_type_linear,
            self.btn_type_exp,
            self.btn_type_step,
        ]:
            widget.setEnabled(not disabled)

        for slider in self.slider_widgets:
            slider.setEnabled(not disabled)

    def _on_adjust_clicked(self):
        """Recalcula las barras según el tipo de perfil actual."""
        profile_type = self._selected_type()

        if profile_type == ProfileType.NONE:
            sp = self._get_uf_setpoint()
            self._slider_values = [sp] * 6
        else:
            start = float(self._slider_values[0])
            end = float(self._slider_values[-1])

            if profile_type == ProfileType.LINEAR:
                self._slider_values = self._generate_linear_from_ends(start, end)
            elif profile_type == ProfileType.CUSTOM:  # Exp
                self._slider_values = self._generate_exp_from_ends(start, end)
            elif profile_type == ProfileType.STEP:
                self._slider_values = self._generate_step_from_ends(start, end)

        for idx, slider in enumerate(self.slider_widgets):
            slider.blockSignals(True)
            slider.setValue(int(round(self._slider_values[idx] * 100.0)))
            slider.blockSignals(False)

        self._set_selected_slider(self._selected_index)
        self._update_selected_value_label()

    def _generate_linear_from_ends(self, start: float, end: float):
        values = []
        for i in range(6):
            progress = i / 5.0
            values.append(start + (end - start) * progress)
        return [self._clamp_value(v) for v in values]

    def _generate_exp_from_ends(self, start: float, end: float):
        return self._calculate_decay_curve(start, end)

    def _generate_step_from_ends(self, start: float, end: float):
        """
        Escalón alternado:
        Alto - Bajo - Alto - Bajo - Alto - Bajo
        """
        return [
            self._clamp_value(start),  # 1 Alto
            self._clamp_value(end),    # 2 Bajo
            self._clamp_value(start),  # 3 Alto
            self._clamp_value(end),    # 4 Bajo
            self._clamp_value(start),  # 5 Alto
            self._clamp_value(end),    # 6 Bajo
        ]

    def _calculate_decay_curve(self, start: float, end: float):
        values = []
        k = 3.0
        for i in range(6):
            progress = i / 5.0
            normalized = (1.0 - math.exp(-k * progress)) / (1.0 - math.exp(-k))
            values.append(start + (end - start) * normalized)
        return [self._clamp_value(v) for v in values]

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_from_parent()
        self.apply_theme_styles()
        try:
            ThemeManager.instance().theme_changed.connect(lambda _t: self.apply_theme_styles())
        except Exception:
            pass


    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        is_mono = bool(tokens.get("monochrome", False))
        is_dark = bool(tokens.get("is_dark", False))

        if is_mono:
            self.setStyleSheet(f"background-color: {tokens['bg_main']};")
            card_style = """
                QFrame#Card {
                    background-color: #FFFFFF;
                    border: 1px solid #D1D5DB;
                    border-radius: 14px;
                }
            """
            self.style_primary_btn = """
                QPushButton {
                    background: #9CA3AF;
                    color: #111827;
                    font-weight: bold;
                    font-size: 18px;
                    border-radius: 12px;
                    border: 2px solid #6B7280;
                    min-height: 52px;
                    padding: 6px 12px;
                }
                QPushButton:hover { background: #6B7280; color: #FFFFFF; }
            """
            self.style_secondary_btn = """
                QPushButton {
                    background: #D9E0E8;
                    color: #374151;
                    font-weight: bold;
                    font-size: 18px;
                    border-radius: 12px;
                    border: 2px solid #C5CDD6;
                    min-height: 52px;
                    padding: 6px 12px;
                }
                QPushButton:hover { background: #C5CED6; }
            """
            self.style_toggle_btn = """
                QPushButton {
                    background: #D9E0E8;
                    color: #374151;
                    font-weight: 600;
                    font-size: 18px;
                    border-radius: 10px;
                    border: 2px solid #C5CDD6;
                    min-height: 52px;
                    padding: 8px 10px;
                }
                QPushButton:checked {
                    background: #9CA3AF;
                    color: #111827;
                    border: 2px solid #6B7280;
                    font-weight: bold;
                }
            """
            lbl_color = "#374151"
            btn_pm_style = """
                QPushButton { background: #D9E0E8; color: #374151; font-size: 42px; font-weight: bold; border-radius: 14px; border: 2px solid #C5CDD6; }
                QPushButton:hover { background: #C5CED6; }
                QPushButton:pressed { background: #B0B8C4; }
            """
            btn_adj_style = """
                QPushButton { background: #D9E0E8; color: #374151; font-size: 18px; font-weight: bold; border-radius: 12px; border: 2px solid #C5CDD6; }
                QPushButton:hover { background: #C5CED6; }
                QPushButton:pressed { background: #B0B8C4; }
            """
        elif is_dark:
            self.setStyleSheet(f"background-color: {tokens['bg_main']};")
            card_style = f"""
                QFrame#Card {{
                    background-color: {tokens['bg_card']};
                    border: 1px solid {tokens['border_card']};
                    border-radius: 14px;
                }}
            """
            self.style_primary_btn = f"""
                QPushButton {{
                    background: {tokens['primary']};
                    color: #FFFFFF;
                    font-weight: bold;
                    font-size: 18px;
                    border-radius: 12px;
                    border: 2px solid {tokens['primary_hover']};
                    min-height: 52px;
                    padding: 6px 12px;
                }}
                QPushButton:hover {{ background: {tokens['primary_hover']}; }}
            """
            self.style_secondary_btn = f"""
                QPushButton {{
                    background: {tokens['bg_card_alt']};
                    color: {tokens['text_primary']};
                    font-weight: bold;
                    font-size: 18px;
                    border-radius: 12px;
                    border: 2px solid {tokens['border_card']};
                    min-height: 52px;
                    padding: 6px 12px;
                }}
                QPushButton:hover {{ background: {tokens['border_card']}; }}
            """
            self.style_toggle_btn = f"""
                QPushButton {{
                    background: {tokens['bg_card_alt']};
                    color: {tokens['text_secondary']};
                    font-weight: 600;
                    font-size: 18px;
                    border-radius: 10px;
                    border: 2px solid {tokens['border_card']};
                    min-height: 52px;
                    padding: 8px 10px;
                }}
                QPushButton:checked {{
                    background: {tokens['primary']};
                    color: #FFFFFF;
                    border: 2px solid {tokens['primary_hover']};
                }}
            """
            lbl_color = tokens['text_primary']
            btn_pm_style = f"""
                QPushButton {{ background: {tokens['primary']}; color: #FFFFFF; font-size: 42px; font-weight: bold; border-radius: 14px; border: 2px solid {tokens['primary_hover']}; }}
                QPushButton:hover {{ background: {tokens['primary_hover']}; }}
            """
            btn_adj_style = f"""
                QPushButton {{ background: {tokens['bg_card_alt']}; color: {tokens['text_primary']}; font-size: 18px; font-weight: bold; border-radius: 12px; border: 2px solid {tokens['border_card']}; }}
                QPushButton:hover {{ background: {tokens['border_card']}; }}
            """
        else:
            self.setStyleSheet("")
            card_style = """
                QFrame#Card {
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 14px;
                }
            """
            self.style_primary_btn = """
                QPushButton {
                    background: #39ec21;
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 18px;
                    border-radius: 12px;
                    border: 2px solid #1e293b;
                    min-height: 52px;
                    padding: 6px 12px;
                }
                QPushButton:pressed { background: #334155; }
            """
            self.style_secondary_btn = """
                QPushButton {
                    background: #0f172a;
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 18px;
                    border-radius: 12px;
                    border: 2px solid #1e293b;
                    min-height: 52px;
                    padding: 6px 12px;
                }
                QPushButton:pressed { background: #334155; }
            """
            self.style_toggle_btn = """
                QPushButton {
                    background: #f1f5f9;
                    color: #0f172a;
                    font-weight: 600;
                    font-size: 18px;
                    border-radius: 10px;
                    border: 2px solid #94a3b8;
                    min-height: 52px;
                    padding: 8px 10px;
                }
                QPushButton:checked {
                    background: #0f766e;
                    color: #ffffff;
                    border: 2px solid #134e4a;
                }
                QPushButton:pressed { background: #115e59; color: #ffffff; }
            """
            lbl_color = "#1e3a8a"
            btn_pm_style = """
                QPushButton { background: #0f172a; color: #ffffff; font-size: 42px; font-weight: bold; border-radius: 14px; }
                QPushButton:pressed { background: #334155; }
            """
            btn_adj_style = """
                QPushButton { background: #0f766e; color: #ffffff; font-size: 18px; font-weight: bold; border-radius: 12px; }
                QPushButton:pressed { background: #115e59; }
            """

        if hasattr(self, "top_card"):
            self.top_card.setStyleSheet(card_style)
        if hasattr(self, "main_card"):
            self.main_card.setStyleSheet(card_style)
        if hasattr(self, "btn_accept"):
            self.btn_accept.setStyleSheet(self.style_primary_btn)
        if hasattr(self, "btn_cancel"):
            self.btn_cancel.setStyleSheet(self.style_secondary_btn)
        if hasattr(self, "btn_plus"):
            self.btn_plus.setStyleSheet(btn_pm_style)
        if hasattr(self, "btn_minus"):
            self.btn_minus.setStyleSheet(btn_pm_style)
        if hasattr(self, "btn_adjust"):
            self.btn_adjust.setStyleSheet(btn_adj_style)
        if hasattr(self, "lbl_screen"):
            self.lbl_screen.setStyleSheet(f"font-size: 26px; font-weight: bold; color: {lbl_color};")
        if hasattr(self, "lbl_therapy_time"):
            self.lbl_therapy_time.setStyleSheet(f"font-size: 22px; font-weight: 600; color: {lbl_color};")
        if hasattr(self, "lbl_selected_value"):
            self.lbl_selected_value.setStyleSheet(f"font-size: 30px; font-weight: bold; color: {lbl_color};")

        for b in getattr(self, "type_button_group", []).buttons() if hasattr(self, "type_button_group") else []:
            b.setStyleSheet(self.style_toggle_btn)

        if hasattr(self, "slider_widgets"):
            for i, slider in enumerate(self.slider_widgets):
                slider.setStyleSheet(self._slider_style(i == getattr(self, "_selected_index", 0)))
