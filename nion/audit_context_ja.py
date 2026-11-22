"""Audita comparaciones V5 sin traducir de nuevo ni modificar archivos originales.

Detecta repeticiones, reducción extrema y pérdida de entidades/terminología
específica. Las señales no sustituyen la revisión humana de significado.
"""
import argparse
import json
import os
import re
from collections import Counter

REPETITION = re.compile(r"(.{2,8}?)\1{3,}")
TERMS = {
    "dungeon": ("ダンジョン",),
    "dungeons": ("ダンジョン",),
    "demon king": ("魔王", "悪魔王"),
    "demon lord": ("魔王", "悪魔王"),
    "volcano": ("火山",),
    "princess": ("姫", "王女"),
    "capital": ("首都", "王都"),
}
PROPER = {
    "eisel": ("アイゼル", "イーゼル"),
    "dusaria": ("デュサリア", "ダサリア"),
}


def flags_for(group):
    en, ja = group["en_joined"], group["ja_joined"]
    flags = []
    if REPETITION.search(ja):
        flags.append("repeticion_grave")
    if len(en) >= 70 and len(ja.strip()) < len(en) * 0.28:
        flags.append("posible_omision_por_longitud")
    low = en.lower()
    for term, variants in {**TERMS, **PROPER}.items():
        if re.search(r"\b" + re.escape(term) + r"\b", low) and not any(v in ja for v in variants):
            flags.append("termino_ausente:" + term)
    # Comprobación de frases completas, no una puntuación semántica.
    if "pacific kingdom" in low and "太平洋" in ja:
        flags.append("falso_amigo_pacific")
    if "hope finally falls" in low and "希望" in ja:
        flags.append("hope_interpretado_como_sustantivo")
    return flags


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("report", help="comparacion_contexto_ja_v5.json")
    p.add_argument("--out", required=True, help="Ruta nueva")
    args = p.parse_args()
    if os.path.abspath(args.report) == os.path.abspath(args.out) or os.path.exists(args.out):
        p.error("La salida ya existe o coincide con la entrada")
    with open(args.report, encoding="utf-8") as f:
        data = json.load(f)
    groups = data.get("groups")
    if not isinstance(groups, list):
        p.error("Reporte V5 sin groups")
    reviewed = []
    counter = Counter()
    for group in groups:
        if not all(isinstance(group.get(k), str) for k in ("en_joined", "ja_joined")):
            p.error("Grupo V5 incompleto")
        flags = flags_for(group)
        counter.update(flags)
        reviewed.append({**group, "alertas_v5": flags, "requiere_revision_humana": True})
        print("Grupo %s: %s" % (group.get("ids"), ", ".join(flags) if flags else "sin señales automáticas"))
    output = {"experimental": True, "groups": reviewed,
              "summary": {"groups": len(reviewed),
                          "flagged": sum(bool(g["alertas_v5"]) for g in reviewed),
                          "counts": dict(counter)},
              "warning": "Sin alertas no significa traducción correcta. No exportar a RPG Maker."}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "x", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("Grupos con señales: %d/%d" % (output["summary"]["flagged"], len(reviewed)))
    print("Guardado:", args.out)
    print("No se alteraron memorias ni datos del juego.")


if __name__ == "__main__":
    main()
