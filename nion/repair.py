"""Preparacion segura de revisiones de traduccion NION (sin aplicar cambios)."""
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from .quality import inspect

SEVERE = {"traduccion_vacia", "repeticion_anomala", "expansion_extrema",
          "reduccion_extrema", "codigos_diferentes", "marcadores_diferentes"}

def build_review(memory):
    rows = []
    for original, translation in memory.items():
        if not isinstance(original, str):
            continue
        problems = sorted(SEVERE.intersection(inspect(original, translation)))
        if problems:
            rows.append({
                "original": original,
                "traduccion_actual": translation,
                "problemas": problems,
                "propuesta": "",
                "aprobado": False,
            })
    return rows

def main(argv=None):
    parser = argparse.ArgumentParser(description="Prepara revision sin modificar memoria")
    parser.add_argument("memory", help="Archivo de memoria JSON")
    parser.add_argument("--out", default="nion_reparacion_pendiente.json")
    args = parser.parse_args(argv)
    memory_path = Path(args.memory).resolve()
    output_path = Path(args.out).resolve()
    if not memory_path.is_file():
        parser.error("No existe la memoria: " + str(memory_path))
    if output_path == memory_path or output_path.exists():
        parser.error("La salida coincide con la memoria o ya existe")
    data = json.loads(memory_path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        parser.error("La memoria debe contener un objeto JSON")
    rows = build_review(data)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = memory_path.with_name(memory_path.name + ".backup_" + stamp)
    if backup.exists():
        parser.error("El respaldo ya existe")
    shutil.copy2(memory_path, backup)
    try:
        with output_path.open("x", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
    except Exception:
        backup.unlink(missing_ok=True)
        raise
    print("Memoria intacta:", memory_path)
    print("Respaldo:", backup)
    print("Casos graves:", len(rows))
    print("Revision:", output_path)
    print("No se ha cambiado ninguna traduccion.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
