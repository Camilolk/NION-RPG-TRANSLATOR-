"""V6: auditoría comparativa conservadora de grupos japoneses.

No vuelve a traducir, no elige automáticamente ganadores y no toca memorias.
Compara señales entre salida conjunta y salida por fragmentos; identifica
omisiones conocidas que las reglas V5 no captaban.
"""
import argparse
import json
import os
import re

# Anclas de cobertura conservadoras para conceptos identificables.
# Solo son indicios: presencia de una ancla no garantiza traducción correcta.
ANCHORS = (
    (r"\bdemon king\b", ("魔王", "悪魔王")),
    (r"\bdungeons?\b", ("ダンジョン",)),
    (r"\bvolcano\b", ("火山",)),
    (r"\bprincess\b", ("姫", "王女")),
    (r"\bcapital\b", ("首都", "王都")),
    (r"\bwar\b", ("戦争", "戦", "戦い")),
    (r"\bsword\b", ("剣",)),
    (r"\bschool\b", ("学校",)),
    (r"\bmonsters?\b", ("モンスター", "怪物")),
    (r"\bfortress\b", ("要塞", "砦")),
    (r"\btechnology\b", ("技術",)),
)
# Pares conceptuales que faltaron en la salida conjunta de V5.
CONTRASTS = (
    ("but it's pretty much mine", ("私のもの", "自分のもの")),
    ("this brought enormous change", ("大きな変化", "巨大な変化", "大変化")),
    ("they're all laughing", ("笑",)),
    ("fucking", ("クソ", "くそ", "ふざけ")),
    ("demon king", ("魔王", "悪魔王")),
)
REPEAT = re.compile(r"(.{2,8}?)\1{3,}")


def inspect(en, ja):
    issues = []
    low = en.lower()
    if REPEAT.search(ja):
        issues.append("repeticion_grave")
    if len(en) >= 70 and len(ja.strip()) < len(en) * 0.28:
        issues.append("reduccion_sospechosa")
    for pattern, variants in ANCHORS:
        if re.search(pattern, low) and not any(x in ja for x in variants):
            issues.append("ancla_ausente:" + pattern.replace(r"\b", ""))
    for phrase, variants in CONTRASTS:
        if phrase in low and not any(x in ja for x in variants):
            issues.append("concepto_ausente:" + phrase)
    if "pacific kingdom" in low and "太平洋" in ja:
        issues.append("falso_amigo_pacific")
    if "hope finally falls" in low and "希望" in ja:
        issues.append("hope_mal_interpretado")
    return issues


def compare(group):
    en = group["en_joined"]
    joined = group["ja_joined"]
    fragments = group["ja_original"]
    # La versión aislada es solo una concatenación de referencia; no una
    # reconstrucción lista para mostrar en RPG Maker.
    isolated = "".join(fragments)
    a = inspect(en, isolated)
    b = inspect(en, joined)
    if not a and not b:
        status = "ambas_sin_senales_revisar"
    elif not b and a:
        status = "conjunta_prometedora_revisar"
    elif b and not a:
        status = "aislada_prometedora_revisar"
    else:
        status = "ambas_con_senales_revisar"
    return {"ids": group["ids"], "en_joined": en,
            "ja_isolated": isolated, "ja_joined": joined,
            "alertas_aislada": a, "alertas_conjunta": b,
            "estado": status, "aprobado_para_exportar": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", help="comparacion_contexto_ja_v5.json")
    parser.add_argument("--out", required=True, help="Reporte nuevo")
    args = parser.parse_args()
    if os.path.abspath(args.report) == os.path.abspath(args.out) or os.path.exists(args.out):
        parser.error("La salida ya existe o coincide con la entrada")
    with open(args.report, encoding="utf-8") as f:
        data = json.load(f)
    groups = data.get("groups")
    if not isinstance(groups, list):
        parser.error("No se encontró groups")
    rows = []
    for g in groups:
        if (not isinstance(g, dict) or not isinstance(g.get("en_joined"), str)
                or not isinstance(g.get("ja_joined"), str)
                or not isinstance(g.get("ja_original"), list)
                or not all(isinstance(x, str) for x in g["ja_original"])
                or not isinstance(g.get("ids"), list)):
            parser.error("Grupo inválido")
        row = compare(g)
        rows.append(row)
        print("Grupo %s: %s" % (row["ids"], row["estado"]))
        if row["alertas_conjunta"]:
            print("  Conjunta:", ", ".join(row["alertas_conjunta"]))
        if row["alertas_aislada"]:
            print("  Aislada:", ", ".join(row["alertas_aislada"]))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "x", encoding="utf-8") as f:
        json.dump({"experimental": True, "groups": rows,
                   "note": "Ninguna alternativa está aprobada para exportación automática."},
                  f, ensure_ascii=False, indent=2)
    print("\nComparados:", len(rows))
    print("Reporte:", args.out)
    print("No se modificaron memorias ni archivos del juego.")


if __name__ == "__main__":
    main()
