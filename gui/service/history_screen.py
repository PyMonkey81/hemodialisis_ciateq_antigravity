# gui/service/history_screen.py

"""
Pantalla de consulta de historial de tratamientos realizados y mantenimientos,
con visor integrado de Reportes Clínicos Nefrológicos / Hoja de Enfermería
y exportación directa a PDF, JSON y CSV.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QSizePolicy, QDialog, QTextBrowser
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from gui.components.floating_confirm import FloatingConfirmDialog
from gui.theme_manager import ThemeManager
from utilities.therapy_report_generator import TherapyReportGenerator

logger = logging.getLogger(__name__)


class TherapyReportViewerDialog(QDialog):
    """
    Visor modal táctil para consultar el Reporte Clínico Nefrológico y Hoja de Enfermería
    de una sesión de hemodiálisis y exportarlo a PDF o CSV.
    """

    def __init__(self, report_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.report_data = report_data
        self.parent_window = parent
        self.setWindowTitle(f"Reporte Clínico de Terapia - Folio {report_data.get('report_id', '')}")
        self.resize(1380, 860)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        t = ThemeManager.get_tokens()
        bg_primary = t.get("bg_primary", "#f1f5f9")
        bg_card = t.get("bg_card", "#ffffff")
        text_primary = t.get("text_primary", "#0f172a")
        border = t.get("border", "#cbd5e1")
        accent = t.get("accent", "#2563eb")

        self.setStyleSheet(f"QDialog {{ background-color: {bg_primary}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # Header
        header_row = QHBoxLayout()
        p_name = self.report_data.get("patient", {}).get("name", "Paciente")
        folio = self.report_data.get("report_id", "")
        lbl_title = QLabel(f"Reporte Clínico de Hemodiálisis — {p_name} (Folio: {folio})")
        lbl_title.setStyleSheet(f"font-size: 24px; font-weight: 800; color: {text_primary};")
        header_row.addWidget(lbl_title)
        header_row.addStretch()
        layout.addLayout(header_row)

        # Visor HTML (siempre sobre papel blanco clínico para fidelidad al PDF)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: #ffffff;
                color: #0f172a;
                border: 2px solid {border};
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        html = TherapyReportGenerator.render_html_report(self.report_data)
        self.browser.setHtml(html)
        layout.addWidget(self.browser, stretch=1)

        # Botonera inferior
        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {accent};")
        btn_row.addWidget(self.lbl_status)
        btn_row.addStretch()

        btn_pdf = QPushButton("Exportar PDF")
        btn_pdf.setFixedSize(220, 56)
        btn_pdf.setStyleSheet("""
            QPushButton {
                background-color: #16a34a;
                color: #ffffff;
                font-size: 20px;
                font-weight: bold;
                border-radius: 10px;
            }
            QPushButton:hover { background-color: #15803d; }
        """)
        btn_pdf.clicked.connect(self._on_export_pdf)
        btn_row.addWidget(btn_pdf)

        btn_csv = QPushButton("Exportar CSV")
        btn_csv.setFixedSize(220, 56)
        btn_csv.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                color: #ffffff;
                font-size: 20px;
                font-weight: bold;
                border-radius: 10px;
            }}
            QPushButton:hover {{ background-color: #1d4ed8; }}
        """)
        btn_csv.clicked.connect(self._on_export_csv)
        btn_row.addWidget(btn_csv)

        btn_close = QPushButton("Cerrar")
        btn_close.setFixedSize(180, 56)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #64748b;
                color: #ffffff;
                font-size: 20px;
                font-weight: bold;
                border-radius: 10px;
            }
            QPushButton:hover { background-color: #475569; }
        """)
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def _on_export_pdf(self):
        try:
            bundle = TherapyReportGenerator.save_session_report_bundle(self.report_data)
            pdf_path = bundle.get("pdf_path", "")
            self.lbl_status.setText(f"PDF guardado en: {pdf_path}")
        except Exception as e:
            self.lbl_status.setText(f"Error al exportar PDF: {e}")

    def _on_export_csv(self):
        try:
            bundle = TherapyReportGenerator.save_session_report_bundle(self.report_data)
            csv_path = bundle.get("csv_path", "")
            self.lbl_status.setText(f"CSV guardado en: {csv_path}")
        except Exception as e:
            self.lbl_status.setText(f"Error al exportar CSV: {e}")


class HistoryScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        
        self.treatments = []
        self.cleanings = []
        self.current_filter = "Tratamientos"

        self.setObjectName("HistoryScreen")
        self.setup_ui()
        try:
            ThemeManager.instance().theme_changed.connect(self._on_theme_changed)
        except Exception:
            pass

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(18)
        main_layout.setContentsMargins(24, 20, 24, 20)

        # ==================== TÍTULO ====================
        self.lbl_title = QLabel("Historial Clínico de Terapias y Reportes Nefrológicos")
        self.lbl_title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.lbl_title)

        # ==================== FILTRO Y TOTAL ====================
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(14)
        
        self.lbl_tipo_registro = QLabel("Vista:")
        filter_layout.addWidget(self.lbl_tipo_registro)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Tratamientos", "Limpieza"])
        self.type_combo.setFixedWidth(220)
        self.type_combo.setFixedHeight(48)
        self.type_combo.currentTextChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.type_combo)

        self.load_button = QPushButton("Actualizar")
        self.load_button.setFixedSize(180, 48)
        self.load_button.clicked.connect(self.refresh_data)
        filter_layout.addWidget(self.load_button)

        self.btn_live_report = QPushButton("Reporte Sesión Actual")
        self.btn_live_report.setFixedSize(260, 48)
        self.btn_live_report.clicked.connect(self.open_current_session_report)
        filter_layout.addWidget(self.btn_live_report)

        filter_layout.addStretch()

        # Indicador de total de horas
        self.total_label = QLabel("Total de horas: 0.0 h")
        self.total_label.setAlignment(Qt.AlignCenter)
        filter_layout.addWidget(self.total_label)

        main_layout.addLayout(filter_layout)

        # ==================== TABLA DENTRO DE SCROLL ====================
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)       

        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.doubleClicked.connect(lambda _idx: self.view_selected_report())

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setDefaultAlignment(Qt.AlignCenter)

        self.scroll.setWidget(self.table)
        main_layout.addWidget(self.scroll, stretch=1)

        # ==================== BOTONES INFERIORES ====================
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(16)

        self.btn_view_report = QPushButton("Ver Reporte Clínico")
        self.btn_view_report.setFixedSize(250, 68)
        self.btn_view_report.clicked.connect(self.view_selected_report)

        self.btn_export_pdf = QPushButton("Exportar PDF")
        self.btn_export_pdf.setFixedSize(220, 68)
        self.btn_export_pdf.clicked.connect(self.export_selected_to_pdf)

        self.export_btn = QPushButton("Exportar CSV")
        self.export_btn.setFixedSize(220, 68)
        self.export_btn.clicked.connect(self.export_to_csv)

        self.delete_btn = QPushButton("Eliminar Historial")
        self.delete_btn.setFixedSize(230, 68)
        self.delete_btn.clicked.connect(self.confirm_delete_all)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_view_report)
        btn_layout.addWidget(self.btn_export_pdf)
        btn_layout.addWidget(self.export_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()

        main_layout.addLayout(btn_layout)

        self._apply_theme_styles()

    def _on_theme_changed(self, _theme_name: str):
        self._apply_theme_styles()
        self.update_table()

    def _apply_theme_styles(self):
        t = ThemeManager.get_tokens()
        bg_primary = t.get("bg_primary", "#FCFCFC")
        bg_card = t.get("bg_card", "#ffffff")
        bg_alt = t.get("bg_card_alt", "#f8fafc")
        text_primary = t.get("text_primary", "#0f172a")
        text_secondary = t.get("text_secondary", "#475569")
        border = t.get("border", "#cbd5e1")
        accent = t.get("accent", "#2563eb")
        accent_soft = t.get("accent_soft", "#dbeafe")
        btn_bg = t.get("btn_primary_bg", "#06298a")
        btn_hover = t.get("btn_primary_hover", "#1e40af")

        self.setStyleSheet(f"QWidget#HistoryScreen {{ background-color: {bg_primary}; }}")
        self.lbl_title.setStyleSheet(
            f"color: {text_primary}; font-size: 32px; font-weight: 800; background: transparent;"
        )
        self.lbl_tipo_registro.setStyleSheet(f"font-size: 20px; font-weight: 600; color: {text_secondary};")

        self.type_combo.setStyleSheet(f"""
            QComboBox {{ 
                color: {text_primary}; 
                background-color: {bg_card}; 
                font-size: 20px; 
                padding: 4px 10px; 
                border: 1px solid {border}; 
                border-radius: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {bg_card};
                color: {text_primary};
                selection-background-color: {accent};
                selection-color: #ffffff;
            }}
        """)

        primary_btn_qss = f"""
            QPushButton {{
                background: {btn_bg};
                font-size: 20px;
                font-weight: bold;
                color: #FFFFFF;
                border-radius: 10px;
            }}
            QPushButton:hover {{ background: {btn_hover}; }}
            QPushButton:pressed {{ background: {accent}; }}
        """
        self.load_button.setStyleSheet(primary_btn_qss)
        self.export_btn.setStyleSheet(primary_btn_qss)

        self.btn_live_report.setStyleSheet("""
            QPushButton {
                background: #0d9488;
                font-size: 19px;
                font-weight: bold;
                color: #FFFFFF;
                border-radius: 10px;
            }
            QPushButton:hover { background: #0f766e; }
        """)
        self.btn_view_report.setStyleSheet(f"""
            QPushButton {{
                background: {accent};
                font-size: 20px;
                font-weight: bold;
                color: #FFFFFF;
                border-radius: 10px;
            }}
            QPushButton:hover {{ background: {btn_hover}; }}
        """)
        self.btn_export_pdf.setStyleSheet("""
            QPushButton {
                background: #16a34a;
                font-size: 20px;
                font-weight: bold;
                color: #FFFFFF;
                border-radius: 10px;
            }
            QPushButton:hover { background: #15803d; }
        """)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background: #dc2626;
                font-size: 20px;
                font-weight: bold;
                color: #FFFFFF;
                border-radius: 10px;
            }
            QPushButton:hover { background: #b91c1c; }
        """)

        self.total_label.setStyleSheet(f"""
            QLabel {{ 
                background: {accent_soft}; 
                color: {text_primary}; 
                font-size: 22px; 
                font-weight: bold; 
                padding: 6px 18px;
                border-radius: 8px;
                border: 1px solid {border};
            }}
        """)

        self.scroll.setStyleSheet(f"""
            QScrollArea {{ 
                border: 1px solid {border}; 
                background: {bg_card}; 
                border-radius: 10px;
            }}
            QScrollBar:vertical {{
                border: none;
                background: {bg_alt};
                width: 34px;
                margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {t.get('border_strong', '#8a8a9c')};
                min-height: 50px;
                border-radius: 4px;
                margin: 4px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)

        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {bg_card};
                color: {text_primary};
                font-size: 17px;
                gridline-color: {border};
                border: none;
                outline: none;
            }}
            QHeaderView::section {{
                background-color: {bg_alt};
                color: {text_primary};
                font-weight: bold;
                font-size: 18px;
                padding: 8px;
                border: 1px solid {border};
            }}
            QHeaderView::section:vertical {{
                background-color: {bg_alt};
                color: {text_secondary};
                font-weight: bold;
                font-size: 15px;
                padding: 4px;
                border: 1px solid {border};
            }}
            QTableWidget QTableCornerButton::section {{
                background-color: {bg_alt};
                border: 1px solid {border};
            }}
            QTableWidget::item:selected {{
                background-color: {accent_soft};
                color: {text_primary};
            }}
        """)

    def refresh_data(self):
        """Actualiza los datos desde el main window"""
        if self.parent_window:
            self.treatments = getattr(self.parent_window, 'treatment_history', [])
            self.cleanings = getattr(self.parent_window, 'cleaning_history', [])

        self.update_table()

    def on_filter_changed(self, text):
        self.current_filter = text
        is_treatments = (text == "Tratamientos")
        self.btn_view_report.setVisible(is_treatments)
        self.btn_export_pdf.setVisible(is_treatments)
        self.update_table()

    @staticmethod
    def _safe_minutes(value, default=0):
        """Convierte un valor de duración a minutos de forma segura."""
        if value is None:
            return default

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)

        if isinstance(value, str):
            cleaned = value.strip().replace(',', '.')
            if not cleaned:
                return default

            try:
                return int(float(cleaned))
            except ValueError:
                pass

            if ':' in cleaned:
                parts = cleaned.split(':')
                try:
                    if len(parts) == 2:
                        hours, minutes = parts
                        return int(float(hours)) * 60 + int(float(minutes))
                    if len(parts) == 3:
                        hours, minutes, seconds = parts
                        return int(float(hours)) * 3600 + int(float(minutes)) * 60 + int(float(seconds))
                except ValueError:
                    return default

        return default

    def update_table(self):
        """Actualiza la tabla según el filtro seleccionado"""
        t = ThemeManager.get_tokens()
        fg_color = QColor(t.get("text_primary", "#0f172a"))
        self.table.setRowCount(0)

        if self.current_filter == "Tratamientos":
            data = self.treatments
            self.table.setColumnCount(8)
            self.table.setHorizontalHeaderLabels([
                "Fecha",
                "Paciente",
                "Modalidad",
                "Horario",
                "Duración",
                "UF (L)",
                "Kt/V",
                "PA Final",
            ])
            for row_data in data:
                if not isinstance(row_data, dict):
                    continue
                row = self.table.rowCount()
                self.table.insertRow(row)

                h_ini = str(row_data.get("hora_inicio", ""))[:5]
                h_fin = str(row_data.get("hora_fin", ""))[:5]
                horario = f"{h_ini} - {h_fin}" if (h_ini or h_fin) else "—"
                paciente = str(row_data.get("paciente") or row_data.get("patient_name") or "Sin registrar")
                modalidad = str(row_data.get("tipo_tratamiento", "Hemodiálisis"))
                duracion = str(row_data.get("duracion_hhmm", "00:00"))
                uf_val = row_data.get("uf_lograda_l")
                uf_str = f"{float(uf_val):.2f} L" if uf_val is not None else "—"
                ktv_val = row_data.get("ktv_final")
                ktv_str = f"{float(ktv_val):.2f}" if ktv_val is not None else "—"
                pa_str = str(row_data.get("pa_final") or "—")

                cells = [
                    str(row_data.get("fecha", "")),
                    paciente,
                    modalidad,
                    horario,
                    duracion,
                    uf_str,
                    ktv_str,
                    pa_str,
                ]
                for col, txt in enumerate(cells):
                    item = QTableWidgetItem(txt)
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setForeground(fg_color)
                    self.table.setItem(row, col, item)
        else:
            data = self.cleanings
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels([
                "Fecha",
                "Hora Inicio",
                "Hora Fin",
                "Tipo",
                "Duración",
            ])
            for row_data in data:
                if not isinstance(row_data, dict):
                    continue
                row = self.table.rowCount()
                self.table.insertRow(row)

                cells = [
                    str(row_data.get("fecha", "")),
                    str(row_data.get("hora_inicio", "")),
                    str(row_data.get("hora_fin", "")),
                    str(row_data.get("tipo_tratamiento", "")),
                    str(row_data.get("duracion_hhmm", "00:00")),
                ]
                for col, txt in enumerate(cells):
                    item = QTableWidgetItem(txt)
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setForeground(fg_color)
                    self.table.setItem(row, col, item)

        total_minutes = sum(
            self._safe_minutes(item.get("duracion_minutos", 0))
            for item in data
            if isinstance(item, dict)
        )
        total_hours = total_minutes / 60.0
        self.total_label.setText(f"Total de horas: {total_hours:.1f} h")

    def _resolve_report_for_row(self, row_idx: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene o reconstruye el diccionario de reporte clínico para la fila seleccionada.
        Si existe `report_json_path` en disco lo carga; de lo contrario reconstruye un reporte
        válido a partir de los metadatos del registro histórico.
        """
        if not self.treatments:
            return None
        if row_idx < 0 or row_idx >= len(self.treatments):
            row_idx = len(self.treatments) - 1

        record = self.treatments[row_idx]
        if not isinstance(record, dict):
            return None

        json_path = record.get("report_json_path")
        if json_path and Path(json_path).exists():
            try:
                with Path(json_path).open("r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"No se pudo cargar report_json_path {json_path}: {e}")

        if isinstance(record.get("report_data"), dict):
            return record["report_data"]

        # Reconstruir reporte desde registro histórico legado
        synthetic_values = {
            "patient_id": record.get("patient_id", "S/ID"),
            "patient_name": record.get("paciente", "Paciente Histórico"),
            "uf_goal_liters": float(record.get("uf_meta_l", 0.0) or 0.0),
            "ktv_current": float(record.get("ktv_final", 0.0) or 0.0),
        }
        dur_min = self._safe_minutes(record.get("duracion_minutos", 0))
        report = TherapyReportGenerator.build_session_report(
            current_values=synthetic_values,
            elapsed_seconds=dur_min * 60.0,
            uf_removed_liters=float(record.get("uf_lograda_l", 0.0) or 0.0),
            start_time_str=record.get("hora_inicio", "00:00:00"),
            end_time_str=record.get("hora_fin", "00:00:00"),
            completion_status="Registro Histórico",
        )
        report["session_date"] = str(record.get("fecha", report["session_date"]))
        return report

    def view_selected_report(self):
        """Abre el visor clínico con el reporte del tratamiento seleccionado."""
        if self.current_filter != "Tratamientos":
            return
        if not self.treatments:
            if self.parent_window and hasattr(self.parent_window, "show_warning_message"):
                self.parent_window.show_warning_message("No hay sesiones de terapia registradas. Use 'Reporte Sesión Actual' para vista previa.", 3000)
            return

        row_idx = self.table.currentRow()
        report = self._resolve_report_for_row(row_idx)
        if not report:
            return

        dlg = TherapyReportViewerDialog(report, parent=self)
        dlg.exec()

    def open_current_session_report(self):
        """Construye y muestra en vivo el reporte de la sesión actual (en curso o recién terminada)."""
        if self.parent_window and hasattr(self.parent_window, "build_current_clinical_report"):
            report = self.parent_window.build_current_clinical_report()
        else:
            vals = getattr(self.parent_window, "current_values", {}) if self.parent_window else {}
            report = TherapyReportGenerator.build_session_report(current_values=vals)

        dlg = TherapyReportViewerDialog(report, parent=self)
        dlg.exec()

    def export_selected_to_pdf(self):
        """Exporta directamente a PDF el tratamiento seleccionado (o la sesión actual si no hay historial)."""
        row_idx = self.table.currentRow()
        report = self._resolve_report_for_row(row_idx)
        if not report:
            if self.parent_window and hasattr(self.parent_window, "build_current_clinical_report"):
                report = self.parent_window.build_current_clinical_report()
            else:
                if self.parent_window and hasattr(self.parent_window, "show_warning_message"):
                    self.parent_window.show_warning_message("No hay reporte disponible para exportar.", 2500)
                return

        try:
            bundle = TherapyReportGenerator.save_session_report_bundle(report)
            pdf_path = bundle.get("pdf_path", "")
            if self.parent_window and hasattr(self.parent_window, "show_info_message"):
                self.parent_window.show_info_message(f"Reporte PDF generado:\n{pdf_path}", 3500)
            else:
                QMessageBox.information(self, "Reporte PDF", f"Reporte PDF generado:\n{pdf_path}")
        except Exception as e:
            if self.parent_window and hasattr(self.parent_window, "show_error_message"):
                self.parent_window.show_error_message(f"Error al exportar PDF:\n{e}", 3000)

    def export_to_csv(self):
        """Exporta los datos actuales a CSV"""
        if self.current_filter == "Tratamientos":
            data = self.treatments
            filename = f"historial_tratamientos_{datetime.now().strftime('%Y%m%d')}.csv"
        else:
            data = self.cleanings
            filename = f"historial_limpieza_{datetime.now().strftime('%Y%m%d')}.csv"

        if not data:
            if self.parent_window and hasattr(self.parent_window, "show_warning_message"):
                self.parent_window.show_warning_message("No hay registros para exportar.", 2500)
            else:
                QMessageBox.information(self, "Historial", "No hay registros para exportar.")
            return

        try:
            os.makedirs("exports", exist_ok=True)
            filepath = f"exports/{filename}"

            all_keys = []
            for item in data:
                if isinstance(item, dict):
                    for k in item.keys():
                        if k not in all_keys and k != "report_data":
                            all_keys.append(k)

            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(data)

            if self.parent_window and hasattr(self.parent_window, "show_info_message"):
                self.parent_window.show_info_message(f"Archivo exportado correctamente:\n{filepath}", 2500)
            else:
                QMessageBox.information(self, "Historial", f"Archivo exportado correctamente:\n{filepath}")

        except Exception as e:
            if self.parent_window and hasattr(self.parent_window, "show_error_message"):
                self.parent_window.show_error_message(f"No se pudo exportar:\n{str(e)}", 2500)
            else:
                QMessageBox.critical(self, "Historial", f"No se pudo exportar:\n{str(e)}")

    def confirm_delete_all(self):
        """Confirma antes de eliminar todo el historial"""
        dialog = FloatingConfirmDialog(self)
        msg = f"¿Estás seguro de eliminar TODO el historial de {self.current_filter}?\n\nEsta acción es irreversible."

        if dialog.show_confirm(msg, accept_text="Sí, Eliminar Todo", cancel_text="Cancelar"):
            if self.current_filter == "Tratamientos":
                self.treatments.clear()
                if self.parent_window:
                    self.parent_window.treatment_history = []
                    self.parent_window._save_treatment_history()
            else:
                self.cleanings.clear()
                if self.parent_window:
                    self.parent_window.cleaning_history = []
                    self.parent_window._save_cleaning_history()

            self.update_table()
            if self.parent_window and hasattr(self.parent_window, "show_success_message"):
                self.parent_window.show_success_message(f"Historial de {self.current_filter} eliminado correctamente.", 2500)
            else:
                QMessageBox.information(self, "Historial", f"Historial de {self.current_filter} eliminado correctamente.")
