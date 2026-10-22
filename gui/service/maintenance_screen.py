from gui.theme_manager import ThemeManager
# gui/service/maintenance_screen.py
"""
Pantalla de Mantenimiento Preventivo
Incluye: Power On Hours, Horas de Operación en Tratamiento y Horas de Limpieza
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, 
    QHBoxLayout
)
from PySide6.QtCore import Qt
import logging
from gui.components.floating_confirm import FloatingConfirmDialog
from core.state_manager import TreatmentPhase
logger = logging.getLogger(__name__)


class MaintenanceScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        
        # Fondo claro forzado
        self.setStyleSheet("""
            MaintenanceScreen {
                background-color: #f8fafc;
                color: #1e293b;
            }
        """)
        
        self.setup_ui()
        self.apply_theme_styles()
        try:
            ThemeManager.instance().theme_changed.connect(lambda _t: self.apply_theme_styles())
        except Exception:
            pass

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(30)
        main_layout.setContentsMargins(30, 30, 30, 30)

        # Título
        self.title_label = QLabel("Mantenimiento Preventivo")
        self.title_label.setStyleSheet("color: #1e293b; font-size: 36px; font-weight: bold;")
        self.title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.title_label)

        # Estilo base para los marcos
        frame_style = """
            QFrame {
                background: #ffffff; 
                border: 1px solid #cbd5e1; 
                border-radius: 10px; 
                padding: 5px;
            }
        """
    
        label_style = """
            color: #475569; 
            font-size: 26px;
            border: none;
        """
        
        value_style = """
            color: #0f172a; 
            font-size: 46px; 
            font-weight: bold;
            border: none;
        """

        # ==================== Power On Hours ====================
        self.pon_frame = QFrame()
        self.pon_frame.setStyleSheet(frame_style)
        pon_layout = QVBoxLayout(self.pon_frame)
        pon_layout.setSpacing(15)
        pon_layout.setAlignment(Qt.AlignCenter)   # Centrado horizontal

        self.lbl_pon = QLabel("Horas de Máquina Encendida")
        self.lbl_pon.setStyleSheet(label_style)
        self.lbl_pon.setAlignment(Qt.AlignCenter)

        self.pon_value = QLabel("00:00:00 hh:mm:ss")
        self.pon_value.setStyleSheet(value_style)
        self.pon_value.setAlignment(Qt.AlignCenter)

        pon_layout.addStretch()          
        pon_layout.addWidget(self.lbl_pon)
        pon_layout.addWidget(self.pon_value)
        pon_layout.addStretch()          

        main_layout.addWidget(self.pon_frame)

        # ==================== Horas de Operación ====================
        self.op_frame = QFrame()
        self.op_frame.setStyleSheet(frame_style)
        op_layout = QVBoxLayout(self.op_frame)
        op_layout.setSpacing(15)
        op_layout.setAlignment(Qt.AlignCenter)

        self.lbl_op = QLabel("Horas de Operación en Tratamiento")
        self.lbl_op.setStyleSheet(label_style)
        self.lbl_op.setAlignment(Qt.AlignCenter)

        self.op_value = QLabel("00:00:00 hh:mm:ss")
        self.op_value.setStyleSheet(value_style)
        self.op_value.setAlignment(Qt.AlignCenter)

        op_layout.addStretch()
        op_layout.addWidget(self.lbl_op)
        op_layout.addWidget(self.op_value)
        op_layout.addStretch()

        main_layout.addWidget(self.op_frame)

        # ==================== Horas de Limpieza ====================
        self.clean_frame = QFrame()
        self.clean_frame.setStyleSheet(frame_style)
        clean_layout = QVBoxLayout(self.clean_frame)
        clean_layout.setSpacing(15)
        clean_layout.setAlignment(Qt.AlignCenter)

        self.lbl_clean = QLabel("Horas de Limpieza")
        self.lbl_clean.setStyleSheet(label_style)
        self.lbl_clean.setAlignment(Qt.AlignCenter)

        self.clean_value = QLabel("00:00:00 hh:mm:ss")
        self.clean_value.setStyleSheet(value_style)
        self.clean_value.setAlignment(Qt.AlignCenter)

        clean_layout.addStretch()
        clean_layout.addWidget(self.lbl_clean)
        clean_layout.addWidget(self.clean_value)
        clean_layout.addStretch()

        main_layout.addWidget(self.clean_frame)

        # Información IMSS
        self.imss_info = QLabel("Requisito IMSS: Mínimo 350 horas de operación en tratamiento")
        self.imss_info.setStyleSheet("color: #1e293b; font-size: 24px;")
        self.imss_info.setWordWrap(True)
        self.imss_info.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.imss_info)

        main_layout.addStretch()

        # ==================== Botones de Reset ====================
        btn_style = """
            QPushButton { 
                background: #C4302B; 
                color: #ffffff; 
                font-size: 30px; 
                padding: 5px; 
                border-radius: 8px; 
            }
            QPushButton:hover { 
                background: #991b1b; 
            }
        """

        reset_layout = QHBoxLayout()
        reset_layout.setSpacing(20)

        self.btn_reset_pon = QPushButton("Resetear Encendido")
        self.btn_reset_pon.setStyleSheet(btn_style)
        self.btn_reset_pon.clicked.connect(self.reset_power_on_hours)

        self.btn_reset_op = QPushButton("Resetear Operación")
        self.btn_reset_op.setStyleSheet(btn_style)
        self.btn_reset_op.clicked.connect(self.reset_operation_hours)

        self.btn_reset_clean = QPushButton("Resetear Limpieza")
        self.btn_reset_clean.setStyleSheet(btn_style)
        self.btn_reset_clean.clicked.connect(self.reset_cleaning_hours)

        reset_layout.addWidget(self.btn_reset_pon)
        reset_layout.addWidget(self.btn_reset_op)
        reset_layout.addWidget(self.btn_reset_clean)
        main_layout.addLayout(reset_layout)

    # ==================== Métodos de actualización (Soporte legado por si acaso) ====================
    def update_power_on_hours(self, hours: int, minutes: int, seconds: int = 0):
        self.pon_value.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d} hh:mm:ss")

    def update_operation_hours(self, hours: int, minutes: int, seconds: int = 0):
        self.op_value.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d} hh:mm:ss")

    def update_cleaning_hours(self, hours: int, minutes: int, seconds: int = 0):
        self.clean_value.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d} hh:mm:ss")

    # ==================== Métodos de reset ====================
    def reset_power_on_hours(self):
        if self._confirm_reset("Power On Hours"):
            if self.parent_window:
                if hasattr(self.parent_window, 'timer_manager'):
                    self.parent_window.timer_manager.power_on_hours = 0.0
                    self.parent_window.timer_manager._save_power_on_hours()
                self.pon_value.setText("00:00:00 hh:mm:ss")
                logger.warning("Power On Hours fue reseteado por técnico")

    def reset_operation_hours(self):
        if self._confirm_reset("Horas de Operación en Tratamiento"):
            if self.parent_window:
                if hasattr(self.parent_window, 'timer_manager'):
                    self.parent_window.timer_manager.total_operation_hours = 0.0
                    self.parent_window.timer_manager._save_operation_hours()
                self.op_value.setText("00:00:00 hh:mm:ss")
                logger.warning("Horas de Operación en Tratamiento fueron reseteadas por técnico")

    def reset_cleaning_hours(self):
        if self._confirm_reset("Horas de Limpieza"):
            if self.parent_window:
                if hasattr(self.parent_window, 'timer_manager'):
                    self.parent_window.timer_manager.cleaning_hours = 0.0
                    self.parent_window.timer_manager._save_cleaning_hours()
                self.clean_value.setText("00:00:00 hh:mm:ss")
                logger.warning("Horas de Limpieza fueron reseteadas por técnico")
                
    def _confirm_reset(self, counter_name: str) -> bool:
        dialog = FloatingConfirmDialog(self)
        mensaje = f"¿Estás seguro de resetear {counter_name}?\nEsta acción es irreversible.\nPresiona 'Resetear' si estás completamente seguro."
        return dialog.show_confirm(mensaje, accept_text="Sí, Resetear", cancel_text="Cancelar")

    def update_hours_display(self, power_on: float, operation: float, cleaning: float):
        """Actualiza los displays de horas en tiempo real desde TimerManager calculando Segundos"""
        try:
            # Función auxiliar para convertir las horas en formato decimal a H:M:S
            def convert_to_hms(decimal_hours):
                total_seconds = int(decimal_hours * 3600)
                h = total_seconds // 3600
                m = (total_seconds % 3600) // 60
                s = total_seconds % 60
                return h, m, s

            # Power On
            po_h, po_m, po_s = convert_to_hms(power_on)
            self.pon_value.setText(f"{po_h:02d}:{po_m:02d}:{po_s:02d} hh:mm:ss")

            # Operation
            op_h, op_m, op_s = convert_to_hms(operation)
            self.op_value.setText(f"{op_h:02d}:{op_m:02d}:{op_s:02d} hh:mm:ss")

            # Cleaning
            cl_h, cl_m, cl_s = convert_to_hms(cleaning)
            self.clean_value.setText(f"{cl_h:02d}:{cl_m:02d}:{cl_s:02d} hh:mm:ss")

        except Exception as e:
            logger.warning(f"Error actualizando horas en MaintenanceScreen: {e}")
            
    def update_state(self, phase: TreatmentPhase):
        pass


    def apply_theme_styles(self, theme_name: str | None = None):
        tokens = ThemeManager.get_tokens(theme_name)
        is_mono = bool(tokens.get("monochrome", False))
        is_dark = bool(tokens.get("is_dark", False))

        self.setStyleSheet(f"background-color: {tokens['bg_main']}; color: {tokens['text_primary']};")

        if is_mono:
            if hasattr(self, "title_label"):
                self.title_label.setStyleSheet("color: #4B5563; font-size: 36px; font-weight: bold; background: transparent;")
            frame_style = """
                QFrame {
                    background: #FFFFFF;
                    border: 1px solid #D1D5DB;
                    border-radius: 10px;
                    padding: 5px;
                }
            """
            lbl_style = "color: #374151; font-size: 26px; border: none; background: transparent;"
            val_style = "color: #111827; font-size: 46px; font-weight: bold; border: none; background: transparent;"
            btn_style = """
                QPushButton {
                    background: #D9E0E8;
                    color: #374151;
                    font-size: 30px;
                    font-weight: bold;
                    padding: 5px;
                    border-radius: 8px;
                    border: 2px solid #C5CDD6;
                }
                QPushButton:hover { background: #C5CED6; }
                QPushButton:pressed { background: #B0B8C4; }
            """
            imss_style = "color: #374151; font-size: 24px; background: transparent;"

        elif is_dark:
            if hasattr(self, "title_label"):
                self.title_label.setStyleSheet(f"color: {tokens.get('text_primary', '#F8FAFC')}; font-size: 36px; font-weight: bold; background: transparent;")
            frame_style = f"""
                QFrame {{
                    background: {tokens.get('bg_card', '#1E293B')};
                    border: 1px solid {tokens.get('border_card', '#334155')};
                    border-radius: 10px;
                    padding: 5px;
                }}
            """
            lbl_style = f"color: {tokens.get('text_secondary', '#94A3B8')}; font-size: 26px; border: none; background: transparent;"
            val_style = f"color: {tokens.get('text_primary', '#F8FAFC')}; font-size: 46px; font-weight: bold; border: none; background: transparent;"
            btn_style = f"""
                QPushButton {{
                    background: {tokens.get('danger', '#ef4444')};
                    color: #ffffff;
                    font-size: 30px;
                    font-weight: bold;
                    padding: 5px;
                    border-radius: 8px;
                }}
                QPushButton:hover {{ background: {tokens.get('border_strong', '#b91c1c')}; }}
            """
            imss_style = f"color: {tokens.get('text_secondary', '#94A3B8')}; font-size: 24px; background: transparent;"

        else:
            if hasattr(self, "title_label"):
                self.title_label.setStyleSheet("color: #1e293b; font-size: 36px; font-weight: bold; background: transparent;")
            frame_style = """
                QFrame {
                    background: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 10px;
                    padding: 5px;
                }
            """
            lbl_style = "color: #475569; font-size: 26px; border: none; background: transparent;"
            val_style = "color: #0f172a; font-size: 46px; font-weight: bold; border: none; background: transparent;"
            btn_style = """
                QPushButton {
                    background: #C4302B;
                    color: #ffffff;
                    font-size: 30px;
                    padding: 5px;
                    border-radius: 8px;
                }
                QPushButton:hover { background: #991b1b; }
            """
            imss_style = "color: #1e293b; font-size: 24px; background: transparent;"

        for fr in (getattr(self, "pon_frame", None), getattr(self, "op_frame", None), getattr(self, "clean_frame", None)):
            if fr:
                fr.setStyleSheet(frame_style)

        for lbl in (getattr(self, "lbl_pon", None), getattr(self, "lbl_op", None), getattr(self, "lbl_clean", None)):
            if lbl:
                lbl.setStyleSheet(lbl_style)

        for val in (getattr(self, "pon_value", None), getattr(self, "op_value", None), getattr(self, "clean_value", None)):
            if val:
                val.setStyleSheet(val_style)

        for btn in (getattr(self, "btn_reset_pon", None), getattr(self, "btn_reset_op", None), getattr(self, "btn_reset_clean", None)):
            if btn:
                btn.setStyleSheet(btn_style)

        if hasattr(self, "imss_info"):
            self.imss_info.setStyleSheet(imss_style)
