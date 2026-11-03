"""
Pure logic for start checklist validation.

Validates that all required parameters are configured before starting therapy.
No side effects, no I/O, no phase checking.
"""


def missing_start_items(values: dict) -> list[str]:
    """
    Check which required items are missing or invalid for therapy start.
    
    Args:
        values: Dictionary of current parameter values
    
    Returns:
        List of missing/invalid item descriptions, in validation order.
        Empty list if all required items are present and valid.
    
    Validation order:
        1. patient_id
        2. patient_name
        3. bloodFlowControlSetPoint (Qb)
        4. balanceChamberSetTiming (Qd)
        5. dialyTempControlSetPoint (temperature)
        6. dialyCondControlSetPoint (conductivity)
        7. heparineTherapyHours and heparineTherapyMinutes (therapy time)
        8. heparineSyringeVolume (if heparin infusion enabled)
        9. heparineAutoStopHours and heparineAutoStopMinutes (if heparin infusion enabled)
    
    Notes:
        - None and empty string both count as missing
        - Does not check UF flow, access, allergies, or Kt/V
        - balanceChamberSetTiming is Qd; no conversion is performed
        - Heparin infusion time is only required if heparineInfusionEnabled != 0
    """
    missing = []
    
    # 1. Check patient_id
    patient_id = values.get("patient_id")
    if not patient_id:
        missing.append("Falta el paciente")
    
    # 2. Check patient_name
    patient_name = values.get("patient_name")
    if not patient_name:
        missing.append("Falta el nombre del paciente")
    
    # 3. Check bloodFlowControlSetPoint (Qb)
    blood_flow = values.get("bloodFlowControlSetPoint")
    if blood_flow is None or blood_flow == "" or blood_flow <= 0:
        missing.append("Falta el flujo de sangre (Qb)")
    
    # 4. Check balanceChamberSetTiming (Qd)
    chamber_timing = values.get("balanceChamberSetTiming")
    if chamber_timing is None or chamber_timing == "" or chamber_timing <= 0:
        missing.append("Falta el flujo de dializante (Qd)")
    
    # 5. Check dialyTempControlSetPoint (temperature)
    temp = values.get("dialyTempControlSetPoint")
    if temp is None or temp == "" or temp <= 0:
        missing.append("Falta la temperatura")
    
    # 6. Check dialyCondControlSetPoint (conductivity)
    conductivity = values.get("dialyCondControlSetPoint")
    if conductivity is None or conductivity == "" or conductivity <= 0:
        missing.append("Falta la conductividad")
    
    # 7. Check heparineTherapyHours and heparineTherapyMinutes (therapy time)
    therapy_hours = values.get("heparineTherapyHours", 0)
    therapy_minutes = values.get("heparineTherapyMinutes", 0)
    
    try:
        therapy_hours = int(therapy_hours) if therapy_hours is not None else 0
        therapy_minutes = int(therapy_minutes) if therapy_minutes is not None else 0
    except (ValueError, TypeError):
        therapy_hours = 0
        therapy_minutes = 0
    
    if therapy_hours == 0 and therapy_minutes == 0:
        missing.append("Falta el tiempo de terapia")
    
    # 8. Check heparineSyringeVolume if heparin infusion is enabled
    heparin_enabled = values.get("heparineInfusionEnabled")
    # None or 1 means enabled; 0 means disabled
    if heparin_enabled != 0:
        syringe_volume = values.get("heparineSyringeVolume")
        if syringe_volume is None or syringe_volume == "" or syringe_volume <= 0:
            missing.append("Falta el volumen de heparina en la jeringa")
        
        # 9. Check heparineAutoStopHours and heparineAutoStopMinutes (infusion time)
        # Only if heparin infusion is enabled
        infusion_hours = values.get("heparineAutoStopHours")
        infusion_minutes = values.get("heparineAutoStopMinutes")
        
        try:
            infusion_hours = int(infusion_hours) if infusion_hours is not None else 0
            infusion_minutes = int(infusion_minutes) if infusion_minutes is not None else 0
        except (ValueError, TypeError):
            infusion_hours = 0
            infusion_minutes = 0
        
        if infusion_hours == 0 and infusion_minutes == 0:
            missing.append("Falta el tiempo de infusión de heparina")
    
    return missing
