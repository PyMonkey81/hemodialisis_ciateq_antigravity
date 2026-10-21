# core/therapy_session_tracker.py
"""
Rastreador clínico de sesión de hemodiálisis en tiempo real.
Acumula métricas hemodinámicas, volumen de sangre procesada, infusión de heparina,
alarmas/eventos y la tabla periódica de monitoreo horario (formato Hoja de Enfermería / Nefrología).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any

from logic.calculos import convertir_ciclos_a_flujo

logger = logging.getLogger(__name__)

MODALITY_NAMES = {
    1: "Hemodiálisis (HD)",
    2: "Ultrafiltración Aislada (UFA)",
    3: "Hemodiafiltración (HDF)",
    4: "Hemofiltración (HF)",
}


@dataclass
class MetricAccumulator:
    """Acumulador estadístico ligero (promedio, mínimo, máximo, último valor)."""
    count: int = 0
    total: float = 0.0
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    last_val: float = 0.0

    def add(self, value: float):
        if value is None or not math.isfinite(value):
            return
        self.count += 1
        self.total += value
        self.last_val = value
        if self.min_val is None or value < self.min_val:
            self.min_val = value
        if self.max_val is None or value > self.max_val:
            self.max_val = value

    @property
    def avg(self) -> float:
        return round(self.total / self.count, 2) if self.count > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "avg": self.avg,
            "min": round(self.min_val, 2) if self.min_val is not None else 0.0,
            "max": round(self.max_val, 2) if self.max_val is not None else 0.0,
            "last": round(self.last_val, 2),
        }


@dataclass
class MonitoringSnapshot:
    """
    Columna de monitoreo periódico (Hoja de Enfermería / Nefrología IMSS).
    """
    index: int
    horario: str                   # "HH:MM"
    elapsed_min: float             # Minutos desde inicio de terapia
    origen: str                    # "Inicio", "NIBP Auto", "NIBP Manual", "Periódico", "Final"
    ta_str: str                    # "120/80" o "—"
    sys: Optional[int]
    dia: Optional[int]
    map_mmhg: Optional[int]
    hr: Optional[int]
    spo2: Optional[int]
    temp_corporal_c: float         # Temperatura (°C)
    qb_ml_min: float               # Flujo Sanguíneo Qb (mL/min)
    qd_ml_min: float               # Flujo Dializante Qd (mL/min)
    pv_mmhg: float                 # Presión Venosa (mmHg)
    pa_mmhg: float                 # Presión Arterial (mmHg)
    temp_dial_c: float             # Temperatura del Dializante (°C)
    cond_ms_cm: float              # Conductividad (mS/cm)
    ptm_mmhg: float                # PTM (mmHg)
    uf_rate_l_h: float             # Ultrafiltración Horaria (L/h)
    uf_removed_l: float            # UF acumulada (L)
    blood_processed_l: float       # Sangre Procesada acumulada (L)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TherapySessionTracker:
    """
    Rastreador de sesión clínica para reportes automáticos de terapia.
    """

    PERIODIC_SNAPSHOT_INTERVAL_S = 15 * 60  # Cada 15 minutos en RUNNING

    def __init__(self):
        self.reset()

    def reset(self):
        self.active: bool = False
        self.session_id: str = ""
        self.start_dt: Optional[datetime] = None
        self.end_dt: Optional[datetime] = None
        self.last_tick_elapsed_s: float = 0.0
        self.last_snapshot_elapsed_s: float = -9999.0

        # Sangre procesada integrada (Litros)
        self.blood_processed_liters: float = 0.0

        # Último SpO2 válido recibido del módulo NIBP2020 UP
        self.last_spo2: Optional[int] = None
        self.last_nibp: Dict[str, Optional[int]] = {
            "sys": None,
            "dia": None,
            "map": None,
            "hr": None,
        }

        # Acumuladores estadísticos
        self.stats: Dict[str, MetricAccumulator] = {
            "qb": MetricAccumulator(),
            "qd": MetricAccumulator(),
            "pa": MetricAccumulator(),
            "pv": MetricAccumulator(),
            "ptm": MetricAccumulator(),
            "temp_dial": MetricAccumulator(),
            "cond": MetricAccumulator(),
            "uf_rate_lh": MetricAccumulator(),
            "spo2": MetricAccumulator(),
        }

        # Snapshots horarios (columnas de la hoja de enfermería)
        self.snapshots: List[MonitoringSnapshot] = []

        # Registro de alarmas / eventos ocurridos en sesión
        self.alarm_events: List[Dict[str, Any]] = []
        self._last_alarm_text: str = ""

    def start_session(self, current_values: Dict[str, Any]):
        """Inicia una nueva sesión clínica al entrar a RUNNING desde inicio."""
        self.reset()
        now = datetime.now()
        self.active = True
        self.start_dt = now
        self.session_id = now.strftime("%Y%m%d_%H%M%S")
        self.last_tick_elapsed_s = 0.0
        self.last_snapshot_elapsed_s = 0.0

        # Capturar snapshot inicial (t = 0)
        self.capture_snapshot(
            current_values=current_values,
            elapsed_s=0.0,
            origen="Inicio",
            include_last_nibp=True,
        )
        logger.info(f"[SessionTracker] Sesión clínica iniciada: {self.session_id}")

    def update_spo2(self, spo2_val: Optional[int]):
        """Actualiza el último valor válido de SpO2."""
        if spo2_val is not None and 50 <= int(spo2_val) <= 100:
            self.last_spo2 = int(spo2_val)
            if self.active:
                self.stats["spo2"].add(float(self.last_spo2))

    def record_alarm(self, alarm_text: str, elapsed_s: float = 0.0, severity: str = "warning"):
        """Registra una alarma o evento relevante sin duplicar ráfagas idénticas consecutivas."""
        clean = (alarm_text or "").strip()
        if not clean or clean == self._last_alarm_text:
            return
        self._last_alarm_text = clean
        self.alarm_events.append({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "elapsed_min": round(max(0.0, elapsed_s) / 60.0, 1),
            "severity": severity,
            "message": clean,
        })

    def on_therapy_tick(
        self,
        current_values: Dict[str, Any],
        elapsed_s: float,
        uf_removed_liters: float = 0.0,
    ):
        """
        Se invoca periódicamente (ej. cada 1s en _master_timer_tick mientras phase == RUNNING).
        Integra el volumen de sangre procesada y actualiza estadísticas.
        """
        if not self.active:
            self.start_session(current_values)

        dt_s = max(0.0, elapsed_s - self.last_tick_elapsed_s)
        # Si hubo un salto anormal (> 30s), limitar dt_s a 1s para evitar picos espurios
        if dt_s > 30.0:
            dt_s = 1.0
        self.last_tick_elapsed_s = elapsed_s

        qb = self._extract_qb(current_values)
        qd = self._extract_qd(current_values)
        pa = float(current_values.get("arterialPressureSensor", 0.0) or 0.0)
        pv = float(current_values.get("venousPressureSensor", 0.0) or 0.0)
        ptm = float(current_values.get("TMPValue", 0.0) or 0.0)
        temp_dial = float(
            current_values.get("dialyTempSensor")
            or current_values.get("dialyTempControlSetPoint")
            or 36.5
        )
        cond = float(
            current_values.get("dialyCondSensor")
            or current_values.get("dialyCondControlSetPoint")
            or 13.8
        )
        uf_speed_ml_min = float(current_values.get("ultraFilterPumpSpeed", 0.0) or 0.0)
        uf_rate_lh = round((uf_speed_ml_min * 60.0) / 1000.0, 2)

        # Integrar sangre procesada: Qb (mL/min) * (dt_s / 60) / 1000 -> Litros
        if qb > 0 and dt_s > 0:
            self.blood_processed_liters += (qb * (dt_s / 60.0)) / 1000.0

        self.stats["qb"].add(qb)
        self.stats["qd"].add(qd)
        self.stats["pa"].add(pa)
        self.stats["pv"].add(pv)
        self.stats["ptm"].add(ptm)
        self.stats["temp_dial"].add(temp_dial)
        self.stats["cond"].add(cond)
        self.stats["uf_rate_lh"].add(uf_rate_lh)

        # Captura periódica automática cada 15 min si no hubo captura reciente
        if (elapsed_s - self.last_snapshot_elapsed_s) >= self.PERIODIC_SNAPSHOT_INTERVAL_S:
            self.capture_snapshot(
                current_values=current_values,
                elapsed_s=elapsed_s,
                origen="Periódico",
                uf_removed_liters=uf_removed_liters,
                include_last_nibp=False,
            )

    def on_nibp_measurement(
        self,
        sys_mmhg: int,
        dia_mmhg: int,
        map_mmhg: int,
        hr_bpm: int,
        origen: str,
        current_values: Dict[str, Any],
        elapsed_s: Optional[float] = None,
        uf_removed_liters: float = 0.0,
    ):
        """Registra una toma del baumanómetro y genera una columna en la tabla de monitoreo."""
        self.last_nibp = {
            "sys": sys_mmhg,
            "dia": dia_mmhg,
            "map": map_mmhg,
            "hr": hr_bpm,
        }
        eff_elapsed = elapsed_s if elapsed_s is not None else self.last_tick_elapsed_s
        self.capture_snapshot(
            current_values=current_values,
            elapsed_s=eff_elapsed,
            origen=f"NIBP ({origen})",
            uf_removed_liters=uf_removed_liters,
            sys_mmhg=sys_mmhg,
            dia_mmhg=dia_mmhg,
            map_mmhg=map_mmhg,
            hr_bpm=hr_bpm,
        )

    def capture_snapshot(
        self,
        current_values: Dict[str, Any],
        elapsed_s: float = 0.0,
        origen: str = "Periódico",
        uf_removed_liters: float = 0.0,
        sys_mmhg: Optional[int] = None,
        dia_mmhg: Optional[int] = None,
        map_mmhg: Optional[int] = None,
        hr_bpm: Optional[int] = None,
        include_last_nibp: bool = False,
    ) -> MonitoringSnapshot:
        """Crea y almacena una columna de signos vitales + parámetros de máquina."""
        now = datetime.now()
        self.last_snapshot_elapsed_s = max(0.0, elapsed_s or 0.0)

        if include_last_nibp and sys_mmhg is None and self.last_nibp.get("sys") is not None:
            sys_mmhg = self.last_nibp["sys"]
            dia_mmhg = self.last_nibp["dia"]
            map_mmhg = self.last_nibp["map"]
            hr_bpm = self.last_nibp["hr"]

        ta_str = f"{sys_mmhg}/{dia_mmhg}" if (sys_mmhg is not None and dia_mmhg is not None) else "—"

        qb = self._extract_qb(current_values)
        qd = self._extract_qd(current_values)
        pa = float(current_values.get("arterialPressureSensor", 0.0) or 0.0)
        pv = float(current_values.get("venousPressureSensor", 0.0) or 0.0)
        ptm = float(current_values.get("TMPValue", 0.0) or 0.0)
        temp_dial = float(
            current_values.get("dialyTempSensor")
            or current_values.get("dialyTempControlSetPoint")
            or 36.5
        )
        cond = float(
            current_values.get("dialyCondSensor")
            or current_values.get("dialyCondControlSetPoint")
            or 13.8
        )
        uf_speed_ml_min = float(current_values.get("ultraFilterPumpSpeed", 0.0) or 0.0)
        uf_rate_lh = round((uf_speed_ml_min * 60.0) / 1000.0, 2)

        snap = MonitoringSnapshot(
            index=len(self.snapshots) + 1,
            horario=now.strftime("%H:%M"),
            elapsed_min=round(max(0.0, elapsed_s or 0.0) / 60.0, 1),
            origen=origen,
            ta_str=ta_str,
            sys=sys_mmhg,
            dia=dia_mmhg,
            map_mmhg=map_mmhg,
            hr=hr_bpm,
            spo2=self.last_spo2,
            temp_corporal_c=round(temp_dial, 1),
            qb_ml_min=round(qb, 1),
            qd_ml_min=round(qd, 1),
            pv_mmhg=round(pv, 1),
            pa_mmhg=round(pa, 1),
            temp_dial_c=round(temp_dial, 1),
            cond_ms_cm=round(cond, 2),
            ptm_mmhg=round(ptm, 1),
            uf_rate_l_h=uf_rate_lh,
            uf_removed_l=round(uf_removed_liters, 3),
            blood_processed_l=round(self.blood_processed_liters, 2),
        )
        self.snapshots.append(snap)
        return snap

    def finish_session(
        self,
        current_values: Dict[str, Any],
        elapsed_s: float = 0.0,
        uf_removed_liters: float = 0.0,
    ):
        """Cierra la sesión y toma la lectura final."""
        self.end_dt = datetime.now()
        self.capture_snapshot(
            current_values=current_values,
            elapsed_s=elapsed_s,
            origen="Final",
            uf_removed_liters=uf_removed_liters,
            include_last_nibp=True,
        )
        self.active = False

    @staticmethod
    def _extract_qb(values: Dict[str, Any]) -> float:
        qb = float(values.get("bloodFlowSensor", 0.0) or 0.0)
        if qb <= 0.0:
            qb = float(values.get("bloodFlowControlSetPoint", 0.0) or 0.0)
        return qb

    @staticmethod
    def _extract_qd(values: Dict[str, Any]) -> float:
        cycles = float(values.get("balanceChamberSetTiming", 0.0) or 0.0)
        if cycles > 0:
            try:
                return float(convertir_ciclos_a_flujo(cycles))
            except Exception:
                pass
        return float(values.get("dialysateFlowSetPoint", 500.0) or 500.0)
