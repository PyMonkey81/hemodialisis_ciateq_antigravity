import logging

from PySide6.QtWidgets import QVBoxLayout, QWidget

from gui.components.conductivity_bar import ConductivityBar
from gui.components.tank_gauge import TankGauge

logger = logging.getLogger(__name__)


class SideIndicators:
    def __init__(self, window):
        self.window = window
        self._ui_built = False
        if (
            hasattr(window, "main_layout")
            and window.main_layout is not None
            and not hasattr(window, "arterial_pressure_gauge")
        ):
            self.setup_ui()

    def setup_ui(self):
        if self._ui_built:
            return
        self._ui_built = True

        # ====================================================================
        #                  GAUGES IZQUIERDA (PA + PV)
        # ====================================================================
        self.window.left_container = QWidget()  # CONTENEDOR FIJO SIEMPRE VISIBLE
        self.window.left_container.setFixedSize(180, 903)
        left_layout_outer = QVBoxLayout(self.window.left_container)
        left_layout_outer.setContentsMargins(0, 0, 0, 0)

        self.window.left_content = QWidget()  # CONTENEDOR DE WIDGETS
        self.window.left_content.setFixedSize(180, 903)
        left_inner_layout = QVBoxLayout(self.window.left_content)
        left_inner_layout.setContentsMargins(0, 0, 0, 0)
        left_inner_layout.setSpacing(0)

        self.window.arterial_pressure_gauge = TankGauge("Art", -100, 400, "mmHg", "#dc2626")
        self.window.venous_pressure_gauge = TankGauge("Ven", -50, 400, "mmHg", "#1640f9")
        self.window.arterial_pressure_gauge.setFixedSize(180, 451)
        self.window.venous_pressure_gauge.setFixedSize(180, 452)
        left_inner_layout.addWidget(self.window.arterial_pressure_gauge)
        left_inner_layout.addWidget(self.window.venous_pressure_gauge)

        left_layout_outer.addWidget(self.window.left_content)
        self.window.main_layout.addWidget(self.window.left_container, 1, 0, 2, 1)

        # ====================================================================
        # ===================== Right gauges (Temp + Conductivity) ===========
        # ====================================================================
        self.window.right_container = QWidget()  # CONTENEDOR DERECHO FIJO
        self.window.right_container.setFixedSize(180, 903)
        right_outer_layout = QVBoxLayout(self.window.right_container)
        right_outer_layout.setContentsMargins(0, 0, 0, 0)

        self.window.right_content = QWidget()  # CONTENEDOR DE WIDGETS
        self.window.right_content.setFixedSize(180, 903)
        right_inner_layout = QVBoxLayout(self.window.right_content)
        right_inner_layout.setContentsMargins(0, 0, 0, 0)
        right_inner_layout.setSpacing(0)

        self.window.dialysate_temp_gauge = TankGauge("Temp.", 0, 50, "°C", "#A31A1A")
        self.window.conductivity_bar = ConductivityBar()

        self.window.dialysate_temp_gauge.setFixedWidth(180)
        self.window.conductivity_bar.setFixedWidth(180)

        right_inner_layout.addWidget(self.window.dialysate_temp_gauge, 1)
        right_inner_layout.addWidget(self.window.conductivity_bar, 1)

        right_outer_layout.addWidget(self.window.right_content)
        self.window.main_layout.addWidget(self.window.right_container, 1, 5, 2, 1)

    build = setup_ui

    def _update_gauges(self):
        current_values = getattr(self.window, "current_values", None) or {}
        gauge_mapping = {
            "bloodArteryPressureData": getattr(self.window, "arterial_pressure_gauge", None),
            "bloodVenousPressureData": getattr(self.window, "venous_pressure_gauge", None),
            "dialyTempIFProcessData": getattr(self.window, "dialysate_temp_gauge", None),
            "dialyCondVariableData": getattr(self.window, "conductivity_bar", None),
        }
        for tag, gauge in gauge_mapping.items():
            if gauge is not None:
                if tag == "dialyTempIFProcessData":
                    if hasattr(self.window, "_get_temperature_display_value"):
                        value = self.window._get_temperature_display_value()
                    elif getattr(self.window, "temp_readings", None):
                        value = getattr(self.window, "dialyTempIFProcessData_avg", 0.0)
                    else:
                        value = current_values.get("dialyTempIFProcessData", 0.0)
                else:
                    value = current_values.get(tag, 0.0)
                if value is None or value == "":
                    value = 0.0
                try:
                    gauge.setValue(value)
                except Exception as e:
                    logger.error(f"Error actualizando gauge {tag}: {e}")

    update_gauges = _update_gauges
    refresh = _update_gauges
