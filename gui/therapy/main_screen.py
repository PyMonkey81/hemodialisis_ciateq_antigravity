# gui/therapy/main_screen.py
# Home / Welcome screen displayed at startup (stacked index 0)

"""
Pantalla de inicio / bienvenida de la interfaz HMI modernizada y compatible con temas.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy
from PySide6.QtCore import Qt
import logging
from _version import __version__
from gui.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class MainScreen(QWidget):
    """
    Widget principal de bienvenida de la máquina de hemodiálisis.
    """

    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setup_ui()

        tm = ThemeManager.instance()
        tm.theme_changed.connect(self.apply_theme_styles)
        self.apply_theme_styles(tm.current_theme_name)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(60, 40, 60, 40)
        main_layout.addStretch(1)

        # Tarjeta central hero
        self.hero_card = QFrame()
        self.hero_card.setMaximumWidth(1200)
        hero_layout = QVBoxLayout(self.hero_card)
        hero_layout.setContentsMargins(60, 50, 60, 50)
        hero_layout.setSpacing(16)

        # Badge superior institucional
        self.badge_label = QLabel("TECNOLOGÍA MÉDICA • CIATEQ A.C.")
        self.badge_label.setAlignment(Qt.AlignCenter)
        hero_layout.addWidget(self.badge_label, alignment=Qt.AlignCenter)

        # Título principal
        self.title_label = QLabel("SISTEMA DE HEMODIÁLISIS")
        self.title_label.setAlignment(Qt.AlignCenter)
        hero_layout.addWidget(self.title_label)

        # Subtítulo / Marca
        self.subtitle_label = QLabel("Yeztli")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        hero_layout.addWidget(self.subtitle_label)

        # Separador decorativo
        self.divider = QFrame()
        self.divider.setFixedHeight(3)
        self.divider.setFixedWidth(260)
        hero_layout.addWidget(self.divider, alignment=Qt.AlignCenter)

        hero_layout.addSpacing(16)

        # Tarjetas de metadatos inferiores
        meta_row = QHBoxLayout()
        meta_row.setSpacing(24)

        self.dev_card = QFrame()
        dev_layout = QVBoxLayout(self.dev_card)
        dev_layout.setContentsMargins(24, 18, 24, 18)
        self.lbl_dev_caption = QLabel("DESARROLLADO POR")
        self.lbl_dev_caption.setAlignment(Qt.AlignCenter)
        self.lbl_dev_val = QLabel("CIATEQ A.C.")
        self.lbl_dev_val.setAlignment(Qt.AlignCenter)
        dev_layout.addWidget(self.lbl_dev_caption)
        dev_layout.addWidget(self.lbl_dev_val)

        self.ver_card = QFrame()
        ver_layout = QVBoxLayout(self.ver_card)
        ver_layout.setContentsMargins(24, 18, 24, 18)
        self.lbl_ver_caption = QLabel("VERSIÓN DE SOFTWARE")
        self.lbl_ver_caption.setAlignment(Qt.AlignCenter)
        self.lbl_ver_val = QLabel(f"v{__version__}")
        self.lbl_ver_val.setAlignment(Qt.AlignCenter)
        ver_layout.addWidget(self.lbl_ver_caption)
        ver_layout.addWidget(self.lbl_ver_val)

        self.mode_card = QFrame()
        mode_layout = QVBoxLayout(self.mode_card)
        mode_layout.setContentsMargins(24, 18, 24, 18)
        self.lbl_mode_caption = QLabel("MODALIDADES CLÍNICAS")
        self.lbl_mode_caption.setAlignment(Qt.AlignCenter)
        self.lbl_mode_val = QLabel("HD • HDF • UF")
        self.lbl_mode_val.setAlignment(Qt.AlignCenter)
        mode_layout.addWidget(self.lbl_mode_caption)
        mode_layout.addWidget(self.lbl_mode_val)

        meta_row.addWidget(self.dev_card)
        meta_row.addWidget(self.ver_card)
        meta_row.addWidget(self.mode_card)
        hero_layout.addLayout(meta_row)

        main_layout.addWidget(self.hero_card, alignment=Qt.AlignCenter)
        main_layout.addStretch(1)
        logger.info("MainScreen initialized successfully.")

    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        self.setStyleSheet(f"background-color: {tokens['bg_main']}; border-radius: 15px;")

        self.hero_card.setStyleSheet(
            f"QFrame {{ background-color: {tokens['bg_card']}; "
            f"border: 2px solid {tokens['border_card']}; border-radius: 24px; }}"
        )
        self.badge_label.setStyleSheet(
            f"background-color: {tokens['bg_card_alt']}; color: {tokens['primary']}; "
            f"font-size: 16px; font-weight: bold; letter-spacing: 2px; "
            f"padding: 6px 20px; border-radius: 14px; border: 1px solid {tokens['border_card']};"
        )
        self.title_label.setStyleSheet(
            f"font-size: 50px; font-weight: bold; color: {tokens['text_primary']}; "
            f"background: transparent; border: none; padding-top: 8px;"
        )
        brand_color = "#9F1239" if not tokens.get("is_dark") else "#FB7185"
        self.subtitle_label.setStyleSheet(
            f"font-size: 62px; font-weight: bold; color: {brand_color}; "
            f"background: transparent; border: none;"
        )
        self.divider.setStyleSheet(
            f"background-color: {tokens['primary']}; border: none; border-radius: 2px;"
        )

        subcard_style = (
            f"QFrame {{ background-color: {tokens['bg_card_alt']}; "
            f"border: 1px solid {tokens['border_card']}; border-radius: 16px; }}"
        )
        caption_style = (
            f"font-size: 15px; font-weight: bold; color: {tokens['text_muted']}; "
            f"border: none; background: transparent;"
        )
        val_style = (
            f"font-size: 26px; font-weight: bold; color: {tokens['text_primary']}; "
            f"border: none; background: transparent;"
        )

        for card in (self.dev_card, self.ver_card, self.mode_card):
            card.setStyleSheet(subcard_style)
        for cap in (self.lbl_dev_caption, self.lbl_ver_caption, self.lbl_mode_caption):
            cap.setStyleSheet(caption_style)
        for val in (self.lbl_dev_val, self.lbl_ver_val, self.lbl_mode_val):
            val.setStyleSheet(val_style)
