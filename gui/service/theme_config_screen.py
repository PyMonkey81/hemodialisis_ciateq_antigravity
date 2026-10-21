# gui/service/theme_config_screen.py
"""
Pantalla de configuración de Temas y Apariencia Visual de la Interfaz.
Permite cambiar en vivo entre los 4 temas clínicos (Clínico Claro, Modo Oscuro UCI,
Azul Biomédico y Alto Contraste) y la familia tipográfica, persistiendo en QSettings.
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFrame, QLabel, QPushButton, QComboBox, QSizePolicy
)
from PySide6.QtCore import Qt
from gui.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class ThemePreviewCard(QFrame):
    """Tarjeta táctil de selección y previsualización de un tema clínico."""

    def __init__(self, theme_name: str, tokens: dict, on_select_callback, parent=None):
        super().__init__(parent)
        self.theme_name = theme_name
        self.tokens = tokens
        self.on_select_callback = on_select_callback
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        # Fila superior: Nombre del tema + Badge de estado
        header_row = QHBoxLayout()
        self.title_lbl = QLabel(self.theme_name)
        self.badge_lbl = QLabel("ACTIVO")
        self.badge_lbl.setAlignment(Qt.AlignCenter)
        self.badge_lbl.setFixedSize(110, 32)
        header_row.addWidget(self.title_lbl)
        header_row.addStretch()
        header_row.addWidget(self.badge_lbl)
        layout.addLayout(header_row)

        # Descripción
        self.desc_lbl = QLabel(self.tokens.get("description", ""))
        self.desc_lbl.setWordWrap(True)
        layout.addWidget(self.desc_lbl)

        # Muestra visual en miniatura (Swatches)
        swatch_container = QFrame()
        swatch_container.setFixedHeight(64)
        swatch_container.setStyleSheet(
            f"background-color: {self.tokens['bg_main']}; "
            f"border: 2px solid {self.tokens['border_card']}; "
            f"border-radius: 10px;"
        )
        swatch_layout = QHBoxLayout(swatch_container)
        swatch_layout.setContentsMargins(12, 8, 12, 8)
        swatch_layout.setSpacing(10)

        colors_to_show = [
            ("Fondo", self.tokens["bg_card"], self.tokens["text_primary"]),
            ("Acento", self.tokens["primary"], "#FFFFFF"),
            ("Art.", self.tokens["val_blood"], "#FFFFFF"),
            ("Temp.", self.tokens["val_temp"], "#FFFFFF"),
            ("Nav.", self.tokens["nav_btn_bg"], "#FFFFFF"),
        ]
        for label_txt, bg_hex, fg_hex in colors_to_show:
            pill = QLabel(label_txt)
            pill.setAlignment(Qt.AlignCenter)
            pill.setStyleSheet(
                f"background-color: {bg_hex}; color: {fg_hex}; "
                f"font-size: 14px; font-weight: bold; border-radius: 6px; "
                f"padding: 4px 8px; border: 1px solid {self.tokens['border_card']};"
            )
            swatch_layout.addWidget(pill)

        layout.addWidget(swatch_container)

        # Botón de aplicar
        self.btn_apply = QPushButton(f"Aplicar {self.theme_name}")
        self.btn_apply.setFixedHeight(52)
        self.btn_apply.clicked.connect(lambda: self.on_select_callback(self.theme_name))
        layout.addWidget(self.btn_apply)

    def refresh_active_state(self, active_theme: str, ui_tokens: dict):
        is_active = (self.theme_name == active_theme)
        border_col = ui_tokens["primary"] if is_active else ui_tokens["border_card"]
        border_w = 3 if is_active else 2

        self.setStyleSheet(
            f"ThemePreviewCard {{ "
            f"background-color: {ui_tokens['bg_card']}; "
            f"border: {border_w}px solid {border_col}; "
            f"border-radius: 16px; "
            f"}}"
        )
        self.title_lbl.setStyleSheet(
            f"color: {ui_tokens['text_primary']}; font-size: 26px; font-weight: bold; border: none;"
        )
        self.desc_lbl.setStyleSheet(
            f"color: {ui_tokens['text_secondary']}; font-size: 17px; font-weight: normal; border: none;"
        )
        if is_active:
            self.badge_lbl.setText("● ACTIVO")
            self.badge_lbl.setStyleSheet(
                f"background-color: {ui_tokens['success']}; color: #FFFFFF; "
                f"font-size: 15px; font-weight: bold; border-radius: 8px; border: none;"
            )
            self.btn_apply.setText("Tema Seleccionado ✓")
            self.btn_apply.setStyleSheet(
                f"QPushButton {{ background-color: {ui_tokens['success']}; color: #FFFFFF; "
                f"font-size: 20px; font-weight: bold; border-radius: 10px; border: none; }}"
            )
        else:
            self.badge_lbl.setText("DISPONIBLE")
            self.badge_lbl.setStyleSheet(
                f"background-color: {ui_tokens['bg_card_alt']}; color: {ui_tokens['text_muted']}; "
                f"font-size: 14px; font-weight: bold; border-radius: 8px; "
                f"border: 1px solid {ui_tokens['border_card']};"
            )
            self.btn_apply.setText(f"Activar {self.theme_name}")
            self.btn_apply.setStyleSheet(
                f"QPushButton {{ background-color: {ui_tokens['nav_btn_bg']}; color: #FFFFFF; "
                f"font-size: 20px; font-weight: bold; border-radius: 10px; border: none; }}"
                f"QPushButton:hover {{ background-color: {ui_tokens['primary']}; }}"
            )


class ThemeConfigScreen(QWidget):
    """Pantalla dedicada para configurar el tema visual y la tipografía de la HMI."""

    FONT_OPTIONS = [
        "Segoe UI",
        "Arial",
        "Tahoma",
        "Verdana",
        "Calibri",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.theme_cards: dict[str, ThemePreviewCard] = {}
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setup_ui()

        tm = ThemeManager.instance()
        tm.theme_changed.connect(self.apply_theme_styles)
        self.apply_theme_styles(tm.current_theme_name)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(18)

        # Encabezado con título y botón regresar
        header_layout = QHBoxLayout()
        self.title_label = QLabel("TEMAS Y APARIENCIA VISUAL")
        self.title_label.setObjectName("screen_title")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        self.btn_back = QPushButton("← Volver a Servicio")
        self.btn_back.setFixedSize(260, 56)
        self.btn_back.clicked.connect(self._go_back)
        header_layout.addWidget(self.btn_back)
        main_layout.addLayout(header_layout)

        # Grid 2x2 de temas
        cards_grid = QGridLayout()
        cards_grid.setSpacing(20)
        tm = ThemeManager.instance()

        for idx, (theme_name, tokens) in enumerate(tm.THEME_TOKENS.items()):
            card = ThemePreviewCard(
                theme_name=theme_name,
                tokens=tokens,
                on_select_callback=self._on_theme_selected,
                parent=self,
            )
            self.theme_cards[theme_name] = card
            cards_grid.addWidget(card, idx // 2, idx % 2)

        main_layout.addLayout(cards_grid, stretch=1)

        # Barra inferior de tipografía
        self.font_bar = QFrame()
        self.font_bar.setFixedHeight(84)
        font_layout = QHBoxLayout(self.font_bar)
        font_layout.setContentsMargins(24, 12, 24, 12)
        font_layout.setSpacing(20)

        self.lbl_font = QLabel("Tipografía Clínica del Sistema:")
        font_layout.addWidget(self.lbl_font)

        self.combo_font = QComboBox()
        self.combo_font.addItems(self.FONT_OPTIONS)
        self.combo_font.setFixedSize(280, 50)
        curr_font = tm.current_font_family
        if curr_font in self.FONT_OPTIONS:
            self.combo_font.setCurrentText(curr_font)
        self.combo_font.currentTextChanged.connect(self._on_font_changed)
        font_layout.addWidget(self.combo_font)

        font_layout.addStretch()
        self.lbl_info = QLabel("El tema seleccionado se guarda automáticamente y se aplica en todas las pantallas.")
        font_layout.addWidget(self.lbl_info)

        main_layout.addWidget(self.font_bar)

    def _on_theme_selected(self, theme_name: str):
        tm = ThemeManager.instance()
        tm.apply_theme(theme_name)
        if self.parent_window and hasattr(self.parent_window, "show_success_message"):
            self.parent_window.show_success_message(f"Tema '{theme_name}' aplicado correctamente", 2500)

    def _on_font_changed(self, font_family: str):
        if not font_family:
            return
        tm = ThemeManager.instance()
        tm.apply_font(font_family, tm.current_font_size)

    def _go_back(self):
        if self.parent_window and hasattr(self.parent_window, "show_options_screen"):
            self.parent_window.show_options_screen()

    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        active_name = ThemeManager.instance().current_theme_name

        self.setStyleSheet(f"background-color: {tokens['bg_main']};")
        self.title_label.setStyleSheet(
            f"color: {tokens['title_color']}; font-size: 34px; font-weight: bold; background: transparent;"
        )
        self.btn_back.setStyleSheet(
            f"QPushButton {{ background-color: {tokens['nav_btn_bg']}; color: #FFFFFF; "
            f"font-size: 20px; font-weight: bold; border-radius: 10px; padding: 8px 16px; }}"
            f"QPushButton:hover {{ background-color: {tokens['primary']}; }}"
        )
        self.font_bar.setStyleSheet(
            f"QFrame {{ background-color: {tokens['bg_card']}; "
            f"border: 2px solid {tokens['border_card']}; border-radius: 14px; }}"
        )
        self.lbl_font.setStyleSheet(
            f"color: {tokens['text_primary']}; font-size: 20px; font-weight: bold; border: none;"
        )
        self.lbl_info.setStyleSheet(
            f"color: {tokens['text_muted']}; font-size: 16px; font-weight: normal; border: none;"
        )

        for card in self.theme_cards.values():
            card.refresh_active_state(active_name, tokens)
