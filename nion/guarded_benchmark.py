"""Prueba reproducible de traduccion protegida sin escribir en la memoria."""
import argparse
import json
import time
from collections import Counter
from pathlib import Path

from .engine import MarianEngine
from .guarded_translate import translate_guarded


class LazyQwen:
    """Cargar GGUF solo si una traduccion llega a cuarentena."""
    def __init__(self, model, threads):
        self.model, self.threads, self.engine = model, threads, None

    def translate(self, source):
        if self.engine is None:
            from .repair_gguf import LocalGGUF
            self.engine = LocalGGUF(self.model, n_threads=self.threads)
        return self.engine.translate(source)

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
    parser.add_argument("--gguf", help="Modelo Qwen GGUF opcional para cuarentena")
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args(argv)
    if not 1 <= args.threads <= 64:
        parser.error("--threads debe estar entre 1 y 64")
    if args.gguf and not Path(args.gguf).is_file():
        parser.error("No existe el modelo GGUF")
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
    qwen = LazyQwen(args.gguf, args.threads) if args.gguf else None
    rows = translate_guarded(texts, MarianEngine(), qwen_engine=qwen)
    elapsed = round(time.perf_counter() - started, 2)
    counts = Counter(row["estado"] for row in rows)
    report = {
        "motor": "marian",
        "segundos": elapsed,
        "total": len(rows),
        "reintentos": sum(bool(row["reintento"]) for row in rows),
        "qwen_usados": sum(bool(row.get("qwen_usado")) for row in rows),
        "estados": dict(counts),
        "resultados": rows,
    }
    with output.open("x", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    print("Textos:", len(rows), "| Reintentos:", report["reintentos"])
    print("Estados:", dict(counts), "| Segundos:", elapsed)
    print("Qwen usado:", report["qwen_usados"])
    for i, row in enumerate(rows, 1):
        print(f"CASO {i}: {row['estado']} | {row['alertas']}")
    print("Informe:", output)
    print("Memoria y archivos del juego intactos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
