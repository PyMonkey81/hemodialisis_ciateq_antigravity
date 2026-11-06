# core/operator_messages.py
"""
Catálogo de avisos de sesión (session messages).

Cada aviso tiene clave, texto, nivel, modos permitidos y duración.
Los avisos "hasta_aceptar" no tienen timeout.

Modos basados en TreatmentPhase:
  - ESPERA: IDLE
  - TERAPIA: PREPARING, READY, RUNNING, PAUSED, FINISHING
  - LIMPIEZA: CLEANING
  - FALLO: ERROR
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from core.state_manager import TreatmentPhase

logger = logging.getLogger(__name__)


# Catálogo de avisos: clave -> {texto, nivel, modos, duración}
CATALOG = {
    "HEP_TIEMPO_LIMITADO": {
        "text_template": (
            "Tiempo de heparina limitado a {horas:02d}:{minutos:02d}. "
            "No se infunde durante los últimos 30 minutos de la terapia."
        ),
        "level": "warning",
        "allowed_modes": ["ESPERA", "TERAPIA"],
        "duration": "hasta_aceptar",
    },
    "HEP_PARO_AUTO": {
        "text_template": "Paro automático de bomba de heparina por temporizador",
        "level": "warning",
        "allowed_modes": ["TERAPIA"],
        "duration": "hasta_aceptar",
    },
    "CIERRE_ABRUPTO_TERAPIA": {
        "text_template": "Cierre abrupto detectado. Tratamiento detenido por seguridad.",
        "level": "warning",
        "allowed_modes": ["TERAPIA"],
        "duration": "hasta_aceptar",
    },
    "CIERRE_ABRUPTO_LIMPIEZA": {
        "text_template": "Cierre abrupto detectado. Limpieza detenida por seguridad.",
        "level": "warning",
        "allowed_modes": ["LIMPIEZA"],
        "duration": "hasta_aceptar",
    },
}


def modo_de(fase: TreatmentPhase) -> str:
    """
    Convierte TreatmentPhase a modo de operación.
    
    Args:
        fase: TreatmentPhase enum
        
    Returns:
        str: "ESPERA", "TERAPIA", "LIMPIEZA" o "FALLO"
    """
    if fase == TreatmentPhase.IDLE:
        return "ESPERA"
    elif fase in (
        TreatmentPhase.PREPARING,
        TreatmentPhase.READY,
        TreatmentPhase.RUNNING,
        TreatmentPhase.PAUSED,
        TreatmentPhase.FINISHING,
    ):
        return "TERAPIA"
    elif fase == TreatmentPhase.CLEANING:
        return "LIMPIEZA"
    elif fase == TreatmentPhase.ERROR:
        return "FALLO"
    else:
        return "FALLO"


def resolver(clave: str, fase: TreatmentPhase, **campos) -> Optional[Dict[str, Any]]:
    """
    Resuelve un aviso de sesión si la clave existe y el modo es permitido.
    
    Retorna un diccionario con:
      {
          "clave": str,
          "texto": str (formado),
          "nivel": str,
          "modo": str,
          "fase": str,
          "duracion": str,
          "timestamp": str (ISO 8601)
      }
    
    Si la clave no existe o el modo no la permite, retorna None sin lanzar excepción.
    Si retorna un aviso permitido, anexa una línea a logs/mensajes_sesion.jsonl.
    
    Args:
        clave: Clave del aviso (ej: "HEP_TIEMPO_LIMITADO")
        fase: TreatmentPhase actual
        **campos: Campos para formatear el texto (ej: horas=2, minutos=30)
        
    Returns:
        Dict con aviso formado, o None si no se puede resolver
    """
    if clave not in CATALOG:
        return None
    
    aviso_def = CATALOG[clave]
    modo = modo_de(fase)
    
    if modo not in aviso_def["allowed_modes"]:
        return None
    
    # Formar el texto
    try:
        texto = aviso_def["text_template"].format(**campos)
    except KeyError:
        # Algunos campos no fueron proporcionados
        texto = aviso_def["text_template"]
    
    resultado = {
        "clave": clave,
        "texto": texto,
        "nivel": aviso_def["level"],
        "modo": modo,
        "fase": fase.name,
        "duracion": aviso_def["duration"],
        "timestamp": datetime.now().isoformat(),
    }
    
    # Anexar línea a logs/mensajes_sesion.jsonl
    _append_message_log(resultado)
    
    return resultado


def _append_message_log(mensaje: Dict[str, Any]) -> None:
    """
    Anexa una línea JSON a logs/mensajes_sesion.jsonl
    
    Args:
        mensaje: Diccionario del mensaje a registrar
    """
    try:
        # Crear directorio si no existe
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        log_file = logs_dir / "mensajes_sesion.jsonl"
        
        # Escribir línea JSON
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(mensaje, ensure_ascii=False) + "\n")
        
        logger.debug(f"Mensaje registrado: {mensaje['clave']}")
    except Exception as e:
        logger.error(f"Error escribiendo log de mensajes de sesión: {e}", exc_info=True)
