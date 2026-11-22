"""Repara el último diálogo francés con respaldo y validación; vista previa por defecto."""
import argparse
from datetime import datetime
from pathlib import Path
import shutil

from .codes import CODE_RE
from .extract import protected_names
from .glossary import load_glossary
from .memory import Memory
from .pipeline import pending_texts, scan

SOURCE = "I feel really bad, Grant. So... I... w-what can I do to make it up to you? I'll pay you back for whatever you spent for us..."
TARGET = "Je me sens vraiment mal, Grant. Alors... je... q-qu'est-ce que je peux faire pour me racheter ? Je te rembourserai tout ce que tu as dépensé pour nous..."


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game")
    parser.add_argument("--memory", required=True)
    parser.add_argument("--commit", action="store_true", help="Guardar con respaldo")
    args = parser.parse_args()
    path = Path(args.memory)
    if not path.is_file():
        parser.error("No se encontró la memoria: " + str(path))
    folder, entries = scan(args.game)
    glossary = load_glossary()
    names = protected_names(folder, glossary)
    memory = Memory(str(path))
    pending = pending_texts(entries, memory, names, glossary)
    if pending != [SOURCE]:
        print("Pendientes encontrados:", len(pending))
        for item in pending[:10]:
            print(repr(item))
        parser.error("El conjunto de pendientes cambió. No se modificó la memoria.")
    if CODE_RE.findall(SOURCE) != CODE_RE.findall(TARGET):
        parser.error("Los códigos RPG Maker no coinciden.")
    print("EN:", SOURCE)
    print("FR:", TARGET)
    if not args.commit:
        print("VISTA PREVIA: no se modificó la memoria. Añade --commit para guardar.")
        return
    backup = path.with_name(path.name + ".before-fr-repair-" +
                            datetime.now().strftime("%Y%m%d-%H%M%S") + ".bak")
    shutil.copy2(path, backup)
    memory.set(SOURCE, TARGET)
    memory.save()
    remaining = pending_texts(entries, memory, names, glossary)
    print("RESPALDO:", backup)
    print("Pendientes restantes:", len(remaining))


if __name__ == "__main__":
    main()
