"""Repara seis textos italianos con vista previa, validación y respaldo."""
import argparse
from datetime import datetime
from pathlib import Path
import re
import shutil

from .codes import CODE_RE
from .extract import protected_names
from .glossary import load_glossary
from .memory import Memory
from .pipeline import pending_texts, scan

TRANSLATIONS = {
    "I'm absolutely... not enjoying it! I hate it! Stop it right now... i-it's":
        "Non mi sta piacendo... per niente! Lo odio! Smettila subito... è-è...",
    "She's over there! R-Right in the middle...!":
        "È laggiù! P-Proprio in mezzo...!",
    "\\}A prostitute, huh? I'll have to take it out on her for now. Better than nothing.":
        "\\}Una prostituta, eh? Per ora dovrò sfogarmi su di lei. Meglio di niente.",
    "%1’s %2 went up!":
        "%1: %2 è aumentato!",
    "%1’s %2 went down!":
        "%1: %2 è diminuito!",
    "%1’s %2 returned to normal!":
        "%1: %2 è tornato alla normalità!",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game")
    parser.add_argument("--memory", required=True)
    parser.add_argument("--commit", action="store_true", help="Guardar con respaldo")
    args = parser.parse_args()
    path = Path(args.memory)
    if not path.is_file():
        parser.error("Memoria no encontrada: " + str(path))
    folder, entries = scan(args.game)
    glossary = load_glossary()
    memory = Memory(str(path))
    names = protected_names(folder, glossary)
    pending = pending_texts(entries, memory, names, glossary)
    if len(pending) != 6 or set(pending) != set(TRANSLATIONS):
        print("Pendientes encontrados:", len(pending))
        for source in pending:
            print(repr(source))
        parser.error("Los pendientes no coinciden; no se modificó la memoria.")
    for source in pending:
        target = TRANSLATIONS[source]
        if CODE_RE.findall(source) != CODE_RE.findall(target):
            parser.error("Códigos RPG Maker distintos: " + repr(source))
        if sorted(re.findall(r"%[1-9]\d*", source)) != sorted(re.findall(r"%[1-9]\d*", target)):
            parser.error("Variables RPG Maker distintas: " + repr(source))
        print("EN:", repr(source))
        print("IT:", repr(target))
    if not args.commit:
        print("VISTA PREVIA: añade --commit para guardar.")
        return
    backup = path.with_name(path.name + ".before-it-repair-" +
                            datetime.now().strftime("%Y%m%d-%H%M%S") + ".bak")
    shutil.copy2(path, backup)
    for source in pending:
        memory.set(source, TRANSLATIONS[source])
    memory.save()
    remaining = pending_texts(entries, memory, names, glossary)
    print("RESPALDO:", backup)
    print("Pendientes restantes:", len(remaining))


if __name__ == "__main__":
    main()
