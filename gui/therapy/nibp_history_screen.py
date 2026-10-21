# gui/therapy/nibp_history_screen.py
"""
Pantalla de historial de mediciones de presión arterial (NIBP) para una sesión de terapia.
- Gráfica pyqtgraph con sistólica (rojo), diastólica (azul), FC (verde)
- Tabla con todas las mediciones incluyendo las "antes" (sin elapsed_s)
- Botón para volver a la pantalla del baumanómetro
"""

import logging
from os import name
from typing import Optional
from PySide6.QtWidgets import (
    QGridLayout, QWidget, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

import pyqtgraph as pg
import numpy as np

from core.nibp_pressure_history import NibpPressureHistory
from gui.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class NibpHistoryScreen(QWidget):
    """Pantalla de visualización del historial de presiones de una terapia."""
    
    def __init__(self, parent=None, history: Optional[NibpPressureHistory] = None):
        super().__init__(parent)
        self.parent_window = parent
        self.history = history if history is not None else NibpPressureHistory()
        
        self.programmed_therapy_minutes = 240  # duración programada (se actualiza desde main)
        
        self.setup_background()
        self.setup_ui()
        self.update_from_history()
        try:
            ThemeManager.instance().theme_changed.connect(self._on_theme_changed)
        except Exception:
            pass
    
    def setup_background(self):
        """Fondo de la pantalla."""
        t = ThemeManager.get_tokens()
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), QColor(t.get("bg_primary", "#ffffff")))
        self.setPalette(p)
    
    def setup_ui(self):
        """Construye la interfaz: encabezado, gráfica, tabla, botón."""
        main = QGridLayout(self)
        
        # Márgenes DPI-aware
        dpi = self.logicalDpiX() / 96.0
        margen = int(16 * max(dpi, 1.0))
        main.setContentsMargins(margen, margen, margen, margen)
        main.setSpacing(10)
        
        # ─── ENCABEZADO ───────────────────────────────────────────────
        header_layout = QHBoxLayout()
        self.lbl_title = QLabel("Historial de Presión Arterial")
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()
        
        self.btn_close = QPushButton("Cerrar")
        self.btn_close.clicked.connect(self.on_close_clicked)
        header_layout.addWidget(self.btn_close)
        
        main.addLayout(header_layout, 0, 0, 1, 4)
        
        # ─── GRÁFICA ───────────────────────────────────────────────────
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.hideButtons()
        self.plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.plot_item = self.plot_widget.plotItem
        self.plot_item.showGrid(x=True, y=True, alpha=0.25)
        
        # Configurar eje izquierdo
        left_axis = self.plot_item.getAxis("left")
        left_axis.enableAutoSIPrefix(False)
        left_axis.setStyle(tickTextOffset=7)
        left_axis.setWidth(110)

        # Configurar eje inferior
        bottom_axis = self.plot_item.getAxis("bottom")
        bottom_axis.enableAutoSIPrefix(False)
        bottom_axis.setStyle(tickTextOffset=6)
        
        self.plot_item.hideAxis("top")
        self.plot_item.hideAxis("right")

        # ViewBox con rangos fijos
        self.plot_item.vb.enableAutoRange(False)
        self.plot_item.vb.setYRange(40, 200, padding=0)
        self.plot_item.vb.setXRange(0, max(self.programmed_therapy_minutes, 1), padding=0)

        # Crear las tres curvas
        self.curve_sys = self.plot_widget.plot(
            [], [], pen=pg.mkPen("#dc2626", width=2.5),
            symbol="o", symbolSize=8, symbolBrush="#dc2626", name="Sistólica",
        )
        self.curve_dia = self.plot_widget.plot(
            [], [], pen=pg.mkPen("#2563eb", width=2.5),
            symbol="o", symbolSize=8, symbolBrush="#2563eb", name="Diastólica",
        )
        self.curve_hr = self.plot_widget.plot(
            [], [], pen=pg.mkPen("#15803d", width=2.5),
            symbol="o", symbolSize=8, symbolBrush="#15803d", name="FC (lpm)",
        )

        # Leyenda flotante dentro de la cuadrícula
        self.legend = pg.LegendItem(offset=(8, 8))
        self.legend.setParentItem(self.plot_item.vb)
        self.legend.addItem(self.curve_sys, "Sistólica")
        self.legend.addItem(self.curve_dia, "Diastólica")
        self.legend.addItem(self.curve_hr, "FC (lpm)")

        # Agregar plot a la fila 1, columnas 0-1
        main.addWidget(self.plot_widget, 1, 0, 1, 2)
        
        # ─── LABEL DEL EJE X (separado) ───────────────────────────────
        self.lbl_x_axis = QLabel("Minutos de Terapia")
        self.lbl_x_axis.setAlignment(Qt.AlignCenter)
        
        # Agregar label en fila 2, columnas 0-1 (solo bajo la gráfica)
        main.addWidget(self.lbl_x_axis, 2, 0, 1, 2)
        
        # ─── TABLA ─────────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "No.", "Tiempo", "SYS", "DIA", "MAP", "FC", "SpO2", "Origen"
        ])
        
        # Ajustar columnas
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        
        # Agregar tabla en fila 3, 4 columnas
        main.addWidget(self.table, 3, 0, 1, 4)
        
        # ─── PIE DE PÁGINA ─────────────────────────────────────────────
        footer_layout = QHBoxLayout()
        self.lbl_count = QLabel("Total: 0 mediciones")
        footer_layout.addWidget(self.lbl_count)
        footer_layout.addStretch()
        
        # Agregar pie en fila 4, 4 columnas
        main.addLayout(footer_layout, 4, 0, 1, 4)

        # ─── CONFIGURAR STRETCH FACTORS ────────────────────────────────
        # Columnas: igual stretch para 0, 1, 2, 3
        main.setColumnStretch(0, 1)
        main.setColumnStretch(1, 1)
        main.setColumnStretch(2, 1)
        main.setColumnStretch(3, 1)
        
        # Filas: gráfica 3, tabla 2
        main.setRowStretch(0, 0)  # Encabezado: auto
        main.setRowStretch(1, 3)  # Gráfica: 3 partes
        main.setRowStretch(2, 0)  # Label eje X: auto
        main.setRowStretch(3, 2)  # Tabla: 2 partes
        main.setRowStretch(4, 0)  # Footer: auto
        
        self.setLayout(main)
        self._apply_theme_styles()

    def _on_theme_changed(self, _theme_name: str):
        self.setup_background()
        self._apply_theme_styles()

    def _apply_theme_styles(self):
        t = ThemeManager.get_tokens()
        bg_card = t.get("bg_card", "#ffffff")
        bg_alt = t.get("bg_card_alt", "#f8fafc")
        text_primary = t.get("text_primary", "#0f172a")
        text_secondary = t.get("text_secondary", "#475569")
        border = t.get("border", "#cbd5e1")
        accent = t.get("accent", "#2563eb")
        accent_soft = t.get("accent_soft", "#dbeafe")

        self.lbl_title.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {text_primary};")
        self.btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('btn_secondary_bg', '#64748b')};
                color: {t.get('btn_secondary_text', '#ffffff')};
                font-size: 16px;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 8px;
                border: 1px solid {border};
            }}
            QPushButton:hover {{ background-color: {accent}; color: #ffffff; }}
        """)
        self.plot_widget.setBackground(bg_card)
        self.plot_item.vb.setBackgroundColor(bg_card)
        self.plot_item.setLabel("left", "mmHg", color=text_primary)
        self.plot_item.setLabel("bottom", "", color=text_primary)
        left_axis = self.plot_item.getAxis("left")
        left_axis.setPen(pg.mkPen(text_secondary))
        left_axis.setTextPen(pg.mkPen(text_primary))
        bottom_axis = self.plot_item.getAxis("bottom")
        bottom_axis.setPen(pg.mkPen(text_secondary))
        bottom_axis.setTextPen(pg.mkPen(text_primary))
        self.plot_item.vb.setBorder(pg.mkPen(border, width=1))

        c_bg = QColor(bg_alt)
        self.legend.setBrush(pg.mkBrush(c_bg.red(), c_bg.green(), c_bg.blue(), 230))
        self.legend.setPen(pg.mkPen(border))

        self.lbl_x_axis.setStyleSheet(f"font-size: 13px; color: {text_primary}; font-weight: normal;")
        self.lbl_count.setStyleSheet(f"font-size: 14px; color: {text_primary};")

        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {bg_card};
                gridline-color: {border};
                border: 1px solid {border};
                border-radius: 8px;
                color: {text_primary};
            }}
            QTableWidget::item {{
                padding: 4px;
                background-color: {bg_card};
                color: {text_primary};
            }}
            QTableWidget::item:selected {{
                background-color: {accent_soft};
                color: {text_primary};
            }}
            QHeaderView {{
                background-color: {bg_alt};
                border: none;
            }}
            QHeaderView::section {{
                background-color: {bg_alt};
                color: {text_primary};
                padding: 4px;
                border: none;
                border-bottom: 2px solid {border};
                font-weight: bold;
            }}
            QTableCornerButton::section {{
                background-color: {bg_alt};
                border: none;
            }}
        """)
    
    def update_from_history(self):
        """Actualiza gráfica y tabla desde el historial."""
        measurements = self.history.get_all_measurements()
        self.table.setRowCount(len(measurements))

        for row_idx, measurement in enumerate(measurements):
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(measurement.n)))

            if measurement.elapsed_s is not None:
                minutes = int(measurement.elapsed_s // 60)
                seconds = int(measurement.elapsed_s % 60)
                time_str = f"{minutes:02d}:{seconds:02d}"
            else:
                time_str = "antes"

            self.table.setItem(row_idx, 1, QTableWidgetItem(time_str))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(measurement.sys)))
            self.table.setItem(row_idx, 3, QTableWidgetItem(str(measurement.dia)))
            self.table.setItem(row_idx, 4, QTableWidgetItem(str(measurement.map_mmhg)))
            self.table.setItem(row_idx, 5, QTableWidgetItem(str(measurement.hr)))
            spo2_str = str(measurement.spo2) if measurement.spo2 is not None else "—"
            self.table.setItem(row_idx, 6, QTableWidgetItem(spo2_str))
            self.table.setItem(row_idx, 7, QTableWidgetItem(measurement.origen))

        measurements_with_elapsed = self.history.get_measurements_with_elapsed()

        if measurements_with_elapsed:
            x_data = np.array([m.elapsed_s / 60.0 for m in measurements_with_elapsed], dtype=float)
            sys_data = np.array([m.sys for m in measurements_with_elapsed], dtype=float)
            dia_data = np.array([m.dia for m in measurements_with_elapsed], dtype=float)
            hr_data = np.array([m.hr for m in measurements_with_elapsed], dtype=float)

            self.curve_sys.setData(x_data, sys_data)
            self.curve_dia.setData(x_data, dia_data)
            self.curve_hr.setData(x_data, hr_data)
        else:
            self.curve_sys.clear()
            self.curve_dia.clear()
            self.curve_hr.clear()

        # Rangos fijos (se aplican siempre, con o sin datos)
        self.plot_item.vb.enableAutoRange(False)
        self.plot_item.vb.setXRange(0, max(self.programmed_therapy_minutes, 1), padding=0)
        self.plot_item.vb.setYRange(40, 200, padding=0)

        self.lbl_count.setText(f"Total: {len(measurements)} mediciones")
    
    def set_programmed_duration(self, hours: int, minutes: int):
        """Establece la duración programada de la terapia para el rango del eje X."""
        self.programmed_therapy_minutes = hours * 60 + minutes
    
    def on_close_clicked(self):
        """Vuelve a la pantalla del baumanómetro."""
        if self.parent_window and hasattr(self.parent_window, "show_nibp_screen"):
            self.parent_window.show_nibp_screen()
