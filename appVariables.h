#ifndef APPVARIABLES_H
#define	APPVARIABLES_H

/*********************************************************************************************************************************************
 * 
 *                           M A P A  D E  C O N S T A N T E S  A S O C I A D A S  A  L O S  P I N E S  D E  E / S
 *
 ********************************************************************************************************************************************/
// Canales Analógicos para sensores
#define HEMATOCRIT_SENSOR     A0                            // Sensor de Hematocrito
#define PRES_DIALYZER_FLOUT   A1                            // Presión en la salida del Filtro Dializante
#define PRES_DIALYZER_FLIN    A2                            // Presión en la entrada del Filtro Dializante
#define DIALY_BLOOD_SENSOR    A3                            // Detector de sangre en dializante
#define TMP_DIALYZER_FLIN     A4                            // Temperatura Entrada Filtro Dializante
#define TMP_DIALYZER_FLOUT    A5                            // Temperatura Salida Filtro Dializante
#define DIALY_CONDUCT_FLIN    A6                            // Conductividad en la entrada del Filtro Dializante
#define DIALY_CONDUCT_FLOUT   A7                            // Conductividad en la salida del Filtro Dializante
#define PRES_ARTBLOOD_FLOUT   A8                            // Presión Arterial del paciente
#define PRES_VENBLOOD_FLOUT   A9                            // Presión Venosa del paciente
#define AIRBUBBLE_BLOOD_SENS  A10                           // Detector de burbuja en sangre
#define IN_ANALOGVAR_AVAIL    A11                           // Señal analógica o GPIO disponible

// Analógicas de Salida (Actuadores)
#define CITRIC_ACID_VALUE     67                            // Disponible 4 como GPIO 66 (DAC0)
#define BICARBONATE_VALUE     66                            // Disponible 5 como GPIO 67 (DAC1) 

// Bomba de Flujo de Dializante
#define PWM_PUMP1             2
#define FWD_PUMP1             22
#define REV_PUMP1             23

// Bomba de Deaereación
//#define PWM_PUMP2             3
//#define FWD_PUMP2             24
//#define REV_PUMP2             25

// Bomba 3 (Disponible)
//#define PWM_PUMP3             4 
//#define FWD_PUMP3             26
//#define REV_PUMP3             27

// Bomba de Deaereación
#define PWM_PUMP4             5
#define FWD_PUMP4             28
#define REV_PUMP4             29

// Bomba Ultrafiltrado
#define PWM_UFILTER           4   // PWM_PUMP3 

// Bomba Peristáltica 2
//#define RENA_PPUMP2           11
#define DIRE_PPUMP1           8         // Señal de DIR para el nuevo driver  (Antes era RPWM_PPUMP2)
//#define LENA_PPUMP2           10
#define PULS_PPUMP1           9         // Señal de entrada de pulsos del nuevo driver (Antes era LPWM_PPUMP2)

// Bomba Peristáltica 1
//#define RENA_PPUMP1           13
#define RPWM_PPUMP1           6         // Señal de PWM para el nuevo driver (Sigue siendo RPWM_PPUMP1)
//#define LENA_PPUMP1           12
#define STRT_PPUMP1           7         // Señal de Start para el nuevo Driver (Antes era LPWM_PPUMP1)

// Bombas Dosificadoras
#define BICARBONATE_START     30
#define BICARBONATE_STATUS    31
#define CITRIT_ACID_START     32
#define CITRIT_ACID_STATUS    33

// Sensores de Nivel
#define LS_1                  34                            // STP_SDO2
#define LS_2                  35                            // ENA_SDO2
#define LS_3                  3                             // LS_3 queda en lugar de PWM_PUMP3

// Válvulas solenoides y SSRs
#define SV_31                 42      // Cámara de balance Válvula 31
#define SV_32                 43      // Cámara de balance Válvula 32
#define SV_33                 44      // Cámara de balance Válvula 33
#define SV_34                 45      // Cámara de balance Válvula 34
#define SV_35                 46      // Cámara de balance Válvula 35
#define SV_36                 47      // Cámara de balance Válvula 36
#define SV_37                 48      // Cámara de balance Válvula 37
#define SV_38                 49      // Cámara de balance Válvula 38
#define SV_25                 39      // Válvula de corte de salida al filtro
#define SV_24                 38      // Válvula de Corte de entrada del Filtrado
#define SV_50                 36      // Válvula de de Cámara Caliente
#define SV_27                 50      // Válvula de Entrada de Agua
#define SV_30                 68      // Válvula de Drenaje
#define SV_39                 51      // Válvula de Recirculación
#define SV_43                 37      // Válvula Venteo Camara de Separación de aire
#define SV_26                 69      // Válvula de Bypass Filtrado
#define HEATER_SSR1_OUT       40      // Salida al SSR1 del calefactor
#define HEATER_SSR2_OUT       41      // Salida al SSR2 del calefactor

// Tacómetros
#define TACH_PERISTALTIC_PMP1 52
#define TACH_PERISTALTIC_PMP2 53

// SPI Pinout
#define SPI_MISO              74
#define SPI_MOSI              75
#define SPI_SCLK              76
#define SPI_DCS1              14
#define SPI_RDY               15

/*******************************************************************************************************************
*                Otros Registros
********************************************************************************************************************/
// Registers
#define MAXNUM_OPERATION_REGS 40
#define MAXNUM_CLINICVAR_REGS  7
#define MAXNUM_CLINICSET_REGS  9
#define MAXNUM_CONTRLVAR_REGS 27
#define MAXNUM_PROCESVAR_REGS 15
#define MAXNUM_CALIBRVAR_REGS 12
#define MAXNUM_ALRLIMVAR_REGS 12

// I2C Slave Address
#define I2C_HEPARINE_ADDR       0x08
#define MAX_DATAIN_BUFFER_SIZE  128

// MAX31865 RTD Constants
// The value of the Rref resistor. Use 430.0 for PT100 and 4300.0 for PT1000
#define RREF      430.0

// The 'nominal' 0-degrees-C resistance of the sensor
// 100.0 for PT100, 1000.0 for PT1000
#define RNOMINAL  100.0

#define AUTO_CTRL       true
#define MANUAL_CTRL     false

// Objeto L2RProtocol
L2RProtocol iFace;                                // Interfaz del Protocolo L2R


/*********************************************************************************************************************************************
 * 
 *                           M A P A  D E  V A R I B L E S  A S O C I A D A S  A  L A  A P L I C A C I O N
 *
 ********************************************************************************************************************************************/
// Permisivos de Control - Tipo 0x01
uint8_t *bloodPumpStartButton       = &iFace.operatControlData[ 0 ];     // Botón de arranque de la bomba peristáltica
uint8_t *bloodPumpStopButton        = &iFace.operatControlData[ 1 ];     // Botón de paro de la bomba peristáltica
uint8_t *bloodPumpFWDButton         = &iFace.operatControlData[ 2 ];     // Botón de dirección normal de la bomba peristáltica
uint8_t *bloodPumpREVButton         = &iFace.operatControlData[ 3 ];     // Botón de dirección reversa de la bomba peristáltica
uint8_t *dialyserPumpStartButton    = &iFace.operatControlData[ 4 ];     // Botón de arranque de la bomba de purga del Tanque de Agua
uint8_t *dialyserPumpStopButton     = &iFace.operatControlData[ 5 ];     // Botón de paro de la bomba de deaereación
uint8_t *heparinePumpsStartButton   = &iFace.operatControlData[ 6 ];     // Botón de arranque de la bomba de la heparina
uint8_t *heparinePumpsStopButton    = &iFace.operatControlData[ 7 ];     // Botón de paro de la bomba de la heparina
uint8_t *heparinePumpFWDButton      = &iFace.operatControlData[ 8 ];     // Botón de dirección normal de la bomba de heparina
uint8_t *heparinePumpREVButton      = &iFace.operatControlData[ 9 ];     // Botón de dirección reversa de la bomba de heparina
uint8_t *bloodControlLoopEnable     = &iFace.operatControlData[ 10 ];    // Selector de habilitación/Deshabilitación del lazo de control de flujo del circuito sanguíneo
uint8_t *bloodControlLoopMode       = &iFace.operatControlData[ 11 ];    // Selector de Automático/Manual del lazo de control de flujo del circuito sanguíneo
uint8_t *dialyCondCtrlLoopEnable    = &iFace.operatControlData[ 12 ];    // Selector de habilitación/Deshabilitación del lazo de control de conductividad del dializante
uint8_t *dialyCondCtrlLoopMode      = &iFace.operatControlData[ 13 ];    // Selector de Automático/Manual del lazo de control de conductividad del dializante
uint8_t *dialyTempCtrlLoopEnable    = &iFace.operatControlData[ 14 ];    // Selector de habilitación/Deshabilitación del lazo de control de temperatura del dializante
uint8_t *dialyTempCtrlLoopMode      = &iFace.operatControlData[ 15 ];    // Selector de Automático/Manual del lazo de control de temperatura del dializante
uint8_t *heparinePumpHomePosition   = &iFace.operatControlData[ 16 ];    // Botón de envío a Home
uint8_t *dialiserBalChambStrButt    = &iFace.operatControlData[ 17 ];    // Botón de start de la cámara de balance
uint8_t *dialiserBalChambStpButt    = &iFace.operatControlData[ 18 ];    // Botón de Paro de la cámara de balance
uint8_t *heparinApplyBolusDose      = &iFace.operatControlData[ 19 ];    // Botón de aplicación de Bolo
uint8_t *heparineOperPauseResume    = &iFace.operatControlData[ 20 ];    // Botón de operación de Pausar y Continuar
uint8_t *dialyCircuitElementsOpSel  = &iFace.operatControlData[ 21 ];    // Selector Operación de elementos del circuito del dializante
uint8_t *dialyPurgePumpStartButt    = &iFace.operatControlData[ 22 ];    // Botón de arranque de la bomba del dializante
uint8_t *dialyPurgePumpStopButt     = &iFace.operatControlData[ 23 ];    // Botón de paro de la bomba del dializante
uint8_t *dialyUltraFPumpStartButt   = &iFace.operatControlData[ 24 ];    // Botón de arranque de la bomba de ultrafiltrado
uint8_t *dialyUltraFPumpStoptButt   = &iFace.operatControlData[ 25 ];    // Botón de paro de la bomba de ultrafiltrado
uint8_t *dialyBicarbonPumpStartButt = &iFace.operatControlData[ 26 ];    // Botón de arranque de la bomba de Bicarbonato
uint8_t *dialyBicarbonPumpStopButt  = &iFace.operatControlData[ 27 ];    // Botón de paro de la bomba de Bicarbonato
uint8_t *dialyCitricAcPumpStartButt = &iFace.operatControlData[ 28 ];    // Botón de arranque de la bomba de ácido cítrico
uint8_t *dialyCitricAcPumpStopButt  = &iFace.operatControlData[ 29 ];    // Botón de paro de la bomba de ácido cítrico
uint8_t *dialyWaterInletValveButt   = &iFace.operatControlData[ 30 ];    // Selector de energizado/desenergizado de la válvula de Entrada de Agua
uint8_t *dialyRecirculatValveButt   = &iFace.operatControlData[ 31 ];    // Selector de energizado/desenergizado de la válvula de recirculación
uint8_t *dialyHotChambValveButt     = &iFace.operatControlData[ 32 ];    // Selector de energizado/desenergizado de la válvula de Cámara Caliente
uint8_t *dialyAirVentSepChambButt   = &iFace.operatControlData[ 33 ];    // Selector de energizado/desenergizado de la válvula de venteo de la CS Aire **

uint8_t *dialyBypassFilterButt      = &iFace.operatControlData[ 34 ];    // Selector de energizado/desenergizado de la válvula de corte de Filtrado
uint8_t *dialyInputFilterCutButt    = &iFace.operatControlData[ 35 ];    // Selector de energizado/desenergizado de la válvula de corte entrada Filtro
uint8_t *dialyOutputFilterCutButt   = &iFace.operatControlData[ 36 ];    // Selector de energizado/desenergizado de la válvula de corte salida Filtro
uint8_t *dialyWaterDrainValveButt   = &iFace.operatControlData[ 37 ];    // Selector de energizado/desenergizado de la válvula de Drenaje

uint8_t *dialyBalanceChambCycleEnd  = &iFace.operatControlData[ 38 ];    // Bit de Fin de ciclo de la cámara de balance
uint8_t *dialyStartDialysisButt     = &iFace.operatControlData[ 39 ];    // Arranque de secuencia de Diálisis
uint8_t *dialyStopDialysisButt      = &iFace.operatControlData[ 40 ];    // Paro de secuencia de Diálisis    
uint8_t *watterTankHeaterProtect    = &iFace.operatControlData[ 41 ];    // Bit de Protección de Resistores del calefactor 
uint8_t *availableBoolVariable1     = &iFace.operatControlData[ 42 ];    // Disponible para función digital 3
uint8_t *availableBoolVariable2     = &iFace.operatControlData[ 43 ];    // Disponible para función digital 4
uint8_t *availableBoolVariable3     = &iFace.operatControlData[ 44 ];    // Disponible para función digital 5
uint8_t *availableBoolVariable4     = &iFace.operatControlData[ 45 ];    // Disponible para función digital 6
uint8_t *availableBoolVariable5     = &iFace.operatControlData[ 46 ];    // Disponible para función digital 7
uint8_t *availableBoolVariable6     = &iFace.operatControlData[ 47 ];    // Disponible para función digital 8
uint8_t *airBubbleInBloodDetected   = &iFace.operatControlData[ 48 ];    // Indicador detector de burbuja de aire en sangre
uint8_t *bloodInDialyCircDetected   = &iFace.operatControlData[ 49 ];    // Indicador detector de sangre en dializante 
uint8_t *dialyTankHiLevelSwitch     = &iFace.operatControlData[ 50 ];    // Interruptor de Nivel Alto en Tanque de Agua 
uint8_t *dialyDeaerChamLevSwitch    = &iFace.operatControlData[ 51 ];    // Interruptor de Nivel en Cámara de Deaereación
uint8_t *availableBoolVariable7     = &iFace.operatControlData[ 52 ];    // Disponible para función digital 11
uint8_t *availableBoolVariable8     = &iFace.operatControlData[ 53 ];    // Disponible para función digital 12
uint8_t *availableBoolVariable9     = &iFace.operatControlData[ 54 ];    // Disponible para función digital 13
uint8_t *availableBoolVariable10    = &iFace.operatControlData[ 55 ];    // Disponible para función digital 14
uint8_t *availableBoolVariable11    = &iFace.operatControlData[ 56 ];    // Disponible para función digital 15
uint8_t *availableBoolVariable12    = &iFace.operatControlData[ 57 ];    // Disponible para función digital 16
uint8_t *availableBoolVariable13    = &iFace.operatControlData[ 58 ];    // Disponible para función digital 17
uint8_t *availableBoolVariable14    = &iFace.operatControlData[ 59 ];    // Disponible para función digital 18

 
// Variables de Representación de Datos de pantalla clínica - Tipo 0x02
double *interMembPresClinicData    = &iFace.allDoubleVariables[ 0 ];        // Presión intermembrana
double *availableClinicVariable2   = &iFace.allDoubleVariables[ 1 ];        // Variable clínica disponible
double *availableClinicVariable3   = &iFace.allDoubleVariables[ 2 ];        // Variable clínica disponible
double *availableClinicVariable4   = &iFace.allDoubleVariables[ 3 ];        // Variable clínica disponible
double *balanceChamberCycleSet     = &iFace.allDoubleVariables[ 4 ];        // Variable clínica disponible
double *heparineCurrentDosage      = &iFace.allDoubleVariables[ 5 ];        // Variable clínica disponible
double *balanceChamberCycleCount   = &iFace.allDoubleVariables[ 6 ];        // Variable clínica disponible

// Otros Puntos de ajuste en pantalla clínica - Tipo 0x03 
double *ultraFilterPumpSpeed       = &iFace.allDoubleVariables[ 7 ];         // Velocidad de Ultrafiltración
double *balanceChamberSetTiming    = &iFace.allDoubleVariables[ 8 ];         // ajuste de tiempo de ciclo de la cámara de balance ultraFilterPumpSpeed
double *heparineTherapyHours       = &iFace.allDoubleVariables[ 9 ];         // Tiempo de terapia Horas
double *heparineTherapyMinutes     = &iFace.allDoubleVariables[ 10 ];        // Tiempo de terapia Minutos
double *heparineSyrinjeScaleSize   = &iFace.allDoubleVariables[ 11 ];        // Dimensión de jeringa mm/ml
double *heparineTherapyDosage      = &iFace.allDoubleVariables[ 12 ];        // Dosis de terapia
double *heparineBolusQuantity      = &iFace.allDoubleVariables[ 13 ];        // Cantidad en ml de Bolo de Heparina
double *bicarbonatePumpSpeed       = &iFace.allDoubleVariables[ 14 ];        // Variable clínica de ajuste disponible
double *citricAcidPumpSpeed        = &iFace.allDoubleVariables[ 15 ];        // Variable clínica de ajuste disponible

// Parámetros de Ajuste de los Controladores y pantalla clínica - Tipo 0x04
double *bloodFlowControlSetPoint   = &iFace.allDoubleVariables[ 16 ];       // Variable para guardar el valor del Set Point del flujo sanguíneo. Cofepris / 15 - 500ml/min 
double *bloodFlowVariableData      = &iFace.allDoubleVariables[ 17 ];       // Variable de Flujo del circuito de sangre. Cofepris / 15 - 500ml/min
double *bloodFlowControlOutput     = &iFace.allDoubleVariables[ 18 ];       // Variable para guardar el valor de la salida de control del lazo de flujo sanguíneo ( 0 - 100% )
double *bloodFlowControlPropGain   = &iFace.allDoubleVariables[ 19 ];       // Variable para guardar el valor de la ganancia proporcional del lazo de flujo sanguíneo
double *bloodFlowControlInteGain   = &iFace.allDoubleVariables[ 20 ];       // Variable para guardar el valor de la ganancia integral del lazo de flujo sanguíneo
double *bloodFlowControlDeriGain   = &iFace.allDoubleVariables[ 21 ];       // Variable para guardar el valor de la ganancia derivativa del lazo de flujo sanguíneo
double *dialyCondControlSetPoint   = &iFace.allDoubleVariables[ 22 ];       // Setpoint de la variable del lazo de control de conductividad
double *dialyCondVariableData      = &iFace.allDoubleVariables[ 23 ];       // Variable proceso del lazo de control de conductividad
double *dialyCondControlOutput     = &iFace.allDoubleVariables[ 24 ];       // Variable de salida del lazo de control de conductividad 
double *dialyCondControlPropGain   = &iFace.allDoubleVariables[ 25 ];       // Ganancia proporcional del lazo de control de conductividad
double *dialyCondControlInteGain   = &iFace.allDoubleVariables[ 26 ];       // Ganancia integral del lazo de control de conductividad
double *dialyCondControlDeriGain   = &iFace.allDoubleVariables[ 27 ];       // Ganancia derivativa del lazo de control de conductividad
double *dialyTempControlSetPoint   = &iFace.allDoubleVariables[ 28 ];       // Variable para guardar el valor del Set Point del lazo de temperatura del dializante. Cofepris / 35 a 38°C
double *dialyTempVariableData      = &iFace.allDoubleVariables[ 29 ];       // Variable de Temperatura del Dializante. Cofepris / 35 a 38°C
double *dialyTempControlOutput     = &iFace.allDoubleVariables[ 30 ];       // Variable para guardar el valor de la salida de control del lazo de temperatura del dializante
double *dialyTempControlPropGain   = &iFace.allDoubleVariables[ 31 ];       // Variable para guardar el valor de la ganancia proporcional del lazo de temperatura del dializante 
double *dialyTempControlInteGain   = &iFace.allDoubleVariables[ 32 ];       // Variable para guardar el valor de la ganancia integral del lazo de temperatura del dializante  
double *dialyTempControlDeriGain   = &iFace.allDoubleVariables[ 33 ];       // Variable para guardar el valor de la ganancia derivativa del lazo de temperatura del dializante
double *bloodFlowFeedForwardGain   = &iFace.allDoubleVariables[ 34 ];       // Ganancia de Feedforward del control Feedforward de flujo
double *bloodFlowFeedForwardLead   = &iFace.allDoubleVariables[ 35 ];       // Tiempo Retardo/adelanto del control Feedforward de flujo
double *dialyFlowControlOutput     = &iFace.allDoubleVariables[ 36 ];       // Variable para guardar el valor del Set Point del flujo del dializante. Cofepris / 300 - 800ml/min
double *dialyDeaerControlOutput    = &iFace.allDoubleVariables[ 37 ];       // Variable para guardar el valor de la salida de la bomba de purga (deaereación)
double *variableCtrlParamData1     = &iFace.allDoubleVariables[ 38 ];       // Variable disponible 1 
double *variableCtrlParamData2     = &iFace.allDoubleVariables[ 39 ];       // Variable disponible 2 
double *variableCtrlParamData3     = &iFace.allDoubleVariables[ 40 ];       // Variable disponible 3
double *variableCtrlParamData4     = &iFace.allDoubleVariables[ 41 ];       // Variable disponible 4
double *variableCtrlParamData5     = &iFace.allDoubleVariables[ 42 ];       // Variable disponible 5 


// Variables de Representación de Datos de proceso interno - Tipo 0x05
double *bloodSpeedVariableData    = &iFace.allDoubleVariables[ 43 ];        // Variable para guardar el valor de la velocidad de la bomba peristáltica de sangre
double *heparFlowProcessData      = &iFace.allDoubleVariables[ 44 ];        // Variable para guardar el valor del flujo de heparina
double *arterPresProcessData      = &iFace.allDoubleVariables[ 45 ];        // Variable para guardar el valor de la presión arterial en línea sanguínea
double *venouPresProcessData      = &iFace.allDoubleVariables[ 46 ];        // Variable para guardar el valor de la presión venosa en línea sanguínea
double *dialyPresIFProcessData    = &iFace.allDoubleVariables[ 47 ];        // Variable para guardar el valor de la presión venosa
double *dialyPresOFProcessData    = &iFace.allDoubleVariables[ 48 ];        // Variable para guardar el valor de la del filtro de sangre
double *dialyLineWaterPresData    = &iFace.allDoubleVariables[ 49 ];        // Variable para guardar el valor de la Presión en la línea del dializante
double *dialyTempIFProcessData    = &iFace.allDoubleVariables[ 50 ];        // Variable para guardar el valor de la Temperatura del dializante Entrada del filtro IF
double *dialyTempOFProcessData    = &iFace.allDoubleVariables[ 51 ];        // Variable para guardar el valor de la Temperatura del dializante Salida del filtro OF
double *subsLiqFlowProcessData    = &iFace.allDoubleVariables[ 52 ];        // Variable para guardar el valor del Flujo del líquido de sustitución
double *dialyConductIFProcessData = &iFace.allDoubleVariables[ 53 ];        // Variable para guardar el valor de la Conductividad del dializante antes del Filtro
double *dialyConductOFProcessData = &iFace.allDoubleVariables[ 54 ];        // Variable para guardar el valor de la Conductividad del dializante después del Filtro
double *patHeartFreqProcessData   = &iFace.allDoubleVariables[ 55 ];        // Variable para guardar el valor de la Frecuencia cardiaca del paciente
double *dialyTankPresProcessData  = &iFace.allDoubleVariables[ 56 ];        // Variable presión en el tanque de calentamiento
double *dialyLinePresProcessData  = &iFace.allDoubleVariables[ 57 ];        // Variable presión en la línea del dializante
double *dialyPFilPmpPresProcessData= &iFace.allDoubleVariables[ 58 ];       // Variable presión Prefiltrado   

// Parámetros de calibración - Tipo 0x06
double *heparCalibFactorData        = &iFace.allDoubleVariables[ 59 ];        // Variable para guardar el valor de la Relación de cálculo de velocidad y volumen bomba Heparnia
double *dialyUFilPresProcessData    = &iFace.allDoubleVariables[ 60 ];        // Variable de presión de ultrafiltrado
double *dialyBChamPresProcessData   = &iFace.allDoubleVariables[ 61 ];        // Variable de presión en la cámara de balance
double *bloodArteryPressureData     = &iFace.allDoubleVariables[ 62 ];        // Variable que guarda la presión arterial del circuito de sangre del paciente 
double *bloodVenousPressureData     = &iFace.allDoubleVariables[ 63 ];        // Variable que guarda la presión venosa del circuito de sangre del paciente 
double *dialyCycleOperationCount    = &iFace.allDoubleVariables[ 64 ];        // Contador de ciclos de dialización de la máquina
double *artPresCircAlarmHiLimData   = &iFace.allDoubleVariables[ 65 ];        //
double *artPresCircAlarmLoLimData   = &iFace.allDoubleVariables[ 66 ];        //
double *venPresCircAlarmHiLimData   = &iFace.allDoubleVariables[ 67 ];        //
double *venPresCircAlarmLoLimData   = &iFace.allDoubleVariables[ 68 ];        //
double *membPressAlarmHiLimData     = &iFace.allDoubleVariables[ 69 ];        //
double *membPressAlarmLoLimData     = &iFace.allDoubleVariables[ 70 ];        //

// Alarm Presets - Tipo 0x07
double *artPresCircAlarmHiLimData  = &iFace.allDoubleVariables[ 71 ];       // Variable para guardar el valor de la alarma de Presión arterial del circuito Alta
double *artPresCircAlarmLoLimData  = &iFace.allDoubleVariables[ 72 ];       // Variable para guardar el valor de la alarma de Presión arterial del circuito Baja
double *venPresCircAlarmHiLimData  = &iFace.allDoubleVariables[ 73 ];       // Variable para guardar el valor de la alarma de Presión venosa del circuito Alta
double *venPresCircAlarmLoLimData  = &iFace.allDoubleVariables[ 74 ];       // Variable para guardar el valor de la alarma de Presión venosa del circuito Baja
double *membPressAlarmHiLimData    = &iFace.allDoubleVariables[ 75 ];       // Variable para guardar el valor de la alarma de Presión transmembrana Alta
double *membPressAlarmLoLimData    = &iFace.allDoubleVariables[ 76 ];       // Variable para guardar el valor de la alarma de Presión transmembrana Baja
double *dialyFlowAlarmHiLimData    = &iFace.allDoubleVariables[ 77 ];       // Variable para guardar el valor de la alarma de Flujo del líquido dializante Alto
double *dialyFlowAlarmLoLimData    = &iFace.allDoubleVariables[ 78 ];       // Variable para guardar el valor de la alarma de Flujo del líquido dializante Bajo
double *bloodFlowAlarmHiLimData    = &iFace.allDoubleVariables[ 79 ];       // Variable para guardar el valor de la alarma de Flujo de sangre Alto
double *bloodFlowAlarmLoLimData    = &iFace.allDoubleVariables[ 80 ];       // Variable para guardar el valor de la alarma de Flujo de sangre Bajo
double *ultraFilterAlarmSignalData = &iFace.allDoubleVariables[ 81 ];      // Variable para guardar el valor de la alarma de Ultrafiltración
double *dialyConductAlarmHiLimData = &iFace.allDoubleVariables[ 82 ];      // Variable para guardar el valor de la alarma de Conductividad Alta
double *dialyConductAlarmLoLimData = &iFace.allDoubleVariables[ 83 ];      // Variable para guardar el valor de la alarma de Conductividad Baja
double *dialyTemperAlarmHiLimData  = &iFace.allDoubleVariables[ 84 ];      // Variable para guardar el valor de la alarma de Temperatura del líquido dializante Alta
double *dialyTemperAlarmLoLimData  = &iFace.allDoubleVariables[ 85 ];      // Variable para guardar el valor de la alarma de Temperatura del líquido dializante Baja
double *bloodLeakAlarmSignalData   = &iFace.allDoubleVariables[ 86 ];      // Variable para guardar el valor de la alarma de Fugas sanguíneas
double *bloodAirAlarmSignalData    = &iFace.allDoubleVariables[ 87 ];      // Variable para guardar el valor de la alarma de Detección de aire en la sangre
double *waterSuppAlarmSignalData   = &iFace.allDoubleVariables[ 88 ];      // Variable para guardar el valor de la alarma de Falla en el suministro de agua
double *energySuppAlarmSignalData  = &iFace.allDoubleVariables[ 89 ];      // Variable para guardar el valor de la alarma de Falla en el suministro de energía eléctrica
double *artPresPatAlarmHiLimData   = &iFace.allDoubleVariables[ 90 ];      // Variable para guardar el valor de la alarma de Presión arterial del paciente Alta
double *artPresPatAlarmLoLimData   = &iFace.allDoubleVariables[ 91 ];      // Variable para guardar el valor de la alarma de Presión arterial del paciente Baja
double *variableAlarmLoLimData1    = &iFace.allDoubleVariables[ 92 ];      // 
double *variableAlarmHiLimData2    = &iFace.allDoubleVariables[ 93 ];      // 
double *variableAlarmLoLimData3    = &iFace.allDoubleVariables[ 94 ];      // 
double *variableAlarmHiLimData4    = &iFace.allDoubleVariables[ 95 ];      // 
double *variableAlarmLoLimData5    = &iFace.allDoubleVariables[ 96 ];      // 

const byte disabled[16]  = { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
const byte tankFill[16]  = { 1, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 0 };
const byte lineFill[16]  = { 1, 1, 0, 0, 1, 1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 0 };
const byte balcFill[16]  = { 1, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0 };
const byte valvbpass[16] = { 0, 1, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0 };
const byte closing[16]   = { 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0 };
const byte initial2[16]  = { 0, 0, 1, 0, 1, 1, 1, 1, 1, 0, 1, 0, 1, 1, 1, 0 };



#endif
