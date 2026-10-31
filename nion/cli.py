"""CLI mínima: python -m nion scan|translate|apply JUEGO ..."""
import argparse
import os
import sys
from .engine import EngineError, get_engine
from .extract import protected_names
from .glossary import load_glossary
from .memory import Memory
from .pipeline import apply_translations, pending_texts, scan, translate_pending


def main(argv=None):
    parser = argparse.ArgumentParser(prog="nion", description="NION RPG Translator (núcleo)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def common(command):
        command.add_argument("game", help="carpeta del juego (o su carpeta data)")
        command.add_argument("--lang", default="es", help="idioma destino (es, pt-br, fr...)")
        command.add_argument("--memory", help="archivo de memoria (por defecto nion_memory_<lang>.json)")
        command.add_argument("--glossary", help="JSON de nombres propios (por defecto nion/glossary.json)")

    scan_parser = sub.add_parser("scan", help="cuenta textos sin traducir ni gastar nada")
    common(scan_parser)
    translate_parser = sub.add_parser("translate", help="traduce lo que falta y lo guarda en la memoria")
    common(translate_parser)
    translate_parser.add_argument("--engine", default="deepl", help="echo | deepl | llamacpp")
    translate_parser.add_argument("--key", default=os.environ.get("NION_DEEPL_KEY"))
    translate_parser.add_argument("--url", default=os.environ.get(
        "NION_LLAMACPP_URL", "http://127.0.0.1:8080"),
        help="URL base del servidor llama.cpp")
    translate_parser.add_argument("--src", default="en")
    apply_parser = sub.add_parser("apply", help="crea una COPIA completa traducida; nunca toca el original")
    common(apply_parser)
    apply_parser.add_argument("--out", help="carpeta de salida (por defecto <data>_<lang>)")

    args = parser.parse_args(argv)
    memory = Memory(args.memory or "nion_memory_%s.json" % args.lang.lower())
    try:
        data_dir, entries = scan(args.game)
        glossary = load_glossary(args.glossary)
        names = protected_names(data_dir, glossary)
        if args.cmd == "scan":
            todo = pending_texts(entries, memory, names, glossary, tgt=args.lang)
            print("Carpeta data:", data_dir)
            print("Entradas:", len(entries))
            print("Nombres protegidos:", len(names))
            print("Por traducir:", len(todo), "textos,", sum(map(len, todo)), "caracteres")
        elif args.cmd == "translate":
            engine = get_engine(args.engine, args.key, args.url)
            translate_pending(entries, memory, engine, args.src, args.lang,
                              protected_terms=names, glossary=glossary)
            print("TERMINADO. Memoria:", memory.path)
        else:
            output = args.out or data_dir.rstrip("/\\") + "_" + args.lang.lower()
            applied, missing = apply_translations(
                args.game, output, memory, glossary=glossary, tgt=args.lang
            )
            if missing:
                with open("faltan.txt", "w", encoding="utf-8") as fh:
                    fh.write("\n".join(missing))
                print("NO SE GENERÓ LA COPIA. Faltan textos; consulta faltan.txt.")
                return 2
            print("LISTO. Salida:", output, "| textos aplicados:", applied)
    except (EngineError, FileNotFoundError, ValueError) as error:
        print("ERROR:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
