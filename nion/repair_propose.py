"""Genera propuestas de reparación con MarianMT, sin tocar la memoria original."""
import argparse
import json
from pathlib import Path

from .engine import MarianEngine
from .quality import inspect
from .repair import SEVERE

def propose(rows, engine, limit=None):
    """Solo propone cambios seguros; nunca modifica las filas originales."""
    result = [dict(row) for row in rows]
    count = 0
    for row in result:
        if limit is not None and count >= limit:
            break
        if row.get("propuesta") or not row.get("original"):
            continue
        source = row["original"]
        try:
            candidate = (engine.translate_repair(source) if hasattr(engine, "translate_repair")
                         else engine.translate_batch([source], "en", "es")[0])
            problems = sorted(SEVERE.intersection(inspect(source, candidate)))
            row["propuesta"] = candidate
            row["problemas_propuesta"] = problems
            row["estado"] = "revisar" if problems else "propuesta_lista"
        except Exception as error:
            row["estado"] = "error"
            row["error"] = str(error)[:300]
        row["aprobado"] = False
        count += 1
        print("Procesados:", count, "|", row["estado"])
    return result

def main(argv=None):
    parser = argparse.ArgumentParser(description="Genera propuestas con MarianMT, sin aplicarlas")
    parser.add_argument("review", help="nion_reparacion_pendiente.json")
    parser.add_argument("--out", default="nion_propuestas_marian.json")
    parser.add_argument("--limit", type=int, default=5, help="Primeros casos para probar (0 = todos)")
    args = parser.parse_args(argv)
    source, dest = Path(args.review).resolve(), Path(args.out).resolve()
    if not source.is_file():
        parser.error("No existe el informe de revision")
    if source == dest or dest.exists():
        parser.error("La salida ya existe o coincide con el informe")
    if args.limit < 0:
        parser.error("--limit no puede ser negativo")
    rows = json.loads(source.read_text(encoding="utf-8-sig"))
    if not isinstance(rows, list) or any(not isinstance(x, dict) for x in rows):
        parser.error("El informe debe ser una lista de registros")
    print("Revisando", len(rows), "casos. La memoria NO se modificara.")
    result = propose(rows, MarianEngine(), None if args.limit == 0 else args.limit)
    with dest.open("x", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print("Propuestas:", dest)
    print("No se modifico la memoria ni se aprobaron propuestas.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
