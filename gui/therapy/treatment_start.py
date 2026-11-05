import logging
from PySide6.QtCore import QDateTime, QTimer

from core.state_manager import TreatmentPhase
from gui.components.floating_confirm import FloatingConfirmDialog
from logic.start_checklist import missing_start_items

logger = logging.getLogger(__name__)


class TreatmentStart:
    def __init__(self, window):
        self.window = window

    def start_treatment(self):
        """
        Delegado seguro con validación de checklist.
        
        - Si fase es PAUSED: procede a reanudar sin validación
        - Si fase es READY: valida items requeridos, muestra faltas o diálogo de confirmación
        - Si fase es RUNNING: retorna sin hacer nada
        """
        if getattr(self.window, '_start_treatment_locked', False):
            return
        self.window._start_treatment_locked = True

        try:
            logger.info("=== BOTÓN INICIAR TRATAMIENTO PRESIONADO ===")
            
            if self.window.state.current_phase == TreatmentPhase.RUNNING:
                return
            
            # Si es PAUSED: proceder sin validación (es reanudar)
            if self.window.state.current_phase == TreatmentPhase.PAUSED:
                success = self.window.treatment_controller.start_treatment()
                if success:
                    self.window._update_therapy_time_displays()
                    self.window._refresh_navigation_bar()
                    self.window.screen_state_manager.update_all_screens(self.window.state.current_phase)
                return
            
            # Si es READY: validar checklist
            if self.window.state.current_phase == TreatmentPhase.READY:
                missing = missing_start_items(self.window.current_values)
                
                if missing:
                    # Mostrar faltas una por línea
                    msg = "\n".join(missing)
                    self.window.show_warning_message(msg, 4500)
                    return
                
                # Lista completa: mostrar diálogo de confirmación
                self.window._show_start_confirmation_dialog()
                return
            
        finally:
            self.window._start_treatment_locked = False

    def _show_start_confirmation_dialog(self):
        """
        Muestra diálogo flotante de confirmación antes de iniciar tratamiento.
        
        Muestra:
        - Paciente
        - Qb en mL/min
        - Temperatura
        - Conductividad
        - Tiempo de terapia (H:MM)
        - Qd como "programado"
        - Infusión de heparina (H:MM) si está encendida
        - UF en L/h (si existe, ya en L/h; mostrar con dos decimales)
        - Volumen jeringa si heparina encendida
        """
        dialog = FloatingConfirmDialog(self.window)
        
        # Construir texto de confirmación
        lines = []
        
        # Paciente
        patient_name = self.window.current_values.get("patient_name", "")
        if patient_name:
            lines.append(f"Paciente: {patient_name}")
        
        # Qb en mL/min
        qb = self.window.current_values.get("bloodFlowControlSetPoint")
        if qb:
            lines.append(f"Qb: {qb} mL/min")
        
        # Temperatura
        temp = self.window.current_values.get("dialyTempControlSetPoint")
        if temp:
            lines.append(f"Temperatura: {temp}°C")
        
        # Conductividad
        cond = self.window.current_values.get("dialyCondControlSetPoint")
        if cond:
            lines.append(f"Conductividad: {cond} mS/cm")
        
        # Tiempo de terapia (H:MM)
        therapy_h = int(self.window.current_values.get("heparineTherapyHours", 0) or 0)
        therapy_m = int(self.window.current_values.get("heparineTherapyMinutes", 0) or 0)
        lines.append(f"Tiempo de terapia: {therapy_h}:{therapy_m:02d}")
        
        # Qd como "programado"
        lines.append("Qd: Programado")
        
        # Infusión de heparina si está encendida (H:MM)
        heparin_enabled = self.window.current_values.get("heparineInfusionEnabled")
        if heparin_enabled != 0:
            infusion_h = int(self.window.current_values.get("heparineAutoStopHours", 0) or 0)
            infusion_m = int(self.window.current_values.get("heparineAutoStopMinutes", 0) or 0)
            lines.append(f"Infusión de heparina: {infusion_h}:{infusion_m:02d}")
        
        # UF en L/h (ya está en L/h, solo mostrar con dos decimales)
        uf_l_h = self.window.current_values.get("ultraFilterPumpSpeed")
        if uf_l_h is not None:
            lines.append(f"UF: {float(uf_l_h):.2f} L/h")
        
        # Volumen jeringa si heparina encendida
        if heparin_enabled != 0:
            syringe_vol = self.window.current_values.get("heparineSyringeVolume")
            if syringe_vol:
                lines.append(f"Volumen jeringa: {syringe_vol} mL")
        
        confirmation_text = "\n".join(lines)
        
        # Mostrar diálogo
        confirmed = dialog.show_confirm(
            text=confirmation_text,
            accept_text="Iniciar",
            cancel_text="Cancelar"
        )
        
        # Si se confirma, proceder con el arranque
        if confirmed:
            success = self.window.treatment_controller.start_treatment()
            if success:
                self.window._update_therapy_time_displays()
                self.window._refresh_navigation_bar()
                self.window.screen_state_manager.update_all_screens(self.window.state.current_phase)

    def _show_filter_fill_dialog_main(self):
        """
        Muestra diálogo modal para confirmación de llenado de filtro.
        Llamado desde primingProcessStatus = 7 con QTimer.singleShot.
        
        Flujo:
        1. Primer diálogo: "Coloque el filtro..." (solo Aceptar, sin Cancelar)
        2. Si acepta → Segundo diálogo: "¿Confirma...?" (Aceptar + Cancelar)
           - Aceptar: manda dialyFilterFillButton=True, llama _start_filter()
           - Cancelar: vuelve al primer diálogo
        """
        def show_first_dialog():
            """Primer paso: instrucción simple sin Cancel (botón oculto)"""
            dialog = FloatingConfirmDialog(self.window)
            
            # Ocultar el botón Cancel antes de mostrar el diálogo
            if hasattr(dialog, 'btn_cancel'):
                dialog.btn_cancel.setVisible(False)
            
            confirmed = dialog.show_confirm(
                text="Coloque el filtro. Cuando esté colocado, presione Aceptar.",
                accept_text="Aceptar",
                cancel_text="Cancelar"  # Texto presente pero botón oculto
            )
            
            if not confirmed:
                # Usuario no presionó Aceptar; reintentar
                QTimer.singleShot(100, show_first_dialog)
                return
            
            # Aceptar → mostrar segundo diálogo
            show_second_dialog()
        
        def show_second_dialog():
            """Segundo paso: confirmación con opción de cancelar"""
            dialog = FloatingConfirmDialog(self.window)
            
            # Mostrar el botón Cancel en el segundo diálogo
            if hasattr(dialog, 'btn_cancel'):
                dialog.btn_cancel.setVisible(True)
            
            confirmed = dialog.show_confirm(
                text="¿Confirma que el filtro ya está colocado?",
                accept_text="Aceptar",
                cancel_text="Cancelar"
            )
            
            if confirmed:
                # Aceptar: ejecutar el llenado
                self.window._write_boolean_command("dialyFilterFillButton", True)
                self.window._start_filter()
                logger.info("Llenado de filtro confirmado por usuario")
            else:
                # Cancelar: volver al primer diálogo
                logger.info("Usuario canceló; mostrando primer diálogo nuevamente")
                QTimer.singleShot(100, show_first_dialog)
        
        # Iniciar con el primer diálogo
        show_first_dialog()

    def _can_start_treatment(self) -> bool:
        """Lógica centralizada para habilitar Iniciar / Reanudar"""
        phase = self.window.state.current_phase
    
        # 1. Filtro rápido de fase
        if phase not in (TreatmentPhase.READY, TreatmentPhase.PAUSED):
            return False

        # 2. Verificación de condiciones físicas (necesarias para ambos estados)
        temp_actual = self.window.current_values.get("dialyTempIFProcessData", 0.0)
        temp_set    = self.window.current_values.get("dialyTempControlSetPoint", 0.0)
        cond_actual = self.window.current_values.get("dialyCondVariableData", 0.0)
        cond_set    = self.window.current_values.get("dialyCondControlSetPoint", 0.0)

        # Rango: Setpoint -1.5 hasta +3.0
        temp_ok = (temp_set - 5 <= temp_actual <= temp_set + 3.0)
        cond_ok = abs(cond_actual - cond_set) <= 2.0
        fisica_ok = temp_ok and cond_ok

        # 3. Lógica según fase
        if phase == TreatmentPhase.PAUSED:
            return fisica_ok

        if phase == TreatmentPhase.READY:
            # Si no se ha iniciado el proceso de llenado, bloqueamos
            if not self.window.filter_fill_waiting or self.window.filter_fill_start_time is None:
                return False
            
            # Verificar tiempo transcurrido
            elapsed = self.window.filter_fill_start_time.secsTo(QDateTime.currentDateTime())
            if elapsed < self.window.MIN_FILTER_FILL_WAIT_SECONDS:
                return False
        
            # Si pasó el tiempo y la física está OK, permitimos iniciar
            return fisica_ok

        return False

    def _start_filter(self):
        """Solo inicia el conteo de 90 segundos (NO verifica)"""
        try:                    
            self.window.filter_fill_start_time = QDateTime.currentDateTime()
            self.window.filter_fill_waiting = True
            logger.info(
                "[FILTER] Conteo de llenado iniciado a las %s",
                self.window.filter_fill_start_time.toString("HH:mm:ss"),
            )
        except Exception as e:
            logger.error(f"Error en _start_filter: {e}", exc_info=True)

    def _reset_filter_fill_flags(self):
        """Reinicia las banderas del llenado de filtro"""
        self.window.filter_fill_start_time = None
        self.window.filter_fill_waiting = False
        logger.info("Flags de llenado de filtro reiniciados")

    def _update_header_during_filter_fill(self):
        """
        Actualiza el encabezado cada segundo durante la espera de 90 s después del llenado de filtro.
        - Si estamos en estado 13 (READY) y aún no se cumplieron los 90 s: "PREPARANDO..."
        - Si ya pasaron los 90 s y _can_start_treatment() es True: "LISTO PARA\nINICIAR"
        - Si el estado deja de ser 13, no pisa el texto del mapa (hardware_state_mapper es la fuente de verdad)
        """
        # Solo actuar si estamos en estado 13 (READY)
        if self.window._last_priming_status != 13:
            return
        
        # Verificar si el hardware_mapper está disponible
        if not hasattr(self.window, "hardware_mapper") or self.window.hardware_mapper is None:
            return
        
        # Verificar si el label del encabezado está disponible
        if not hasattr(self.window, "current_process_status") or self.window.current_process_status is None:
            return
        
        # Si no estamos en la espera del llenado, no hacer nada
        if not self.window.filter_fill_waiting or self.window.filter_fill_start_time is None:
            return
        
        # Calcular tiempo transcurrido desde el inicio del llenado
        elapsed = self.window.filter_fill_start_time.secsTo(QDateTime.currentDateTime())
        
        # Determinar el texto que debe mostrar el encabezado
        if elapsed < self.window.MIN_FILTER_FILL_WAIT_SECONDS:
            # Aún no se han cumplido los 90 segundos: mostrar "PREPARANDO..."
            desired_text = "PREPARANDO..."
        elif self.window._can_start_treatment():
            # Ya pasaron los 90 s y se pueden iniciar condiciones: mostrar "LISTO PARA\nINICIAR"
            desired_text = "LISTO PARA\nINICIAR"
        else:
            # Pasaron los 90 s pero aún no hay condiciones de inicio: mantener "PREPARANDO..."
            desired_text = "PREPARANDO..."
        
        # Actualizar el encabezado si el texto es diferente
        current_text = self.window.current_process_status.text()
        if current_text != desired_text:
            self.window.current_process_status.setText(desired_text)
