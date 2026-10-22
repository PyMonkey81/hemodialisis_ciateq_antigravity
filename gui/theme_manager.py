# gui/theme_manager.py
import os
import sys
import logging
from typing import Dict, Any, Optional
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtCore import QSettings, Signal, QObject

logger = logging.getLogger(__name__)

# Marca / Modelo,Tipo de letra principal,Características
# Fresenius 5008 / 6008,Segoe UI o Arial,"Negrita, sans-serif"
# Baxter / Gambro,Helvetica Neue o Arial,Muy limpia
# Braun Dialog+ / Adimea,Tahoma / Verdana,Buena legibilidad
# Nikkiso / Bellco,Arial Bold,Estilo industrial
# Estándar recomendado,Segoe UI / Arial / Helvetica,Mejor opción actual


class ThemeManager(QObject):
    theme_changed = Signal(str)  # Señal para notificar cuando el tema ha cambiado
    font_changed = Signal(str)   # Señal para notificar cuando cambia la fuente global

    _instance: Optional["ThemeManager"] = None

    DEFAULT_FONT_FAMILY = "Segoe UI"
    DEFAULT_FALLBACK_FONTS = '"Segoe UI", "Helvetica Neue", Arial, sans-serif'
    DEFAULT_MONOSPACE_FONTS = 'Consolas, "Cascadia Mono", "Courier New", monospace'
    DEFAULT_FONT_SIZE = 14
    DEFAULT_FONT_WEIGHT = QFont.Bold

    SETTINGS_THEME_KEY = "AppTheme/CurrentTheme"
    SETTINGS_FONT_FAMILY_KEY = "AppTheme/FontFamily"
    SETTINGS_FONT_SIZE_KEY = "AppTheme/FontSize"

    # Baseline de estilos por pantalla para migración gradual.
    SCREEN_BASELINES = {
        "therapy_config_screen": {
            "meta": {
                "version": "baseline-v1",
                "description": "Registro visual actual de TherapyConfigScreen para homologacion",
            },
            "layout": {
                "main_margins": [40, 30, 40, 30],
                "main_spacing": 20,
                "columns_spacing": 30,
                "col1_spacing": 120,
                "params_grid_spacing": 20,
            },
            "typography": {
                "title": {"size": 42, "weight": "bold"},
                "section_label": {"size": 22, "weight": "bold", "min_height": 50},
                "frame_label": {"size": 18, "weight": "bold"},
                "input": {"size": 24, "family": 'Consolas, "Courier New", monospace'},
                "button": {"size": 20, "weight": "bold"},
            },
            "colors": {
                "title": "#60a5fa",
                "separator": "#fcfcfc",
                "label_text": "#000000",
                "frame_border": "#5c5c5c",
                "frame_label_text": "#2b2b2b",
                "input_bg": "#e2e8f0",
                "input_border": "#64748b",
                "input_focus_border": "#3b82f6",
                "input_focus_bg": "#ffffff",
                "button_enabled_bg": "#39ec21",
                "button_stop_bg": "#DD2911",
                "button_disabled_bg": "#334155",
                "button_disabled_text": "#94a3b8",
                "button_text": "#ffffff",
                "button_border": "#1e293b",
                "button_pressed_bg": "#334155",
            },
            "dimensions": {
                "pump_button": [120, 80],
                "input_field": [120, 50],
            },
            "labels": {
                "title": "Configuracion de Terapia",
                "frames": ["Bomba de Sangre", "Llenado de filtro"],
                "buttons": ["START", "STOP", "START"],
                "parameter_labels": [
                    "Flujo de Sangre (Qb, mL/min):",
                    "Flujo Dializante (Qd, mL/min):",
                    "Flujo UF (L/h):",
                    "Temperatura (C):",
                    "Conductividad (mS/cm):",
                    "T. Terapia (hh:mm)",
                ],
            },
        }
    }

    # =========================================================================
    # DEFINICIÓN DE TOKENS SEMÁNTICOS POR TEMA CLÍNICO
    # =========================================================================
    THEME_TOKENS: Dict[str, Dict[str, Any]] = {
        "Clínico Claro": {
            "id": "Clínico Claro",
            "description": "Interfaz médica diurna de alta legibilidad, limpia y moderna (estilo hospitalario).",
            "is_dark": False,
            "bg_main": "#EEF2F6",
            "bg_header": "#E2E8F0",
            "bg_nav": "#FFFFFF",
            "bg_card": "#FFFFFF",
            "bg_card_alt": "#F8FAFC",
            "bg_input": "#F8FAFC",
            "bg_input_focus": "#FFFFFF",
            "border_card": "#CBD5E1",
            "border_strong": "#94A3B8",
            "border_input": "#64748B",
            "text_primary": "#0F172A",
            "text_secondary": "#334155",
            "text_muted": "#64748B",
            "text_on_primary": "#FFFFFF",
            "title_color": "#0369A1",
            "primary": "#0284C7",
            "primary_hover": "#0369A1",
            "primary_pressed": "#075985",
            "nav_btn_bg": "#0F296B",
            "nav_btn_hover": "#1E3A8A",
            "nav_btn_active": "#0284C7",
            "nav_btn_active_border": "#38BDF8",
            "btn_disabled_bg": "#CBD5E1",
            "btn_disabled_text": "#64748B",
            "success": "#16A34A",
            "success_bright": "#22C55E",
            "warning": "#F59E0B",
            "danger": "#DC2626",
            "info": "#0284C7",
            "val_blood": "#DC2626",
            "val_venous": "#0284C7",
            "val_temp": "#15803D",
            "val_uf": "#0369A1",
            "val_vital_bp": "#047857",
            "val_vital_hr": "#DC2626",
            "val_vital_spo2": "#0284C7",
            "plot_bg": "#FFFFFF",
            "plot_grid": "#CBD5E1",
            "plot_axis": "#334155",
            "gauge_bg": "#F8FAFC",
            "gauge_tank_bg": "#1E293B",
            "gauge_tank_border": "#475569",
            "table_header_bg": "#F1F5F9",
            "table_row_alt": "#F8FAFC",
            "table_sel_bg": "#BAE6FD",
            "table_sel_text": "#0F172A",
        },
        "Modo Oscuro UCI": {
            "id": "Modo Oscuro UCI",
            "description": "Modo nocturno de bajo deslumbramiento para Unidades de Cuidados Intensivos y guardias.",
            "is_dark": True,
            "bg_main": "#0B1120",
            "bg_header": "#0F172A",
            "bg_nav": "#0F172A",
            "bg_card": "#1E293B",
            "bg_card_alt": "#0F172A",
            "bg_input": "#0F172A",
            "bg_input_focus": "#1E293B",
            "border_card": "#334155",
            "border_strong": "#475569",
            "border_input": "#475569",
            "text_primary": "#F8FAFC",
            "text_secondary": "#CBD5E1",
            "text_muted": "#94A3B8",
            "text_on_primary": "#FFFFFF",
            "title_color": "#38BDF8",
            "primary": "#0284C7",
            "primary_hover": "#0EA5E9",
            "primary_pressed": "#0369A1",
            "nav_btn_bg": "#1E293B",
            "nav_btn_hover": "#334155",
            "nav_btn_active": "#0284C7",
            "nav_btn_active_border": "#38BDF8",
            "btn_disabled_bg": "#1E293B",
            "btn_disabled_text": "#475569",
            "success": "#16A34A",
            "success_bright": "#22C55E",
            "warning": "#F59E0B",
            "danger": "#EF4444",
            "info": "#38BDF8",
            "val_blood": "#F87171",
            "val_venous": "#38BDF8",
            "val_temp": "#4ADE80",
            "val_uf": "#22D3EE",
            "val_vital_bp": "#34D399",
            "val_vital_hr": "#F87171",
            "val_vital_spo2": "#38BDF8",
            "plot_bg": "#0F172A",
            "plot_grid": "#334155",
            "plot_axis": "#CBD5E1",
            "gauge_bg": "#0F172A",
            "gauge_tank_bg": "#020617",
            "gauge_tank_border": "#334155",
            "table_header_bg": "#0F172A",
            "table_row_alt": "#162032",
            "table_sel_bg": "#0369A1",
            "table_sel_text": "#FFFFFF",
        },
        "Azul Biomédico": {
            "id": "Azul Biomédico",
            "description": "Estética biomédica en tonos azul acero y cian clínico con alto confort visual.",
            "is_dark": False,
            "bg_main": "#E0F2FE",
            "bg_header": "#E0F2FE",
            "bg_nav": "#E0F2FE",
            "bg_card": "#F8FAFC",
            "bg_card_alt": "#F0F9FF",
            "bg_input": "#FFFFFF",
            "bg_input_focus": "#F0F9FF",
            "border_card": "#7DD3FC",
            "border_strong": "#0284C7",
            "border_input": "#0284C7",
            "text_primary": "#082F49",
            "text_secondary": "#0C4A6E",
            "text_muted": "#0369A1",
            "text_on_primary": "#FFFFFF",
            "title_color": "#0369A1",
            "primary": "#0284C7",
            "primary_hover": "#0369A1",
            "primary_pressed": "#075985",
            "nav_btn_bg": "#075985",
            "nav_btn_hover": "#0369A1",
            "nav_btn_active": "#0EA5E9",
            "nav_btn_active_border": "#BAE6FD",
            "btn_disabled_bg": "#64748B",
            "btn_disabled_text": "#E2E8F0",
            "success": "#059669",
            "success_bright": "#10B981",
            "warning": "#D97706",
            "danger": "#E11D48",
            "info": "#0284C7",
            "val_blood": "#E11D48",
            "val_venous": "#0284C7",
            "val_temp": "#059669",
            "val_uf": "#0369A1",
            "val_vital_bp": "#059669",
            "val_vital_hr": "#E11D48",
            "val_vital_spo2": "#0284C7",
            "plot_bg": "#FFFFFF",
            "plot_grid": "#BAE6FD",
            "plot_axis": "#0C4A6E",
            "gauge_bg": "#F0F9FF",
            "gauge_tank_bg": "#082F49",
            "gauge_tank_border": "#0284C7",
            "table_header_bg": "#E0F2FE",
            "table_row_alt": "#F0F9FF",
            "table_sel_bg": "#7DD3FC",
            "table_sel_text": "#082F49",
        },
        "Alto Contraste": {
            "id": "Alto Contraste",
            "description": "Máximo contraste cromático para lectura a gran distancia en sala de hemodiálisis.",
            "is_dark": True,
            "bg_main": "#000000",
            "bg_header": "#090D16",
            "bg_nav": "#090D16",
            "bg_card": "#111827",
            "bg_card_alt": "#000000",
            "bg_input": "#000000",
            "bg_input_focus": "#1F2937",
            "border_card": "#FACC15",
            "border_strong": "#FFFFFF",
            "border_input": "#FACC15",
            "text_primary": "#FFFFFF",
            "text_secondary": "#FEF08A",
            "text_muted": "#E5E7EB",
            "text_on_primary": "#000000",
            "title_color": "#FACC15",
            "primary": "#2563EB",
            "primary_hover": "#3B82F6",
            "primary_pressed": "#1D4ED8",
            "nav_btn_bg": "#1F2937",
            "nav_btn_hover": "#374151",
            "nav_btn_active": "#2563EB",
            "nav_btn_active_border": "#FACC15",
            "btn_disabled_bg": "#111827",
            "btn_disabled_text": "#6B7280",
            "success": "#16A34A",
            "success_bright": "#4ADE80",
            "warning": "#FACC15",
            "danger": "#FF3333",
            "info": "#22D3EE",
            "val_blood": "#FF4444",
            "val_venous": "#38BDF8",
            "val_temp": "#4ADE80",
            "val_uf": "#FACC15",
            "val_vital_bp": "#4ADE80",
            "val_vital_hr": "#FF4444",
            "val_vital_spo2": "#22D3EE",
            "plot_bg": "#000000",
            "plot_grid": "#4B5563",
            "plot_axis": "#FFFFFF",
            "gauge_bg": "#090D16",
            "gauge_tank_bg": "#000000",
            "gauge_tank_border": "#FACC15",
            "table_header_bg": "#1F2937",
            "table_row_alt": "#090D16",
            "table_sel_bg": "#FACC15",
            "table_sel_text": "#000000",
            "font_size_param_label": "26px",
            "font_size_param_val": "32px",
        },
    }

    # Alias retrocompatibles
    THEME_ALIASES = {
        "light": "Clínico Claro",
        "Light": "Clínico Claro",
        "claro": "Clínico Claro",
        "dark": "Modo Oscuro UCI",
        "Dark": "Modo Oscuro UCI",
        "oscuro": "Modo Oscuro UCI",
        "blue": "Azul Biomédico",
        "contrast": "Alto Contraste",
    }

    DEFAULT_THEME = "Clínico Claro"
    SETTINGS_KEY = "AppTheme/CurrentTheme"

    @classmethod
    def resolve_theme_name(cls, name: str) -> str:
        if not name:
            return cls.DEFAULT_THEME
        if name in cls.THEME_TOKENS:
            return name
        if name in cls.THEME_ALIASES:
            return cls.THEME_ALIASES[name]
        lower_map = {k.lower(): v for k, v in cls.THEME_ALIASES.items()}
        for k in cls.THEME_TOKENS:
            lower_map[k.lower()] = k
        return lower_map.get(str(name).strip().lower(), cls.DEFAULT_THEME)

    @classmethod
    def build_theme_qss(cls, theme_name: str, font_family: str = DEFAULT_FONT_FAMILY) -> str:
        resolved = cls.resolve_theme_name(theme_name)
        t = cls.THEME_TOKENS[resolved]
        mono = cls.DEFAULT_MONOSPACE_FONTS
        return f"""
            /* ===== ESTILO GLOBAL TEMA: {resolved} ===== */
            * {{
                font-family: "{font_family}", "Segoe UI", Arial, sans-serif;
                font-weight: bold;
                color: {t["text_primary"]};
            }}
            QMainWindow, QWidget#main_central_widget {{
                background-color: {t["bg_main"]};
            }}
            QStackedWidget#main_screen_stack,
            QStackedWidget#main_screen_stack > QWidget {{
                background-color: {t["bg_main"]};
            }}
            QFrame#card, QFrame#graph_card, QGroupBox#card, QFrame#themed_card {{
                background-color: {t["bg_card"]};
                border: 2px solid {t["border_card"]};
                border-radius: 14px;
            }}
            QGroupBox {{
                background-color: {t["bg_card"]};
                border: 2px solid {t["border_card"]};
                border-radius: 12px;
                margin-top: 16px;
                font-size: 22px;
                font-weight: bold;
                color: {t["title_color"]};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 16px;
                padding: 2px 12px;
                background-color: {t["bg_card_alt"]};
                color: {t["title_color"]};
                border: 1px solid {t["border_card"]};
                border-radius: 6px;
            }}
            QLabel {{
                color: {t["text_primary"]};
                background-color: transparent;
                font-size: 20px;
            }}
            QLabel#screen_title {{
                color: {t["title_color"]};
                font-size: 38px;
                font-weight: bold;
                background: transparent;
            }}
            QLabel#card_title {{
                color: {t["title_color"]};
                font-size: 20px;
                font-weight: bold;
                background: transparent;
                border: none;
                border-bottom: 2px solid {t["border_card"]};
                padding-bottom: 8px;
                margin-bottom: 8px;
            }}
            QLabel#val_large {{
                color: {t["val_blood"]};
                font-family: {mono};
                font-size: 50px;
                font-weight: bold;
            }}
            QLabel#val_large_yellow {{
                color: {t["warning"]};
                font-family: {mono};
                font-size: 50px;
                font-weight: bold;
            }}
            QLabel#val_large_green {{
                color: {t["val_temp"]};
                font-family: {mono};
                font-size: 50px;
                font-weight: bold;
            }}
            QLabel#val_large_cyan {{
                color: {t["val_uf"]};
                font-family: {mono};
                font-size: 50px;
                font-weight: bold;
            }}
            QLineEdit, ClickableLineEdit {{
                font-family: {mono};
                font-size: 22px;
                color: {t["text_primary"]};
                background-color: {t["bg_input"]};
                border: 2px solid {t["border_input"]};
                border-radius: 8px;
                padding: 6px 10px;
                min-width: 80px;
            }}
            QLineEdit:focus, ClickableLineEdit:focus {{
                border: 2px solid {t["primary"]};
                background-color: {t["bg_input_focus"]};
            }}
            QComboBox {{
                color: {t["text_primary"]};
                background-color: {t["bg_input"]};
                font-size: 22px;
                font-weight: bold;
                padding: 6px 12px;
                border: 2px solid {t["border_input"]};
                border-radius: 8px;
            }}
            QComboBox:hover {{
                border-color: {t["primary"]};
            }}
            QComboBox QAbstractItemView {{
                background-color: {t["bg_card"]};
                color: {t["text_primary"]};
                selection-background-color: {t["primary"]};
                selection-color: #FFFFFF;
                border: 2px solid {t["border_card"]};
            }}
            QPushButton {{
                background-color: {t["primary"]};
                color: #FFFFFF;
                border-radius: 10px;
                font-size: 18px;
                padding: 8px 14px;
                font-weight: bold;
                border: 1px solid {t["primary_hover"]};
            }}
            QPushButton:hover {{
                background-color: {t["primary_hover"]};
            }}
            QPushButton:pressed {{
                background-color: {t["primary_pressed"]};
            }}
            QPushButton:disabled {{
                background-color: {t["btn_disabled_bg"]};
                color: {t["btn_disabled_text"]};
                border: 1px solid {t["border_card"]};
            }}
            QTableWidget {{
                background-color: {t["bg_card"]};
                alternate-background-color: {t["table_row_alt"]};
                color: {t["text_primary"]};
                font-size: 18px;
                gridline-color: {t["border_card"]};
                border: 1px solid {t["border_card"]};
                border-radius: 10px;
                outline: none;
            }}
            QTableWidget::item {{
                padding: 6px;
                color: {t["text_primary"]};
            }}
            QTableWidget::item:selected {{
                background-color: {t["table_sel_bg"]};
                color: {t["table_sel_text"]};
            }}
            QHeaderView::section {{
                background-color: {t["table_header_bg"]};
                color: {t["text_secondary"]};
                font-weight: bold;
                font-size: 19px;
                padding: 8px;
                border: 1px solid {t["border_card"]};
            }}
            QTableWidget QTableCornerButton::section {{
                background-color: {t["table_header_bg"]};
                border: 1px solid {t["border_card"]};
            }}
            QListWidget {{
                background-color: {t["bg_card_alt"]};
                color: {t["text_primary"]};
                font-size: 20px;
                border: 2px solid {t["border_card"]};
                border-radius: 10px;
                padding: 6px;
            }}
            QListWidget::item {{
                padding: 8px 10px;
                border-radius: 6px;
            }}
            QListWidget::item:selected {{
                background-color: {t["primary"]};
                color: #FFFFFF;
            }}
            QScrollBar:vertical {{
                border: none;
                background: {t["bg_card_alt"]};
                width: 32px;
                margin: 0px;
                border-radius: 10px;
            }}
            QScrollBar::handle:vertical {{
                background: {t["border_strong"]};
                min-height: 54px;
                border-radius: 8px;
                margin: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {t["primary"]};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            QMessageBox {{
                background-color: {t["bg_card"]};
                color: {t["text_primary"]};
            }}
            QMessageBox QLabel {{
                color: {t["text_primary"]};
                background-color: transparent;
                padding: 8px;
            }}
            QMessageBox QPushButton {{
                background-color: {t["primary"]};
                color: #FFFFFF;
                border-radius: 8px;
                padding: 8px 20px;
                font-weight: bold;
            }}
        """

    # Compatibilidad con código legado que acceda a THEMES directamente
    THEMES = {
        "Clínico Claro": "",
        "Modo Oscuro UCI": "",
        "Azul Biomédico": "",
        "Alto Contraste": "",
        "Light": "",
        "Dark": "",
    }

    def __init__(self, app: Optional[QApplication] = None):
        super().__init__()
        self.app = app or QApplication.instance()
        ThemeManager._instance = self
        self._current_theme_name = self.DEFAULT_THEME
        self._current_font_family = self.DEFAULT_FONT_FAMILY
        self._current_font_size = self.DEFAULT_FONT_SIZE
        self._settings = QSettings("CIATEQ", "HemodialysisHMI")

        self._load_saved_settings()

    @classmethod
    def instance(cls, app: Optional[QApplication] = None) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = cls(app or QApplication.instance())
        return cls._instance

    @classmethod
    def get_tokens(cls, theme_name: Optional[str] = None) -> Dict[str, Any]:
        if theme_name is None:
            inst = cls._instance
            theme_name = inst.current_theme_name if inst else cls.DEFAULT_THEME
        resolved = cls.resolve_theme_name(theme_name)
        base = dict(cls.THEME_TOKENS.get(resolved, cls.THEME_TOKENS[cls.DEFAULT_THEME]))
        # Proveer alias normalizados para compatibilidad entre todas las pantallas
        base.setdefault("bg_primary", base.get("bg_main", "#F1F5F9"))
        base.setdefault("border", base.get("border_card", "#CBD5E1"))
        base.setdefault("accent", base.get("primary", "#2563EB"))
        base.setdefault("accent_soft", base.get("table_sel_bg", "#DBEAFE"))
        base.setdefault("btn_primary_bg", base.get("primary", "#06298A"))
        base.setdefault("btn_primary_hover", base.get("primary_hover", "#1E40AF"))
        base.setdefault("btn_secondary_bg", base.get("nav_btn_bg", "#475569"))
        base.setdefault("btn_secondary_text", "#FFFFFF")
        base.setdefault("header_pill_bg", base.get("nav_btn_bg", "#06298A"))
        base.setdefault("nav_btn_disabled", base.get("btn_disabled_bg", "#334155"))
        base.setdefault("val_green", base.get("val_temp", "#15803D"))
        base.setdefault("val_cyan", base.get("val_uf", "#0369A1"))

        # Tokens tipográficos escalables y configurables por tema
        base.setdefault("font_size_param_label", "25px")
        base.setdefault("font_size_param_val", "30px")
        base.setdefault("font_size_param_unit", "22px")
        base.setdefault("font_size_val_large", "48px")
        base.setdefault("font_size_card_title", "20px")
        base.setdefault("font_size_vital_val", "24px")
        return base

    def _load_saved_settings(self):
        saved_theme = self._settings.value(self.SETTINGS_KEY, self.DEFAULT_THEME)
        saved_font_family = self._settings.value(self.SETTINGS_FONT_FAMILY_KEY, self.DEFAULT_FONT_FAMILY)
        saved_font_size = self._settings.value(self.SETTINGS_FONT_SIZE_KEY, self.DEFAULT_FONT_SIZE)

        self._current_theme_name = self.resolve_theme_name(str(saved_theme))
        self._current_font_family = str(saved_font_family) if saved_font_family else self.DEFAULT_FONT_FAMILY
        try:
            self._current_font_size = int(saved_font_size)
        except (TypeError, ValueError):
            self._current_font_size = self.DEFAULT_FONT_SIZE

        self.apply_theme(self._current_theme_name, persist=False)

    def _apply_app_font(self):
        if not self.app:
            return
        font = QFont(self._current_font_family, self._current_font_size)
        font.setWeight(self.DEFAULT_FONT_WEIGHT)
        self.app.setFont(font)

    def _apply_app_palette(self, tokens: Dict[str, Any]):
        if not self.app:
            return
        pal = QPalette()
        pal.setColor(QPalette.Window, QColor(tokens["bg_main"]))
        pal.setColor(QPalette.WindowText, QColor(tokens["text_primary"]))
        pal.setColor(QPalette.Base, QColor(tokens["bg_card"]))
        pal.setColor(QPalette.AlternateBase, QColor(tokens["bg_card_alt"]))
        pal.setColor(QPalette.ToolTipBase, QColor(tokens["bg_card"]))
        pal.setColor(QPalette.ToolTipText, QColor(tokens["text_primary"]))
        pal.setColor(QPalette.Text, QColor(tokens["text_primary"]))
        pal.setColor(QPalette.Button, QColor(tokens["primary"]))
        pal.setColor(QPalette.ButtonText, QColor("#FFFFFF"))
        self.app.setPalette(pal)

    def _build_qss(self, theme_name: str) -> str:
        return self.build_theme_qss(theme_name, self._current_font_family)

    def apply_theme(self, theme_name: str, persist: bool = True):
        resolved = self.resolve_theme_name(theme_name)
        self._current_theme_name = resolved
        tokens = self.get_tokens(resolved)

        self._apply_app_font()
        self._apply_app_palette(tokens)
        qss = self._build_qss(resolved)
        if self.app:
            self.app.setStyleSheet(qss)
        if persist:
            self._settings.setValue(self.SETTINGS_KEY, resolved)
        logger.info(f"Tema aplicado: {resolved}")
        self.theme_changed.emit(resolved)

    @classmethod
    def get_screen_baseline(cls, screen_key: str) -> dict:
        """Devuelve el baseline visual registrado para una pantalla."""
        return cls.SCREEN_BASELINES.get(screen_key, {})

    @classmethod
    def get_therapy_config_baseline(cls) -> dict:
        """Atajo para baseline de la pantalla de configuracion de terapia."""
        return cls.get_screen_baseline("therapy_config_screen")

    def apply_font(self, font_family: str, font_size: int | None = None):
        self._current_font_family = font_family
        if font_size is not None:
            self._current_font_size = font_size

        self._apply_app_font()
        qss = self._build_qss(self._current_theme_name)
        if self.app:
            self.app.setStyleSheet(qss)

        self._settings.setValue(self.SETTINGS_FONT_FAMILY_KEY, self._current_font_family)
        self._settings.setValue(self.SETTINGS_FONT_SIZE_KEY, self._current_font_size)
        logger.info(f"Fuente aplicada: {self._current_font_family} ({self._current_font_size} pt)")
        self.font_changed.emit(self._current_font_family)

    def get_available_themes(self) -> list[str]:
        return list(self.THEME_TOKENS.keys())

    @property
    def current_theme_name(self) -> str:
        return self._current_theme_name

    @property
    def current_font_family(self) -> str:
        return self._current_font_family

    @property
    def current_font_size(self) -> int:
        return self._current_font_size
