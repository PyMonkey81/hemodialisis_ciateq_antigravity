# tests/test_themes_and_clinical_reports.py
"""
Pruebas unitarias e integración para:
1. Sistema de Temas Dinámicos (ThemeManager + ThemeConfigScreen + OptionsScreen)
2. Rastreador Clínico de Sesión (TherapySessionTracker)
3. Generador de Reportes Clínicos Nefrológicos y Hoja de Enfermería (PDF + JSON + CSV)
4. Pantalla de Historial y Visor de Reportes (HistoryScreen + TherapyReportViewerDialog)
"""

import sys
import pytest
from PySide6.QtWidgets import QApplication

from gui.theme_manager import ThemeManager
from gui.service.theme_config_screen import ThemeConfigScreen
from gui.service.options_screen import OptionsScreen
from gui.service.history_screen import HistoryScreen, TherapyReportViewerDialog
from core.therapy_session_tracker import TherapySessionTracker
from core.nibp_pressure_history import NibpPressureHistory
from utilities.therapy_report_generator import TherapyReportGenerator


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_theme_manager_switching_and_tokens(qapp):
    tm = ThemeManager.instance(qapp)
    available = tm.get_available_themes()
    assert len(available) >= 4
    for theme_name in ThemeManager.THEME_TOKENS.keys():
        tm.apply_theme(theme_name, persist=False)
        assert tm.current_theme_name == theme_name
        tokens = ThemeManager.get_tokens()
        assert "bg_primary" in tokens
        assert "bg_main" in tokens
        assert "bg_card" in tokens
        assert "accent" in tokens

    # Probar alias de retrocompatibilidad
    tm.apply_theme("dark", persist=False)
    assert tm.current_theme_name == "Modo Oscuro UCI"
    tm.apply_theme("light", persist=False)
    assert tm.current_theme_name == "Clínico Claro"


def test_theme_config_and_options_screens(qapp):
    tm = ThemeManager.instance(qapp)
    screen = ThemeConfigScreen()
    assert len(screen.theme_cards) == len(ThemeManager.THEME_TOKENS)

    opt = OptionsScreen()
    assert hasattr(opt, "theme_combo")
    assert opt.theme_combo.count() == len(ThemeManager.THEME_TOKENS)

    # Cambiar tema y verificar que ambas pantallas reaccionan sin excepción
    tm.apply_theme("Azul Biomédico", persist=False)
    tm.apply_theme("Alto Contraste", persist=False)
    tm.apply_theme("Clínico Claro", persist=False)


def test_session_tracker_and_report_bundle(qapp, tmp_path):
    values = {
        "patient_id": "P001",
        "patient_name": "Juan Pérez López",
        "patient_nss": "4291-84-1029",
        "patient_gender": 1,
        "patient_age": 58,
        "patient_height_cm": 170.0,
        "patient_dry_weight_kg": 68.5,
        "patient_pre_weight_kg": 72.0,
        "uf_goal_liters": 3.5,
        "patient_access_type": "Fístula AV (FAV)",
        "patient_blood_type": "O+",
        "patient_dialyzer": "F8HPS (1.8 m²)",
        "patient_diagnosis": "ERC Estadio 5",
        "patient_physician": "Dr. A. Mendoza",
        "treatmentModeSelection": 1,
        "bloodFlowSensor": 300.0,
        "bloodFlowControlSetPoint": 300.0,
        "balanceChamberSetTiming": 20.0,
        "arterialPressureSensor": -145.0,
        "venousPressureSensor": 135.0,
        "TMPValue": 95.0,
        "dialyTempSensor": 36.6,
        "dialyCondSensor": 13.9,
        "ultraFilterPumpSpeed": 14.5,  # mL/min (~0.87 L/h)
        "heparineInfusionEnabled": 1.0,
        "heparineBolusQuantity": 2.0,
        "heparineTherapyFlow": 1.0,
        "heparineCurrentDosage": 3.5,
        "ktv_current": 1.34,
    }

    tracker = TherapySessionTracker()
    tracker.start_session(values)
    tracker.update_spo2(97)

    # Simular 60 minutos (3600 s) en pasos de 20s (para respetar límite de dt_s <= 30s)
    for step_s in range(20, 3601, 20):
        tracker.on_therapy_tick(values, elapsed_s=float(step_s), uf_removed_liters=(step_s / 3600.0) * 0.85)

    nibp_hist = NibpPressureHistory()
    nibp_hist.add_measurement(sys=135, dia=82, map_mmhg=100, hr=76, elapsed_s=60.0, spo2=97, origen="auto")
    tracker.on_nibp_measurement(
        sys_mmhg=135, dia_mmhg=82, map_mmhg=100, hr_bpm=76,
        origen="auto", current_values=values, elapsed_s=60.0, uf_removed_liters=0.05
    )

    nibp_hist.add_measurement(sys=124, dia=78, map_mmhg=93, hr=74, elapsed_s=3500.0, spo2=98, origen="manual")
    tracker.update_spo2(98)
    tracker.on_nibp_measurement(
        sys_mmhg=124, dia_mmhg=78, map_mmhg=93, hr_bpm=74,
        origen="manual", current_values=values, elapsed_s=3500.0, uf_removed_liters=0.82
    )

    tracker.record_alarm("Presión Venosa Alta (195.0)", elapsed_s=1200.0, severity="amarillo")
    tracker.finish_session(values, elapsed_s=3600.0, uf_removed_liters=0.85)

    # 300 mL/min * 60 min = 18.0 L de sangre procesada
    assert 17.5 <= tracker.blood_processed_liters <= 18.5
    assert len(tracker.snapshots) >= 5

    ktv_hist = [
        {"timestamp": "10:15:00", "ktv": 0.42, "ureica": 110.0},
        {"timestamp": "11:00:00", "ktv": 1.34, "ureica": 42.0},
    ]

    report = TherapyReportGenerator.build_session_report(
        current_values=values,
        tracker=tracker,
        nibp_history=nibp_hist,
        ktv_history=ktv_hist,
        elapsed_seconds=3600.0,
        uf_removed_liters=0.85,
        uf_profile_name="Lineal (Descendente)",
        na_profile_name="Escalón (14.2 -> 13.8)",
        completion_status="Completada",
    )

    assert report["patient"]["name"] == "Juan Pérez López"
    assert report["patient"]["nss"] == "4291-84-1029"
    assert report["adequacy"]["ktv_final"] == 1.34
    assert report["adequacy"]["ktv_target_met"] is True
    assert report["adequacy"]["blood_processed_liters"] >= 17.5
    assert len(report["monitoring_snapshots"]) >= 5

    html = TherapyReportGenerator.render_html_report(report)
    assert "TENSIÓN ARTERIAL (mmHg)" in html
    assert "SANGRE PROCESADA (L)" in html
    assert "Juan Pérez López" in html

    pdf_file = tmp_path / "test_report.pdf"
    csv_file = tmp_path / "test_report.csv"
    TherapyReportGenerator.export_pdf(report, pdf_file)
    TherapyReportGenerator.export_csv(report, csv_file)

    assert pdf_file.exists() and pdf_file.stat().st_size > 1500
    assert csv_file.exists() and csv_file.stat().st_size > 200

    # Probar HistoryScreen y visor
    hist_screen = HistoryScreen()
    hist_screen.treatments = [{
        "fecha": report["session_date"],
        "hora_inicio": report["start_time"],
        "hora_fin": report["end_time"],
        "paciente": report["patient"]["name"],
        "tipo_tratamiento": report["prescription"]["modality"],
        "duracion_minutos": 60,
        "duracion_hhmm": "01:00",
        "uf_lograda_l": 0.85,
        "ktv_final": 1.34,
        "pa_final": report["hemodynamics"]["pa_final"],
        "report_data": report,
    }]
    hist_screen.update_table()
    assert hist_screen.table.rowCount() == 1

    viewer = TherapyReportViewerDialog(report)
    assert "Juan Pérez López" in viewer.browser.toPlainText()
