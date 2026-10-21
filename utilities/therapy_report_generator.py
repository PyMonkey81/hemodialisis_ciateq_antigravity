# utilities/therapy_report_generator.py
"""
Generador de Reportes Clínicos de Terapia de Hemodiálisis (PDF + JSON + CSV).
Diseñado conforme a la Hoja de Registros Clínicos e Intervenciones de Enfermería y
Reporte Nefrológico de Adecuación Dialítica (IMSS / CIATEQ).
"""

from __future__ import annotations

import csv
import json
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QPdfWriter, QPageSize, QPageLayout, QTextDocument

from core.therapy_session_tracker import TherapySessionTracker, MODALITY_NAMES
from logic.heitmann import heitmann
from logic.calculos import convertir_ciclos_a_flujo


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)


def _gender_label(val: Any) -> str:
    if val in (1, "1", "M", "Masculino"):
        return "Masculino (M)"
    if val in (2, "2", "F", "Femenino"):
        return "Femenino (F)"
    return "No especificado"


def _estimate_urr_from_ktv(ktv: float) -> float:
    """
    Estima el Porcentaje de Reducción de Urea (URR %) a partir de spKt/V (relación de Daugirdas):
    Kt/V ≈ -ln(1 - URR) => URR ≈ (1 - exp(-Kt/V)) * 100
    """
    if ktv is None or ktv <= 0:
        return 0.0
    urr = (1.0 - math.exp(-float(ktv) * 0.85)) * 100.0
    return round(min(99.0, max(0.0, urr)), 1)


class TherapyReportGenerator:
    """
    Construye, respalda (JSON/CSV) y exporta a PDF el reporte clínico integral de una sesión.
    """

    @staticmethod
    def get_reports_backup_dir() -> Path:
        d = get_project_root() / "logs" / "reportes_terapia"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def get_pdf_export_dir() -> Path:
        d = get_project_root() / "exports" / "reportes_pdf"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @classmethod
    def build_session_report(
        cls,
        current_values: Dict[str, Any],
        tracker: Optional[TherapySessionTracker] = None,
        nibp_history: Any = None,
        ktv_history: Optional[List[Dict[str, Any]]] = None,
        elapsed_seconds: float = 0.0,
        uf_removed_liters: float = 0.0,
        uf_profile_name: str = "Lineal (Sin perfil)",
        na_profile_name: str = "Constante (Sin perfil)",
        completion_status: str = "Completada",
        start_time_str: Optional[str] = None,
        end_time_str: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = datetime.now()
        report_id = (
            tracker.session_id
            if (tracker and tracker.session_id)
            else now.strftime("%Y%m%d_%H%M%S")
        )

        # 1. Datos de Paciente y Pesos
        patient_id = str(current_values.get("patient_id") or "S/ID")
        patient_name = str(current_values.get("patient_name") or "Paciente No Registrado")
        patient_nss = str(current_values.get("patient_nss") or "—")
        gender_code = int(current_values.get("patient_gender", 0) or 0)
        age = int(current_values.get("patient_age", 0) or 0)
        height_cm = float(current_values.get("patient_height_cm", 0.0) or 0.0)
        dry_weight_kg = float(current_values.get("patient_dry_weight_kg", 0.0) or 0.0)
        pre_weight_kg = float(current_values.get("patient_pre_weight_kg", 0.0) or 0.0)
        uf_goal_l = float(current_values.get("uf_goal_liters", 0.0) or 0.0)
        if uf_goal_l <= 0.0 and pre_weight_kg > dry_weight_kg > 0:
            uf_goal_l = round(pre_weight_kg - dry_weight_kg, 2)

        uf_achieved_l = round(max(0.0, float(uf_removed_liters or 0.0)), 3)
        estimated_post_weight = (
            round(max(0.0, pre_weight_kg - uf_achieved_l), 2)
            if pre_weight_kg > 0
            else 0.0
        )
        weight_gain = (
            round(max(0.0, pre_weight_kg - dry_weight_kg), 2)
            if (pre_weight_kg > 0 and dry_weight_kg > 0)
            else 0.0
        )

        # Volumen de distribución de urea V (Heitmann / Watson)
        sex_heitmann = 1 if gender_code == 1 else 0
        heitmann_v = float(current_values.get("bioz_tbw_liters", 0.0) or 0.0)
        if heitmann_v <= 0.0 and dry_weight_kg > 20 and height_cm > 80 and age > 10:
            try:
                z_ohm = float(current_values.get("bioz_resistance", 500.0) or 500.0)
                v_calc = heitmann(Z=z_ohm, H=height_cm, W=dry_weight_kg, G=sex_heitmann, E=age)
                heitmann_v = round(float(v_calc or 0.0), 2)
            except Exception:
                heitmann_v = round(dry_weight_kg * (0.58 if sex_heitmann == 1 else 0.52), 2)

        # 2. Modalidad y Tiempos
        mode_code = int(current_values.get("treatmentModeSelection", 1) or 1)
        modality_str = MODALITY_NAMES.get(mode_code, "Hemodiálisis (HD)")

        prog_h = int(current_values.get("heparineTherapyHours", 4) or 4)
        prog_m = int(current_values.get("heparineTherapyMinutes", 0) or 0)
        prog_total_min = prog_h * 60 + prog_m
        prog_str = f"{prog_h:02d}:{prog_m:02d} h ({prog_total_min} min)"

        eff_min = int(round(max(0.0, elapsed_seconds) / 60.0))
        eff_h = eff_min // 60
        eff_rem_m = eff_min % 60
        eff_str = f"{eff_h:02d}:{eff_rem_m:02d} h ({eff_min} min)"

        if not start_time_str:
            if tracker and tracker.start_dt:
                start_time_str = tracker.start_dt.strftime("%H:%M:%S")
            else:
                start_time_str = now.strftime("%H:%M:%S")
        if not end_time_str:
            end_time_str = now.strftime("%H:%M:%S")

        # 3. Prescripción y Heparina
        qb_set = float(current_values.get("bloodFlowControlSetPoint", 300.0) or 300.0)
        cycles = float(current_values.get("balanceChamberSetTiming", 0.0) or 0.0)
        try:
            qd_set = float(convertir_ciclos_a_flujo(cycles)) if cycles > 0 else 500.0
        except Exception:
            qd_set = 500.0
        temp_set = float(current_values.get("dialyTempControlSetPoint", 36.5) or 36.5)
        cond_set = float(current_values.get("dialyCondControlSetPoint", 13.8) or 13.8)

        hep_enabled = bool(current_values.get("heparineInfusionEnabled", 1.0))
        hep_bolus_ml = float(current_values.get("heparineBolusQuantity", 0.0) or 0.0)
        hep_flow_ml_h = float(current_values.get("heparineTherapyFlow", 1.0) or 1.0)
        hep_dosage_ml = float(
            current_values.get("heparineCurrentDosage")
            or current_values.get("heparineTherapyDosage")
            or 0.0
        )
        hep_total_ml = round((hep_bolus_ml + hep_dosage_ml) if hep_enabled else 0.0, 2)

        uf_pct = round((uf_achieved_l / uf_goal_l) * 100.0, 1) if uf_goal_l > 0 else 100.0

        # 4. Adecuación Dialítica (Kt/V y Sangre Procesada)
        ktv_list = list(ktv_history or [])
        ktv_initial = 0.0
        ktv_final = float(current_values.get("ktv_current", 0.0) or 0.0)
        if ktv_list:
            ktv_initial = float(ktv_list[0].get("ktv", 0.0) or 0.0)
            ktv_final = float(ktv_list[-1].get("ktv", ktv_final) or ktv_final)
        urr_pct = _estimate_urr_from_ktv(ktv_final)

        blood_processed_l = (
            round(tracker.blood_processed_liters, 2)
            if tracker and tracker.blood_processed_liters > 0
            else round((qb_set * eff_min) / 1000.0, 2)
        )

        # 5. Tomas de Baumanómetro (NIBP) y SpO2
        nibp_rows: List[Dict[str, Any]] = []
        if nibp_history and hasattr(nibp_history, "get_all_measurements"):
            for m in nibp_history.get_all_measurements():
                if m.elapsed_s is not None:
                    mm = int(m.elapsed_s // 60)
                    ss = int(m.elapsed_s % 60)
                    t_label = f"{mm:02d}:{ss:02d}"
                else:
                    t_label = "Pre-HD"
                nibp_rows.append({
                    "n": m.n,
                    "tiempo_terapia": t_label,
                    "elapsed_s": m.elapsed_s,
                    "sys": m.sys,
                    "dia": m.dia,
                    "map": m.map_mmhg,
                    "hr": m.hr,
                    "spo2": m.spo2,
                    "origen": m.origen,
                })

        pa_initial = "—"
        pa_final = "—"
        sys_vals = [r["sys"] for r in nibp_rows if r.get("sys") is not None]
        dia_vals = [r["dia"] for r in nibp_rows if r.get("dia") is not None]
        hr_vals = [r["hr"] for r in nibp_rows if r.get("hr") is not None]
        spo2_vals = [r["spo2"] for r in nibp_rows if r.get("spo2") is not None]

        if nibp_rows:
            first_r = nibp_rows[0]
            last_r = nibp_rows[-1]
            pa_initial = f"{first_r['sys']}/{first_r['dia']} mmHg (PAM {first_r['map']}, FC {first_r['hr']})"
            pa_final = f"{last_r['sys']}/{last_r['dia']} mmHg (PAM {last_r['map']}, FC {last_r['hr']})"

        hypotension_episodes = sum(1 for s in sys_vals if s < 90)

        # 6. Estadísticas de Máquina y Snapshots Horarios (Hoja de Enfermería IMSS)
        machine_stats = {}
        snapshots_list = []
        alarm_events = []
        if tracker:
            machine_stats = {k: v.to_dict() for k, v in tracker.stats.items()}
            snapshots_list = [s.to_dict() for s in tracker.snapshots]
            alarm_events = list(tracker.alarm_events)

        # Si no hay snapshots en tracker pero sí tomas NIBP, construir columnas desde NIBP
        if not snapshots_list and nibp_rows:
            for idx, r in enumerate(nibp_rows, start=1):
                snapshots_list.append({
                    "index": idx,
                    "horario": r["tiempo_terapia"],
                    "elapsed_min": round((r["elapsed_s"] or 0.0) / 60.0, 1),
                    "origen": f"NIBP ({r['origen']})",
                    "ta_str": f"{r['sys']}/{r['dia']}",
                    "sys": r["sys"],
                    "dia": r["dia"],
                    "map_mmhg": r["map"],
                    "hr": r["hr"],
                    "spo2": r["spo2"],
                    "temp_corporal_c": round(temp_set, 1),
                    "qb_ml_min": round(qb_set, 1),
                    "qd_ml_min": round(qd_set, 1),
                    "pv_mmhg": round(float(current_values.get("venousPressureSensor", 0.0) or 0.0), 1),
                    "pa_mmhg": round(float(current_values.get("arterialPressureSensor", 0.0) or 0.0), 1),
                    "temp_dial_c": round(temp_set, 1),
                    "cond_ms_cm": round(cond_set, 2),
                    "ptm_mmhg": round(float(current_values.get("TMPValue", 0.0) or 0.0), 1),
                    "uf_rate_l_h": round(uf_goal_l / max(1.0, prog_total_min / 60.0), 2),
                    "uf_removed_l": uf_achieved_l,
                    "blood_processed_l": blood_processed_l,
                })

        # Asegurar al menos una columna de resumen si fue sesión rápida de prueba
        if not snapshots_list:
            snapshots_list.append({
                "index": 1,
                "horario": end_time_str[:5],
                "elapsed_min": float(eff_min),
                "origen": "Resumen",
                "ta_str": "—",
                "sys": None,
                "dia": None,
                "map_mmhg": None,
                "hr": None,
                "spo2": tracker.last_spo2 if tracker else None,
                "temp_corporal_c": round(temp_set, 1),
                "qb_ml_min": round(qb_set, 1),
                "qd_ml_min": round(qd_set, 1),
                "pv_mmhg": round(float(current_values.get("venousPressureSensor", 0.0) or 0.0), 1),
                "pa_mmhg": round(float(current_values.get("arterialPressureSensor", 0.0) or 0.0), 1),
                "temp_dial_c": round(temp_set, 1),
                "cond_ms_cm": round(cond_set, 2),
                "ptm_mmhg": round(float(current_values.get("TMPValue", 0.0) or 0.0), 1),
                "uf_rate_l_h": round(uf_goal_l / max(1.0, prog_total_min / 60.0), 2),
                "uf_removed_l": uf_achieved_l,
                "blood_processed_l": blood_processed_l,
            })

        spo2_avg = (
            round(sum(spo2_vals) / len(spo2_vals), 1)
            if spo2_vals
            else (machine_stats.get("spo2", {}).get("avg") or None)
        )

        report_data = {
            "report_id": report_id,
            "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "session_date": now.strftime("%Y-%m-%d"),
            "start_time": start_time_str,
            "end_time": end_time_str,
            "duration_programmed_str": prog_str,
            "duration_effective_str": eff_str,
            "duration_effective_min": eff_min,
            "completion_status": completion_status,
            "patient": {
                "id": patient_id,
                "name": patient_name,
                "nss": patient_nss,
                "gender_code": gender_code,
                "gender_str": _gender_label(gender_code),
                "age": age,
                "height_cm": height_cm,
                "dry_weight_kg": dry_weight_kg,
                "pre_weight_kg": pre_weight_kg,
                "estimated_post_weight_kg": estimated_post_weight,
                "weight_gain_kg": weight_gain,
                "weight_loss_kg": uf_achieved_l,
                "access_type": str(current_values.get("patient_access_type") or "Fístula AV (FAV)"),
                "blood_type": str(current_values.get("patient_blood_type") or "O+"),
                "dialyzer": str(current_values.get("patient_dialyzer") or "F8HPS (Polisulfona 1.8 m²)"),
                "diagnosis": str(current_values.get("patient_diagnosis") or "ERC Estadio 5"),
                "physician": str(current_values.get("patient_physician") or "Médico Nefrólogo adscrito"),
                "allergies": str(current_values.get("patient_allergies") or "Ninguna conocida"),
            },
            "prescription": {
                "modality": modality_str,
                "uf_goal_liters": uf_goal_l,
                "uf_achieved_liters": uf_achieved_l,
                "uf_achievement_pct": uf_pct,
                "uf_profile_name": uf_profile_name,
                "na_profile_name": na_profile_name,
                "conductivity_setpoint": round(cond_set, 2),
                "temp_setpoint": round(temp_set, 1),
                "qb_setpoint": round(qb_set, 1),
                "qd_setpoint": round(qd_set, 1),
                "heparin_enabled": hep_enabled,
                "heparin_bolus_ml": round(hep_bolus_ml, 2),
                "heparin_rate_ml_h": round(hep_flow_ml_h, 2),
                "heparin_total_ml": hep_total_ml,
            },
            "adequacy": {
                "ktv_initial": round(ktv_initial, 2),
                "ktv_final": round(ktv_final, 2),
                "ktv_target_met": bool(ktv_final >= 1.2),
                "urr_estimated_pct": urr_pct,
                "heitmann_v_liters": heitmann_v,
                "blood_processed_liters": blood_processed_l,
                "ktv_history": ktv_list,
            },
            "hemodynamics": {
                "pa_initial": pa_initial,
                "pa_final": pa_final,
                "pa_min_sys": min(sys_vals) if sys_vals else None,
                "pa_max_sys": max(sys_vals) if sys_vals else None,
                "pa_min_dia": min(dia_vals) if dia_vals else None,
                "pa_max_dia": max(dia_vals) if dia_vals else None,
                "hr_avg": round(sum(hr_vals) / len(hr_vals), 1) if hr_vals else None,
                "spo2_avg": spo2_avg,
                "spo2_min": min(spo2_vals) if spo2_vals else None,
                "hypotension_alerts": hypotension_episodes,
                "nibp_measurements": nibp_rows,
            },
            "machine_stats": machine_stats,
            "monitoring_snapshots": snapshots_list,
            "alarm_events": alarm_events,
        }
        return report_data

    @classmethod
    def render_html_report(cls, report: Dict[str, Any]) -> str:
        """
        Genera el documento HTML clínico de alta resolución para visualización y exportación PDF.
        Incluye la tabla matricial de monitoreo por HORARIO (estilo Hoja de Enfermería IMSS).
        """
        p = report.get("patient", {})
        rx = report.get("prescription", {})
        ad = report.get("adequacy", {})
        hemo = report.get("hemodynamics", {})
        mstats = report.get("machine_stats", {})
        snaps = report.get("monitoring_snapshots", [])
        alarms = report.get("alarm_events", [])

        ktv_val = ad.get("ktv_final", 0.0)
        ktv_badge_bg = "#dcfce7" if ktv_val >= 1.2 else "#fef3c7"
        ktv_badge_fg = "#166534" if ktv_val >= 1.2 else "#92400e"
        ktv_status_txt = "ÓPTIMO (≥ 1.2)" if ktv_val >= 1.2 else "SUBÓPTIMO (< 1.2)"

        # Construir columnas de la tabla matricial de monitoreo (máximo 10 columnas por página)
        display_snaps = snaps[:10] if snaps else []

        header_cols_html = "".join(
            f"<th style='background:#1e3a8a; color:#ffffff; text-align:center; padding:5px;'>"
            f"{s.get('horario', '—')}<br/><span style='font-size:8pt; font-weight:normal; color:#bfdbfe;'>"
            f"({s.get('origen', '')})</span></th>"
            for s in display_snaps
        )

        def _row_cells(key: str, fmt: str = "{}") -> str:
            cells = []
            for s in display_snaps:
                val = s.get(key)
                if val is None or val == "":
                    txt = "—"
                else:
                    try:
                        txt = fmt.format(val)
                    except Exception:
                        txt = str(val)
                cells.append(f"<td style='text-align:center; padding:4px 6px;'>{txt}</td>")
            return "".join(cells)

        monitoring_matrix_html = f"""
        <table width="100%" cellspacing="0" cellpadding="3" style="border-collapse:collapse; border:1px solid #94a3b8; font-size:9pt; margin-top:6px;">
            <thead>
                <tr>
                    <th style="background:#0f172a; color:#ffffff; text-align:left; padding:5px 8px; width:210px;">PARÁMETRO / HORARIO</th>
                    {header_cols_html}
                </tr>
            </thead>
            <tbody>
                <tr style="background:#f8fafc;">
                    <td style="font-weight:bold; padding:4px 8px;">TENSIÓN ARTERIAL (mmHg)</td>
                    {_row_cells('ta_str')}
                </tr>
                <tr>
                    <td style="font-weight:bold; padding:4px 8px;">PRESIÓN ARTERIAL MEDIA (PAM)</td>
                    {_row_cells('map_mmhg')}
                </tr>
                <tr style="background:#f8fafc;">
                    <td style="font-weight:bold; padding:4px 8px;">FRECUENCIA CARDIACA (lpm)</td>
                    {_row_cells('hr')}
                </tr>
                <tr>
                    <td style="font-weight:bold; padding:4px 8px;">SATURACIÓN DE OXÍGENO SpO2 (%)</td>
                    {_row_cells('spo2')}
                </tr>
                <tr style="background:#f8fafc;">
                    <td style="font-weight:bold; padding:4px 8px;">TEMPERATURA (°C)</td>
                    {_row_cells('temp_corporal_c', '{:.1f}')}
                </tr>
                <tr>
                    <td style="font-weight:bold; padding:4px 8px;">FLUJO SANGUÍNEO Qb (mL/min)</td>
                    {_row_cells('qb_ml_min', '{:.0f}')}
                </tr>
                <tr style="background:#f8fafc;">
                    <td style="font-weight:bold; padding:4px 8px;">FLUJO DIALIZANTE Qd (mL/min)</td>
                    {_row_cells('qd_ml_min', '{:.0f}')}
                </tr>
                <tr>
                    <td style="font-weight:bold; padding:4px 8px;">PRESIÓN VENOSA PV (mmHg)</td>
                    {_row_cells('pv_mmhg', '{:.0f}')}
                </tr>
                <tr style="background:#f8fafc;">
                    <td style="font-weight:bold; padding:4px 8px;">PRESIÓN ARTERIAL PA (mmHg)</td>
                    {_row_cells('pa_mmhg', '{:.0f}')}
                </tr>
                <tr>
                    <td style="font-weight:bold; padding:4px 8px;">TEMPERATURA DIALIZANTE (°C)</td>
                    {_row_cells('temp_dial_c', '{:.1f}')}
                </tr>
                <tr style="background:#f8fafc;">
                    <td style="font-weight:bold; padding:4px 8px;">CONDUCTIVIDAD (mS/cm)</td>
                    {_row_cells('cond_ms_cm', '{:.2f}')}
                </tr>
                <tr>
                    <td style="font-weight:bold; padding:4px 8px;">PTM (mmHg)</td>
                    {_row_cells('ptm_mmhg', '{:.0f}')}
                </tr>
                <tr style="background:#f8fafc;">
                    <td style="font-weight:bold; padding:4px 8px;">ULTRAFILTRACIÓN HORARIA (L/h)</td>
                    {_row_cells('uf_rate_l_h', '{:.2f}')}
                </tr>
                <tr>
                    <td style="font-weight:bold; padding:4px 8px;">UF ACUMULADA (L)</td>
                    {_row_cells('uf_removed_l', '{:.3f}')}
                </tr>
                <tr style="background:#eff6ff;">
                    <td style="font-weight:bold; padding:4px 8px; color:#1e3a8a;">SANGRE PROCESADA (L)</td>
                    {_row_cells('blood_processed_l', '{:.2f}')}
                </tr>
            </tbody>
        </table>
        """

        # Tabla detallada de NIBP
        nibp_rows = hemo.get("nibp_measurements", [])
        if nibp_rows:
            nibp_trs = "".join(
                f"<tr>"
                f"<td style='text-align:center; padding:4px;'>{r.get('n')}</td>"
                f"<td style='text-align:center; padding:4px;'>{r.get('tiempo_terapia')}</td>"
                f"<td style='text-align:center; padding:4px; font-weight:bold; color:#dc2626;'>{r.get('sys')}</td>"
                f"<td style='text-align:center; padding:4px; font-weight:bold; color:#2563eb;'>{r.get('dia')}</td>"
                f"<td style='text-align:center; padding:4px;'>{r.get('map')}</td>"
                f"<td style='text-align:center; padding:4px; color:#15803d; font-weight:bold;'>{r.get('hr')}</td>"
                f"<td style='text-align:center; padding:4px;'>{r.get('spo2') if r.get('spo2') is not None else '—'}</td>"
                f"<td style='text-align:center; padding:4px;'>{r.get('origen')}</td>"
                f"</tr>"
                for r in nibp_rows
            )
        else:
            nibp_trs = (
                "<tr><td colspan='8' style='text-align:center; padding:8px; color:#64748b;'>"
                "No se registraron tomas de baumanómetro durante la sesión.</td></tr>"
            )

        # Tabla de evolución Kt/V
        ktv_rows = ad.get("ktv_history", [])
        if ktv_rows:
            ktv_trs = "".join(
                f"<tr>"
                f"<td style='text-align:center; padding:4px;'>{idx}</td>"
                f"<td style='text-align:center; padding:4px;'>{k.get('timestamp', '—')}</td>"
                f"<td style='text-align:center; padding:4px; font-weight:bold;'>{float(k.get('ktv', 0.0)):.2f}</td>"
                f"<td style='text-align:center; padding:4px;'>{float(k.get('ureica', 0.0)):.1f} mg/dL</td>"
                f"</tr>"
                for idx, k in enumerate(ktv_rows, start=1)
            )
        else:
            ktv_trs = (
                "<tr><td colspan='4' style='text-align:center; padding:8px; color:#64748b;'>"
                "Sin lecturas seriadas del sensor óptico URIT en esta sesión.</td></tr>"
            )

        # Tabla de alarmas
        if alarms:
            alarm_trs = "".join(
                f"<tr>"
                f"<td style='text-align:center; padding:3px;'>{a.get('timestamp')}</td>"
                f"<td style='text-align:center; padding:3px;'>{a.get('elapsed_min')} min</td>"
                f"<td style='padding:3px 6px;'>{a.get('message')}</td>"
                f"</tr>"
                for a in alarms[:15]
            )
        else:
            alarm_trs = (
                "<tr><td colspan='3' style='text-align:center; padding:6px; color:#15803d;'>"
                "Sesión completada sin alarmas clínicas críticas registradas.</td></tr>"
            )

        def _stat_str(metric_key: str, unit: str = "") -> str:
            st = mstats.get(metric_key, {})
            if not st or not st.get("count"):
                return "—"
            return f"Prom: {st.get('avg')} {unit} (Mín: {st.get('min')} / Máx: {st.get('max')})"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8"/>
            <style>
                body {{
                    font-family: 'Segoe UI', Arial, Helvetica, sans-serif;
                    color: #0f172a;
                    font-size: 9.5pt;
                    line-height: 1.35;
                    margin: 0;
                    padding: 0;
                }}
                .header-bar {{
                    background-color: #0f172a;
                    color: #ffffff;
                    padding: 12px 16px;
                    border-bottom: 4px solid #2563eb;
                }}
                .section-title {{
                    background-color: #e2e8f0;
                    color: #0f172a;
                    font-weight: bold;
                    font-size: 10pt;
                    padding: 5px 10px;
                    margin-top: 12px;
                    margin-bottom: 4px;
                    border-left: 5px solid #1e40af;
                }}
                table.grid-table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                table.grid-table th, table.grid-table td {{
                    border: 1px solid #cbd5e1;
                    padding: 4px 7px;
                    font-size: 9pt;
                }}
                .lbl {{
                    color: #475569;
                    font-weight: bold;
                    background-color: #f8fafc;
                }}
                .val {{
                    color: #0f172a;
                    font-weight: 600;
                }}
            </style>
        </head>
        <body>
            <!-- ENCABEZADO INSTITUCIONAL -->
            <table width="100%" cellspacing="0" cellpadding="8" style="background:#0f172a; color:#ffffff; border-bottom:3px solid #2563eb;">
                <tr>
                    <td width="68%">
                        <div style="font-size:14pt; font-weight:bold; letter-spacing:0.5px;">
                            REGISTROS CLÍNICOS Y REPORTE NEFROLÓGICO DE HEMODIÁLISIS
                        </div>
                        <div style="font-size:9.5pt; color:#93c5fd; margin-top:2px;">
                            Sistema de Hemodiálisis CIATEQ — Hoja de Enfermería y Adecuación Dialítica
                        </div>
                    </td>
                    <td width="32%" align="right" style="font-size:9pt; color:#e2e8f0;">
                        <b>Folio Sesión:</b> {report.get('report_id')}<br/>
                        <b>Fecha:</b> {report.get('session_date')}<br/>
                        <b>Horario:</b> {report.get('start_time')} a {report.get('end_time')}<br/>
                        <b>Estado:</b> {report.get('completion_status')}
                    </td>
                </tr>
            </table>

            <!-- 1. IDENTIFICACIÓN DEL PACIENTE Y CONTROL PONDERAL -->
            <div class="section-title">1. IDENTIFICACIÓN DEL PACIENTE, ACCESO VASCULAR Y CONTROL DE PESO</div>
            <table class="grid-table">
                <tr>
                    <td class="lbl" width="15%">Paciente:</td>
                    <td class="val" width="35%">{p.get('name')} (ID: {p.get('id')})</td>
                    <td class="lbl" width="16%">N.S.S. / Registro:</td>
                    <td class="val" width="34%">{p.get('nss')}</td>
                </tr>
                <tr>
                    <td class="lbl">Edad / Sexo:</td>
                    <td class="val">{p.get('age')} años / {p.get('gender_str')} ({p.get('height_cm')} cm)</td>
                    <td class="lbl">Grupo y Rh / Alergias:</td>
                    <td class="val">{p.get('blood_type')} | Alergias: {p.get('allergies')}</td>
                </tr>
                <tr>
                    <td class="lbl">Diagnóstico:</td>
                    <td class="val">{p.get('diagnosis')}</td>
                    <td class="lbl">Médico Nefrólogo:</td>
                    <td class="val">{p.get('physician')}</td>
                </tr>
                <tr>
                    <td class="lbl">Acceso Vascular:</td>
                    <td class="val">{p.get('access_type')}</td>
                    <td class="lbl">Filtro / Dializador:</td>
                    <td class="val">{p.get('dialyzer')}</td>
                </tr>
                <tr>
                    <td class="lbl">Peso Seco:</td>
                    <td class="val">{p.get('dry_weight_kg'):.2f} kg (Ganancia interdiálisis: +{p.get('weight_gain_kg'):.2f} kg)</td>
                    <td class="lbl">Peso Inicial / Final Est.:</td>
                    <td class="val">Pre-HD: <b>{p.get('pre_weight_kg'):.2f} kg</b> → Post-HD Est.: <b>{p.get('estimated_post_weight_kg'):.2f} kg</b> (Pérdida: {p.get('weight_loss_kg'):.3f} kg)</td>
                </tr>
            </table>

            <!-- 2. PRESCRIPCIÓN MÉDICA Y DOSIS DE ADECUACIÓN DIALÍTICA -->
            <div class="section-title">2. PRESCRIPCIÓN DIALÍTICA, ANTICOAGULACIÓN Y ADECUACIÓN (Kt/V - URR)</div>
            <table class="grid-table">
                <tr>
                    <td class="lbl" width="18%">Modalidad:</td>
                    <td class="val" width="32%">{rx.get('modality')}</td>
                    <td class="lbl" width="18%">Duración Prog. / Efectiva:</td>
                    <td class="val" width="32%">{report.get('duration_programmed_str')} / <b>{report.get('duration_effective_str')}</b></td>
                </tr>
                <tr>
                    <td class="lbl">UF Meta / UF Lograda:</td>
                    <td class="val">Meta: {rx.get('uf_goal_liters'):.2f} L | Lograda: <b>{rx.get('uf_achieved_liters'):.3f} L</b> ({rx.get('uf_achievement_pct'):.1f}%)</td>
                    <td class="lbl">Perfiles UF / Sodio:</td>
                    <td class="val">UF: {rx.get('uf_profile_name')} | Na+: {rx.get('na_profile_name')} ({rx.get('conductivity_setpoint')} mS/cm)</td>
                </tr>
                <tr>
                    <td class="lbl">Anticoagulación (Heparina):</td>
                    <td class="val">
                        {"Habilitada" if rx.get('heparin_enabled') else "Sin Heparina"} |
                        Bolo Inicial: <b>{rx.get('heparin_bolus_ml'):.1f} mL</b> |
                         Continua: <b>{rx.get('heparin_rate_ml_h'):.1f} mL/h</b> (Total: {rx.get('heparin_total_ml'):.2f} mL)
                    </td>
                    <td class="lbl">Sangre Total Procesada:</td>
                    <td class="val"><b>{ad.get('blood_processed_liters'):.2f} Litros</b> (Vol. Urea Heitmann V: {ad.get('heitmann_v_liters'):.2f} L)</td>
                </tr>
                <tr>
                    <td class="lbl">Kt/V Inicial / Final:</td>
                    <td class="val" style="background:{ktv_badge_bg}; color:{ktv_badge_fg};">
                        Inicial: {ad.get('ktv_initial'):.2f} → <b>Kt/V Final: {ktv_val:.2f}</b> [{ktv_status_txt}]
                    </td>
                    <td class="lbl">URR Estimado / PA:</td>
                    <td class="val">URR Est.: <b>{ad.get('urr_estimated_pct'):.1f}%</b> | PA Inicio: {hemo.get('pa_initial')} → Final: {hemo.get('pa_final')}</td>
                </tr>
            </table>

            <!-- 3. MONITOREO HORARIO MULTICOLUMNA (FORMATO HOJA DE ENFERMERÍA IMSS) -->
            <div class="section-title">3. REGISTRO PERIÓDICO DE SIGNOS VITALES Y PARÁMETROS DE MÁQUINA (POR HORARIO)</div>
            {monitoring_matrix_html}

            <!-- 4. DETALLE DE TOMAS DE BAUMANÓMETRO (NIBP / SpO2) Y KT/V -->
            <table width="100%" cellspacing="0" cellpadding="0" style="margin-top:8px;">
                <tr>
                    <td width="62%" valign="top" style="padding-right:8px;">
                        <div class="section-title" style="margin-top:4px;">4. HISTORIAL DETALLADO DE BAUMANÓMETRO (NIBP) Y SpO2</div>
                        <table class="grid-table">
                            <thead>
                                <tr style="background:#1e293b; color:#ffffff;">
                                    <th>No.</th>
                                    <th>Tiempo</th>
                                    <th>SYS</th>
                                    <th>DIA</th>
                                    <th>PAM</th>
                                    <th>FC (lpm)</th>
                                    <th>SpO2 (%)</th>
                                    <th>Origen</th>
                                </tr>
                            </thead>
                            <tbody>
                                {nibp_trs}
                            </tbody>
                        </table>
                    </td>
                    <td width="38%" valign="top">
                        <div class="section-title" style="margin-top:4px;">5. CURVA DE ADECUACIÓN KT/V (SENSOR URIT)</div>
                        <table class="grid-table">
                            <thead>
                                <tr style="background:#1e293b; color:#ffffff;">
                                    <th>#</th>
                                    <th>Hora</th>
                                    <th>Kt/V</th>
                                    <th>Urea</th>
                                </tr>
                            </thead>
                            <tbody>
                                {ktv_trs}
                            </tbody>
                        </table>
                    </td>
                </tr>
            </table>

            <!-- 6. RESUMEN TÉCNICO DE PARÁMETROS EXTRACORPÓREOS Y EVENTOS -->
            <div class="section-title">6. ESTADÍSTICAS TÉCNICAS DEL CIRCUITO Y BITÁCORA DE EVENTOS / ALARMAS</div>
            <table class="grid-table">
                <tr>
                    <td class="lbl" width="18%">Flujo Sanguíneo (Qb):</td>
                    <td class="val" width="32%">{_stat_str('qb', 'mL/min')}</td>
                    <td class="lbl" width="18%">Flujo Dializante (Qd):</td>
                    <td class="val" width="32%">{_stat_str('qd', 'mL/min')}</td>
                </tr>
                <tr>
                    <td class="lbl">Presión Arterial (PA):</td>
                    <td class="val">{_stat_str('pa', 'mmHg')}</td>
                    <td class="lbl">Presión Venosa (PV):</td>
                    <td class="val">{_stat_str('pv', 'mmHg')}</td>
                </tr>
                <tr>
                    <td class="lbl">PTM (Transmembrana):</td>
                    <td class="val">{_stat_str('ptm', 'mmHg')}</td>
                    <td class="lbl">Temp. / Conductividad:</td>
                    <td class="val">T: {_stat_str('temp_dial', '°C')} | Cond: {_stat_str('cond', 'mS/cm')}</td>
                </tr>
            </table>

            <table class="grid-table" style="margin-top:6px;">
                <thead>
                    <tr style="background:#f1f5f9;">
                        <th width="15%">Hora</th>
                        <th width="15%">Minuto Terapia</th>
                        <th width="70%" align="left">Descripción de Alarma / Intervención</th>
                    </tr>
                </thead>
                <tbody>
                    {alarm_trs}
                </tbody>
            </table>

            <!-- FIRMAS DE RESPONSABILIDAD CLÍNICA -->
            <table width="100%" cellspacing="0" cellpadding="10" style="margin-top:26px; font-size:9pt;">
                <tr>
                    <td width="45%" align="center" style="border-top:1px solid #334155;">
                        <b>NOMBRE Y FIRMA DE ENFERMERÍA</b><br/>
                        Responsable de Conexión, Monitoreo y Desconexión
                    </td>
                    <td width="10%"></td>
                    <td width="45%" align="center" style="border-top:1px solid #334155;">
                        <b>NOMBRE Y FIRMA DEL MÉDICO NEFRÓLOGO</b><br/>
                        {p.get('physician')}
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        return html

    @classmethod
    def export_pdf(cls, report: Dict[str, Any], pdf_path: Path | str) -> Path:
        """
        Exporta el reporte clínico a un archivo PDF de alta resolución (300 DPI)
        usando QPdfWriter + QTextDocument de PySide6.
        """
        out_path = Path(pdf_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        writer = QPdfWriter(str(out_path))
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.Letter))
        writer.setPageOrientation(QPageLayout.Orientation.Portrait)
        writer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Unit.Millimeter)
        writer.setResolution(300)

        doc = QTextDocument()
        # Ajustar el ancho lógico del documento al área imprimible de la página
        page_rect = writer.pageLayout().paintRectPixels(writer.resolution())
        doc.setPageSize(QSizeF(page_rect.width(), page_rect.height()))
        doc.setHtml(cls.render_html_report(report))
        doc.print_(writer)

        logger.info(f"[ReportGenerator] PDF clínico generado en: {out_path}")
        return out_path

    @classmethod
    def export_csv(cls, report: Dict[str, Any], csv_path: Path | str) -> Path:
        """
        Exporta un respaldo tabular CSV con los metadatos de sesión y la tabla de monitoreo horario.
        """
        out_path = Path(csv_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        p = report.get("patient", {})
        rx = report.get("prescription", {})
        ad = report.get("adequacy", {})
        snaps = report.get("monitoring_snapshots", [])

        with out_path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["REPORTE CLÍNICO DE HEMODIÁLISIS - CIATEQ"])
            w.writerow(["Folio", report.get("report_id"), "Fecha", report.get("session_date")])
            w.writerow(["Paciente", p.get("name"), "ID", p.get("id"), "NSS", p.get("nss")])
            w.writerow([
                "Peso Seco (kg)", p.get("dry_weight_kg"),
                "Peso Pre-HD (kg)", p.get("pre_weight_kg"),
                "Peso Post-HD Est (kg)", p.get("estimated_post_weight_kg"),
            ])
            w.writerow([
                "Modalidad", rx.get("modality"),
                "UF Meta (L)", rx.get("uf_goal_liters"),
                "UF Lograda (L)", rx.get("uf_achieved_liters"),
                "Kt/V Final", ad.get("ktv_final"),
                "Sangre Procesada (L)", ad.get("blood_processed_liters"),
            ])
            w.writerow([])
            w.writerow([
                "No.", "Horario", "Minutos", "Origen", "TA (mmHg)", "SYS", "DIA", "PAM",
                "FC (lpm)", "SpO2 (%)", "Temp (°C)", "Qb (mL/min)", "Qd (mL/min)",
                "PV (mmHg)", "PA (mmHg)", "Temp Dial (°C)", "Cond (mS/cm)",
                "PTM (mmHg)", "UF Horaria (L/h)", "UF Acum (L)", "Sangre Proc (L)"
            ])
            for s in snaps:
                w.writerow([
                    s.get("index"),
                    s.get("horario"),
                    s.get("elapsed_min"),
                    s.get("origen"),
                    s.get("ta_str"),
                    s.get("sys", ""),
                    s.get("dia", ""),
                    s.get("map_mmhg", ""),
                    s.get("hr", ""),
                    s.get("spo2", ""),
                    s.get("temp_corporal_c"),
                    s.get("qb_ml_min"),
                    s.get("qd_ml_min"),
                    s.get("pv_mmhg"),
                    s.get("pa_mmhg"),
                    s.get("temp_dial_c"),
                    s.get("cond_ms_cm"),
                    s.get("ptm_mmhg"),
                    s.get("uf_rate_l_h"),
                    s.get("uf_removed_l"),
                    s.get("blood_processed_l"),
                ])

        logger.info(f"[ReportGenerator] CSV clínico generado en: {out_path}")
        return out_path

    @classmethod
    def save_session_report_bundle(cls, report: Dict[str, Any]) -> Dict[str, str]:
        """
        Guarda automáticamente:
        1. Respaldo JSON completo en `logs/reportes_terapia/reporte_<id>.json`
        2. Respaldo CSV en `logs/reportes_terapia/reporte_<id>.csv`
        3. Reporte PDF listo para impresión en `exports/reportes_pdf/Reporte_HD_<pid>_<id>.pdf`
        Retorna un dict con las rutas generadas.
        """
        report_id = report.get("report_id") or datetime.now().strftime("%Y%m%d_%H%M%S")
        pid = str(report.get("patient", {}).get("id") or "PAC").replace(" ", "_")

        backup_dir = cls.get_reports_backup_dir()
        pdf_dir = cls.get_pdf_export_dir()

        json_path = backup_dir / f"reporte_{report_id}.json"
        csv_path = backup_dir / f"reporte_{report_id}.csv"
        pdf_path = pdf_dir / f"Reporte_HD_{pid}_{report_id}.pdf"

        try:
            with json_path.open("w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[ReportGenerator] Error guardando JSON de reporte: {e}")

        try:
            cls.export_csv(report, csv_path)
        except Exception as e:
            logger.error(f"[ReportGenerator] Error guardando CSV de reporte: {e}")

        try:
            cls.export_pdf(report, pdf_path)
        except Exception as e:
            logger.error(f"[ReportGenerator] Error generando PDF de reporte: {e}")

        return {
            "report_id": report_id,
            "json_path": str(json_path),
            "csv_path": str(csv_path),
            "pdf_path": str(pdf_path),
        }
