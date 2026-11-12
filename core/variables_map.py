#core/variables_map.py

"""
Módulo para el mapeo centralizado de todas las variables del sistema de hemodiálisis.

Este módulo define la estructura y metadatos de todas las variables (sensores,
actuadores, setpoints, flags de estado) utilizadas en la máquina de hemodiálisis.
Sirve como una fuente única de verdad para la interfaz de usuario (GUI),
el sistema de comunicación serial, el sistema de alarmas y cualquier
otro componente que necesite interactuar con los datos del controlador.

Proporciona definiciones detalladas, incluyendo:
- Nombre descriptivo
- Etiqueta corta para UI
- Tipo de dato (booleano, double, int, string)
- Acceso de lectura/escritura (read/write - rw)
- Unidades de medida
- Límites de operación o alarma
- Tag único para identificación programática

Estructuras de Datos Principales:
----------------------------------
1.  **`VARIABLES` (Dict[int, Dict[int, Dict[str, Any]]])**:
    - Es el diccionario principal que organiza todas las variables.
    - La primera clave `int` representa el **Código de Grupo Modbus** (ej. `0x01` para Booleanos de Operación, `0x02` para Parámetros Clínicos, etc.).
    - La segunda clave `int` es la **Dirección/ID** de la variable dentro de ese grupo.
    - El valor asociado es un diccionario con los metadatos de la variable:
        - `name` (str): Nombre completo descriptivo de la variable.
        - `label` (str): Etiqueta corta para mostrar en la UI.
        - `type` (str): Tipo de dato (`"bool"`, `"double"`, `"int"`, `"string"`).
        - `rw` (bool): `True` si es de lectura/escritura, `False` si es solo de lectura.
        - `unit` (str): Unidades de medida (ej. "mmHg", "°C", "ml/min").
        - `limites` (Tuple[float, float], optional): Tupla `(min_val, max_val)` para validación o alarmas. `None` si no aplica.
        - `tag` (str): Identificador único de cadena para la variable, crucial para el intercambio de datos entre módulos.
        - `nivel` (str): Nivel de severidad para alarmas (ej. "rojo", "amarillo", "cian"), usado por el sistema de alarmas.
        - `id` (int, solo para booleanos): ID directo para booleanos dentro de su grupo.
        - `value` (Any, opcional): Valor inicial (usado para `patternCondRaw`).
        - `description` (str, opcional): Descripción adicional.

2.  **`ANALOG_MAP` (List[Tuple[int, int]])**:
    - Una lista ordenada de tuplas `(group_code, address_in_group)` que define
      el orden y la ubicación de las variables analógicas en una trama de
      lectura masiva Modbus. Esto es utilizado por `SerialCommunication` para
      parsear eficientemente los datos recibidos.

3.  **`TVAR_TO_GROUP` (Dict[int, str])**:
    - Mapeo de códigos de grupo Modbus a nombres legibles de grupo.
      Facilita la organización visual de las variables en la UI (ej. en el
      monitor de variables en tiempo real).

Rol en el Sistema:
------------------
- **Consistencia**: Garantiza que todos los módulos de la aplicación utilicen
  la misma definición y semántica para cada variable.
- **Mantenibilidad**: Simplifica la adición o modificación de variables sin
  necesidad de cambiar código en múltiples lugares de la aplicación.
- **Configuración de Alarmas**: Proporciona los límites (`limites`) y niveles
  de severidad (`nivel`) para el sistema de alarmas.
- **Comunicación Serial**: Define los tags y direcciones para el envío y
  recepción de datos con el controlador.
- **Interfaz de Usuario**: Suministra los nombres, etiquetas y unidades
  para la representación de datos en la GUI.

Uso:
----
Importar `VARIABLES`, `ANALOG_MAP` y `TVAR_TO_GROUP` en los módulos que
necesiten acceder a la configuración de las variables del sistema.

Ejemplo:
`from core.variables_map import VARIABLES`
`temperatura_label = VARIABLES[0x04][0x0D]["label"]`
"""

from typing import Dict, List, Tuple, Any

import logging
logger = logging.getLogger(__name__)

# ================================================================
# MAPEO COMPLETO DE VARIABLES - HEMODIÁLISIS
# ================================================================

VARIABLES: Dict[int, Dict[int, Dict[str, Any]]] = {

    # ================================================================
    # BOOLEANOS OPERACIÓN (0x01) - 60 variables (0x00 a 0x3B)
    # ================================================================
    0x01: {
        **{i: {"name": name, "label": label,"type": "bool", "rw": True, "nivel": nivel, "tag": tag, "id": i}
            for i, (name, label, nivel, tag) in enumerate([
                # --- VARIABLES DE CONTROL (ESCRITURA/LECTURA) - ID 0 a 40 (RW=True) ---
                
                ("Bomba peristáltica - Arranque", "INICIAR B.S.", "cian", "bloodPumpStartButton"),      # 0  no mostrar en catalogo
                ("Bomba peristáltica - Paro", "PARAR B.S.", "cian", "bloodPumpStopButton"),             # 1  no mostrar en catalogo
                ("Bomba peristáltica - Avance", "FWD B.S.", "cian", "bloodPumpFWDButton"),              # 2  no mostrar en catalogo
                ("Bomba peristáltica - Reversa", "BCK B.S.", "cian", "bloodPumpREVButton"),             # 3  no mostrar en catalogo
                ("Bomba de purga - Arranque", "INICIAR PURGA", "cian", "dialyserPumpStartButton"),      # 4  no mostrar en catalogo
                ("Bomba de purga - Paro", "PARAR PURGA", "cian", "dialyserPumpStopButton"),             # 5  no mostrar en catalogo
                ("Bomba Heparina - Arranque", "INIC. HEPARINA", "cian", "heparinePumpsStartButton"),    # 6  no mostrar en catalogo
                ("Bomba Heparina - Paro", "PARAR HEPARINA", "cian", "heparinePumpsStopButton"),         # 7  no mostrar en catalogo
                ("Bomba Heparina - Avance", "FWD HEPARINA", "cian", "heparinePumpFWDButton"),           # 8  no mostrar en catalogo
                ("Bomba Heparina - Reversa", "REV HEPARINA", "cian", "heparinePumpREVButton"),          # 9  no mostrar en catalogo
                ("Control Flujo Sangre - Habilitar", "HAB. CTRL FLUJO", "cian", "bloodControlLoopEnable"), # 10  no mostrar en catalogo
                ("Control Flujo Sangre - Auto/Manual", "AUTO/MAN FLUJO", "cian", "bloodControlLoopMode"),  # 11  no mostrar en catalogo
                ("Control Conductividad - Habilitar", "HAB. CTRL COND", "cian", "dialyCondCtrlLoopEnable"),# 12  no mostrar en catalogo
                ("Control Conductividad - Auto/Manual", "AUTO/MAN COND", "cian", "dialyCondCtrlLoopMode"), # 13  no mostrar en catalogo
                ("Control Temp Dializante - Habilitar", "HAB. CTRL TEMP", "cian", "dialyTempCtrlLoopEnable"),# 14  no mostrar en catalogo
                ("Control Temp Dializante - Auto/Manual", "AUTO/MAN TEMP", "cian", "dialyTempCtrlLoopMode"), # 15  no mostrar en catalogo
                ("Bomba Heparina - Home", "HOME HEPARINA", "cian", "heparinePumpHomePosition"),         # 16  no mostrar en catalogo
                ("Cámara Balance - Start", "INICIO CAM.BAL", "cian", "dialiserBalChambStrButt"),        # 17  no mostrar en catalogo
                ("Cámara Balance - Stop", "PARO CAM.BAL", "cian", "dialiserBalChambStpButt"),           # 18  no mostrar en catalogo
                ("Bolo Heparina", "BOLO HEPARINA", "cian", "heparinApplyBolusDose"),                    # 19  no mostrar en catalogo
                ("Pausar/Continuar", "PAUSA/CONT.", "cian", "heparineOperPauseResume"),                 # 20  no mostrar en catalogo
                ("Operar Elementos Dializante", "ELEM. DIALIZ.", "cian", "dialyCircuitElementsOpSel"),  # 21  no mostrar en catalogo
                ("Bomba Purga Dializante - Start", "INI PURGA DIAL", "cian", "dialyPurgePumpStartButt"), # 22  no mostrar en catalogo
                ("Bomba Purga Dializante - Stop", "FIN PURGA DIAL", "cian", "dialyPurgePumpStopButt"),   # 23  no mostrar en catalogo
                ("Bomba UF - Start", "INICIAR UF", "cian", "dialyUltraFPumpStartButt"),                 # 24  no mostrar en catalogo
                ("Bomba UF - Stop", "PARAR UF", "cian", "dialyUltraFPumpStoptButt"),                    # 25  no mostrar en catalogo
                ("Bomba Bicarbonato - Start", "INI BICARBONATO", "cian", "dialyBicarbonPumpStartButt"), # 26  no mostrar en catalogo
                ("Bomba Bicarbonato - Stop", "FIN BICARBONATO", "cian", "dialyBicarbonPumpStopButt"),   # 27  no mostrar en catalogo
                ("Bomba Ácido Cítrico - Start", "INI AC.CITRICO", "cian", "dialyCitricAcPumpStartButt"),# 28  no mostrar en catalogo
                ("Bomba Ácido Cítrico - Stop", "FIN AC.CITRICO", "cian", "dialyCitricAcPumpStopButt"),  # 29  no mostrar en catalogo
                ("Válvula Agua Entrada", "VALV ENTRADA", "cian", "dialyWaterInletValveButt"),           # 30
                ("Válvula Recirculación", "VALV RECIRCUL", "cian", "dialyRecirculatValveButt"),         # 31
                ("Válvula Cámara Caliente", "VALV CAM.CAL.", "cian", "dialyHotChambValveButt"),         # 32
                ("Válvula Venteo Aire", "VALV VENTEO", "cian", "dialyAirVentSepChambButt"),             # 33
                ("Válvula Bypass Filtro", "VALV BYPASS", "cian", "dialyBypassFilterButt"),              # 34
                ("Válvula Corte Entrada Filtro", "CORTE ENT FILT", "cian", "dialyInputFilterCutButt"),  # 35
                ("Válvula Corte Salida Filtro", "CORTE SAL FILT", "cian", "dialyOutputFilterCutButt"),  # 36
                ("Válvula de Drenaje", "VALV DRENAJE", "cian", "dialyWaterDrainValveButt"),             # 37
                ("Fin de Ciclo Cámara Balance", "FIN CICLO BAL", "amarillo", "dialyBalanceChambCycleEnd"),# 38 no mostrar en catalogo
                ("Iniciar Diálisis", "INICIO DIALISIS", "cian", "dialyStartDialysisButt"),              # 39 no mostrar en catalogo
                ("Parar Diálisis", "PARO DIALISIS", "cian", "dialyStopDialysisButt"),                   # 40 no mostrar en catalogo
                ("Protección Resistores Calefactor", "PROT CALEFACTOR", "cian", "watterTankHeaterProtect"), # 41     alarma que se activa constantemente pero no importante para usuario
                ("Disponible para Función Digital 3", "RESERVA 3", "cian", "availableBoolVariable1"),       # 42  no mostrar en catalogo
                ("Disponible para Función Digital 4", "RESERVA 4", "cian", "availableBoolVariable2"),       # 43  no mostrar en catalogo
                ("Disponible para Función Digital 5", "RESERVA 5", "cian", "availableBoolVariable3"),       # 44  no mostrar en catalogo
                ("Disponible para Función Digital 6", "RESERVA 6", "cian", "availableBoolVariable4"),       # 45  no mostrar en catalogo
                ("Disponible para Función Digital 7", "RESERVA 7", "cian", "availableBoolVariable5"),       # 46  no mostrar en catalogo
                ("Disponible para Función Digital 8", "RESERVA 8", "cian", "availableBoolVariable6"),       # 47
                ("Detector Burbuja Aire en Sangre", "AIRE EN LINEA", "rojo", "airBubbleInBloodDetected"),   # 48 (ALARMA)
                ("Detector Sangre en Dializante", "FUGA SANGRE", "rojo", "bloodInDialyCircDetected"),       # 49 (ALARMA)
                ("Nivel Alto Tanque Agua", "NIVEL AGUA ALTO", "amarillo", "dialyTankHiLevelSwitch"),        # 50
                ("Nivel Cámara Deaereación", "NIVEL DEAERAC.", "amarillo", "dialyDeaerChamLevSwitch"),      # 51
                ("Disponible para Función Digital 11", "RESERVA 11", "cian", "availableBoolVariable7"),     # 52
                ("Start Operation mode", "ESTADO START", "cian", "dialyModeOperationStart"),                      # 53 no mostrar en catalogo
                ("Stop Operation mode", "ESTADO STOP", "cian", "dialyModeOperationStop"),                         # 54 no mostrar en catalogo
                ("Pause Operation mode", "ESTADO PAUSE", "cian", "dialyModeOperationPause"),    # 55 no mostrar en catalogo
                ("Llenado de filtro", "LLENADO DE FILTRO", "cian", "dialyFilterFillButton"),    # 56
                ("Sobrepresión Bomba Diálisis", "SOBREPRESIÓN DIALIZANTE", "rojo", "dialyDialyPumpOverPress"),    # 57
                ("Sobrepresión Bomba Deaeración", "SOBREPRESIÓN DEAERACIÓN", "rojo", "dialyDeaerPumpOverPress"),    # 58
                ("Activación de posición jeringa", "ACT POS JERINGA", "cian", "heparineSynringeAct"),    # 59
            ], start=0)}
    },


    # ================================================================
    # PARÁMETROS CLÍNICOS (0x02)
    # ================================================================
    0x02: {
        0x00: {"name": "Presión intermembrana", "label": "PTM", "type": "double", "rw": True, "unit": "mmHg", "limites": (1, 100), "tag": "interMembPresClinicData", "nivel": "cian"},           # 0
        0x01: {"name": "Selección de modo de tratamiento", "label": "MODO TTO", "type": "double", "rw": True, "unit": "NA", "limites": (0, 100), "tag": "treatmentModeSelection", "nivel": "cian"}, # 1 *dialyOpModeSelector  no mostrar en catalogo
        0x02: {"name": "Estado actual de proceso de cebado", "label": "ESTADO CEBADO", "type": "double", "rw": True, "unit": "NA", "limites": (0, 100), "tag": "primingProcessStatus", "nivel": "cian"},  # 2 dialyCurrProcessState no mostrar en catalogo
        0x03: {"name": "Número de ciclos UF", "label": "CICLOS UF", "type": "double", "rw": True, "unit": "ml", "limites": (0, 100000), "tag": "ultraFilterCycleCount", "nivel": "cian"},  # 3 no mostrar en catalogo
        0x04: {"name": "Selector de ciclos cámara de balance", "label": "SET CICLOS BAL.", "type": "double", "rw": True, "unit": "n", "limites": (1, 100), "tag": "balanceChamberCycleSet", "nivel": "cian"}, # 4 no mostrar en catalogo
        0x05: {"name": "Volumen de heparina dosificado actual", "label": "VOL. HEPARINA", "type": "double", "rw": True, "unit": "ml", "limites": (0, 100), "tag": "heparineCurrentDosage", "nivel": "cian"},# 5
        0x06: {"name": "Número de ciclos Camara de balance", "label": "CICLOS ACTUAL", "type": "double", "rw": True, "unit": "c", "limites": (0, 10000), "tag": "balanceChamberCycleCount", "nivel": "cian"},# 6 no mostrar en catalogo
    },
    # ================================================================
    # SETPOINTS (0x03)
    # ================================================================
    0x03: {
        0x00: {"name": "Velocidad de UltraFiltrado", "label": "TASA UF", "type": "double", "rw": True, "unit": "L/h", "limites": (0, 2), "tag": "ultraFilterPumpSpeed", "nivel": "cian"},              # 7 no mostrar en catalogo
        0x01: {"name": "Ajuste de tiempo de ciclo de cámara de balance", "label": "TIEMPO CICLO", "type": "double", "rw": True, "unit": "s", "limites": (0, 100), "tag": "balanceChamberSetTiming", "nivel": "cian"}, # 8 no mostrar en catalogo
        0x02: {"name": "Tiempo auto-paro heparina: horas", "label": "T. HEP (H)", "type": "double", "rw": True, "unit": "h", "limites": (0, 10), "tag": "heparineAutoStopHours", "nivel": "cian"},         # 9 no mostrar en catalogo
        0x03: {"name": "Tiempo auto-paro heparina: minutos", "label": "T. HEP (M)", "type": "double", "rw": True, "unit": "m", "limites": (0, 59), "tag": "heparineAutoStopMinutes", "nivel": "cian"},    # 10 no mostrar en catalogo
        0x04: {"name": "Tamaño de escala de jeringa", "label": "ESC. JERINGA", "type": "double", "rw": True, "unit": "mm/ml", "limites": (1, 10), "tag": "heparineSyringeSize", "nivel": "cian"},      # 11 no mostrar en catalogo
        0x05: {"name": "Dosis de heparina por terapia ml/h", "label": "DOSIS HEPAR", "type": "double", "rw": True, "unit": "ml/h", "limites": (0, 50), "tag": "heparineTherapyDosage", "nivel": "cian"},   # 12
        0x06: {"name": "Cantidad de bolo", "label": "CANT. BOLO", "type": "double", "rw": True, "unit": "ml", "limites": (0, 10), "tag": "heparineBolusQuantity", "nivel": "cian"},                       # 13
        0x07: {"name": "Ajuste de velocidad de bomba bicarbonato", "label": "VEL BICARB", "type": "double", "rw": True, "unit": "%", "limites": (0, 100), "tag": "bicarbonatePumpSpeed", "nivel": "cian"},# 14  no mostrar en catalogo
        0x08: {"name": "Ajuste de velocidad de ácido cítrico", "label": "VEL ACIDO", "type": "double", "rw": True, "unit": "%", "limites": (0, 100), "tag": "citricAcidPumpSpeed", "nivel": "cian"},     # 15 no mostrar en catalogo
    },

    # ================================================================
    # CONTROL PID (0x04)
    # ================================================================
    0x04: {
        0x00: {"name": "Setpoint flujo sanguíneo", "label": "SP FLUJO S.", "type": "double", "rw": True, "unit": "ml/min", "limites": (0, 600), "tag": "bloodFlowControlSetPoint", "nivel": "cian"},        # 16
        0x01: {"name": "Cálculo flujo circuito sanguíneo", "label": "CALC FLUJO S.", "type": "double", "rw": True, "unit": "ml/min", "limites": (0, 600), "tag": "bloodFlowVariableData", "nivel": "cian"},   # 17 
        0x02: {"name": "Salida control flujo sanguíneo", "label": "OUT FLUJO S.", "type": "double", "rw": True, "unit": "%", "limites": (0, 100), "tag": "bloodFlowControlOutput", "nivel": "cian"},         # 18  no mostrar en catalogo
        0x03: {"name": "Kp control de flujo sanguíneo", "label": "KP FLUJO S.", "type": "double", "rw": True, "unit": "", "limites": (0, 10), "tag": "bloodFlowControlPropGain", "nivel": "cian"},          # 19  no mostrar en catalogo
        0x04: {"name": "Ki control de flujo sanguíneo", "label": "KI FLUJO S.", "type": "double", "rw": True, "unit": "", "limites": (0, 10), "tag": "bloodFlowControlInteGain", "nivel": "cian"},          # 20  no mostrar en catalogo
        0x05: {"name": "Kd control de flujo sanguíneo", "label": "KD FLUJO S.", "type": "double", "rw": True, "unit": "", "limites": (0, 10), "tag": "bloodFlowControlDeriGain", "nivel": "cian"},          # 21  no mostrar en catalogo
        0x06: {"name": "Setpoint conductividad", "label": "SP COND.", "type": "double", "rw": True, "unit": "mS/cm", "limites": (13.0, 15.0), "tag": "dialyCondControlSetPoint", "nivel": "cian"},       # 22
        0x07: {"name": "Conductividad medida", "label": "COND. REAL", "type": "double", "rw": False, "unit": "mS/cm", "limites": (12.5, 15.5), "tag": "dialyCondVariableData", "nivel": "amarillo"},       # 23
        0x08: {"name": "Salida control de conductividad", "label": "OUT COND.", "type": "double", "rw": True, "unit": "%", "limites": (0, 100), "tag": "dialyCondControlOutput", "nivel": "cian"},       # 24 no mostrar en catalogo
        0x09: {"name": "Kp control de conductividad", "label": "KP COND.", "type": "double", "rw": True, "unit": "", "limites": (0, 10), "tag": "dialyCondControlPropGain", "nivel": "cian"},            # 25  no mostrar en catalogo
        0x0A: {"name": "Ki control de conductividad", "label": "KI COND.", "type": "double", "rw": True, "unit": "", "limites": (0, 10), "tag": "dialyCondControlInteGain", "nivel": "cian"},            # 26  no mostrar en catalogo
        0x0B: {"name": "Kd control de conductividad", "label": "KD COND.", "type": "double", "rw": True, "unit": "", "limites": (0, 10), "tag": "dialyCondControlDeriGain", "nivel": "cian"},            # 27  no mostrar en catalogo
        0x0C: {"name": "Setpoint temperatura", "label": "SP TEMP.", "type": "double", "rw": True, "unit": "°C", "limites": (35.0, 39.0), "tag": "dialyTempControlSetPoint", "nivel": "cian"},            # 28 
        0x0D: {"name": "Temperatura medida", "label": "TEMP. REAL", "type": "double", "rw": False, "unit": "°C", "limites": (34.5, 39.5), "tag": "dialyTempVariableData", "nivel": "amarillo"},            # 29
        0x0E: {"name": "Salida control temperatura", "label": "OUT TEMP.", "type": "double", "rw": True, "unit": "%", "limites": (0, 100), "tag": "dialyTempControlOutput", "nivel": "cian"},            # 30 no mostrar en catalogo
        0x0F: {"name": "Kp control temperatura", "label": "KP TEMP.", "type": "double", "rw": True, "unit": "", "limites": (0, 10), "tag": "dialyTempControlPropGain", "nivel": "cian"},                 # 31 no mostrar en catalogo
        0x10: {"name": "Ki control temperatura", "label": "KI TEMP.", "type": "double", "rw": True, "unit": "", "limites": (0, 10), "tag": "dialyTempControlInteGain", "nivel": "cian"},                 # 32 no mostrar en catalogo
        0x11: {"name": "Kd control temperatura", "label": "KD TEMP.", "type": "double", "rw": True, "unit": "", "limites": (0, 10), "tag": "dialyTempControlDeriGain", "nivel": "cian"},                 # 33 no mostrar en catalogo
        0x12: {"name": "Ganancia Feedforward flujo", "label": "GAN FF FLUJO", "type": "double", "rw": True, "unit": "", "limites": (0, 5), "tag": "bloodFlowFeedForwardGain", "nivel": "cian"},              # 34  no mostrar en catalogo
        0x13: {"name": "Tiempo adelanto Feedforward flujo", "label": "T. ADELANTO FF", "type": "double", "rw": True, "unit": "s", "limites": (0, 10), "tag": "bloodFlowFeedForwardLead", "nivel": "cian"},     # 35 no mostrar en catalogo
        0x14: {"name": "Setpoint flujo dializante", "label": "SP FLUJO DIAL", "type": "double", "rw": True, "unit": "ml/min", "limites": (300, 800), "tag": "dialyFlowControlOutput", "nivel": "cian"},       # 36
        0x15: {"name": "Salida bomba de purga", "label": "OUT B.PURGA", "type": "double", "rw": True, "unit": "%", "limites": (0, 100), "tag": "dialyDeaerControlOutput", "nivel": "cian"},                # 37
        0x16: {"name": "Posición inicial de jeringa", "label": "POS. INI. JER.", "type": "double", "rw": True, "unit": "", "limites": (0,4), "tag": "heparineSyringeVolume", "nivel": "cian"},           # 38 no mostrar en catalogo
        0x17: {"name": "Limite alto de presion de agua", "label": "LIM. ALT. P. AGUA", "type": "double", "rw": True, "unit": "", "limites": (0, 20), "tag": "dialyLineWaterPresHiLimit", "nivel": "cian"},           # 39 no mostrar en catalogo
        0x18: {"name": "Limite bajo de presion de agua", "label": "LIM. B. P. AGUA", "type": "double", "rw": True, "unit": "", "limites": (0, 20), "tag": "dialyLineWaterPresLoLimit", "nivel": "cian"},           # 40 no mostrar en catalogo
        0x19: {"name": "Limite alto conductividad", "label": "LIM. ALT. COND.", "type": "double", "rw": True, "unit": "", "limites": (0, 20), "tag": "dialyConductHiLimitBand", "nivel": "cian"},           # 41 no mostrar en catalogo
        0x1A: {"name": "Limite bajo conductividad", "label": "LIM. B. COND.", "type": "double", "rw": True, "unit": "", "limites": (0, 20), "tag": "dialyConductLoLimitBand", "nivel": "cian"},           # 42 no mostrar en catalogo
    },

    # ================================================================
    # PROCESO - ANALÓGICAS (0x05)
    # ================================================================
    0x05: {
        0x00: {"name": "Velocidad bomba peristáltica de sangre", "label": "VEL B.SANGRE", "type": "double", "rw": True, "unit": "RPM", "limites": (0, 600), "tag": "bloodSpeedVariableData", "nivel": "cian"}, # 43
        0x01: {"name": "Flujo de heparina", "label": "FLUJO HEPAR", "type": "double", "rw": True, "unit": "ml/h", "limites": (0, 50), "tag": "heparFlowProcessData", "nivel": "cian"},                        # 44
        0x02: {"name": "Presión arterial en línea sanguínea", "label": "P. ARTERIAL", "type": "double", "rw": True, "unit": "mmHg", "limites": (-100, 400), "tag": "arterPresProcessData", "nivel": "rojo"},  # 45
        0x03: {"name": "Presión venosa en línea sanguínea", "label": "P. VENOSA", "type": "double", "rw": True, "unit": "mmHg", "limites": (-50, 300), "tag": "venouPresProcessData", "nivel": "rojo"},     # 46
        0x04: {"name": "Presión del dializante Entrada del filtro (EF)", "label": "P. DIAL ENT", "type": "double", "rw": True, "unit": "mmHg", "limites": (-200, 600), "tag": "dialyPresIFProcessData", "nivel": "amarillo"}, # 47
        0x05: {"name": "Presión del dializante Salida del filtro (SF)", "label": "P. DIAL SAL", "type": "double", "rw": True, "unit": "mmHg", "limites": (-200, 600), "tag": "dialyPresOFProcessData", "nivel": "amarillo"},  # 48
        0x06: {"name": "Falla suministro agua", "label": "P. AGUA RED", "type": "double", "rw": True, "unit": "bar", "limites": (2.0, 5.0), "tag": "dialyLineWaterPresData", "nivel": "cian"},        # 49
        0x07: {"name": "Temperatura del dializante EF", "label": "TEMP DIAL ENT", "type": "double", "rw": True, "unit": "°C", "limites": (35.0, 39.0), "tag": "dialyTempIFProcessData", "nivel": "amarillo"},   # 50
        0x08: {"name": "Temperatura del dializante SF", "label": "TEMP DIAL SAL", "type": "double", "rw": True, "unit": "°C", "limites": (35.0, 39.0), "tag": "dialyTempIOFProcessData", "nivel": "amarillo"},   # 51 
        0x09: {"name": "Flujo de líquido de sustitución", "label": "FLUJO SUST.", "type": "double", "rw": True, "unit": "ml/h", "limites": (0, 5000), "tag": "subsLiqFlowProcessData", "nivel": "cian"},      # 52
        0x0A: {"name": "Conductividad dializante antes del filtro", "label": "COND. PRE-F", "type": "double", "rw": True, "unit": "mS/cm", "limites": (13.0, 15.0), "tag": "dialyConductIFProcessData", "nivel": "amarillo"}, # 53
        0x0B: {"name": "Conductividad dializante después del filtro", "label": "COND. POST-F", "type": "double", "rw": True, "unit": "mS/cm", "limites": (13.0, 15.0), "tag": "dialyConductOFProcessData", "nivel": "amarillo"}, # 54
        0x0C: {"name": "Parametro de control ", "label": "FREC. CARD.", "type": "double", "rw": True, "unit": "lpm", "limites": (0,1000), "tag": "patHeartFreqProcessData", "nivel": "rojo"},     # 55 
        0x0D: {"name": "Presión en el tanque de calentamiento", "label": "P. TQ CALENT", "type": "double", "rw": True, "unit": "mmHg", "limites": (-100, 100), "tag": "dialyTankPresProcessData", "nivel": "cian"}, # 56
        0x0E: {"name": "Presión en la línea del dializante", "label": "P. LIN DIAL", "type": "double", "rw": True, "unit": "mmHg", "limites": (-200, 600), "tag": "dialyLinePresProcessData", "nivel": "amarillo"}, # 57 PT-3
        0x0F: {"name": "Presión Prefiltrado", "label": "P. PRE-FILTRO", "type": "double", "rw": True, "unit": "mmHg", "limites": (0, 500), "tag": "dialyPFilPmpPresProcessData", "nivel": "cian"},              #58  
    },
    
    # ================================================================
    # CALIBRACIÓN - ANALÓGICAS (0x06) 
    # ================================================================
    0x06: {
        0x00: {"name": "Factor calibración bomba heparina", "label": "CAL HEPARINA", "type": "double", "rw": True, "unit": "ml/rev", "limites": (0.01, 10.0), "tag": "heparCalibFactorData", "nivel": "cian"},          # 59 no mostrar en catalogo
        0x01: {"name": "Presión de ultrafiltrado", "label": "P. ULTRAFILT", "type": "double", "rw": True, "unit": "mmHg", "limites": (-50, 500), "tag": "dialyUFilPresProcessData", "nivel": "amarillo"},               # 60 
        0x02: {"name": "Presión en cámara de balance", "label": "P. CAM.BAL", "type": "double", "rw": False, "unit": "mmHg", "limites": (-100, 600), "tag": "dialyBChamPresProcessData", "nivel": "amarillo"},        # 61 PT- 7
        0x03: {"name": "Presión arterial del circuito de sangre", "label": "P. ART CIRC", "type": "double", "rw": False, "unit": "mmHg", "limites": (-300, 600), "tag": "bloodArteryPressureData", "nivel": "rojo"},   # 62 
        0x04: {"name": "Presión venosa del circuito de sangre", "label": "P. VEN CIRC", "type": "double", "rw": False, "unit": "mmHg", "limites": (-100, 500), "tag": "bloodVenousPressureData", "nivel": "rojo"},     # 63
        0x05: {"name": "Contador de ciclos de dialización", "label": "CONT CICLOS", "type": "double", "rw": False, "unit": "ciclos", "limites": (0, 100000), "tag": "dialyCycleOperationCount", "nivel": "cian"},      # 64
        0x06: {"name": "Limite alto presión arterial", "label": "PA ALTA", "type": "double", "rw": True, "unit": "", "limites": (-300, 300), "tag": "artPresCircAlarmHiLimData", "nivel": "rojo"},                 # 65
        0x07: {"name": "Limite bajo presión arterial", "label": "PA BAJA", "type": "double", "rw": True, "unit": "", "limites": (-300, 300), "tag": "artPresCircAlarmLoLimData", "nivel": "rojo"},                                # 66
        0x08: {"name": "Limite alto presión venosa", "label": "PV ALTA", "type": "double", "rw": True, "unit": "", "limites": (-100, 500), "tag": "venPresCircAlarmHiLimData", "nivel": "rojo"},                                # 67
        0x09: {"name": "Limite bajo presión venosa", "label": "PV BAJA", "type": "double", "rw": True, "unit": "", "limites": (-100, 500), "tag": "venPresCircAlarmLoLimData", "nivel": "rojo"},                              # 68
        0x0A: {"name": "limite alto presión transmembrana", "label": "PTM ALTA", "type": "double", "rw": True, "unit": "", "limites": (-100, 1000), "tag": "membPressAlarmHiLimData", "nivel": "rojo"},                              # 69
        0x0B: {"name": "Limite bajo presión transmembrana", "label": "PTM BAJA", "type": "double", "rw": True, "unit": "", "limites": (-100, 1000), "tag": "membPressAlarmLoLimData", "nivel": "rojo"},                              # 70
    },

    # ================================================================
    # BIOIMPEDANCIA Y UREA (0x07)
    # ================================================================
    0x07: {
        0x00: {"name": "BioZ Resistencia", "label": "BIOZ RESIST", "type": "double", "rw": False, "unit": "Ohm", "limites": (0, 1000), "tag": "bioz_resistance", "nivel": "cian"}, 
        0x01: {"name": "BioZ Fase", "label": "BIOZ FASE", "type": "double", "rw": False, "unit": "Deg", "limites": (-180, 180), "tag": "bioz_phase", "nivel": "cian"},           
        0x02: {"name": "Urea Sensor ADC1", "label": "UREA ADC 1", "type": "double", "rw": False, "unit": "ADC", "limites": (0, 4095), "tag": "urea_adc1", "nivel": "cian"},       
        0x03: {"name": "Urea Sensor ADC2", "label": "UREA ADC 2", "type": "double", "rw": False, "unit": "ADC", "limites": (0, 4095), "tag": "urea_adc2", "nivel": "cian"},       
    },

    0x08: {
        0x00: {"name": "patient_id","label": "ID PACIENTE","type": "string","rw": True,"unit": "","limites": None,"tag": "patient_id","nivel": "blanco"},
        0x01: {"name": "patient_name","label": "NOMBRE", "type": "string","rw": True,"unit": "","limites": None,"tag": "patient_name","nivel": "blanco"},
        0x02: {"name": "patient_gender","label": "GÉNERO","type": "int","rw": True,"unit": "","limites": None,"tag": "patient_gender","nivel": "blanco"},
        0x03: {"name": "patient_age","label": "EDAD","type": "int","rw": False, "unit": "años","limites": (0, 150),"tag": "patient_age","nivel": "blanco"},
        0x04: {"name": "patient_height_cm","label": "ESTATURA","type": "double","rw": False,"unit": "cm","limites": (50, 250),"tag": "patient_height_cm","nivel": "blanco"},
        0x05: {"name": "patient_dry_weight_kg","label": "PESO SECO","type": "double","rw": False,"unit": "kg","limites": (20, 200),"tag": "patient_dry_weight_kg","nivel": "blanco"},
        0x06: {"name": "patient_pre_weight_kg","label": "PESO PRE-DIAL","type": "double","rw": False,"unit": "kg","limites": (20, 200),"tag": "patient_pre_weight_kg","nivel": "blanco"},
        0x07: {"name": "uf_goal_liters","label": "OBJETIVO UF","type": "double","rw": True,"unit": "L","limites": (0.0, 10.0),"tag": "uf_goal_liters","nivel": "cian"},
        0x08: {"name": "patient_heitmann", "label": "VOLUMEN DE AGUA", "type": "double","rw": True,"unit": "ml","limites": (0.0, 10.0),"tag": "heitmann_value","nivel": "cian"},
    },
    0x09: {
        0x00: {"name": "pattern conductivity sensor", "label": "PATTERN_CONDUCTIVITY", "type": "double", "rw": True, "unit": "mS/cm","limites": (0, 20), "tag": "patternCondRaw", "nivel":"cian"},
        0x01: {"name": "pattern temperature sensor", "label": "PATTERN_TEMPERATURE", "type": "double", "rw": True, "unit": "°C","limites": (0, 100), "tag": "patternTempSensor", "nivel":"cian"},
        0x02: {"name": "pattern conductivity raw","label": "PATTERN_CONDUCTIVITY_RAW","type": "double","rw": True,"unit": "mS/cm","limites": (0, 50), "tag": "patternCondSensor","nivel": "cian","value": 0.0,"description": "Conductividad sin compensación de temperatura (debug/calibración)" },
    },
    0x0A: {
        0x00: {"name": "Desinfection Mode", "label": "DESINFECTION_MODE", "type": "int", "rw": True, "unit": "", "limites": None, "tag": "DesinftectionMode", "nivel": "cian"},
        0x01: {"name": "Desinfection mode 1 time hours", "label": "DT_HOURS", "type": "int", "rw":True, "unit": None, "tag": "desinfection1TimeHours", "nivel": "cian"},
        0x02: {"name": "Desinfection mode 1 time minuts", "label": "DT_MIN", "type": "int", "rw": True, "unit": None, "tag": "desinfection1TimeMin", "nivel": "cian"},
        0x03: {"name": "Desinfection mode 2 time hours", "label": "DT_HOURS", "type": "int", "rw":True, "unit": None, "tag": "desinfection2TimeHours", "nivel": "cian"},
        0x04: {"name": "Desinfection mofr 2 time minuts", "label": "DT_MIN", "type": "int", "rw": True, "unit": None, "tag": "desinfection2TimeMin",("name"): ("value")},
    },
    0x0B: {
        0x00: {"name": "Horas de aplicacion de bolo", "label": "BOLUS_HOURS", "type": "int", "rw": True, "unit": None, "limites": (0, 24), "tag": "heparinApplyHours", "nivel": "cian"},
        0x01: {"name": "Minutos de aplicacion de bolo", "label": "BOLUS_MIN", "type": "int", "rw": True, "unit": None, "limites": (0, 59), "tag": "heparinApplyMinutes", "nivel": "cian"}, 
    },
    0x0C: {
        0x00: {"name": "Mega conductivity sensor", "label": "MEGA_CONDUCTIVITY", "type": "double", "rw": True, "unit": "mS/cm","limites": (0, 20), "tag": "megaCondSensor", "nivel":"cian"},
        0x01: {"name": "Mega temperature sensor", "label": "MEGA_TEMPERATURE", "type": "double", "rw": True, "unit": "°C","limites": (0, 100), "tag": "megaTempSensor", "nivel":"cian"},
    }
}

# ================================================================
# MAPEO DE LECTURA MASIVA ANALÓGICA (71 doubles)
# ================================================================
ANALOG_MAP: List[Tuple[int, int]] = [
    # 0x02 → 7 variables
    *( (0x02, i) for i in range(7) ),
    # 0x03 → 9 variables
    *( (0x03, i) for i in range(9) ),
    # 0x04 → 27 variables (0x00 a 0x1A)
    *( (0x04, i) for i in range(0x1B) ),
    # 0x05 → 16 variables específicas
    *( (0x05, i) for i in range(0x10) ),
    # 0x06 12 Variables de calibración)
    *( (0x06, i) for i in range(0x0C) )
]

# ================================================================
# GRUPOS PARA TABLAS
# ================================================================
TVAR_TO_GROUP = {
    0x01: "Operación",
    0x02: "Clínicos",
    0x03: "Setpoints",
    0x04: "Control PID",
    0x05: "Proceso",
    0x06: "Calibración",
    0x07: "Bioimpedancia y Urea",
    0x08: "Datos del paciente",
    0x09: "Sensor patron de conductividad",
    0x0A: "Modo de desinfección",
    0x0B: "Tiempo de aplicación de bolo"
}


# ================================================================
# MAPA INVERSO PARA BÚSQUEDA RÁPIDA POR TAG
# ================================================================

TAG_TO_ADDRESS: Dict[str, tuple[int, int]] = {}

for group_key, vars_group in VARIABLES.items():
    if isinstance(vars_group, dict):
        for var_id, info in vars_group.items():
            if "tag" in info:
                tag = info["tag"]
                if tag in TAG_TO_ADDRESS:
                    logger.warning(f"Tag duplicado encontrado: '{tag}'")
                TAG_TO_ADDRESS[tag] = (group_key, var_id)
    
   