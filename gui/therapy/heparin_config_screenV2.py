# gui/therapy/heparin_config_screenV2.py

from PySide6.QtWidgets import (
    QComboBox, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGridLayout, QFrame, QSizePolicy, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QEvent

from gui.components.numpad_modal import NumpadDialog
from gui.components.time_numpad_modal import TimeNumpadDialog
from gui.components.floating_confirm import FloatingConfirmDialog
from gui.components.ui_components import ClickableLineEdit
from gui.theme_manager import ThemeManager
from core.state_manager import TreatmentPhase
from logic.heparin_time import reference_minutes, clamp_heparin_time, was_clamped
from utilities.platform_runtime import safe_float

import logging
logger = logging.getLogger(__name__)


HEPARIN_AUTO_STOP_HOURS_TAG = "heparineAutoStopHours"
HEPARIN_AUTO_STOP_MINUTES_TAG = "heparineAutoStopMinutes"
HEPARIN_BOLUS_EPSILON_ML = 0.01


class PushbuttonEvent(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.setFocusPolicy(Qt.NoFocus)

    def event(self, event):
        if event.type() == QEvent.Type.TouchBegin:
            self.setDown(True)
            self.pressed.emit()
            return True
        if event.type() in (QEvent.Type.TouchEnd, QEvent.Type.TouchCancel):
            self.setDown(False)
            self.released.emit()
            return True
        return super().event(event)


class HeparinConfigScreen(QWidget):
    valueChanged = Signal(str, float)
    request_setpoint_change = Signal(str, float)
    request_boolean_change = Signal(str, bool)
    heparin_enabled_changed = Signal(bool)

    def __init__(self, parent=None, values_dict=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_values = values_dict if values_dict is not None else {}
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self.heparin_pause_latched = False
        self._selected_flujo_index = 1
        self._selected_heparin_flow_index = 1
        self._selected_syringe_index = 0
        self._field_labels = []
        self._ctrl_buttons = []

        self.setup_ui()
        try:
            ThemeManager.instance().theme_changed.connect(self._on_theme_changed)
        except Exception:
            pass


    def setup_ui(self):
        layout = QGridLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(18, 18, 18, 18)

        # ===================== CARDS =====================

        # 1. Bolo
        self.bolus_card = QFrame()
        self.bolus_card.setObjectName("card")
        bolus_layout = QVBoxLayout(self.bolus_card)
        bolus_layout.setContentsMargins(20, 20, 20, 20)
        bolus_layout.setSpacing(18)

        title = QLabel("PARÁMETROS DE BOLO")
        title.setObjectName("card_title")
        bolus_layout.addWidget(title)

        # Volumen bolo
        h = QHBoxLayout()
        self.bolus_label = QLabel("Vol. Bolo Heparina (ml):")
        h.addWidget(self.bolus_label)
        self.input_bolus = ClickableLineEdit("0.0")
        self.input_bolus.setFixedSize(130, 52)
        self.input_bolus.setAlignment(Qt.AlignCenter)
        self.input_bolus.setReadOnly(True)
        self.input_bolus.clicked.connect(
            lambda: self.open_numpad("heparineBolusQuantity", self.input_bolus, "Bolo (ml)")
        )
        h.addWidget(self.input_bolus)        

        self.btn_apply_bolus = QPushButton("APLICAR\n BOLO")
        self.btn_apply_bolus.setFixedHeight(60)
        self.btn_apply_bolus.clicked.connect(self.apply_bolus)
        h.addWidget(self.btn_apply_bolus)
        bolus_layout.addLayout(h)

        bolus_layout.addStretch(1)  # para centrar verticalmente los campos

        layout.addWidget(self.bolus_card, 0, 0)

        # 2. Controles de bomba
        ctrls_card = QFrame()
        ctrls_card.setObjectName("card")
        ctrls_layout = QVBoxLayout(ctrls_card)
        ctrls_layout.setContentsMargins(20, 20, 20, 20)
        ctrls_layout.setSpacing(18)

        title = QLabel("CONTROLES BOMBA HEPARINA")
        title.setObjectName("card_title")
        ctrls_layout.addWidget(title)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)

        for text, tag, is_toggle in [
            ("HOME", "heparinePumpHomePosition", False),
            # REV/FWD/PAUSE ocultos a petición clínica; reactivar si se requieren.
            # ("REV", "heparinePumpREVButton", False),
            # ("FWD", "heparinePumpFWDButton", False),
        ]:
            btn = PushbuttonEvent(text, self)
            btn.setFixedSize(150, 75)
            self._ctrl_buttons.append(btn)
            if is_toggle:
                btn.pressed.connect(lambda t=tag: self.on_user_boolean_command(t, True))
            else:
                btn.pressed.connect(lambda t=tag: self.on_user_boolean_command(t, True))
                btn.released.connect(lambda t=tag: self.on_user_boolean_command(t, False))
            buttons_layout.addWidget(btn)

        ctrls_layout.addLayout(buttons_layout)
        ctrls_layout.addStretch(1)   # para centrar verticalmente los botones

        layout.addWidget(ctrls_card, 1, 0)

        # 3. Parámetros de Heparina (Card grande)
        # ===================== CARD GRANDE: PARÁMETROS DE HEPARINA =====================
        heparin_card = QFrame()
        heparin_card.setObjectName("card")
        heparin_layout = QVBoxLayout(heparin_card)
        heparin_layout.setContentsMargins(20, 20, 20, 20)
        heparin_layout.setSpacing(20)

        title = QLabel("PARÁMETROS DE HEPARINA")
        title.setObjectName("card_title")
        heparin_layout.addWidget(title)

        self.chk_heparin_enabled = QCheckBox("Habilitar infusión de heparina")
        self.chk_heparin_enabled.setChecked(True)
        self.chk_heparin_enabled.toggled.connect(self._on_heparin_enabled_toggled)
        heparin_layout.addWidget(self.chk_heparin_enabled)

        # Campos
        fields = [
            # ("Vol. Dosis Heparina (ml):", "heparineTherapyDosage", "input_heparin"),
            ("Flujo Heparina (ml/h):", None, "heparin_flow_combo"), 
            ("Tamaño de Jeringa:", None, "syringe_combo"),
            ("Vol. Heparina en Jeringa (ml):", "heparineSyringeVolume", "input_vol_hep"),
            ("Tiempo Heparina (hh:mm):", None, "input_heparin_auto_stop"),
        ]

        for label_text, tag, widget_name in fields:
            h = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setMinimumHeight(50)   # consistencia
            self._field_labels.append(lbl)
            h.addWidget(lbl)

            if "input_" in widget_name:
                w = ClickableLineEdit("0.0" if "auto_stop" not in widget_name else "00:00")
                w.setFixedSize(130, 52)
                w.setAlignment(Qt.AlignCenter)
                w.setReadOnly(True)
                
                if "auto_stop" in widget_name:
                    w.clicked.connect(
                        lambda wd=w: self.open_time_numpad(
                            wd, HEPARIN_AUTO_STOP_HOURS_TAG, 
                            HEPARIN_AUTO_STOP_MINUTES_TAG, "Paro automático heparina"
                        )
                    )
                else:
                    title_map = {
                        "input_heparin": "Dosis Heparina",
                        "input_vol_hep": "Vol. Heparina en Jeringa"
                    }
                    w.clicked.connect(
                        lambda t=tag, wd=w, tit=title_map.get(widget_name, ""): 
                        self.open_numpad(t, wd, tit)
                    )
                setattr(self, widget_name, w)

            elif widget_name == "heparin_flow_combo":
                w = QComboBox()
                w.addItems(["1.0", "2.0", "3.0", "4.0"])
                w.currentIndexChanged.connect(self._on_flow_hep_changed)
                setattr(self, widget_name, w)

            elif widget_name == "syringe_combo":
                # Jeringa fija a 20 ml (no editable)
                w = QLabel("20 ml")
                w.setAlignment(Qt.AlignCenter)
                w.setFixedSize(150, 52)
                setattr(self, widget_name, w)

            h.addWidget(w)
            heparin_layout.addLayout(h)

        # ← ESTO ES LO QUE ARREGLA QUE TODO SUBA ARRIBA
        heparin_layout.addStretch(1)

        layout.addWidget(heparin_card, 0, 1, 2, 1)

        # Distribución del grid principal
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setRowStretch(0, 1)
        layout.setRowStretch(1, 1)

        self._apply_theme_styles()

    def _on_theme_changed(self, _theme_name: str):
        self._apply_theme_styles()

    def _apply_theme_styles(self):
        t = ThemeManager.get_tokens()
        bg_card = t.get("bg_card", "#ffffff")
        bg_input = t.get("bg_input", "#e2e8f0")
        text_primary = t.get("text_primary", "#0f172a")
        text_secondary = t.get("text_secondary", "#334155")
        border = t.get("border", "#cbd5e1")
        border_strong = t.get("border_strong", "#64748b")
        accent = t.get("accent", "#3b82f6")
        btn_bg = t.get("btn_primary_bg", "#06298a")
        btn_hover = t.get("btn_primary_hover", "#1e40af")

        self.setStyleSheet(f"""
            QWidget {{ background-color: transparent; }}
            QFrame#card {{
                background-color: {bg_card};
                border: 1px solid {border};
                border-radius: 14px;
            }}
            QLabel#card_title {{
                font-family: 'Segoe UI', Arial, sans-serif;
                color: {text_primary};
                font-size: 28px;
                font-weight: bold;
                border-bottom: 1px solid {border};
                padding-bottom: 10px;
                margin-bottom: 12px;
            }}
        """)

        button_style = f"""
            QPushButton {{ 
                background: {btn_bg}; 
                color: #ffffff; 
                border-radius: 20px; 
                font-weight: bold; 
                font-size: 18px;
            }}
            QPushButton:pressed {{ background: {btn_hover}; }}
        """
        for btn in self._ctrl_buttons:
            btn.setStyleSheet(button_style)

        label_style = f"font-size: 26px; color: {text_secondary}; font-weight: 600;"
        for lbl in self._field_labels:
            lbl.setStyleSheet(label_style)

        self.chk_heparin_enabled.setStyleSheet(
            f"QCheckBox {{ color: {text_primary}; font-size: 20px; background: transparent; }}"
            f"QCheckBox::indicator {{ width: 28px; height: 28px; border: 2px solid {border_strong}; border-radius: 4px; background: {bg_input}; }}"
            f"QCheckBox::indicator:checked {{ background-color: {accent}; border-color: {accent}; }}"
        )

        if hasattr(self, "syringe_combo") and isinstance(self.syringe_combo, QLabel):
            self.syringe_combo.setStyleSheet(
                f"font-size: 24px; color: {text_primary}; background-color: {bg_input}; "
                f"border: 1px solid {border}; border-radius: 5px; padding: 5px; min-width: 150px; text-align: center;"
            )

        heparin_enabled = bool(self.current_values.get("heparineInfusionEnabled", 1.0))
        self._apply_disabled_styles(heparin_enabled)


    def _on_flow_hep_changed(self, index):  
        self._selected_heparin_flow_index = index
        if hasattr(self, "heparin_flow_combo") and self.heparin_flow_combo is not None:
            flujo_value = float(self.heparin_flow_combo.currentText())
            self.current_values["heparineTherapyFlow"] = flujo_value
            if self.parent_window and hasattr(self.parent_window, "current_values"):
                self.parent_window.current_values["heparineTherapyFlow"] = flujo_value
            self.on_user_input_setpoint("heparineTherapyFlow", flujo_value)
            # Recalcular dosage cuando cambia el flujo
            self._recalculate_therapy_dosage()


    def open_numpad(self, tag: str, input_widget: ClickableLineEdit, title: str):
        # Verificar si es bolo y heparina está deshabilitada
        if tag == "heparineBolusQuantity" and not bool(self.current_values.get("heparineInfusionEnabled", 1.0)):
            logger.debug("Numpad de bolo bloqueado: heparina deshabilitada")
            return
        
        dialog = NumpadDialog(self, initial_value="", title=title)
        if dialog.exec():
            new_value = dialog.get_value()
            if new_value is not None:
                float_val = float(new_value)
                
                # --- LÓGICA ESPECIAL PARA EL VOLUMEN DE JERINGA ---
                if tag == "heparineSyringeVolume":
                    if not self._validate_syringe_fill_volume(float_val):
                        return
                    syringe_max_vol = self._syringe_max_volume_ml()
                    self.on_user_input_setpoint("heparineSyringeSize", syringe_max_vol)
                    logger.info("Tamaño de jeringa seleccionado: %.2f ml", syringe_max_vol)

                # Actualizar UI y Diccionarios
                input_widget.setText(f"{float_val:.1f}")
                self.current_values[tag] = float_val
                
                if self.parent_window and hasattr(self.parent_window, "current_values"):
                    self.parent_window.current_values[tag] = float_val
                
                # Escribir al puerto (enviar setpoint)
                self.on_user_input_setpoint(tag, float_val)
                print(f"Setpoint enviado: {tag} = {float_val}")

                # --- EJECUTAR BOLO SI ES EL TAG DE JERINGA ---
                if tag == "heparineSyringeVolume":
                    self._adjust_syringe_volume()
                    logger.info("Ajuste de volumen de jeringa enviado: %.2f ml", float_val)

                if hasattr(input_widget, 'clearFocus'):
                    input_widget.clearFocus()
                self.setFocus()


    def open_time_numpad(self, input_widget: ClickableLineEdit,
                         tag_hours: str = None, tag_minutes: str = None,
                         title: str = "Config. Tiempo"):
        # Bloquear si estamos en RUNNING o PAUSED
        if self.parent_window and hasattr(self.parent_window, "state"):
            phase = self.parent_window.state.current_phase
            if phase in (TreatmentPhase.RUNNING, TreatmentPhase.PAUSED):
                # Campo bloqueado: no abrir numpad
                logger.info("Tiempo de heparina bloqueado en fase %s", phase)
                return
        
        dialog = TimeNumpadDialog(self, initial_hh_mm="", title=title)

        if dialog.exec():
            hours, minutes = dialog.get_hours_minutes()
            if hours is not None and minutes is not None:
                if (
                    tag_hours == HEPARIN_AUTO_STOP_HOURS_TAG
                    and tag_minutes == HEPARIN_AUTO_STOP_MINUTES_TAG
                ):
                    hours, minutes = self._coerce_heparin_auto_stop_time(hours, minutes)

                input_widget.setText(f"{hours:02d}:{minutes:02d}")
                input_widget.clearFocus()  
                if tag_hours:
                    self.current_values[tag_hours] = float(hours)
                    if self.parent_window and hasattr(self.parent_window, "current_values"):
                        self.parent_window.current_values[tag_hours] = float(hours)
                if tag_minutes:
                    self.current_values[tag_minutes] = float(minutes)
                    if self.parent_window and hasattr(self.parent_window, "current_values"):
                        self.parent_window.current_values[tag_minutes] = float(minutes)
                if tag_hours and tag_minutes:
                    self.on_user_input_setpoint(tag_hours, float(hours))
                    self.on_user_input_setpoint(tag_minutes, float(minutes))
                    # Recalcular dosage si cambió el tiempo de paro automático de heparina
                    if tag_hours == HEPARIN_AUTO_STOP_HOURS_TAG:
                        self._recalculate_therapy_dosage()

    def _coerce_heparin_auto_stop_time(self, hours: int, minutes: int) -> tuple[int, int]:
        """
        Valida y ajusta el tiempo de heparina según la regla clínica.
        Delegado a logic/heparin_time.py para lógica pura.
        """
        # Obtener tiempo de referencia según fase
        therapy_h = int(self.current_values.get("heparineTherapyHours", 0) or 0)
        therapy_m = int(self.current_values.get("heparineTherapyMinutes", 0) or 0)
        programmed_minutes = (therapy_h * 60) + therapy_m
        
        # Obtener tiempo restante si está disponible
        remaining_seconds = 0
        if (self.parent_window and hasattr(self.parent_window, "state") and 
            hasattr(self.parent_window, "get_remaining_therapy_minutes")):
            phase = self.parent_window.state.current_phase
            if phase in (TreatmentPhase.RUNNING, TreatmentPhase.PAUSED):
                # Usar get_remaining_therapy_minutes() basado en get_elapsed_seconds()
                remaining_minutes = self.parent_window.get_remaining_therapy_minutes()
                remaining_seconds = int(max(0, remaining_minutes * 60))
        else:
            phase = TreatmentPhase.PREPARING  # default
        
        # Calcular referencia y validar
        ref_minutes = reference_minutes(
            phase=self.parent_window.state.current_phase if self.parent_window and hasattr(self.parent_window, "state") else TreatmentPhase.PREPARING,
            programmed_minutes=programmed_minutes,
            remaining_seconds=remaining_seconds
        )
        
        # Ajustar al máximo permitido
        clamped_h, clamped_m = clamp_heparin_time(hours, minutes, ref_minutes)
        
        # Mostrar aviso si fue recortado
        if was_clamped(hours, minutes, ref_minutes):
            msg = (
                f"Tiempo de heparina limitado a {clamped_h:02d}:{clamped_m:02d}. "
                "No se infunde durante los últimos 30 minutos de la terapia."
            )
            logger.warning(msg)
            if self.parent_window and hasattr(self.parent_window, "show_warning_message"):
                self.parent_window.show_warning_message(msg, 4000)
        
        return clamped_h, clamped_m

    def _toggle_heparin_pause_resume(self):
        """Alterna PAUSE/CONTINUAR para la bomba de heparina con comando latch."""
        self.heparin_pause_latched = not self.heparin_pause_latched
        self.on_user_boolean_command("heparineOperPauseResume", self.heparin_pause_latched)

        if hasattr(self, "btn_pause_hep") and self.btn_pause_hep is not None:
            self.btn_pause_hep.setText("CONT.." if self.heparin_pause_latched else "PAUSE")

        logger.info(
            f"Heparina pause/resume latch -> {self.heparin_pause_latched}"
        )

    def _on_heparin_enabled_toggled(self, checked: bool):
        # Bolo y HOME quedan operables aun deshabilitado: son acciones
        # puntuales de servicio, no infusión automática de terapia.
        if not checked:
            # Mostrar modal de confirmación al desmarcar
            dialog = FloatingConfirmDialog(self.parent_window if self.parent_window else self)
            title = "Suspender infusión de heparina"
            message = (
                "Va a deshabilitar la infusión de heparina para este tratamiento.\n"
                "No se administrará bolo ni infusión continua. Debe indicarse\n"
                "por prescripción médica. ¿Confirma suspender la heparina?"
            )
            result = dialog.show_confirm(message, accept_text="Sí", cancel_text="No")
            
            if not result:  # Usuario seleccionó No
                # Restablecer el estado del checkbox sin emitir la señal
                self.chk_heparin_enabled.blockSignals(True)
                self.chk_heparin_enabled.setChecked(True)
                self.chk_heparin_enabled.blockSignals(False)
                logger.info("[HEPARIN] Deshabilitación cancelada por usuario")
                return
            
            # Usuario confirmó deshabilitar
            logger.info("[HEPARIN] disabled")
            self.current_values["heparineInfusionEnabled"] = 0.0
            # Enviar setpoint de dosis a 0 cuando se deshabilita
            self.on_user_input_setpoint("heparineTherapyDosage", 0.0)
        else:
            # Heparin habilitado: recalcular dosage
            self.current_values["heparineInfusionEnabled"] = 1.0
            self._recalculate_therapy_dosage()
        
        self._update_heparin_dose_fields_enabled(checked)
        if self.parent_window and hasattr(self.parent_window, "set_heparin_infusion_enabled"):
            self.parent_window.set_heparin_infusion_enabled(checked)
        self.heparin_enabled_changed.emit(checked)

    def _update_heparin_dose_fields_enabled(self, enabled: bool):
        # Detectar si estamos en RUNNING o PAUSED
        is_running_or_paused = False
        if self.parent_window and hasattr(self.parent_window, "state"):
            is_running_or_paused = self.parent_window.state.current_phase in (TreatmentPhase.RUNNING, TreatmentPhase.PAUSED)
        
        # Deshabilitar/habilitar tarjeta de bolo completa
        self.bolus_card.setEnabled(enabled)
        self.input_bolus.setEnabled(enabled)
        self.btn_apply_bolus.setEnabled(enabled)
        self.bolus_label.setEnabled(enabled)
        
        # Deshabilitar/habilitar parámetros de heparina
        for widget_name in ("heparin_flow_combo", "input_heparin_auto_stop", "input_vol_hep", "syringe_combo"):
            widget = getattr(self, widget_name, None)
            if widget is not None and hasattr(widget, "setEnabled"):
                # En RUNNING/PAUSED, input_heparin_auto_stop siempre queda deshabilitado
                if widget_name == "input_heparin_auto_stop" and is_running_or_paused:
                    widget.setEnabled(False)
                else:
                    widget.setEnabled(enabled)
        
        # Aplicar estilos QSS para estado disabled
        self._apply_disabled_styles(enabled)

    def _apply_disabled_styles(self, enabled: bool):
        """Aplica estilos QSS para el estado enabled/disabled de controles de heparina."""
        t = ThemeManager.get_tokens()
        bg_card = t.get("bg_card", "#ffffff")
        bg_input = t.get("bg_input", "#e2e8f0")
        bg_alt = t.get("bg_card_alt", "#f1f5f9")
        text_primary = t.get("text_primary", "#0f172a")
        text_secondary = t.get("text_secondary", "#334155")
        text_muted = t.get("text_muted", "#94a3b8")
        border = t.get("border", "#cbd5e1")
        border_strong = t.get("border_strong", "#64748b")
        accent = t.get("accent", "#3b82f6")
        btn_bg = t.get("btn_primary_bg", "#06298a")
        btn_hover = t.get("btn_primary_hover", "#1e40af")

        # Detectar si estamos en RUNNING o PAUSED
        is_running_or_paused = False
        if self.parent_window and hasattr(self.parent_window, "state"):
            is_running_or_paused = self.parent_window.state.current_phase in (TreatmentPhase.RUNNING, TreatmentPhase.PAUSED)
        
        if enabled:
            # Restaurar estilos normales
            button_style = f"""
                QPushButton {{ 
                    background: {btn_bg}; 
                    color: #ffffff; 
                    border-radius: 20px; 
                    font-weight: bold; 
                    font-size: 18px;
                }}
                QPushButton:pressed {{ background: {btn_hover}; }}
            """
            input_style = f"""
                ClickableLineEdit {{
                    font-family: Consolas, "Courier New", monospace;
                    font-size: 24px;
                    color: {text_primary};
                    background: {bg_input};
                    border: 2px solid {border_strong};
                    border-radius: 8px;
                    padding: 5px;
                    min-width: 120px;
                }}
                ClickableLineEdit:focus {{
                    border: 2px solid {accent};
                    background: {bg_card};
                }}
                ClickableLineEdit:disabled {{
                    color: {text_muted};
                    background-color: {bg_alt};
                    border: 2px solid {border};
                }}
            """
            # Estilo para input_heparin_auto_stop en RUNNING/PAUSED: mantener gris
            input_heparin_auto_stop_style = f"""
                ClickableLineEdit {{
                    font-family: Consolas, "Courier New", monospace;
                    font-size: 24px;
                    color: {text_muted};
                    background-color: {bg_alt};
                    border: 2px solid {border};
                    border-radius: 8px;
                    padding: 5px;
                    min-width: 120px;
                }}
                ClickableLineEdit:focus {{
                    color: {text_muted};
                    background-color: {bg_alt};
                    border: 2px solid {border};
                }}
                ClickableLineEdit:disabled {{
                    color: {text_muted};
                    background-color: {bg_alt};
                    border: 2px solid {border};
                }}
            """
            combo_style = f"""
                QComboBox {{
                    font-size: 24px;
                    min-width: 180px;
                    color: {text_primary};
                    background-color: {bg_card};
                    border: 1px solid {border};
                    border-radius: 5px;
                    padding: 5px;
                }}
                QComboBox::drop-down {{
                    border: none;
                }}
                QComboBox QAbstractItemView {{
                    background-color: {bg_card};
                    color: {text_primary};
                    selection-background-color: {accent};
                    selection-color: #ffffff;
                    border: 1px solid {border};
                }}
            """
            label_style = f"font-size: 26px; color: {text_secondary}; font-weight: 600;"
            
            self.btn_apply_bolus.setStyleSheet(button_style)
            self.input_bolus.setStyleSheet(input_style)
            self.bolus_label.setStyleSheet(label_style)
            
            # Restaurar estilos de combos e inputs de heparina
            for widget_name in ("heparin_flow_combo", "input_heparin_auto_stop", "input_vol_hep", "syringe_combo"):
                widget = getattr(self, widget_name, None)
                if widget is None:
                    continue
                
                # Si estamos en RUNNING/PAUSED, el input_heparin_auto_stop debe mantenerse gris
                # Verificar el estado actual del widget, no solo la flag de enabled
                if widget_name == "input_heparin_auto_stop":
                    if is_running_or_paused or not widget.isEnabled():
                        widget.setStyleSheet(input_heparin_auto_stop_style)
                    else:
                        widget.setStyleSheet(input_style)
                elif isinstance(widget, QComboBox):
                    widget.setStyleSheet(combo_style)
                elif isinstance(widget, ClickableLineEdit):
                    widget.setStyleSheet(input_style)
        else:
            # Estilos para estado disabled (gris)
            disabled_button_style = f"""
                QPushButton:disabled {{
                    background-color: {text_muted};
                    color: {bg_alt};
                }}
            """
            disabled_input_style = f"""
                ClickableLineEdit:disabled {{
                    color: {text_muted};
                    background-color: {bg_alt};
                    border: 2px solid {border};
                }}
            """
            disabled_combo_style = f"""
                QComboBox:disabled {{
                    color: {text_muted};
                    background-color: {bg_alt};
                    border: 1px solid {border};
                }}
            """
            disabled_label_style = f"font-size: 26px; color: {text_muted}; font-weight: 600;"
            
            self.btn_apply_bolus.setStyleSheet(disabled_button_style)
            self.input_bolus.setStyleSheet(disabled_input_style)
            self.bolus_label.setStyleSheet(disabled_label_style)
            
            # Aplicar estilos disabled a combos e inputs de heparina
            for widget_name in ("heparin_flow_combo", "input_heparin_auto_stop", "input_vol_hep", "syringe_combo"):
                widget = getattr(self, widget_name, None)
                if widget is None:
                    continue
                if isinstance(widget, QComboBox):
                    widget.setStyleSheet(disabled_combo_style)
                elif isinstance(widget, ClickableLineEdit):
                    widget.setStyleSheet(disabled_input_style)

    def _recalculate_therapy_dosage(self):
        """
        Calcula y envía el setpoint de dosis de heparina (ml).
        Fórmula: dosis_ml = tiempo_horas * flujo_ml_por_h
        Tiempo: desde heparineAutoStopHours y heparineAutoStopMinutes
        Flujo: desde heparin_flow_combo (combobox)
        """
        # Verificar que heparina esté habilitada
        if not bool(self.current_values.get("heparineInfusionEnabled", 1.0)):
            # Si heparina deshabilitada, no recalcular
            return
        
        try:
            # Obtener tiempo de paro automático en horas y minutos
            auto_h = int(self.current_values.get(HEPARIN_AUTO_STOP_HOURS_TAG, 0) or 0)
            auto_m = int(self.current_values.get(HEPARIN_AUTO_STOP_MINUTES_TAG, 0) or 0)
            time_hours = auto_h + (auto_m / 60.0)
            
            # Obtener flujo del combo (ml/h)
            if not hasattr(self, "heparin_flow_combo") or self.heparin_flow_combo is None:
                logger.warning("heparin_flow_combo no disponible para cálculo de dosage")
                return
            
            flow_ml_per_h = float(self.heparin_flow_combo.currentText())
            
            # Calcular dosage: tiempo * flujo
            dosage_ml = round(time_hours * flow_ml_per_h, 2)
            
            # Actualizar valores internos
            self.current_values["heparineTherapyDosage"] = dosage_ml
            if self.parent_window and hasattr(self.parent_window, "current_values"):
                self.parent_window.current_values["heparineTherapyDosage"] = dosage_ml
            
            # Enviar setpoint al puerto
            self.on_user_input_setpoint("heparineTherapyDosage", dosage_ml)
            logger.debug(
                f"Dosis heparina recalculada: tiempo={auto_h:02d}:{auto_m:02d}h ({time_hours:.2f}h), "
                f"flujo={flow_ml_per_h:.1f}ml/h → dosis={dosage_ml:.2f}ml"
            )
        except Exception as e:
            logger.error(f"Error recalculando dosis de heparina: {e}")

    
    def _update_input_display(self, widget: ClickableLineEdit, tag: str, precision: int = 1):
        if widget.hasFocus():
            return
        value = self.current_values.get(tag, 0.0)
        # Tratar None como 0.0
        if value is None:
            value = 0.0
        widget.setText(f"{value:.{precision}f}")

    def update_values(self, new_values: dict):
        # IMPORTANTE: No reemplaces la referencia de current_values
        # para evitar perder cambios hechos en otros lugares.
        # En su lugar, actualiza los valores dentro del diccionario existente.
        if self.current_values is not new_values:
            # Solo actualiza si son diccionarios diferentes
            self.current_values.update(new_values)
        
        # Asegurar que heparineSyringeSize siempre es 20.0
        self.current_values["heparineSyringeSize"] = 20.0
        if self.parent_window and hasattr(self.parent_window, "current_values"):
            self.parent_window.current_values["heparineSyringeSize"] = 20.0
        
        # Nota: heparineTherapyDosage ahora se calcula automáticamente, no se actualiza directamente
        self._update_input_display(self.input_bolus, "heparineBolusQuantity")
        auto_h = int(self.current_values.get(HEPARIN_AUTO_STOP_HOURS_TAG, 0) or 0)
        auto_m = int(self.current_values.get(HEPARIN_AUTO_STOP_MINUTES_TAG, 0) or 0)
        self.input_heparin_auto_stop.setText(f"{auto_h:02d}:{auto_m:02d}")

        heparin_enabled = bool(self.current_values.get("heparineInfusionEnabled", 1.0))
        if self.chk_heparin_enabled.isChecked() != heparin_enabled:
            self.chk_heparin_enabled.blockSignals(True)
            self.chk_heparin_enabled.setChecked(heparin_enabled)
            self.chk_heparin_enabled.blockSignals(False)
        self._update_heparin_dose_fields_enabled(heparin_enabled)

        # Solo actualizar input_vol_hep, no syringe_combo (que ahora es una etiqueta)
        variables_to_update = {
            "heparineSyringeVolume": self.input_vol_hep
        }

        for tag, widget in variables_to_update.items():
            if tag in self.current_values:
                value = self.current_values[tag]
                # Tratar None como 0.0
                if value is None:
                    value = 0.0
                if isinstance(widget, ClickableLineEdit):
                    widget.setText(f"{value:.1f}")

    def _syringe_max_volume_ml(self) -> float:
        # Jeringa siempre fija a 20 ml
        return 20.0

    def _validate_syringe_fill_volume(self, fill_volume: float) -> bool:
        if fill_volume < 0:
            logger.warning("Volumen de jeringa bloqueado: valor negativo (volumen=%.2f ml)", fill_volume)
            self._show_bolus_message("El volumen en jeringa no puede ser negativo.")
            return False

        max_volume = self._syringe_max_volume_ml()
        if max_volume > 0 and fill_volume > max_volume + HEPARIN_BOLUS_EPSILON_ML:
            logger.warning(
                "Volumen de jeringa bloqueado: excede capacidad (volumen=%.2f ml, tamaño=%.2f ml)",
                fill_volume,
                max_volume,
            )
            self._show_bolus_message(
                "El volumen de heparina no puede ser mayor que el tamaño de la jeringa.\n"
                f"Volumen capturado: {fill_volume:.2f} ml\n"
                f"Tamaño de jeringa: {max_volume:.0f} ml"
            )
            return False

        return True

    def _heparin_remaining_ml(self) -> tuple[float, float, float]:
        syringe_volume = safe_float(self.current_values.get("heparineSyringeVolume"), 0.0)
        current_dosage = safe_float(self.current_values.get("heparineCurrentDosage"), 0.0)
        return syringe_volume - current_dosage, syringe_volume, current_dosage

    def _show_bolus_message(self, message: str):
        alert_owner = self.parent_window if self.parent_window is not None else self
        if getattr(alert_owner, "_operator_dialog_open", False):
            logger.debug("Diálogo de bolo suprimido por reentrancia")
            return

        alert_owner._operator_dialog_open = True
        try:
            if self.parent_window and hasattr(self.parent_window, "begin_operator_alert"):
                self.parent_window.begin_operator_alert("warning")
            dialog = FloatingConfirmDialog(alert_owner)
            dialog.show_confirm(message, accept_text="Aceptar", cancel_text="Cerrar")
        finally:
            if self.parent_window and hasattr(self.parent_window, "end_operator_alert"):
                self.parent_window.end_operator_alert()
            alert_owner._operator_dialog_open = False

    def _can_apply_bolus(self) -> bool:
        bolus_quantity = safe_float(self.current_values.get("heparineBolusQuantity"), 0.0)
        remaining, syringe_volume, current_dosage = self._heparin_remaining_ml()

        if bolus_quantity <= 0:
            logger.info("Bolo bloqueado: volumen inválido (bolo=%.2f ml)", bolus_quantity)
            self._show_bolus_message("El volumen de bolo debe ser mayor que 0 ml.")
            return False

        if remaining <= HEPARIN_BOLUS_EPSILON_ML:
            logger.info(
                "Bolo bloqueado: heparina agotada (jeringa=%.2f ml, dosificado=%.2f ml, restante=%.2f ml)",
                syringe_volume,
                current_dosage,
                remaining,
            )
            self._show_bolus_message(
                "La heparina se ha agotado.\n"
                f"Volumen en jeringa: {syringe_volume:.2f} ml\n"
                f"Dosificado: {current_dosage:.2f} ml\n"
                "Restante: 0.00 ml"
            )
            return False

        if bolus_quantity > remaining + HEPARIN_BOLUS_EPSILON_ML:
            logger.info(
                "Bolo bloqueado: volumen insuficiente (bolo=%.2f ml, restante=%.2f ml, jeringa=%.2f ml)",
                bolus_quantity,
                remaining,
                syringe_volume,
            )
            self._show_bolus_message(
                "No hay heparina suficiente para este bolo.\n"
                f"Bolo solicitado: {bolus_quantity:.2f} ml\n"
                f"Restante en jeringa: {remaining:.2f} ml\n"
                f"Volumen en jeringa: {syringe_volume:.2f} ml"
            )
            return False

        return True

    def apply_bolus(self):
        # Verificar que heparina esté habilitada
        if not bool(self.current_values.get("heparineInfusionEnabled", 1.0)):
            logger.debug("Bolo bloqueado: heparina deshabilitada")
            return
        if not self._can_apply_bolus():
            return
        self.on_user_boolean_command("heparinApplyBolusDose", True)

    def _adjust_syringe_volume(self):
        # Firmware: se cambio el bit que avanza el driver al volumen de jeringa.
        self.on_user_boolean_command("heparineSynringeAct", True)

    def on_user_input_setpoint(self, tag, value):
        self.request_setpoint_change.emit(tag, value)

    def on_user_boolean_command(self, tag, state):
        self.request_boolean_change.emit(tag, state)

    def update_state(self, phase: TreatmentPhase):
        enabled = phase not in (TreatmentPhase.CLEANING, TreatmentPhase.ERROR)
        self.input_bolus.setEnabled(enabled)
        if not bool(self.current_values.get("heparineInfusionEnabled", 1.0)):
            self._update_heparin_dose_fields_enabled(False)
        
        # En RUNNING o PAUSED, el campo de tiempo de heparina debe estar bloqueado
        if phase in (TreatmentPhase.RUNNING, TreatmentPhase.PAUSED):
            self.input_heparin_auto_stop.setEnabled(False)
        elif phase not in (TreatmentPhase.CLEANING, TreatmentPhase.ERROR):
            self.input_heparin_auto_stop.setEnabled(True)

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()
