"""Repara ocho textos rusos con validación estricta y respaldo; vista previa por defecto."""
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
        "Мне это совершенно... не нравится! Ненавижу! Прекрати немедленно... э-это",
    "\\}W-Why is she dressed like that...? How can she go around like that without being ashamed...?":
        "\\}П-почему она так одета...? Как она может так ходить и совсем не стыдиться...?",
    "Hey, are you okay? You're a bit pale. Don't you go fainting on me, pal!":
        "Эй, ты в порядке? Ты немного побледнел. Только не вздумай падать в обморок, приятель!",
    "What? Come on. I can't go back there with a boner. What are they going to think?":
        "Что? Да ладно. Я не могу вернуться туда с эрекцией. Что они обо мне подумают?",
    "Who... who are you?! (A-And why are you dressed like that...?)\\!":
        "Кто... кто ты?! (И-и почему ты так одета...?)\\!",
    "Huh... Where does this even lead? Is it towards the Temple, maybe?":
        "Хм... Куда вообще ведёт эта дорога? Может, к Храму?",
    "Nnnnnhhh....!!! W-What are you doing?! I didn't... you can't... why did you...":
        "Ннннхх....!!! Ч-что ты делаешь?! Я не... ты не можешь... зачем ты...",
    "\\}What the hell was that?! Did the viewport malfunction? It was still synchronized to Erika's communicator...":
        "\\}Что, чёрт возьми, это было?! Смотровой экран неисправен? Он ведь всё ещё был синхронизирован с коммуникатором Эрики...",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game")
    parser.add_argument("--memory", required=True)
    parser.add_argument("--commit", action="store_true", help="Guardar tras crear respaldo")
    args = parser.parse_args()
    path = Path(args.memory)
    if not path.is_file():
        parser.error("Memoria no encontrada: " + str(path))
    folder, entries = scan(args.game)
    glossary = load_glossary()
    memory = Memory(str(path))
    pending = pending_texts(entries, memory, protected_names(folder, glossary), glossary)
    if len(pending) != 8 or set(pending) != set(TRANSLATIONS):
        print("Pendientes actuales:", len(pending))
        for source in pending:
            print(repr(source))
        parser.error("Los pendientes ya no coinciden; no se modificó la memoria.")
    for source in pending:
        target = TRANSLATIONS[source]
        if CODE_RE.findall(source) != CODE_RE.findall(target):
            parser.error("Códigos RPG Maker distintos: " + repr(source))
        if sorted(re.findall(r"%[1-9]\d*", source)) != sorted(re.findall(r"%[1-9]\d*", target)):
            parser.error("Variables RPG Maker distintas: " + repr(source))
        print("EN:", repr(source))
        print("RU:", repr(target))
    if not args.commit:
        print("VISTA PREVIA: usa --commit para guardar con respaldo.")
        return
    backup = path.with_name(path.name + ".before-ru-repair-" +
                            datetime.now().strftime("%Y%m%d-%H%M%S") + ".bak")
    shutil.copy2(path, backup)
    for source in pending:
        memory.set(source, TRANSLATIONS[source])
    memory.save()
    remaining = pending_texts(entries, memory, protected_names(folder, glossary), glossary)
    print("RESPALDO:", backup)
    print("Pendientes restantes:", len(remaining))


if __name__ == "__main__":
    main()
