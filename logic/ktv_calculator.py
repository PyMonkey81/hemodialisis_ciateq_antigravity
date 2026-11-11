#logic/ktv_calculator.py
        
import math
import logging 
from typing import Optional
logger = logging.getLogger(__name__)

class CalculadoraKtV:
    def __init__(self, parent=None, values_dict=None):
        
        self.parent_windows = parent
        self.current_values = values_dict if values_dict is not None else {}
        self.reset()

    def reset(self):
        """Reinicia todos los valores acumulados para un nuevo ciclo de cálculo de Kt/V."""
        # Acumulación de Kt
        self.kt_acumulado: float = 0.0
        self.tiempo_ultima_medicion: Optional[float] = None
        self.d_vigente: float = 0.0  # D que cierra el intervalo anterior
        self._cierre_hecho: bool = False
        
        self.volumen_distribucion_v = 0.0 
        self.parametros_antropometricos = {} 

        # Almacenamiento de conductividades para los dos puntos
        # Las conductividades YA vienen compensadas a 25°C desde el firmware
        self._cd_in_t1: float = 0.0
        self._cd_out_t1: float = 0.0

        self._cd_in_t2: float = 0.0
        self._cd_out_t2: float = 0.0
        
        logger.debug("[KTV_CALC] CalculadoraKtV reiniciada. Kt=0, D_vigente=0")

    def config_paciente(self, peso: float, altura: float, edad: int, genero: int):
        """
        Configura los parámetros antropométricos del paciente y calcula el Volumen (V)
        usando la fórmula de Watson si no hay datos de bioimpedancia.
        V se guarda en mL.
        """
        self.parametros_antropometricos = {
            "peso": peso, "altura": altura, "edad": edad, "genero": genero
        }

        # Ecuaciones de Watson (V en litros)
        v_litros = 0.0
        if genero == 1: # Hombre
            v_litros = 2.447 - (0.09156 * edad) + (0.1074 * altura) + (0.3362 * peso)
        elif genero == 2: # Mujer
            v_litros = -2.097 + (0.1069 * altura) + (0.2466 * peso)
        else:
            logger.warning(f"[KTV_CALC] Género '{genero}' no reconocido. No se puede usar Watson.")
            
        self.volumen_distribucion_v = v_litros * 1000 # Convertir a mL y almacenar
        logger.debug(f"[KTV_CALC] Volumen de Watson calculado: {self.volumen_distribucion_v:.2f} mL")


    def set_volumen_bioimpedancia(self, v_bis_litros: float):
        """
        Establece el Volumen (V) directamente desde una lectura de Bioimpedancia.
        V se guarda en mL.
        """
        if v_bis_litros > 0:
            self.volumen_distribucion_v = v_bis_litros * 1000 # Convertir a mL
            logger.debug(f"[KTV_CALC] Volumen de Bioimpedancia establecido: {self.volumen_distribucion_v:.2f} mL")
        else:
            logger.warning(f"[KTV_CALC] Volumen de Bioimpedancia no válido: {v_bis_litros} L. No se actualizará V.")


    def store_conductivity_t1(self, cd_in: float, cd_out: float):
        """
        Almacena las lecturas de conductividad (entrada, salida) en el tiempo 1.
        
        Las conductividades YA vienen compensadas a 25°C desde el firmware.
        No se requiere compensación adicional en Python.
        
        Args:
            cd_in: Conductividad EF (entrada del filtro) en mS/cm, ya a 25°C
            cd_out: Conductividad SF (salida del filtro) en mS/cm, ya a 25°C
        """
        self._cd_in_t1 = cd_in
        self._cd_out_t1 = cd_out
        logger.debug(f"[KTV_CALC] T1 almacenado: CdEF={cd_in:.2f}, CdSF={cd_out:.2f} (ya a 25°C)")

    def store_conductivity_t2(self, cd_in: float, cd_out: float):
        """
        Almacena las lecturas de conductividad (entrada, salida) en el tiempo 2.
        
        Las conductividades YA vienen compensadas a 25°C desde el firmware.
        
        Args:
            cd_in: Conductividad EF (entrada del filtro) en mS/cm, ya a 25°C
            cd_out: Conductividad SF (salida del filtro) en mS/cm, ya a 25°C
        """
        self._cd_in_t2 = cd_in
        self._cd_out_t2 = cd_out
        logger.debug(f"[KTV_CALC] T2 almacenado: CdEF={cd_in:.2f}, CdSF={cd_out:.2f} (ya a 25°C)")

    def calculate_d_ionic(self, qd: float, qf: float, qb: float, r: float = 0.0) -> float:
        """
        Calcula D (dialisancia iónica) utilizando el método de dos puntos de conductividad.
        
        Las conductividades YA vienen compensadas a 25°C desde el firmware.
        No se realiza compensación de temperatura en Python.
        
        Args:
            qd: Flujo de dializado en mL/min
            qf: Flujo de filtración en L/h (será convertido a mL/min)
            qb: Flujo de sangre en mL/min
            r: Factor de recirculación (0.0 a 1.0)
        
        Returns:
            D en mL/min, o 0.0 si no es posible calcular
        """
        # Validaciones iniciales
        if self.volumen_distribucion_v <= 0:
            logger.error("[KTV_CALC] Error: Volumen de distribución (V) no válido. D = 0.0")
            return 0.0

        cd_ef_t1 = self._cd_in_t1
        cd_sf_t1 = self._cd_out_t1
        cd_ef_t2 = self._cd_in_t2
        cd_sf_t2 = self._cd_out_t2

        # Deltas de conductividad (ya compensadas a 25°C en el firmware)
        delta_ef = cd_ef_t2 - cd_ef_t1
        delta_sf = cd_sf_t2 - cd_sf_t1

        # Protección: si abs(delta_ef) < 0.05 mS/cm, no calculamos D
        if abs(delta_ef) < 0.05:
            logger.warning(f"[KTV_CALC] abs(delta_EF) = {abs(delta_ef):.4f} < 0.05 mS/cm. D no se calcula.")
            return 0.0

        # Convertir Qf de L/h a mL/min (solo una vez)
        qf_ml_min = (qf * 1000) / 60

        # Calcular D usando la fórmula iónica
        d_raw = (qd + qf_ml_min) * (1 - delta_sf / delta_ef)

        # Limitar 0 <= D <= Qd + Qf (sin margen extra)
        d = max(0.0, min(d_raw, qd + qf_ml_min))

        # Corrección por recirculación (D efectiva no debe superar D)
        d_efectiva = d
        if qb > 50 and d > 0 and r > 0.0:
            denom = 1 - r * (1 - d / qb)
            if abs(denom) > 0.001:
                d_efectiva = d * ((1 - r) / denom)
            else:
                logger.warning("[KTV_CALC] Denominador de recirculación cercano a cero.")
        
        d_efectiva = min(d_efectiva, d)

        logger.debug(
            f"[KTV_CALC] D_ionic: delta_EF={delta_ef:.4f}, delta_SF={delta_sf:.4f}, "
            f"D_raw={d_raw:.1f}, D={d:.1f}, D_efectiva={d_efectiva:.1f}"
        )

        return d_efectiva

    def update_kt(self, current_time_minutes: float, qd: float, qf: float, qb: float, r: float = 0.0) -> None:
        """
        Actualiza Kt acumulado usando el intervalo cerrado con la D vigente anterior.
        
        - Primera D válida: No suma Kt, solo se guarda como D_vigente
        - D siguientes válidas: Suma Kt con la D_vigente anterior, luego actualiza D_vigente
        - Si abs(delta_EF) < 0.05: No calcula D, mantiene D_vigente igual
        
        Args:
            current_time_minutes: Tiempo total transcurrido de terapia en minutos
            qd, qf, qb, r: Parámetros para calculate_d_ionic()
        """
        if self._cierre_hecho:
            logger.debug("[KTV_CALC] Kt/V ya cerrado. No se acumula otra D.")
            return

        d_nueva = self.calculate_d_ionic(qd, qf, qb, r)
        
        # Si D no se calcula (delta_EF < 0.05), no hacemos nada
        if d_nueva == 0.0:
            logger.debug("[KTV_CALC] D no calculada (delta_EF < 0.05). D_vigente se mantiene.")
            return

        # Primera medición válida: solo se guarda, no suma Kt
        if self.tiempo_ultima_medicion is None:
            self.d_vigente = d_nueva
            self.tiempo_ultima_medicion = current_time_minutes
            logger.debug(f"[KTV_CALC] Primera D válida: D_vigente={d_nueva:.1f}, t={current_time_minutes:.2f}, Kt permanece en {self.kt_acumulado:.1f}")
            return

        # Mediciones siguientes: suma con D_vigente anterior, luego actualiza D_vigente
        dt = current_time_minutes - self.tiempo_ultima_medicion
        if dt > 0:
            self.kt_acumulado += self.d_vigente * dt
            logger.debug(
                f"[KTV_CALC] Acumulación: dt={dt:.2f} min, D_vigente={self.d_vigente:.1f} mL/min, "
                f"Kt_acumulado={self.kt_acumulado:.1f}"
            )
        
        self.d_vigente = d_nueva
        self.tiempo_ultima_medicion = current_time_minutes
        logger.debug(f"[KTV_CALC] D_vigente actualizada a {d_nueva:.1f}")

    def get_ktv_delivered(self, current_time_minutes: float) -> float:
        """
        Devuelve Kt/V acumulado real hasta current_time_minutes (sin proyectar).
        
        Si aún hay tiempo entre la última medición y current_time_minutes,
        suma el tramo final (D_vigente * dt_final) al Kt acumulado.
        
        Returns: Kt/V entregado = Kt / V
        """
        if self.volumen_distribucion_v <= 0:
            return 0.0

        kt_total = self.kt_acumulado
        
        # Si hay una última medición y el tiempo actual es posterior, sumar tramo final
        if self.tiempo_ultima_medicion is not None and current_time_minutes > self.tiempo_ultima_medicion:
            dt_final = current_time_minutes - self.tiempo_ultima_medicion
            kt_total += self.d_vigente * dt_final
            logger.debug(
                f"[KTV_CALC] Kt/V entregado: dt_final={dt_final:.2f} min, "
                f"Kt_total={kt_total:.1f}, Kt/V={kt_total / self.volumen_distribucion_v:.3f}"
            )
        
        return kt_total / self.volumen_distribucion_v

    def commit_final_interval(self, current_time_minutes: float) -> float:
        """Cierra el tramo abierto hasta el tiempo efectivo y deja el entregado.

        Es idempotente: una segunda llamada no vuelve a sumar el mismo intervalo.
        Si no hubo ninguna D válida, el entregado es 0.
        """
        if self.volumen_distribucion_v <= 0:
            self._cierre_hecho = True
            return 0.0

        if not self._cierre_hecho:
            if (
                self.tiempo_ultima_medicion is not None
                and current_time_minutes > self.tiempo_ultima_medicion
            ):
                dt_final = current_time_minutes - self.tiempo_ultima_medicion
                self.kt_acumulado += self.d_vigente * dt_final
                self.tiempo_ultima_medicion = current_time_minutes
                logger.info(
                    "[KTV_CALC] Cierre: dt_final=%.2f min, D_vigente=%.1f, Kt=%.1f",
                    dt_final,
                    self.d_vigente,
                    self.kt_acumulado,
                )
            self._cierre_hecho = True

        return self.kt_acumulado / self.volumen_distribucion_v

    def get_ktv_projected(self, current_time_minutes: float, t_total_minutes: float) -> float:
        """
        Devuelve Kt/V proyectado al final de la sesión.
        
        Proyectado = (Kt + D_vigente * t_restante) / V
        donde t_restante = max(0, t_total - t_actual)
        
        Returns: Kt/V proyectado
        """
        if self.volumen_distribucion_v <= 0:
            return 0.0

        if self.d_vigente <= 0 or self.tiempo_ultima_medicion is None:
            return 0.0

        tiempo_desde_ultima_medicion = t_total_minutes - self.tiempo_ultima_medicion
        if current_time_minutes < self.tiempo_ultima_medicion:
            tiempo_desde_ultima_medicion = t_total_minutes - current_time_minutes

        kt_proyectado = self.kt_acumulado + (self.d_vigente * tiempo_desde_ultima_medicion)

        
        logger.debug(
            f"[KTV_CALC] Kt/V proyectado: t_última_med={self.tiempo_ultima_medicion:.2f} min, "
            f"t_total={t_total_minutes:.2f} min, tiempo_desde_última={tiempo_desde_ultima_medicion:.2f} min, "
            f"D_vigente={self.d_vigente:.1f}, Kt_proyectado={kt_proyectado:.1f}, "
            f"Kt/V={kt_proyectado / self.volumen_distribucion_v:.3f}"
        )
        
        return kt_proyectado / self.volumen_distribucion_v

    def calculate_ktv_ionic(
        self, 
        qd: float, 
        qf: float, 
        qb: float, 
        t_min: float, 
        r: float = 0.0
    ) -> float:
        """
        DEPRECATED: Use update_kt(), get_ktv_delivered(), get_ktv_projected() instead.
        
        Kept for backward compatibility. Computes D only; does not accumulate.
        """
        return self.calculate_d_ionic(qd, qf, qb, r)
