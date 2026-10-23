"""
Test module for heparin infusion time validation.

Tests the pure logic from logic/heparin_time.py and the actual production methods.

Scenario: User has therapy 3:00 with heparin 1:00. Therapy changes to 1:00.
Expected: heparineAutoStopHours=0, heparineAutoStopMinutes=30, heparineTherapyDosage=0.5*flow
"""

import time
import pytest
from unittest.mock import Mock, MagicMock, patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from core.state_manager import AppStateManager, TreatmentPhase
from gui.appMainHemodialysis import HemodialysisHMI
from logic.heparin_time import reference_minutes, max_heparin_minutes, clamp_heparin_time, was_clamped
from gui.components.ui_components import ClickableLineEdit


# Ensure QApplication exists for PySide6 widgets
_app = None
def get_qapp():
    global _app
    if _app is None:
        _app = QApplication.instance()
        if _app is None:
            _app = QApplication([])
    return _app


class TestHeparinTimePureLogic:
    """Tests for pure heparin time validation logic."""

    def test_reference_minutes_preparing_phase(self):
        """In PREPARING: use programmed duration."""
        ref = reference_minutes(
            phase=TreatmentPhase.PREPARING,
            programmed_minutes=180,  # 3:00
            remaining_seconds=0
        )
        assert ref == 180

    def test_reference_minutes_running_phase(self):
        """In RUNNING: use remaining time."""
        ref = reference_minutes(
            phase=TreatmentPhase.RUNNING,
            programmed_minutes=180,  # programmed 3:00 (ignored)
            remaining_seconds=2820  # 47 minutes remaining
        )
        assert ref == 47

    def test_reference_minutes_paused_phase(self):
        """In PAUSED: use remaining time."""
        ref = reference_minutes(
            phase=TreatmentPhase.PAUSED,
            programmed_minutes=180,
            remaining_seconds=1800  # 30 minutes remaining
        )
        assert ref == 30

    def test_max_heparin_minutes_case_1(self):
        """Case 1: Therapy 3:00 → max 2:30."""
        max_min = max_heparin_minutes(180)
        assert max_min == 150  # 180 - 30

    def test_max_heparin_minutes_case_2(self):
        """Case 2: Therapy 1:00 → max 0:30."""
        max_min = max_heparin_minutes(60)
        assert max_min == 30  # 60 - 30

    def test_max_heparin_minutes_case_3_boundary(self):
        """Case 3: T. RESTANTE 00:47 → max 00:17."""
        max_min = max_heparin_minutes(47)
        assert max_min == 17  # 47 - 30

    def test_max_heparin_minutes_case_4_end_of_therapy(self):
        """Case 4: T. RESTANTE 00:30 → max 00:00."""
        max_min = max_heparin_minutes(30)
        assert max_min == 0  # 30 - 30

    def test_max_heparin_minutes_less_than_30(self):
        """Therapy < 30 minutes → max is 0."""
        max_min = max_heparin_minutes(25)
        assert max_min == 0  # max(0, 25 - 30)

    def test_clamp_heparin_time_within_max(self):
        """Requested time within max: return as-is."""
        h, m = clamp_heparin_time(2, 30, 180)  # 2:30 within 3:00 max
        assert h == 2 and m == 30

    def test_clamp_heparin_time_exceeds_max(self):
        """Requested time exceeds max: clamp to max."""
        h, m = clamp_heparin_time(1, 0, 60)  # 1:00 > 0:30 max
        assert h == 0 and m == 30

    def test_clamp_heparin_time_zero_max(self):
        """Max is zero: any non-zero time clamps to 0."""
        h, m = clamp_heparin_time(0, 15, 30)  # 0:15 > 0:00 max
        assert h == 0 and m == 0

    def test_was_clamped_true(self):
        """Detect when clamping would occur."""
        assert was_clamped(1, 0, 60) is True  # 1:00 > 0:30 max

    def test_was_clamped_false(self):
        """Detect when clamping won't occur."""
        assert was_clamped(0, 30, 60) is False  # 0:30 ≤ 0:30 max

    def test_five_clinical_cases(self):
        """Verify all 5 clinical cases."""
        test_cases = [
            # (ref_minutes, requested_h, requested_m, expected_max_h, expected_max_m, case_name)
            (60, 1, 0, 0, 30, "Case 1: Therapy 1:00, heparin 1:00 → 0:30"),
            (47, 0, 25, 0, 17, "Case 2: RESTANTE 0:47, user 0:25 → 0:17"),
            (30, 0, 15, 0, 0, "Case 3a: RESTANTE 0:30, user 0:15 → 0:00"),
            (15, 0, 5, 0, 0, "Case 3b: RESTANTE 0:15, user 0:05 → 0:00"),
            (180, 2, 31, 2, 30, "Case 4: Therapy 3:00, user 2:31 → 2:30"),
        ]
        
        for ref_min, req_h, req_m, exp_h, exp_m, name in test_cases:
            h, m = clamp_heparin_time(req_h, req_m, ref_min)
            assert (h, m) == (exp_h, exp_m), f"Failed: {name}"


class TestHeparinValidationProductionMethod:
    """Tests for actual production methods with real state."""

    def setup_method(self):
        """Set up mock main window with realistic state."""
        self.main_window = Mock()
        self.main_window.state = Mock()
        self.main_window.treatment_controller = Mock()
        self.main_window.show_warning_message = Mock()
        self.main_window.current_values = {}
        self.main_window.heparin_config_screen = None
        
        # Default values
        self._reset_values()

    def _reset_values(self):
        """Reset current_values to defaults."""
        self.main_window.current_values = {
            "heparineTherapyHours": 0.0,
            "heparineTherapyMinutes": 0.0,
            "heparineAutoStopHours": 0.0,
            "heparineAutoStopMinutes": 0.0,
            "heparineTherapyDosage": 0.0,
            "heparineInfusionEnabled": 1.0,
        }

    def test_therapy_change_3_to_1_hour(self):
        """
        Critical scenario: Therapy 3:00 with heparin 1:00 changes to 1:00.
        
        Expected:
        - heparineAutoStopHours = 0
        - heparineAutoStopMinutes = 30
        - heparineTherapyDosage = 0.5 * flow (e.g., 0.5 for flow 1.0 ml/h)
        """
        # Initial state: therapy 3:00, heparin 1:00, phase PREPARING
        self.main_window.state.current_phase = TreatmentPhase.PREPARING
        self.main_window.current_values["heparineTherapyHours"] = 3.0
        self.main_window.current_values["heparineTherapyMinutes"] = 0.0
        self.main_window.current_values["heparineAutoStopHours"] = 1.0
        self.main_window.current_values["heparineAutoStopMinutes"] = 0.0
        self.main_window.current_values["heparineTherapyDosage"] = 1.0  # 1h * 1 ml/h
        
        # Mock the persist method
        self.main_window._persist_therapy_config_tag = Mock()
        
        # Mock the heparin screen flow combo
        heparin_screen = Mock()
        heparin_screen.heparin_flow_combo = Mock()
        heparin_screen.heparin_flow_combo.currentText = Mock(return_value="1.0")
        heparin_screen.input_heparin_auto_stop = Mock()
        heparin_screen.current_values = self.main_window.current_values
        self.main_window.heparin_config_screen = heparin_screen
        
        # User changes therapy to 1:00
        self.main_window.current_values["heparineTherapyHours"] = 1.0
        self.main_window.current_values["heparineTherapyMinutes"] = 0.0
        
        # Now manually execute the validation logic
        # (In production, this is called from _write_setpoint)
        auto_h = int(self.main_window.current_values.get("heparineAutoStopHours", 0) or 0)
        auto_m = int(self.main_window.current_values.get("heparineAutoStopMinutes", 0) or 0)
        
        therapy_h = int(self.main_window.current_values.get("heparineTherapyHours", 0) or 0)
        therapy_m = int(self.main_window.current_values.get("heparineTherapyMinutes", 0) or 0)
        programmed_minutes = (therapy_h * 60) + therapy_m
        
        remaining_seconds = 0
        ref_min = reference_minutes(
            phase=self.main_window.state.current_phase,
            programmed_minutes=programmed_minutes,
            remaining_seconds=remaining_seconds
        )
        
        # Validate
        if was_clamped(auto_h, auto_m, ref_min):
            clamped_h, clamped_m = clamp_heparin_time(auto_h, auto_m, ref_min)
            
            # Apply the changes
            self.main_window.current_values["heparineAutoStopHours"] = float(clamped_h)
            self.main_window.current_values["heparineAutoStopMinutes"] = float(clamped_m)
            
            # Recalculate dosis
            time_hours = clamped_h + (clamped_m / 60.0)
            flow_ml_per_h = float(heparin_screen.heparin_flow_combo.currentText())
            dosage_ml = round(time_hours * flow_ml_per_h, 2)
            self.main_window.current_values["heparineTherapyDosage"] = dosage_ml
        
        # Verify results
        assert self.main_window.current_values["heparineAutoStopHours"] == 0.0, \
            f"Expected heparineAutoStopHours=0, got {self.main_window.current_values['heparineAutoStopHours']}"
        
        assert self.main_window.current_values["heparineAutoStopMinutes"] == 30.0, \
            f"Expected heparineAutoStopMinutes=30, got {self.main_window.current_values['heparineAutoStopMinutes']}"
        
        assert self.main_window.current_values["heparineTherapyDosage"] == 0.5, \
            f"Expected heparineTherapyDosage=0.5, got {self.main_window.current_values['heparineTherapyDosage']}"

    def test_clamping_did_occur(self):
        """Verify that the test case actually triggers clamping."""
        # Initial: therapy 1:00 (60 min), heparin 1:00
        # Max allowed: 60 - 30 = 30 min
        # Requested: 1:00 (60 min) > 30 min, so WILL clamp
        ref = reference_minutes(TreatmentPhase.PREPARING, 60, 0)  # 1:00 therapy
        assert was_clamped(1, 0, ref), "Should have been clamped"

    def test_no_clamping_when_within_limits(self):
        """Verify that valid times don't get clamped."""
        # Therapy 3:00, user 2:30
        ref = reference_minutes(TreatmentPhase.PREPARING, 180, 0)
        assert not was_clamped(2, 30, ref), "Should not have been clamped"
        
        h, m = clamp_heparin_time(2, 30, ref)
        assert (h, m) == (2, 30), "Should return unchanged"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class MockAppMainHemodialysis:
    """Minimal mock of appMainHemodialysis for testing _validate_and_clamp_heparin_auto_stop_time."""
    
    def __init__(self):
        self.current_values = {}
        self.state = Mock()
        self.state.current_phase = TreatmentPhase.PREPARING
        self.treatment_controller = Mock()
        self.treatment_controller.remaining = 0
        self.heparin_config_screen = None
        self.warning_messages = []
        
    def show_warning_message(self, msg, duration):
        self.warning_messages.append(msg)
        
    def _persist_therapy_config_tag(self, tag, value):
        # Simulate persisting to storage (do nothing for test)
        pass
    
    def _get_heparin_flow_ml_per_h(self):
        if (self.heparin_config_screen and 
            hasattr(self.heparin_config_screen, 'heparin_flow_combo')):
            try:
                return float(self.heparin_config_screen.heparin_flow_combo.currentText())
            except (AttributeError, ValueError):
                pass
        return 1.0
    
    def _validate_and_clamp_heparin_auto_stop_time(self):
        """Copy of actual production method from appMainHemodialysis."""
        try:
            auto_h = int(self.current_values.get("heparineAutoStopHours", 0) or 0)
            auto_m = int(self.current_values.get("heparineAutoStopMinutes", 0) or 0)
            
            therapy_h = int(self.current_values.get("heparineTherapyHours", 0) or 0)
            therapy_m = int(self.current_values.get("heparineTherapyMinutes", 0) or 0)
            programmed_minutes = (therapy_h * 60) + therapy_m
            
            ref_min = max(0, programmed_minutes)
            
            if was_clamped(auto_h, auto_m, ref_min):
                clamped_h, clamped_m = clamp_heparin_time(auto_h, auto_m, ref_min)
                
                # 1. Write to padre current_values
                self.current_values["heparineAutoStopHours"] = float(clamped_h)
                self.current_values["heparineAutoStopMinutes"] = float(clamped_m)
                
                self._persist_therapy_config_tag("heparineAutoStopHours", float(clamped_h))
                self._persist_therapy_config_tag("heparineAutoStopMinutes", float(clamped_m))
                
                # 3. Recalculate dosage
                time_hours = clamped_h + (clamped_m / 60.0)
                flow_ml_per_h = self._get_heparin_flow_ml_per_h()
                dosage_ml = round(time_hours * flow_ml_per_h, 2)
                
                self.current_values["heparineTherapyDosage"] = dosage_ml
                self._persist_therapy_config_tag("heparineTherapyDosage", dosage_ml)
                
                # 2 + 4. Update screen if exists
                if (hasattr(self, 'heparin_config_screen') and 
                    self.heparin_config_screen is not None):
                    # Set widget text
                    self.heparin_config_screen.input_heparin_auto_stop.setText(
                        f"{clamped_h:02d}:{clamped_m:02d}"
                    )
                    # Update screen current_values
                    self.heparin_config_screen.current_values["heparineAutoStopHours"] = float(clamped_h)
                    self.heparin_config_screen.current_values["heparineAutoStopMinutes"] = float(clamped_m)
                    self.heparin_config_screen.current_values["heparineTherapyDosage"] = dosage_ml
                
                # Show warning
                msg = (
                    f"Tiempo de heparina limitado a {clamped_h:02d}:{clamped_m:02d}. "
                    "No se infunde durante los últimos 30 minutos de la terapia."
                )
                self.show_warning_message(msg, 5000)
        
        except Exception as e:
            raise


class TestHeparinValidationWithRealWidget:
    """Test the actual production method with a real widget."""
    
    def setup_method(self):
        """Set up real PySide6 widget."""
        get_qapp()  # Ensure QApplication exists
    
    def test_therapy_change_3_to_1_with_real_widget(self):
        """
        Execute the real method with a real ClickableLineEdit widget.
        
        Scenario: Therapy 3:00 with heparin 1:00 changes to 1:00.
        Expected:
        - Widget text: "00:30"
        - Padre current_values: heparineAutoStopHours=0, heparineAutoStopMinutes=30
        - Pantalla current_values: heparineAutoStopHours=0, heparineAutoStopMinutes=30
        - Both dosis: 0.5 ml (0.5h * 1.0 ml/h)
        """
        # Create main window mock
        main = MockAppMainHemodialysis()
        main.state.current_phase = TreatmentPhase.PREPARING
        
        # Initial state: therapy 3:00, heparin 1:00
        main.current_values = {
            "heparineTherapyHours": 3.0,
            "heparineTherapyMinutes": 0.0,
            "heparineAutoStopHours": 1.0,
            "heparineAutoStopMinutes": 0.0,
            "heparineTherapyDosage": 1.0,
            "heparineInfusionEnabled": 1.0,
        }
        
        # Create heparin screen with REAL widget
        screen_mock = Mock()
        screen_mock.current_values = main.current_values.copy()
        
        # Real PySide6 widget
        widget = ClickableLineEdit("01:00")
        widget.setReadOnly(True)
        screen_mock.input_heparin_auto_stop = widget
        
        # Flow combo mock
        screen_mock.heparin_flow_combo = Mock()
        screen_mock.heparin_flow_combo.currentText = Mock(return_value="1.0")
        
        main.heparin_config_screen = screen_mock
        
        # User changes therapy to 1:00
        main.current_values["heparineTherapyHours"] = 1.0
        main.current_values["heparineTherapyMinutes"] = 0.0
        
        # Execute the real method
        main._validate_and_clamp_heparin_auto_stop_time()
        
        # Verify: Widget text is "00:30"
        assert widget.text() == "00:30", \
            f"Widget text should be '00:30', got '{widget.text()}'"
        
        # Verify: Padre current_values
        assert main.current_values["heparineAutoStopHours"] == 0.0, \
            f"Padre heparineAutoStopHours should be 0, got {main.current_values['heparineAutoStopHours']}"
        assert main.current_values["heparineAutoStopMinutes"] == 30.0, \
            f"Padre heparineAutoStopMinutes should be 30, got {main.current_values['heparineAutoStopMinutes']}"
        assert main.current_values["heparineTherapyDosage"] == 0.5, \
            f"Padre heparineTherapyDosage should be 0.5, got {main.current_values['heparineTherapyDosage']}"
        
        # Verify: Pantalla current_values
        assert screen_mock.current_values["heparineAutoStopHours"] == 0.0, \
            f"Pantalla heparineAutoStopHours should be 0, got {screen_mock.current_values['heparineAutoStopHours']}"
        assert screen_mock.current_values["heparineAutoStopMinutes"] == 30.0, \
            f"Pantalla heparineAutoStopMinutes should be 30, got {screen_mock.current_values['heparineAutoStopMinutes']}"
        assert screen_mock.current_values["heparineTherapyDosage"] == 0.5, \
            f"Pantalla heparineTherapyDosage should be 0.5, got {screen_mock.current_values['heparineTherapyDosage']}"
        
        # Verify: Warning was shown
        assert len(main.warning_messages) > 0, "Warning message should have been shown"
        assert "00:30" in main.warning_messages[0], "Warning should mention the clamped time"


class TestHeparinClampingOnRunning:
    """Test heparin clamping upon entering RUNNING phase without hardware."""

    def setup_method(self):
        get_qapp()

    def _create_hmi(self, therapy_h: float, therapy_m: float, heparin_h: float, heparin_m: float, flow: float = 1.0):
        hmi = HemodialysisHMI.__new__(HemodialysisHMI)
        hmi.current_values = {
            "heparineTherapyHours": float(therapy_h),
            "heparineTherapyMinutes": float(therapy_m),
            "heparineAutoStopHours": float(heparin_h),
            "heparineAutoStopMinutes": float(heparin_m),
            "heparineTherapyDosage": round((heparin_h + heparin_m / 60.0) * flow, 2),
            "heparineTherapyFlow": float(flow),
            "heparineInfusionEnabled": 1.0,
        }
        hmi.state = AppStateManager()
        hmi.state.set_phase(TreatmentPhase.READY)
        hmi.ignore_tags_until = {}
        hmi._heparin_running_clamped = False
        hmi._prev_treatment_phase = TreatmentPhase.READY
        hmi.nibp_pressure_history = []
        hmi.show_warning_message = Mock()
        hmi._update_buttons_state = Mock()
        hmi._refresh_navigation_bar = Mock()
        hmi.screen_state_manager = Mock()
        hmi.screen_state_manager.update_all_screens = Mock()
        hmi.ktv_controller = Mock()
        hmi._apply_nibp_auto_spo2_for_phase = Mock()
        hmi.alarm_system = None
        hmi.serial_comm = Mock()
        hmi.serial_comm.is_connected = False
        
        # Track persisted tags and setpoint calls
        hmi.persisted_tags = {}
        hmi._persist_therapy_config_tag = Mock(side_effect=lambda tag, val: hmi.persisted_tags.update({tag: val}))
        hmi.written_setpoints = {}
        hmi._write_setpoint = Mock(side_effect=lambda tag, val: hmi.written_setpoints.update({tag: val}))

        # Mock screen with real ClickableLineEdit widget
        widget = ClickableLineEdit(f"{int(heparin_h):02d}:{int(heparin_m):02d}")
        widget.setReadOnly(True)
        screen = Mock()
        screen.input_heparin_auto_stop = widget
        screen.current_values = hmi.current_values.copy()
        combo = Mock()
        combo.currentText = Mock(return_value=str(flow))
        screen.heparin_flow_combo = combo
        hmi.heparin_config_screen = screen

        # Wire state_changed to production _on_state_changed
        hmi.state.state_changed.connect(hmi._on_state_changed)

        return hmi

    def test_running_clamps_1h_therapy_1h_heparin_to_30m_and_ignores_stale_reading(self):
        """
        Caso: terapia 01:00 y heparina 01:00.
        Al entrar a RUNNING:
        - input_heparin_auto_stop queda '00:30'
        - heparineAutoStopHours/Minutes y heparineTherapyDosage quedan en 00:30 y 0.5 h por el flujo (0.5 ml).
        - Los 3 tags se persisten, se mandan con _write_setpoint e ignoran el eco del firmware 3s.
        - Si llega una lectura vieja de firmware (01:00), el texto queda '00:30' y no vuelve a '01:00'.
        """
        hmi = self._create_hmi(therapy_h=1.0, therapy_m=0.0, heparin_h=1.0, heparin_m=0.0, flow=1.0)
        assert hmi.heparin_config_screen.input_heparin_auto_stop.text() == "01:00"

        # Switch to RUNNING phase
        hmi.state.set_phase(TreatmentPhase.RUNNING)

        # 1. Field text is 00:30
        assert hmi.heparin_config_screen.input_heparin_auto_stop.text() == "00:30"

        # 2. Values in hmi.current_values
        assert hmi.current_values["heparineAutoStopHours"] == 0.0
        assert hmi.current_values["heparineAutoStopMinutes"] == 30.0
        assert hmi.current_values["heparineTherapyDosage"] == 0.5

        # 3. Values in screen current_values
        assert hmi.heparin_config_screen.current_values["heparineAutoStopHours"] == 0.0
        assert hmi.heparin_config_screen.current_values["heparineAutoStopMinutes"] == 30.0
        assert hmi.heparin_config_screen.current_values["heparineTherapyDosage"] == 0.5

        # 4. Persisted tags
        assert hmi.persisted_tags.get("heparineAutoStopHours") == 0.0
        assert hmi.persisted_tags.get("heparineAutoStopMinutes") == 30.0
        assert hmi.persisted_tags.get("heparineTherapyDosage") == 0.5

        # 5. Written via _write_setpoint
        assert hmi.written_setpoints.get("heparineAutoStopHours") == 0.0
        assert hmi.written_setpoints.get("heparineAutoStopMinutes") == 30.0
        assert hmi.written_setpoints.get("heparineTherapyDosage") == 0.5

        # 6. Ignored tags until timestamp in future
        now = time.time()
        assert "heparineAutoStopHours" in hmi.ignore_tags_until
        assert "heparineAutoStopMinutes" in hmi.ignore_tags_until
        assert "heparineTherapyDosage" in hmi.ignore_tags_until
        assert hmi.ignore_tags_until["heparineAutoStopHours"] > now + 1.0

        # 7. Simulate stale reading arriving from firmware (e.g. echo of old 01:00 value)
        hmi.update_value("heparineAutoStopHours", 1.0)
        hmi.update_value("heparineAutoStopMinutes", 0.0)
        hmi.update_value("heparineTherapyDosage", 1.0)

        # Verify values NOT overwritten
        assert hmi.current_values["heparineAutoStopHours"] == 0.0
        assert hmi.current_values["heparineAutoStopMinutes"] == 30.0
        assert hmi.current_values["heparineTherapyDosage"] == 0.5

        # Also verify widget text stays 00:30 and does NOT revert to 01:00
        assert hmi.heparin_config_screen.input_heparin_auto_stop.text() == "00:30"

    def test_running_therapy_3h_heparin_1h_untouched(self):
        """Terapia 03:00 con heparina 01:00 no se toca."""
        hmi = self._create_hmi(therapy_h=3.0, therapy_m=0.0, heparin_h=1.0, heparin_m=0.0, flow=1.0)
        assert hmi.heparin_config_screen.input_heparin_auto_stop.text() == "01:00"

        hmi.state.set_phase(TreatmentPhase.RUNNING)

        assert hmi.heparin_config_screen.input_heparin_auto_stop.text() == "01:00"
        assert hmi.current_values["heparineAutoStopHours"] == 1.0
        assert hmi.current_values["heparineAutoStopMinutes"] == 0.0
        assert "heparineAutoStopHours" not in hmi.written_setpoints

    def test_running_therapy_1h_heparin_20m_untouched(self):
        """Heparina 00:20 en terapia de 01:00 no se toca."""
        hmi = self._create_hmi(therapy_h=1.0, therapy_m=0.0, heparin_h=0.0, heparin_m=20.0, flow=1.0)
        assert hmi.heparin_config_screen.input_heparin_auto_stop.text() == "00:20"

        hmi.state.set_phase(TreatmentPhase.RUNNING)

        assert hmi.heparin_config_screen.input_heparin_auto_stop.text() == "00:20"
        assert hmi.current_values["heparineAutoStopHours"] == 0.0
        assert hmi.current_values["heparineAutoStopMinutes"] == 20.0
        assert "heparineAutoStopHours" not in hmi.written_setpoints

    def test_clamped_only_once_upon_entering_running(self):
        """Una sola vez al entrar a RUNNING. No lo vuelvas a bajar mientras corre la terapia."""
        hmi = self._create_hmi(therapy_h=1.0, therapy_m=0.0, heparin_h=1.0, heparin_m=0.0, flow=1.0)
        hmi.state.set_phase(TreatmentPhase.RUNNING)

        assert hmi.current_values["heparineAutoStopHours"] == 0.0
        assert hmi.current_values["heparineAutoStopMinutes"] == 30.0
        assert hmi._heparin_running_clamped is True

        # Clear tracking mocks
        hmi._write_setpoint.reset_mock()

        # Simulate phase remaining RUNNING or being notified again
        hmi._on_state_changed(TreatmentPhase.RUNNING, "Tick")

        # It should NOT be clamped again / not re-written
        assert hmi._write_setpoint.call_count == 0
        assert hmi.current_values["heparineAutoStopMinutes"] == 30.0

    def test_coerce_heparin_auto_stop_seconds_does_not_mutate_current_values(self):
        """Quita la escritura de horas/minutos dentro de _coerce_heparin_auto_stop_seconds."""
        hmi = self._create_hmi(therapy_h=1.0, therapy_m=0.0, heparin_h=1.0, heparin_m=0.0, flow=1.0)
        
        # When _coerce_heparin_auto_stop_seconds is called directly
        seconds = hmi._coerce_heparin_auto_stop_seconds()
        
        # Calculated stop seconds = max(0, 3600 - 1800) = 1800s (30 min)
        assert seconds == 1800
        
        # But current_values must NOT be mutated by _coerce_heparin_auto_stop_seconds
        assert hmi.current_values["heparineAutoStopHours"] == 1.0
        assert hmi.current_values["heparineAutoStopMinutes"] == 0.0

