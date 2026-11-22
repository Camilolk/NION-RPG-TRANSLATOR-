"""Reparación revisada de 15 segmentos PT-BR que CT2 no pudo traducir.

Solo añade segmentos pendientes exactos; hace copia de seguridad de la memoria.
"""
import argparse
import shutil
from pathlib import Path

from .memory import Memory
from .pipeline import pending_texts, scan
from .codes import text_segments
from .glossary import load_glossary, normalize_names
from .extract import protected_names
from .quality import inspect

REPAIRS = {
    "Nhaaahh.. Nghhh--! Ahh.. Ahhhhhnnnn...": "Nhaaahh.. Nghhh--! Ahh.. Ahhhhhnnnn...",
    "Wha...w-haa.... w-what??!!!??": "O-o quê... o-o quê??!!!??",
    "C-C...an.... yo-... h-..r.. e....? E..-lio!": "V-você... consegue... me... ouvir...? E-Elio!",
    "A-Ahhh...! Hey~! It's me, yes. Hold on a second, dear~!": "A-Ahhh...! Ei~! Sou eu, sim. Espere um segundo, querido~!",
    "Eh? Are you alright, Elio? You should've called for us! I had no idea.": "Hã? Você está bem, Elio? Devia ter nos chamado! Eu não fazia ideia.",
    "Did something happen? What is that...? You're covered in some sort of goo...": "Aconteceu alguma coisa? O que é isso...? Você está coberto de algum tipo de gosma...",
    "Hnnng.... haaa... ha...": "Hnnng.... haaa... ha...",
    "It's an Aether Stone. Keep it on you, and it'll naturally heighten your sensitivity": "É uma Pedra de Éter. Fique com ela e sua sensibilidade aumentará naturalmente",
    "Are you crazy? There's an entire horde over there!": "Você está louco? Tem uma horda inteira ali!",
    "Lllck... Slrp... slrp...": "Lllck... Slrp... slrp...",
    "N-No! I'm done! Don't you dare touch me again!!": "N-Não! Chega! Não ouse encostar em mim de novo!!",
    "No...! N-No!!!!!!": "Não...! N-Não!!!!!!",
    "Krrr... tzzk... tzzk... Er....tzzssskk...ika! Hello?": "Krrr... tzzk... tzzk... Er....tzzssskk...ika! Alô?",
    "Ghlkgklh... hghnn.... *puaah*": "Ghlkgklh... hghnn.... *puaah*",
    "N-Nooooo... plea-hic n-not with your mouth... nn... haaaaaahh...!": "N-Nããão... por fa-hic favor, n-não com a boca... nn... haaaaaahh...!",
}

def main(argv=None):
    parser = argparse.ArgumentParser(description="Revisar y reparar 15 segmentos PT-BR, con backup")
    parser.add_argument("game")
    parser.add_argument("--memory", required=True)
    parser.add_argument("--commit", action="store_true", help="guardar tras revisar; sin esto es simulación")
    args = parser.parse_args(argv)
    memory = Memory(args.memory)
    data_dir, entries = scan(args.game)
    glossary = load_glossary()
    names = protected_names(data_dir, glossary)
    pending = pending_texts(entries, memory, names, glossary)
    required = set()
    for original in pending:
        for _, core, _ in text_segments(normalize_names(original, glossary), ()):
            if core not in memory:
                required.add(core)
    missing = required - REPAIRS.keys()
    if missing:
        print("Hay segmentos sin propuesta; no se modifica la memoria:")
        for item in sorted(missing):
            print(repr(item))
        return 2
    severe = {"traduccion_vacia", "repeticion_anomala", "expansion_extrema",
              "reduccion_extrema", "codigos_diferentes", "marcadores_diferentes"}
    for original in sorted(required):
        translated = REPAIRS[original]
        issues = severe.intersection(inspect(original, translated))
        if issues:
            print("Rechazado:", repr(original), sorted(issues))
            return 2
        print("EN:", original)
        print("PT:", translated)
        print()
    print("Segmentos revisados:", len(required), "| textos pendientes:", len(pending))
    if not args.commit:
        print("SIMULACIÓN: nada guardado. Usa --commit para confirmar.")
        return 0
    if not required:
        print("No hay nada que guardar.")
        return 0
    path = Path(args.memory)
    backup = path.with_name(path.name + ".before-pt-repair.bak")
    if backup.exists():
        print("Ya existe la copia de seguridad:", backup)
        return 2
    shutil.copy2(path, backup)
    for original in required:
        memory.set(original, REPAIRS[original])
    memory.save()
    remaining = pending_texts(entries, memory, names, glossary)
    print("Backup:", backup)
    print("Textos pendientes después:", len(remaining))
    return 0 if not remaining else 2

if __name__ == "__main__":
    raise SystemExit(main())
