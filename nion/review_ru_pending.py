"""Muestra los textos rusos pendientes completos para reparación humana.

Solo lectura; no modifica memorias ni archivos del juego.
"""
import argparse
from .extract import protected_names
from .glossary import load_glossary
from .memory import Memory
from .pipeline import scan, pending_texts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game")
    parser.add_argument("--memory", required=True)
    args = parser.parse_args()
    folder, entries = scan(args.game)
    glossary = load_glossary()
    memory = Memory(args.memory)
    pending = pending_texts(entries, memory, protected_names(folder, glossary), glossary)
    print("Pendientes rusos:", len(pending))
    for i, source in enumerate(pending, 1):
        print("%02d EN: %r" % (i, source))


if __name__ == "__main__":
    main()
