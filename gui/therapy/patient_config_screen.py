# gui/therapy/patient_config_screen.py

"""
Módulo para la configuración y gestión de perfiles de paciente.
Incluye datos antropométricos y datos clínicos de la hoja de enfermería / nefrología:
- NSS / Registro médico
- Acceso vascular (Catéter Temporal, Perm-Cath, FAV, Injerto)
- Diagnóstico médico, Médico tratante, Filtro/Dializador, Grupo y Rh, Alergias
"""




from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QMessageBox, QFormLayout,QGridLayout,
    QGroupBox, QListWidget, QSizePolicy, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator, QIntValidator
from gui.components.numpad_modal import NumpadDialog
from gui.components.keyboard_modal import KeyboardDialog
from gui.components.floating_confirm import FloatingConfirmDialog   
from gui.components.floating_message import FloatingMessage
from gui.theme_manager import ThemeManager
from core.variables_map import VARIABLES
import json
from pathlib import Path
from utilities.platform_runtime import get_runtime_config_path, safe_json_load
import logging
logger = logging.getLogger(__name__)

PATIENTS_CONFIG_FILE = get_runtime_config_path("patients.json")

class PatientConfigScreen(QWidget):
    """
    Pantalla de configuración de paciente con entrada táctil.
    - Teclado QWERTY para texto (ID, nombre, diagnóstico, médico, filtro, alergias)
    - Numpad para valores numéricos
    - Mini DB en memoria con pacientes de prueba
    Todo el contenido de la pantalla es desplazable (scrollable).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_values = parent.current_values if parent else {}

        self.patients_db = {}
        self._form_labels = []
        
        self._load_patients_from_file()      # ← Nueva función
        if not self.patients_db:             # Si no hay pacientes guardados, cargar demo
            self._load_test_patients()
        

        # self.setFixedSize(1536, 726)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setup_ui()
        try:
            ThemeManager.instance().theme_changed.connect(self._on_theme_changed)
        except Exception:
            pass

    def _load_patients_from_file(self):
        """Carga pacientes desde archivo JSON"""
        if not PATIENTS_CONFIG_FILE.exists():
            logger.info("No se encontró archivo de pacientes. Se usarán datos de prueba.")
            print("No se encontró archivo de pacientes. Se usarán datos de prueba.")
            return

        try:
            data = safe_json_load(PATIENTS_CONFIG_FILE, {})
            if not isinstance(data, dict):
                raise ValueError("El archivo de pacientes no contiene un objeto JSON válido.")
            self.patients_db = data
            logger.info(f"Se cargaron {len(self.patients_db)} pacientes desde {PATIENTS_CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Error al cargar pacientes desde JSON: {e}")
            self.patients_db = {}
    
    def _save_patients_to_file(self):
        """Guarda todos los pacientes en JSON"""
        try:
            PATIENTS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with PATIENTS_CONFIG_FILE.open('w', encoding='utf-8') as f:
                json.dump(self.patients_db, f, indent=4, ensure_ascii=False)
            logger.info(f"Pacientes guardados correctamente ({len(self.patients_db)})")
        except Exception as e:
            logger.error(f"Error al guardar pacientes en JSON: {e}")

    def _load_test_patients(self):
        """Pacientes de prueba para demo"""
        test_patients = [
            {
                "patient_id": "P001",
                "patient_name": "Juan Pérez López",
                "patient_nss": "4291-84-1029",
                "patient_gender": 1,  # 1 = Hombre
                "patient_age": 58,
                "patient_height_cm": 170.0,
                "patient_dry_weight_kg": 68.5,
                "patient_pre_weight_kg": 73.2,
                "uf_goal_liters": 4.7,  # Calculado de prueba
                "patient_access_type": "Fístula AV (FAV)",
                "patient_blood_type": "O+",
                "patient_dialyzer": "F8HPS (Polisulfona 1.8 m²)",
                "patient_diagnosis": "ERC Estadio 5 (Nefropatía Diabética)",
                "patient_physician": "Dr. A. Mendoza (Nefrología)",
                "patient_allergies": "Ninguna conocida",
            },
            {
                "patient_id": "P002",
                "patient_name": "María González Ramírez",
                "patient_nss": "1832-71-5504",
                "patient_gender": 2,  # 2 = Mujer
                "patient_age": 65,
                "patient_height_cm": 158.0,
                "patient_dry_weight_kg": 55.0,
                "patient_pre_weight_kg": 59.8,
                "uf_goal_liters": 4.8,
                "patient_access_type": "Catéter Perm-Cath",
                "patient_blood_type": "A+",
                "patient_dialyzer": "FX60 (Helixona 1.4 m²)",
                "patient_diagnosis": "ERC Estadio 5 (HAS)",
                "patient_physician": "Dr. A. Mendoza (Nefrología)",
                "patient_allergies": "Penicilina",
            },
            {
                "patient_id": "P003",
                "patient_name": "Carlos Ramírez Torres",
                "patient_nss": "6509-90-3312",
                "patient_gender": 1,
                "patient_age": 42,
                "patient_height_cm": 175.0,
                "patient_dry_weight_kg": 82.0,
                "patient_pre_weight_kg": 87.5,
                "uf_goal_liters": 5.5,
                "patient_access_type": "Fístula AV (FAV)",
                "patient_blood_type": "B+",
                "patient_dialyzer": "FX80 (Helixona 1.8 m²)",
                "patient_diagnosis": "ERC Estadio 5 (Glomerulonefritis)",
                "patient_physician": "Dra. L. Vargas (Nefrología)",
                "patient_allergies": "Ninguna conocida",
            }
        ]
        for p in test_patients:
            self.patients_db[p["patient_id"]] = p

    # def setup_ui(self):
    #     # 1. Layout principal de la pantalla, que contendrá el QScrollArea
    #     main_window_layout = QVBoxLayout(self)
    #     main_window_layout.setContentsMargins(0, 0, 0, 0)
    #     main_window_layout.setSpacing(0)

    #     # 2. Creamos el QScrollArea
    #     self.scroll_area = QScrollArea()
    #     self.scroll_area.setWidgetResizable(True)
        
    #     # 3. Creamos un QWidget contenedor para todo el contenido desplazable
    #     self.content_widget = QWidget()
    #     content_layout = QVBoxLayout(self.content_widget)
    #     content_layout.setContentsMargins(40, 24, 40, 24)
    #     content_layout.setSpacing(18)
        
    #     # Título
    #     self.lbl_title = QLabel("Expediente y Configuración Clínica del Paciente")
    #     self.lbl_title.setAlignment(Qt.AlignCenter)
    #     content_layout.addWidget(self.lbl_title)

    #     # Selector de paciente
    #     self.selector_group = QGroupBox("Seleccionar o registrar paciente")
    #     selector_layout = QVBoxLayout()
    #     selector_layout.setContentsMargins(20, 24, 20, 20)
    #     selector_layout.setSpacing(15)

    #     self.patient_list = QListWidget()
    #     self.patient_list.setMinimumHeight(180)
    #     self.patient_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    #     self._refresh_patient_list()
    #     self.patient_list.itemClicked.connect(self._load_selected_patient)
    #     selector_layout.addWidget(self.patient_list)

    #     btn_layout_selector = QHBoxLayout()
    #     btn_layout_selector.setSpacing(15)

    #     self.btn_new = QPushButton("Nuevo Paciente")
    #     self.btn_new.setFixedHeight(60)
    #     self.btn_new.clicked.connect(self._open_new_patient_dialog)
    #     btn_layout_selector.addWidget(self.btn_new)
    
    #     # === NUEVO BOTÓN ELIMINAR ===
    #     self.btn_delete = QPushButton("Eliminar Paciente")
    #     self.btn_delete.setFixedHeight(60)
    #     self.btn_delete.clicked.connect(self._delete_selected_patient)
    #     self.btn_delete.setEnabled(False)  # Solo se habilita cuando hay selección
    #     btn_layout_selector.addWidget(self.btn_delete)

    #     selector_layout.addLayout(btn_layout_selector)
    #     self.selector_group.setLayout(selector_layout)
    #     content_layout.addWidget(self.selector_group)

    #     # Formulario de datos del paciente
    #     self.form_group = QGroupBox("Datos Clínicos, Antropométricos y Prescripción Base")
    #     self.form_layout = QFormLayout()
    #     self.form_layout.setLabelAlignment(Qt.AlignRight)
    #     self.form_layout.setFormAlignment(Qt.AlignLeft)
    #     self.form_layout.setContentsMargins(20, 24, 20, 20)
    #     self.form_layout.setSpacing(12)

    #     self.fields = {}

    #     def add_field(label_text, key, default="", validator=None, input_mode='numeric'):
    #         label = QLabel(label_text)
    #         self._form_labels.append(label)
    #         if key == "gender":
    #             widget = QComboBox()
    #             widget.addItems(["", "Masculino (M)", "Femenino (F)"])
    #         elif key == "access_type":
    #             widget = QComboBox()
    #             widget.addItems([
    #                 "Fístula AV (FAV)",
    #                 "Catéter Perm-Cath",
    #                 "Catéter Temporal (Mahurkar)",
    #                 "Injerto Vascular (PTFE)",
    #             ])
    #         elif key == "blood_type":
    #             widget = QComboBox()
    #             widget.addItems(["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-", "No especificado"])
    #         else:
    #             widget = QLineEdit(default)
    #             if validator:
    #                 widget.setValidator(validator)
    #             widget.setReadOnly(True)

    #         self.form_layout.addRow(label, widget)
    #         self.fields[key] = widget

    #         # Conectar clic para abrir input táctil (excepto combos)
    #         if not isinstance(widget, QComboBox):
    #             widget.mousePressEvent = lambda e, k=key, w=widget, m=input_mode: \
    #                 self.open_touch_input(k, w, mode=m)

    #     add_field("ID Paciente:", "patient_id", input_mode='text')
    #     add_field("Nombre completo:", "patient_name", input_mode='text')
    #     add_field("N.S.S. / Registro:", "nss", input_mode='text')
    #     add_field("Género:", "gender")
    #     add_field("Edad (años):", "age", validator=QIntValidator(18, 100))
    #     add_field("Altura (cm):", "height_cm", validator=QDoubleValidator(100.0, 250.0, 1))
    #     add_field("Peso seco (kg):", "dry_weight_kg", validator=QDoubleValidator(30.0, 150.0, 1))
    #     add_field("Peso pre-diálisis (kg):", "pre_dialysis_weight_kg", validator=QDoubleValidator(30.0, 200.0, 1))
    #     add_field("Acceso Vascular:", "access_type")
    #     add_field("Grupo y Rh:", "blood_type")
    #     add_field("Filtro / Dializador:", "dialyzer", default="F8HPS (1.8 m²)", input_mode='text')
    #     add_field("Diagnóstico médico:", "diagnosis", default="ERC Estadio 5", input_mode='text')
    #     add_field("Médico Nefrólogo:", "physician", input_mode='text')
    #     add_field("Alergias:", "allergies", default="Ninguna conocida", input_mode='text')

    #     logger.debug("Campos del formulario creados: " + ", ".join(self.fields.keys()))
    #     self.form_group.setLayout(self.form_layout)
    #     self.form_group.hide() # Inicialmente oculto
    #     content_layout.addWidget(self.form_group)

    #     # Botón guardar y stretch al final
    #     btn_layout = QHBoxLayout()
    #     self.btn_save = QPushButton("Guardar y Seleccionar")
    #     self.btn_save.setFixedSize(320, 70)
    #     self.btn_save.clicked.connect(self._save_patient)
    #     self.btn_save.setEnabled(False) # Deshabilitado hasta que se seleccione/cree un paciente
    #     btn_layout.addStretch()
    #     btn_layout.addWidget(self.btn_save)
    #     content_layout.addLayout(btn_layout)
    #     content_layout.addStretch()

    #     self.scroll_area.setWidget(self.content_widget)
    #     main_window_layout.addWidget(self.scroll_area)

    #     self._apply_theme_styles()

    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 6, 12, 6)
        root.setSpacing(8)

        self.lbl_title = QLabel("Expediente y Configuración Clínica del Paciente")
        self.lbl_title.setAlignment(Qt.AlignCenter)
        root.addWidget(self.lbl_title)

        self.selector_group = QGroupBox("Seleccionar o registrar paciente")
        selector_layout = QVBoxLayout()
        selector_layout.setContentsMargins(12, 16, 12, 10)
        selector_layout.setSpacing(8)

        self.patient_list = QListWidget()
        self.patient_list.setFixedHeight(200)
        self.patient_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._refresh_patient_list()
        self.patient_list.itemClicked.connect(self._load_selected_patient)
        selector_layout.addWidget(self.patient_list)

        btn_layout_selector = QHBoxLayout()
        btn_layout_selector.setSpacing(12)
        self.btn_new = QPushButton("Nuevo Paciente")
        self.btn_new.setFixedSize(210,48)
        self.btn_new.clicked.connect(self._open_new_patient_dialog)
        self.btn_delete = QPushButton("Eliminar Paciente")
        self.btn_delete.setFixedSize(210,48)
        self.btn_delete.clicked.connect(self._delete_selected_patient)
        self.btn_delete.setEnabled(False)
        btn_layout_selector.addStretch()
        btn_layout_selector.addWidget(self.btn_new)
        btn_layout_selector.addWidget(self.btn_delete)
        
        selector_layout.addLayout(btn_layout_selector)
        self.selector_group.setLayout(selector_layout)
        root.addWidget(self.selector_group)

        self.form_group = QGroupBox("Datos Clínicos, Antropométricos y Prescripción Base")
        grid = QGridLayout()
        grid.setContentsMargins(12, 16, 12, 10)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        for col in range(4):
            grid.setColumnStretch(col, 1)

        self.fields = {}

        def make_field(label_text, key, default="", validator=None, input_mode="numeric"):
            label = QLabel(label_text)
            self._form_labels.append(label)
            if key == "gender":
                widget = QComboBox()
                widget.addItems(["", "Masculino (M)", "Femenino (F)"])
            elif key == "access_type":
                widget = QComboBox()
                widget.addItems([
                    "Fístula AV (FAV)",
                    "Catéter Perm-Cath",
                    "Catéter Temporal (Mahurkar)",
                    "Injerto Vascular (PTFE)",
                ])
            elif key == "blood_type":
                widget = QComboBox()
                widget.addItems(["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-", "No especificado"])
            else:
                widget = QLineEdit(default)
                if validator:
                    widget.setValidator(validator)
                widget.setReadOnly(True)
                widget.mousePressEvent = lambda e, k=key, w=widget, m=input_mode: self.open_touch_input(k, w, mode=m)
            widget.setFixedHeight(40)
            self.fields[key] = widget
            box = QWidget()
            row = QHBoxLayout(box)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            row.addWidget(label)
            row.addWidget(widget, 1)
            return box

        grid.addWidget(make_field("ID:", "patient_id", input_mode="text"), 0, 0)
        grid.addWidget(make_field("N.S.S.:", "nss", input_mode="text"), 0, 1)
        grid.addWidget(make_field("Género:", "gender"), 0, 2)
        grid.addWidget(make_field("Edad:", "age", validator=QIntValidator(18, 100)), 0, 3)

        grid.addWidget(make_field("Nombre:", "patient_name", input_mode="text"), 1, 0, 1, 2)
        grid.addWidget(make_field("Altura (cm):", "height_cm", validator=QDoubleValidator(100.0, 250.0, 1)), 1, 2)
        grid.addWidget(make_field("Peso seco (kg):", "dry_weight_kg", validator=QDoubleValidator(30.0, 150.0, 1)), 1, 3)

        grid.addWidget(make_field("Peso pre (kg):", "pre_dialysis_weight_kg", validator=QDoubleValidator(30.0, 200.0, 1)), 2, 0)
        grid.addWidget(make_field("Acceso:", "access_type"), 2, 1)
        grid.addWidget(make_field("Grupo:", "blood_type"), 2, 2)
        grid.addWidget(make_field("Filtro:", "dialyzer", default="F8HPS (1.8 m²)", input_mode="text"), 2, 3)

        grid.addWidget(make_field("Diagnóstico:", "diagnosis", default="ERC Estadio 5", input_mode="text"), 3, 0, 1, 2)
        grid.addWidget(make_field("Médico:", "physician", input_mode="text"), 3, 2, 1, 2)
        grid.addWidget(make_field("Alergias:", "allergies", default="Ninguna conocida", input_mode="text"), 4, 0, 1, 4)

        self.form_group.setLayout(grid)
        root.addWidget(self.form_group)

        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Guardar y Seleccionar")
        self.btn_save.setFixedSize(320, 52)
        self.btn_save.clicked.connect(self._save_patient)
        self.btn_save.setEnabled(False)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        btn_layout.addStretch()
        root.addLayout(btn_layout)
        root.addStretch()

        self._apply_theme_styles()
        self._clear_form()
        self._set_form_editable(False)
    
    def _on_theme_changed(self, _theme_name: str):
        self._apply_theme_styles()

    def _set_form_editable(self, enabled: bool):
        for widget in self.fields.values():
            widget.setEnabled(enabled)
        self.btn_save.setEnabled(enabled)

    def _clear_form(self):
        for widget in self.fields.values():
            if isinstance(widget, QComboBox):
                widget.setCurrentIndex(-1)
            else:
                widget.setText("")

    def _apply_theme_styles(self):
        t = ThemeManager.get_tokens()
        bg_primary = t.get("bg_primary", "#fcfcfc")
        bg_card = t.get("bg_card", "#ffffff")
        bg_alt = t.get("bg_card_alt", "#f1f5f9")
        bg_input = t.get("bg_input", "#fcfcfc")
        text_primary = t.get("text_primary", "#0f172a")
        text_secondary = t.get("text_secondary", "#334155")
        border = t.get("border", "#cbd5e1")
        accent = t.get("accent", "#2563eb")
        accent_soft = t.get("accent_soft", "#e0e7ff")

        self.setStyleSheet(f"background-color: {bg_primary}; border-radius: 15px;")   
        self.lbl_title.setStyleSheet(f"font-size: 34px; font-weight: 800; color: {text_primary};")

        group_style = f"""
            QGroupBox {{
                font-size: 24px;
                font-weight: bold;
                color: {text_primary};
                background-color: {bg_card};
                border: 2px solid {border};
                border-radius: 12px;
                margin-top: 18 px;
                padding-top: 18 px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 2px 14px;
                background-color: {accent_soft};
                color: {text_primary};
                border-radius: 6px;
            }}
            QLineEdit, QComboBox {{
                border: 1px solid {border};
                border-radius: 8px;
                padding: 8px;
                background-color: {bg_input};
                color: {text_primary};
                font-size: 22px;
            }}
        """
        self.selector_group.setStyleSheet(group_style)
        self.form_group.setStyleSheet(group_style)

        self.patient_list.setStyleSheet(f"""
            QListWidget {{
                color: {text_primary};
                font-size: 22px;
                padding: 6px;
                border-radius: 8px;
                background-color: {bg_input};
                border: 1px solid {border};
            }}
            QListWidget::item:selected {{
                background-color: {accent};
                color: #ffffff;
                border-radius: 6px;
            }}
        """)

        for lbl in self._form_labels:
            lbl.setStyleSheet(f"font-size: 22px; color: {text_secondary}; font-weight: 600;")

        for w in self.fields.values():
            w.setStyleSheet(f"QLineEdit, QComboBox {{ font-size: 18px; padding: 4px; color: {text_primary}; "
                            f"background-color: {bg_input}; border: 1px solid {border}; border-radius: 8px; }}"
                            "QLineEdit:disabled, QComboBox:disabled {"
                            "background-color: #e2e8f0; color: #94a3b8; }")

        self.btn_new.setStyleSheet("""
            QPushButton {
                font-size: 24px;
                font-weight: bold;
                background: #10b981;
                color: white;
                border-radius: 10px;
                padding: 5px;
            }
            QPushButton:hover { background: #059669; }
            QPushButton:pressed { background: #047857; }
        """)
        self.btn_delete.setStyleSheet("""
            QPushButton {
                font-size: 24px;
                font-weight: bold;
                background: #dc2626;
                color: white;
                border-radius: 10px;
                padding: 5px;
            }
            QPushButton:hover { background: #b91c1c; }
            QPushButton:pressed { background: #991b1b; }
            QPushButton:disabled { background: #64748b; color: #cbd5e1; }
        """)
        self.btn_save.setStyleSheet(f"""
            QPushButton {{
                font-size: 24px;
                background: {accent};
                color: white;
                font-weight: bold;
                border-radius: 10px;
                padding: 5px;
            }}
            QPushButton:hover {{ background: {t.get('btn_primary_hover', '#2563eb')}; }}
            QPushButton:disabled {{ background: #94a3b8; }}
        """)

    def open_touch_input(self, field_key: str, input_widget, mode: str = 'numeric'):
        """
        Abre el diálogo táctil adecuado según el modo.
        Actualiza widget y current_values al aceptar.

        """
        current_text = input_widget.text().strip() if hasattr(input_widget, 'text') else ""

        title_map = {
            "patient_id": "ID del paciente",
            "patient_name": "Nombre completo",
            "nss": "N.S.S. / Registro Médico",
            "age": "Edad (años)",
            "height_cm": "Altura en cm",
            "dry_weight_kg": "Peso seco (kg)",
            "pre_dialysis_weight_kg": "Peso actual pre-diálisis (kg)",
            "dialyzer": "Filtro / Dializador",
            "diagnosis": "Diagnóstico Médico",
            "physician": "Médico Nefrólogo Tratante",
            "allergies": "Alergias Conocidas",
        }
        title = title_map.get(field_key, "Ingrese valor")

        if mode == 'numeric':
            dialog = NumpadDialog(self,  title=title)
        else: # mode == 'text'
            dialog = KeyboardDialog(self, initial_text=current_text, title=title)

        if dialog.exec(): # Si el usuario presiona "ACEPTAR"
            new_raw_value = dialog.get_value() # Esto puede ser float o str
            
            # --- Convertir a string para la validación y visualización en QLineEdit ---
            new_value_as_str = str(new_raw_value) 
            
            # Aplicar validación del QLineEdit
            validator = input_widget.validator()
            if validator:
                # El validate() espera una string, no un float
                state, _, _ = validator.validate(new_value_as_str, 0) 
                
                # Queremos que sea Acceptable, no solo Intermediate (que podría ser un '.' o un '-')
                if state == QDoubleValidator.Acceptable or state == QIntValidator.Acceptable:
                    input_widget.setText(new_value_as_str) # Actualiza el QLineEdit con la string válida
                else:
                    
                    self.show_info_message(f"El valor '{new_value_as_str}' no es válido para este campo o está incompleto.", 2000)
                    
                    return # No actualizar si la validación falla
            else: # No hay validador, aceptar el texto directamente
                input_widget.setText(new_value_as_str) # Asegurarse de que sea string para QLineEdit

        
            patient_key = field_key if field_key.startswith("patient_") else f"patient_{field_key}"
            if mode == 'numeric':
                try:
                    # Usamos el texto del widget, que ya está validado, y lo convertimos a float
                    self.current_values[patient_key] = float(input_widget.text()) 
                except ValueError:
                    # Esto debería ser raro si el validador ya pasó
                    self.current_values[patient_key] = 0.0 
            else:
                self.current_values[patient_key] = input_widget.text().strip()

            print(f"[PatientConfig] {patient_key} → {self.current_values.get(patient_key)}")


    def _delete_selected_patient(self):
        """Elimina el paciente seleccionado con confirmación"""
        current_item = self.patient_list.currentItem()
        if not current_item:
            self.show_warning_message("Seleccione un paciente para eliminar.", 2000)
            return

        pid = current_item.text().split(" - ")[0]
        patient_name = self.patients_db.get(pid, {}).get("patient_name", pid)

      
        message=f"""¿Estás seguro de eliminar al paciente?\n\n 
                    ID: {pid}\n
                    Nombre: {patient_name}\n\n
                    Esta acción no se puede deshacer."""
    
        

        if self._confirm_message(message, "Sí, Eliminar", "Cancelar"):
            if pid in self.patients_db:
                del self.patients_db[pid]
                self._save_patients_to_file()   # Guardar cambios en JSON
                self._refresh_patient_list()

                # Limpiar formulario
                self._clear_form()
                self._set_form_editable(False)
                self.btn_delete.setEnabled(False)
                self.btn_save.setEnabled(False)

                self.show_success_message(f"Paciente {pid} eliminado correctamente.", 2000)
                logger.info(f"Paciente eliminado: {pid} - {patient_name}")
            else:
                self.show_error_message("Error: Paciente no encontrado.", 2000)            
    
    def _confirm_message(self, message: str, accept_text: str, cancel_text: str) -> bool:
        """Muestra un mensaje de confirmación flotante y devuelve True si se acepta."""
        dialog = FloatingConfirmDialog(self)
        return dialog.show_confirm(message, accept_text=accept_text, cancel_text=cancel_text)

    def _refresh_patient_list(self):
        self.patient_list.clear()
        for pid, data in self.patients_db.items():
            access = data.get("patient_access_type", "")
            suffix = f" ({access})" if access else ""
            self.patient_list.addItem(f"{pid} - {data.get('patient_name', 'Sin nombre')}{suffix}")

    def _load_selected_patient(self, item):
        pid = item.text().split(" - ")[0]
        patient = self.patients_db.get(pid)
        if patient:
            self._populate_form(patient)
            # self.form_group.show()
            self._set_form_editable(True)
            self.btn_delete.setEnabled(True)
            self.btn_save.setEnabled(True)
            

    def _open_new_patient_dialog(self):

        dialog = KeyboardDialog(self, title="Ingrese ID del nuevo paciente")
        if dialog.exec():
            pid = dialog.get_value().strip().upper()
            if not pid:                
                self.show_warning_message("Intento de crear paciente con ID vacío.")
                return
            if pid in self.patients_db:
                
                self.show_warning_message(f"El ID '{pid}' ya existe.", 2000)
                return

            new_patient = {
                "patient_id": pid,
                "patient_name": "",
                "patient_nss": "",
                "patient_gender": 0,
                "patient_age": 0,
                "patient_height_cm": 0.0,
                "patient_dry_weight_kg": 0.0,
                "patient_pre_weight_kg": 0.0,
                "uf_goal_liters": 0.0,
                "patient_access_type": "Fístula AV (FAV)",
                "patient_blood_type": "O+",
                "patient_dialyzer": "F8HPS (1.8 m²)",
                "patient_diagnosis": "ERC Estadio 5",
                "patient_physician": "",
                "patient_allergies": "Ninguna conocida",
            }
            self.patients_db[pid] = new_patient
            self._refresh_patient_list()

            # Seleccionar automáticamente
            for i in range(self.patient_list.count()):
                if self.patient_list.item(i).text().startswith(pid):
                    self.patient_list.setCurrentRow(i)
                    self._load_selected_patient(self.patient_list.item(i))
                    break

    def _populate_form(self, patient):
        for key, widget in self.fields.items():
            if key == "gender":
                idx = 0
                g = patient.get("patient_gender", 0)  # clave real en la DB
                if g == 1: idx = 1
                elif g == 2: idx = 2
                widget.setCurrentIndex(idx)
            elif key == "access_type":
                val = patient.get("patient_access_type", "Fístula AV (FAV)")
                idx = widget.findText(val)
                widget.setCurrentIndex(idx if idx >= 0 else 0)
            elif key == "blood_type":
                val = patient.get("patient_blood_type", "O+")
                idx = widget.findText(val)
                widget.setCurrentIndex(idx if idx >= 0 else 0)
            else:
                # Usamos la clave real que está en el diccionario patient
                real_key = {
                    "patient_id": "patient_id",
                    "patient_name": "patient_name",
                    "nss": "patient_nss",
                    "age": "patient_age",
                    "height_cm": "patient_height_cm",
                    "dry_weight_kg": "patient_dry_weight_kg",
                    "pre_dialysis_weight_kg": "patient_pre_weight_kg",
                    "dialyzer": "patient_dialyzer",
                    "diagnosis": "patient_diagnosis",
                    "physician": "patient_physician",
                    "allergies": "patient_allergies",
                }.get(key, key)  # fallback

                value = patient.get(real_key)
                widget.setText(str(value) if value is not None else "")

    def _save_patient(self):
        data = {}              
        # Mapeo de campos del formulario a claves del mapa VARIABLES (0x08) y metadatos clínicos
        field_to_tag = {
            "patient_id": "patient_id",
            "patient_name": "patient_name",
            "nss": "patient_nss",
            "gender": "patient_gender",
            "age": "patient_age",
            "height_cm": "patient_height_cm",
            "dry_weight_kg": "patient_dry_weight_kg",
            "pre_dialysis_weight_kg": "patient_pre_weight_kg",
            "access_type": "patient_access_type",
            "blood_type": "patient_blood_type",
            "dialyzer": "patient_dialyzer",
            "diagnosis": "patient_diagnosis",
            "physician": "patient_physician",
            "allergies": "patient_allergies",
        }

        for field_key, widget in self.fields.items():
            tag = field_to_tag.get(field_key)
            if not tag:
                continue  # Ignorar si no está mapeado

            if field_key == "gender":
                text = widget.currentText()
                data[tag] = 1 if "Masculino" in text else 2 if "Femenino" in text else 0
            elif isinstance(widget, QComboBox):
                data[tag] = widget.currentText().strip()
            else:
                text = widget.text().strip()
                if field_key == "age":
                    try:
                        data[tag] = int(text)
                    except ValueError:
                        data[tag] = 0
                elif field_key in ["height_cm", "dry_weight_kg", "pre_dialysis_weight_kg"]:
                    try:
                        data[tag] = float(text)
                    except ValueError:
                        data[tag] = 0.0
                else:
                    data[tag] = text

        # Validaciones
        if not data.get("patient_id"):
            
            self.show_warning_message("ID del paciente es obligatorio.", 2000)
            return
        if not data.get("patient_name"):
            self.show_warning_message("El nombre es obligatorio.", 2000)
            return
        if data.get("patient_gender") not in [1, 2]:
            self.show_warning_message("Seleccione el género.", 2000)
            return

        # Validaciones de rango usando el mapa
        patient_map = VARIABLES.get(0x08, {})
        for var in patient_map.values():
            tag = var["tag"]
            if tag in data:
                limites = var.get("limites")
                if limites and isinstance(limites, tuple):
                    min_val, max_val = limites
                    value = data[tag]
                    if isinstance(value, (int, float)) and not (min_val <= value <= max_val):
                        self.show_warning_message(f"{var['label']} debe estar entre {min_val} y {max_val} {var['unit']}.", 2000)

        # Calcular UF goal
        pre_weight = data.get("patient_pre_weight_kg", 0.0)  # nota: clave corregida
        dry_weight = data.get("patient_dry_weight_kg", 0.0)
        uf_goal = max(0.0, pre_weight - dry_weight)
        data["uf_goal_liters"] = round(uf_goal, 2)

        # Guardar en DB
        self.patients_db[data["patient_id"]] = data
        
        self._save_patients_to_file()

        # Guardar en current_values (claves exactas del mapa + metadatos clínicos para reporte)
        for tag in [
            "patient_id", "patient_name", "patient_nss", "patient_gender", "patient_age",
            "patient_height_cm", "patient_dry_weight_kg", "patient_pre_weight_kg",
            "uf_goal_liters", "patient_access_type", "patient_blood_type",
            "patient_dialyzer", "patient_diagnosis", "patient_physician", "patient_allergies"
        ]:
            if tag in data:
                self.current_values[tag] = data[tag]
                print(f"[SAVE] Guardado {tag} = {data[tag]}")  # Debug

        self._refresh_patient_list()
        
        self.show_success_message(f"Paciente '{data.get('patient_name', '—')}' guardado. UF Goal: {data['uf_goal_liters']:.2f} L", 2000)


        if hasattr(self.parent_window, 'dialysis_screen'):
            self.parent_window.dialysis_screen.update_values(self.current_values)

    def _map_gender_to_int(self, value):
        """Convierte strings comunes de género a 1/2"""
        if isinstance(value, (int, float)):
            v = int(value)
            return v if v in (1, 2) else 0

        v = str(value).strip().upper()
        if v in ("M", "MASCULINO", "HOMBRE", "1"):
            return 1
        if v in ("F", "FEMENINO", "MUJER", "2"):
            return 2
        return 0
    
    def _queue_patient_writes_if_needed(self):
        """Ejemplo: preparar writes Modbus para campos rw=True"""
        writes = []

        if "patient_id" in self.values and self.values["patient_id"] != self.patient["id"]:
            writes.append((0x08, 0x00, self.patient["id"]))         

        if "patient_name" in self.values and self.values["patient_name"] != self.patient["name"]:
            writes.append((0x08, 0x01, self.patient["name"]))

        # Género: ya es int 1/2
        if self.patient["gender"] != 0:
            writes.append((0x08, 0x02, self.patient["gender"]))

        # UF goal 
        if abs(self.patient["uf_goal_liters"] - self.values.get("uf_goal_liters", 0.0)) > 0.01:
            writes.append((0x08, 0x07, self.patient["uf_goal_liters"]))

        if writes:
            print("[INFO] Pendientes de escritura a máquina:", writes)

    def show_floating_message(self, text: str, timeout_ms: int = 3800):
        """Método genérico (recomendado)"""
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        
        self._floating_msg.show_floating_message(text, timeout_ms)

    # Métodos específicos (más semánticos)
    def show_success_message(self, text: str, timeout_ms: int = 2000):
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        self._floating_msg.show_success_message(text, timeout_ms)

    def show_info_message(self, text: str, timeout_ms: int = 2000):
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        self._floating_msg.show_info_message(text, timeout_ms)

    def show_warning_message(self, text: str, timeout_ms: int = 2000):
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        self._floating_msg.show_warning_message(text, timeout_ms)

    def show_error_message(self, text: str, timeout_ms: int = 3000):
        if not hasattr(self, '_floating_msg') or self._floating_msg is None:
            self._floating_msg = FloatingMessage(self)
        self._floating_msg.show_error_message(text, timeout_ms)
