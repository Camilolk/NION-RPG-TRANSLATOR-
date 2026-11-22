"""Prueba reproducible de traduccion protegida sin escribir en la memoria."""
import argparse
import json
import time
from collections import Counter
from pathlib import Path

from .engine import MarianEngine
from .guarded_translate import translate_guarded

SAMPLES = [
    "N-No!!",
    "Shut UP!!! And die!!!",
    "What's wrong with him? Does he just not want to do it?",
    "I get you, don't worry! Did it work out? And what about the device?",
    "That's e-enough... it's t-too much... I've... already... too many... nghhhhh....!!!",
]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prueba MarianMT protegido sin modificar juegos ni memorias")
    parser.add_argument("--input", help="JSON con lista de textos originales (opcional)")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--out", default="nion_guarded_benchmark.json")
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit debe ser mayor que cero")
    output = Path(args.out).resolve()
    source = Path(args.input).resolve() if args.input else None
    if output.exists() or (source is not None and output == source):
        parser.error("La salida ya existe o coincide con la entrada")
    if source is not None:
        if not source.is_file():
            parser.error("No existe el archivo de entrada")
        texts = json.loads(source.read_text(encoding="utf-8-sig"))
        if not isinstance(texts, list) or any(not isinstance(t, str) for t in texts):
            parser.error("La entrada debe ser una lista JSON de cadenas")
    else:
        texts = SAMPLES
    texts = texts[:args.limit]
    started = time.perf_counter()
    rows = translate_guarded(texts, MarianEngine())
    elapsed = round(time.perf_counter() - started, 2)
    counts = Counter(row["estado"] for row in rows)
    report = {
        "motor": "marian",
        "segundos": elapsed,
        "total": len(rows),
        "reintentos": sum(bool(row["reintento"]) for row in rows),
        "estados": dict(counts),
        "resultados": rows,
    }
    with output.open("x", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    print("Textos:", len(rows), "| Reintentos:", report["reintentos"])
    print("Estados:", dict(counts), "| Segundos:", elapsed)
    for i, row in enumerate(rows, 1):
        print(f"CASO {i}: {row['estado']} | {row['alertas']}")
    print("Informe:", output)
    print("Memoria y archivos del juego intactos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
