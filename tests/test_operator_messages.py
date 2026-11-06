# tests/test_operator_messages.py
"""
Tests para el catálogo de avisos de operador (core/operator_messages.py)
"""

import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from core.operator_messages import modo_de, resolver
from core.state_manager import TreatmentPhase

logger = logging.getLogger(__name__)


class TestModoDeConversion:
    """Tests para la función modo_de()"""
    
    def test_idle_es_espera(self):
        """IDLE mapea a ESPERA"""
        assert modo_de(TreatmentPhase.IDLE) == "ESPERA"
    
    def test_preparing_es_terapia(self):
        """PREPARING mapea a TERAPIA"""
        assert modo_de(TreatmentPhase.PREPARING) == "TERAPIA"
    
    def test_ready_es_terapia(self):
        """READY mapea a TERAPIA"""
        assert modo_de(TreatmentPhase.READY) == "TERAPIA"
    
    def test_running_es_terapia(self):
        """RUNNING mapea a TERAPIA"""
        assert modo_de(TreatmentPhase.RUNNING) == "TERAPIA"
    
    def test_paused_es_terapia(self):
        """PAUSED mapea a TERAPIA"""
        assert modo_de(TreatmentPhase.PAUSED) == "TERAPIA"
    
    def test_finishing_es_terapia(self):
        """FINISHING mapea a TERAPIA"""
        assert modo_de(TreatmentPhase.FINISHING) == "TERAPIA"
    
    def test_cleaning_es_limpieza(self):
        """CLEANING mapea a LIMPIEZA"""
        assert modo_de(TreatmentPhase.CLEANING) == "LIMPIEZA"
    
    def test_error_es_fallo(self):
        """ERROR mapea a FALLO"""
        assert modo_de(TreatmentPhase.ERROR) == "FALLO"


class TestResolverAvisosConLog:
    """Tests para resolver() con escritura a archivo temporal"""
    
    def test_hep_tiempo_limitado_en_running_arma_texto(self, tmp_path, monkeypatch):
        """HEP_TIEMPO_LIMITADO en RUNNING arma el texto correctamente"""
        # Redirigir logs al directorio temporal
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        
        resultado = resolver(
            "HEP_TIEMPO_LIMITADO",
            TreatmentPhase.RUNNING,
            horas=2,
            minutos=30
        )
        
        assert resultado is not None
        assert resultado["clave"] == "HEP_TIEMPO_LIMITADO"
        assert "2:30" in resultado["texto"] or "02:30" in resultado["texto"]
        assert resultado["nivel"] == "warning"
        assert resultado["modo"] == "TERAPIA"
        assert resultado["duracion"] == "hasta_aceptar"
    
    def test_hep_tiempo_limitado_en_cleaning_regresa_none(self, tmp_path, monkeypatch):
        """HEP_TIEMPO_LIMITADO en CLEANING regresa None y no escribe log"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        
        resultado = resolver(
            "HEP_TIEMPO_LIMITADO",
            TreatmentPhase.CLEANING,
            horas=2,
            minutos=30
        )
        
        assert resultado is None
        # Verificar que no se escribió en el archivo de log
        log_file = tmp_path / "logs" / "mensajes_sesion.jsonl"
        assert not log_file.exists()
    
    def test_hep_paro_auto_en_cleaning_es_none(self, tmp_path, monkeypatch):
        """HEP_PARO_AUTO en CLEANING es None"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        
        resultado = resolver(
            "HEP_PARO_AUTO",
            TreatmentPhase.CLEANING
        )
        
        assert resultado is None
    
    def test_hep_paro_auto_en_running_regresa_texto(self, tmp_path, monkeypatch):
        """HEP_PARO_AUTO en RUNNING regresa texto"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        
        resultado = resolver(
            "HEP_PARO_AUTO",
            TreatmentPhase.RUNNING
        )
        
        assert resultado is not None
        assert resultado["clave"] == "HEP_PARO_AUTO"
        assert "temporizador" in resultado["texto"]
        assert resultado["nivel"] == "warning"
        assert resultado["modo"] == "TERAPIA"
    
    def test_cierre_abrupto_limpieza_en_cleaning_regresa_texto(self, tmp_path, monkeypatch):
        """CIERRE_ABRUPTO_LIMPIEZA en CLEANING regresa texto"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        
        resultado = resolver(
            "CIERRE_ABRUPTO_LIMPIEZA",
            TreatmentPhase.CLEANING
        )
        
        assert resultado is not None
        assert resultado["clave"] == "CIERRE_ABRUPTO_LIMPIEZA"
        assert "Limpieza detenida" in resultado["texto"]
        assert resultado["nivel"] == "warning"
        assert resultado["modo"] == "LIMPIEZA"
    
    def test_cierre_abrupto_limpieza_en_running_es_none(self, tmp_path, monkeypatch):
        """CIERRE_ABRUPTO_LIMPIEZA en RUNNING es None"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        
        resultado = resolver(
            "CIERRE_ABRUPTO_LIMPIEZA",
            TreatmentPhase.RUNNING
        )
        
        assert resultado is None
    
    def test_clave_inventada_es_none(self, tmp_path, monkeypatch):
        """Clave inventada regresa None"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        
        resultado = resolver(
            "CLAVE_INEXISTENTE",
            TreatmentPhase.RUNNING
        )
        
        assert resultado is None


class TestLogDeAvisos:
    """Tests para la escritura de logs de avisos"""
    
    def test_aviso_permitido_agrega_linea_a_archivo_temporal(self, tmp_path, monkeypatch):
        """Un aviso permitido agrega una línea a un archivo temporal"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        
        resolver(
            "HEP_PARO_AUTO",
            TreatmentPhase.RUNNING
        )
        
        log_file = tmp_path / "logs" / "mensajes_sesion.jsonl"
        assert log_file.exists()
        
        # Leer y verificar contenido
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        assert len(lines) > 0
        # Parsear como JSON
        mensaje = json.loads(lines[0])
        assert mensaje["clave"] == "HEP_PARO_AUTO"
        assert mensaje["nivel"] == "warning"
        assert mensaje["modo"] == "TERAPIA"
        assert "timestamp" in mensaje
    
    def test_no_escribe_si_resultado_es_none(self, tmp_path, monkeypatch):
        """No escribe si resolver retorna None"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        
        # Intentar resolver un aviso no permitido
        resolver(
            "HEP_TIEMPO_LIMITADO",
            TreatmentPhase.CLEANING
        )
        
        log_file = tmp_path / "logs" / "mensajes_sesion.jsonl"
        # El archivo no debe existir o estar vacío
        if log_file.exists():
            with open(log_file, "r", encoding="utf-8") as f:
                content = f.read()
            assert content.strip() == ""
    
    def test_no_usa_alarm_history(self, tmp_path, monkeypatch):
        """El log de avisos no va a alarm_history.json"""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir(exist_ok=True)
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir(exist_ok=True)
        
        # Crear un archivo alarm_history.json para verificar que no se toca
        alarm_history_path = config_dir / "alarm_history.json"
        alarm_history_path.write_text("[]")
        
        resolver(
            "HEP_PARO_AUTO",
            TreatmentPhase.RUNNING
        )
        
        # Verificar que alarm_history.json no fue modificado
        with open(alarm_history_path, "r") as f:
            content = f.read()
        assert content == "[]"


class TestFormacionDeTextos:
    """Tests para la formación correcta de textos"""
    
    def test_hep_tiempo_limitado_formatea_horas_minutos(self, tmp_path, monkeypatch):
        """HEP_TIEMPO_LIMITADO formatea correctamente horas y minutos"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        
        resultado = resolver(
            "HEP_TIEMPO_LIMITADO",
            TreatmentPhase.IDLE,
            horas=1,
            minutos=15
        )
        
        assert resultado is not None
        # Debe tener el formato 01:15 o 1:15
        assert ("1:15" in resultado["texto"]) or ("01:15" in resultado["texto"])
        assert "No se infunde durante los últimos 30 minutos" in resultado["texto"]
    
    def test_cierre_abrupto_terapia_tiene_texto_completo(self, tmp_path, monkeypatch):
        """CIERRE_ABRUPTO_TERAPIA tiene texto completo"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        
        resultado = resolver(
            "CIERRE_ABRUPTO_TERAPIA",
            TreatmentPhase.RUNNING
        )
        
        assert resultado is not None
        assert "Cierre abrupto detectado" in resultado["texto"]
        assert "Tratamiento detenido por seguridad" in resultado["texto"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
