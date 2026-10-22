"""Borra archivos que la app de hemodiálisis no importa.

Ejecutar desde la raíz de hemodialisis_ciateq:

    python borrar_archivos_sin_uso.py

No toca dialysis_screenV2, heparin_config_screenV2, therapy_config_screenV2,
cleaning_screen.py, las pantallas de alarmas ni tests/test_nibp.py.
"""

from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent

ARCHIVOS = [
    "gui/service/CleaningScreenV2.py",
    "gui/configuration/patSelScreen.py",
    "gui/configuration/dialysisCfgScreen.py",
    "gui/configuration/primeReturnScreen.py",
    "gui/components/tagLabel.py",
    "connection/due_conductivity_sensor.py",
    "core/dialysis_parameter_map.py",
    "gversion.py",
    # Solo existe para probar el sensor Due, que ya no usa la app.
    "tests/test_due_hot_port_runtime.py",
]

CARPETAS = [
    "Actualizacion",
    "Backoup",
]


def main() -> int:
    if not (ROOT / "gui" / "appMainHemodialysis.py").is_file():
        print("No parece la raíz de hemodialisis_ciateq. No se borró nada.")
        return 1

    for relativo in ARCHIVOS:
        ruta = ROOT / relativo
        if ruta.is_file():
            ruta.unlink()
            print(f"borrado  {relativo}")
        else:
            print(f"no está  {relativo}")

    for relativo in CARPETAS:
        ruta = ROOT / relativo
        if ruta.is_dir():
            shutil.rmtree(ruta)
            print(f"borrada  {relativo}/")
        else:
            print(f"no está  {relativo}/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
