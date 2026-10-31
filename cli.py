"""CLI mínima:  python -m nion scan|translate|apply  JUEGO ..."""
import argparse
import os
import sys

from .engine import EngineError, get_engine
from .memory import Memory
from .pipeline import apply_translations, pending_texts, scan, translate_pending


def main(argv=None):
    ap = argparse.ArgumentParser(prog="nion", description="NION RPG Translator (núcleo)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("game", help="carpeta del juego (o su carpeta data)")
        p.add_argument("--lang", default="es", help="idioma destino (es, pt-br, fr...)")
        p.add_argument("--memory", help="archivo de memoria (por defecto nion_memory_<lang>.json)")

    p1 = sub.add_parser("scan", help="cuenta textos sin traducir ni gastar nada")
    common(p1)
    p2 = sub.add_parser("translate", help="traduce lo que falta y lo guarda en la memoria")
    common(p2)
    p2.add_argument("--engine", default="deepl", help="echo | deepl")
    p2.add_argument("--key", default=os.environ.get("NION_DEEPL_KEY"))
    p2.add_argument("--src", default="en")
    p3 = sub.add_parser("apply", help="crea una COPIA traducida de data (no toca el original)")
    common(p3)
    p3.add_argument("--out", help="carpeta de salida (por defecto <data>_<lang>)")

    a = ap.parse_args(argv)
    memory = Memory(a.memory or "nion_memory_%s.json" % a.lang.lower())
    try:
        data_dir, entries = scan(a.game)
        if a.cmd == "scan":
            todo = pending_texts(entries, memory)
            print("Carpeta data:", data_dir)
            print("Entradas:", len(entries))
            print("Por traducir:", len(todo), "textos,", sum(map(len, todo)), "caracteres")
        elif a.cmd == "translate":
            engine = get_engine(a.engine, a.key)
            translate_pending(entries, memory, engine, a.src, a.lang)
            print("TERMINADO. Memoria:", memory.path)
        else:
            out = a.out or data_dir.rstrip("/\\") + "_" + a.lang.lower()
            _, missing = apply_translations(a.game, out, memory)
            if missing:
                with open("faltan.txt", "w", encoding="utf-8") as fh:
                    fh.write("\n".join(missing))
                print("Lo que falta está en faltan.txt")
            print("LISTO. Salida:", out)
    except (EngineError, FileNotFoundError) as e:
        print("ERROR:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
