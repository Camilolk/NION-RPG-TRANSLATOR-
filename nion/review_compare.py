"""Comparador interactivo y seguro de propuestas NION. No aplica cambios."""
import argparse
import json
from pathlib import Path

from .repair_gguf import fidelity_warnings
from .repair_propose import semantic_warnings


def merge_reviews(marian_rows, qwen_rows):
    """Unir por original; detectar duplicados para no mezclar dialogos."""
    for name, rows in (("Marian", marian_rows), ("Qwen", qwen_rows)):
        originals = [row["original"] for row in rows]
        if len(originals) != len(set(originals)):
            raise ValueError(f"Original duplicado en {name}")
    qwen = {row["original"]: row for row in qwen_rows}
    merged = []
    for row in marian_rows:
        combined = dict(row)
        other = qwen.get(row["original"], {})
        for key in ("propuesta_gguf", "alertas_gguf", "estado_gguf", "segundos_gguf"):
            if key in other:
                combined[key] = other[key]
        merged.append(combined)
    return merged


def choices(rows, input_fn=input, output_fn=print):
    """Recoger decisiones explicitas sin cambiar los informes de entrada."""
    decisions = []
    for number, row in enumerate(rows, 1):
        original = row.get("original", "")
        marian = row.get("propuesta", "")
        qwen = row.get("propuesta_gguf", "")
        output_fn(f"\\n{'=' * 60}\\nCASO {number}/{len(rows)}\\n{'=' * 60}")
        output_fn("ORIGINAL: " + original)
        output_fn("ACTUAL: " + str(row.get("traduccion_actual", "")))
        output_fn("MARIAN: " + str(marian))
        output_fn("ALERTAS MARIAN: " + str(row.get("problemas_propuesta", [])))
        output_fn("QWEN: " + str(qwen))
        output_fn("ALERTAS QWEN: " + str(sorted(set(
            row.get("alertas_gguf", []) + (
                fidelity_warnings(original, qwen) + semantic_warnings(original, qwen)
                if isinstance(qwen, str) and qwen else []
            )
        ))))
        while True:
            selection = input_fn("[m] Marian / [q] Qwen / [e] editar / [s] saltar / [x] terminar: ").strip().lower()
            if selection in ("m", "q"):
                proposed = marian if selection == "m" else qwen
                if not isinstance(proposed, str) or not proposed.strip():
                    output_fn("No existe una propuesta valida para esa opcion.")
                    continue
                value = proposed
                break
            if selection == "e":
                value = input_fn("Escribe la traduccion corregida en una linea: ").strip()
                if not value:
                    output_fn("La correccion no puede estar vacia.")
                    continue
                break
            if selection in ("s", "x"):
                value = None
                break
            output_fn("Opcion no reconocida.")
        if selection == "x":
            break
        decisions.append({
            "original": original,
            "decision": {"m": "marian", "q": "qwen", "e": "manual", "s": "pendiente"}[selection],
            "traduccion_elegida": value,
            "aprobado": value is not None,
        })
    return decisions


def main(argv=None):
    parser = argparse.ArgumentParser(description="Revisar traducciones sin modificar la memoria")
    parser.add_argument("marian", help="Informe JSON de Marian")
    parser.add_argument("qwen", help="Informe JSON de Qwen")
    parser.add_argument("--out", default="nion_decisiones_revision.json")
    parser.add_argument("--limit", type=int, default=5, help="0 = todos")
    args = parser.parse_args(argv)
    if args.limit < 0:
        parser.error("--limit no puede ser negativo")
    marian, qwen, out = (Path(p).resolve() for p in (args.marian, args.qwen, args.out))
    if not marian.is_file() or not qwen.is_file():
        parser.error("Falta uno de los informes JSON")
    if out.exists() or out in (marian, qwen):
        parser.error("El archivo de salida ya existe o coincide con un informe")
    first = json.loads(marian.read_text(encoding="utf-8-sig"))
    second = json.loads(qwen.read_text(encoding="utf-8-sig"))
    if not all(isinstance(rows, list) and all(
        isinstance(row, dict) and isinstance(row.get("original"), str) for row in rows
    ) for rows in (first, second)):
        parser.error("Los informes deben ser listas de registros con original")
    rows = merge_reviews(first, second)
    if args.limit:
        rows = rows[:args.limit]
    decisions = choices(rows)
    with out.open("x", encoding="utf-8") as file:
        json.dump(decisions, file, ensure_ascii=False, indent=2)
    print("Decisiones guardadas:", out)
    print("Memoria original intacta; no se aplicaron cambios.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
