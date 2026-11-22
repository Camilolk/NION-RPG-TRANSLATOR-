"""V8: revisión semántica orientada a RPG de los resultados japoneses V7.

Analiza JSON existente sin modelos, sin modificar textos, memoria ni juego.
Las reglas son indicios y no validan traducciones automáticamente.
"""
import argparse
import json
import os
import re
from collections import Counter

# Contextos identificados en el piloto real; no sustituciones universales.
RULES = (
    ("dungeon_como_carcel", r"\bdungeons?\b", r"牢屋|牢獄|刑務所",
     "Dungeon se refiere a mazmorra: ダンジョン"),
    ("pacific_como_oceano", r"\bpacific kingdom\b", r"太平洋",
     "Pacific aquí significa pacífico: 平和な王国"),
    ("corruption_como_administrativa", r"\bcorruption elements\b", r"汚職",
     "Corruption aquí refiere a corrupción moral: 堕落 / 腐敗"),
    ("hope_como_sustantivo", r"\bhope finally falls\b", r"希望",
     "Hope forma parte de la frase 'Hope [he] finally falls', no es el sustantivo esperanza"),
    ("insulto_fuck_repetido", r"\bfuck them\b", r"(?:ほら[\s、,]*){3,}",
     "Insulto omitido y reemplazado por repetición"),
    ("bastards_como_prostitutas", r"\bbastards\b", r"売春婦",
     "Bastards es un insulto distinto de 'prostitutas'"),
)
COVERAGE = (
    ("despertar_rey_demonio", r"\bawakening of the demon king\b", ("魔王", "悪魔王")),
    ("cambio_enorme", r"\bthis brought enormous change\b", ("大きな変化", "巨大な変化", "大変化")),
    ("risas_de_otros", r"\bthey're all laughing\b", ("笑",)),
    ("lugar_propio", r"\bpretty much mine\b", ("私のもの", "自分のもの")),
)
REPEAT = re.compile(r"(.{2,8}?)\1{3,}")


def review(en, ja):
    alerts = []
    for code, source_pattern, target_pattern, advice in RULES:
        if re.search(source_pattern, en, re.I) and re.search(target_pattern, ja):
            alerts.append({"code": code, "advice": advice})
    for code, source_pattern, expected in COVERAGE:
        if re.search(source_pattern, en, re.I) and not any(term in ja for term in expected):
            alerts.append({"code": "concepto_ausente:" + code,
                           "advice": "Revisar omisión del concepto en japonés"})
    if REPEAT.search(ja):
        alerts.append({"code": "repeticion_grave", "advice": "Repetición anómala"})
    return alerts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", help="piloto_oraciones_ja_v7.json")
    parser.add_argument("--out", required=True, help="Archivo nuevo, no se sobrescribe")
    args = parser.parse_args()
    if os.path.abspath(args.report) == os.path.abspath(args.out) or os.path.exists(args.out):
        parser.error("La salida ya existe o coincide con la entrada")
    with open(args.report, encoding="utf-8") as fh:
        data = json.load(fh)
    groups = data.get("groups")
    if not isinstance(groups, list):
        parser.error("El archivo no contiene groups")
    results = []
    counter = Counter()
    for g in groups:
        if not isinstance(g, dict) or not all(isinstance(g.get(k), str)
                for k in ("en_joined", "ja_v5_conjunto", "ja_v7_oraciones")):
            parser.error("Grupo incompleto")
        en = g["en_joined"]
        a = review(en, g["ja_v5_conjunto"])
        b = review(en, g["ja_v7_oraciones"])
        counter.update(x["code"] for x in b)
        row = {"ids": g.get("ids"), "en": en,
               "ja_v5": g["ja_v5_conjunto"], "ja_v7": g["ja_v7_oraciones"],
               "alertas_v5": a, "alertas_v7": b,
               "revision_humana_obligatoria": True, "aprobado_para_exportar": False}
        results.append(row)
        print("Grupo %s | V5: %s | V7: %s" %
              (row["ids"], ", ".join(x["code"] for x in a) or "sin señales",
               ", ".join(x["code"] for x in b) or "sin señales"))
    output = {"experimental": True, "groups": results,
              "summary": {"total": len(results),
                          "v7_con_alertas": sum(bool(g["alertas_v7"]) for g in results),
                          "por_tipo_v7": dict(counter)},
              "warning": "Sin alertas no significa traducción correcta. No exportar."}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "x", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)
    print("\nV7 con señales semánticas: %d/%d" %
          (output["summary"]["v7_con_alertas"], len(results)))
    print("Reporte:", args.out)
    print("Juego y memorias intactos.")


if __name__ == "__main__":
    main()
