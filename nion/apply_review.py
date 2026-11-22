"""Aplicacion segura de decisiones revisadas: vista previa por defecto."""
import argparse
import json
from pathlib import Path

from .quality import inspect

STRUCTURAL = {"codigos_diferentes", "marcadores_diferentes"}


def plan(memory, decisions):
    if not isinstance(memory, dict) or not isinstance(decisions, list):
        raise ValueError("Memoria debe ser objeto y decisiones deben ser lista")
    changes, conflicts, skipped = [], [], []
    seen = set()
    for i, item in enumerate(decisions, 1):
        if not isinstance(item, dict):
            conflicts.append({"fila": i, "motivo": "registro_invalido"})
            continue
        source = item.get("original")
        target = item.get("traduccion_elegida")
        if not isinstance(source, str) or not source:
            conflicts.append({"fila": i, "motivo": "original_invalido"})
            continue
        if source in seen:
            conflicts.append({"fila": i, "motivo": "original_duplicado"})
            continue
        seen.add(source)
        if not item.get("aprobado"):
            skipped.append({"fila": i, "motivo": "no_aprobado"})
            continue
        if not isinstance(target, str) or not target.strip():
            conflicts.append({"fila": i, "motivo": "traduccion_vacia"})
            continue
        if source not in memory:
            conflicts.append({"fila": i, "motivo": "original_ausente"})
            continue
        if not isinstance(memory[source], str):
            conflicts.append({"fila": i, "motivo": "valor_memoria_invalido"})
            continue
        structural = sorted(STRUCTURAL.intersection(inspect(source, target)))
        if structural:
            conflicts.append({"fila": i, "motivo": "estructura_incompatible", "alertas": structural})
            continue
        if memory[source] == target:
            skipped.append({"fila": i, "motivo": "sin_cambios"})
            continue
        changes.append({"fila": i, "original": source, "antes": memory[source], "despues": target})
    return changes, conflicts, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(description="Previsualizar o crear memoria corregida sin sobrescribir originales")
    parser.add_argument("memory", help="Memoria JSON existente")
    parser.add_argument("decisions", help="Decisiones aprobadas JSON")
    parser.add_argument("--apply", action="store_true", help="Crear una NUEVA memoria, nunca sobrescribir")
    parser.add_argument("--out", default="nion_memoria_revisada.json")
    args = parser.parse_args(argv)
    memory_path, decisions_path, out = (Path(p).resolve() for p in
                                        (args.memory, args.decisions, args.out))
    if not memory_path.is_file() or not decisions_path.is_file():
        parser.error("No se encuentra la memoria o las decisiones")
    if args.apply and (out.exists() or out in (memory_path, decisions_path)):
        parser.error("La salida ya existe o coincide con un archivo de entrada")
    memory = json.loads(memory_path.read_text(encoding="utf-8-sig"))
    decisions = json.loads(decisions_path.read_text(encoding="utf-8-sig"))
    try:
        changes, conflicts, skipped = plan(memory, decisions)
    except ValueError as exc:
        parser.error(str(exc))
    print("Cambios propuestos:", len(changes))
    print("Conflictos:", len(conflicts))
    print("Omitidos:", len(skipped))
    for change in changes:
        print(f"  CASO {change['fila']}: {change['antes']!r} -> {change['despues']!r}")
    for conflict in conflicts:
        print(f"  CONFLICTO {conflict['fila']}: {conflict['motivo']}", conflict.get("alertas", ""))
    if not args.apply:
        print("VISTA PREVIA: no se escribio ningun archivo.")
        return 0
    if conflicts:
        print("Aplicacion bloqueada: resuelve primero los conflictos.")
        return 2
    updated = dict(memory)
    for change in changes:
        updated[change["original"]] = change["despues"]
    with out.open("x", encoding="utf-8") as fh:
        json.dump(updated, fh, ensure_ascii=False, indent=2)
    print("Nueva memoria:", out)
    print("Memoria original intacta. No se modificaron archivos del juego.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
