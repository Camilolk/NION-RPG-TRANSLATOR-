"""Auditoría conservadora del piloto japonés NLLB, sin alterar memorias.

Lee el reporte JSON existente y genera otro reporte con alertas verificables.
No intenta corregir automáticamente traducciones ambiguas.
"""
import argparse
import json
import os
import re
from collections import Counter

LABEL_RE = re.compile(r"^\s*(\[[A-Za-z][A-Za-z ]{0,40}\])")
LABELS = {
    "[General Equipment]": "[一般装備]",
    "[Large Shield]": "[大盾]",
    "[Accessory]": "[アクセサリー]",
}
TERMS = [
    (re.compile(r"\bdungeons?\b", re.I), "ダンジョン", ("牢屋", "牢獄", "刑務所")),
    (re.compile(r"\bvein\b", re.I), "鉱脈", ("静脈",)),
    (re.compile(r"\bcharm\b", re.I), "お守り", ("魅力",)),
]
# Estas cadenas son señales de errores concretos observados, no prueba de fallo universal.
ODD_REPETITION = re.compile(r"(.{2,8}?)(?:\1){2,}")


def audit(row):
    source, translated = row["en"], row["ja"]
    flags = []
    label = LABEL_RE.match(source)
    if label:
        expected = LABELS.get(label.group(1))
        if expected and not translated.lstrip().startswith(expected):
            flags.append("etiqueta_perdida_o_incorrecta")
    for pattern, expected, wrong in TERMS:
        if pattern.search(source):
            if any(term in translated for term in wrong):
                flags.append("termino_rpg_erroneo")
            elif expected not in translated:
                flags.append("termino_rpg_revisar")
    if ODD_REPETITION.search(translated):
        flags.append("repeticion_sospechosa")
    if len(source) >= 45 and len(translated.strip()) < max(5, int(len(source) * 0.18)):
        flags.append("reduccion_extrema")
    if source.count("(") > source.count(")") or source.count('"') % 2:
        flags.append("fragmento_sin_contexto")
    if source.endswith(("\n", " of", " and", " the", " if", " from", " for", " to", " in", " a", " an")):
        flags.append("posible_continuacion")
    return flags


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", help="piloto_ja_100.json existente")
    parser.add_argument("--out", required=True, help="Nuevo reporte; nunca se sobrescribe")
    args = parser.parse_args()
    if os.path.abspath(args.report) == os.path.abspath(args.out):
        parser.error("La salida no puede ser el archivo de entrada")
    if os.path.exists(args.out):
        parser.error("La salida ya existe: " + args.out)
    with open(args.report, encoding="utf-8") as fh:
        report = json.load(fh)
    rows = report.get("rows")
    if not isinstance(rows, list):
        parser.error("El reporte no contiene una lista 'rows' válida")
    reviewed, counts = [], Counter()
    for row in rows:
        if not isinstance(row, dict) or not all(isinstance(row.get(k), str) for k in ("en", "ja")):
            parser.error("Una entrada no contiene textos 'en' y 'ja' válidos")
        flags = audit(row)
        counts.update(flags)
        reviewed.append({**row, "alertas_auditoria": flags})
        if flags:
            print("%03s %s | %s" % (row.get("id", "?"), ", ".join(flags), row["en"][:80]))
    result = {"source_report": os.path.basename(args.report),
              "experimental": True, "rows": reviewed,
              "summary": {"total": len(reviewed), "con_alertas": sum(bool(r["alertas_auditoria"]) for r in reviewed),
                          "por_tipo": dict(counts)}}
    parent = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(parent, exist_ok=True)
    with open(args.out, "x", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print("\nAuditoría: %d/%d textos con alertas; %s" %
          (result["summary"]["con_alertas"], len(reviewed), dict(counts)))
    print("Reporte nuevo:", args.out)
    print("No se alteraron memorias, archivos de juego ni traducciones originales.")


if __name__ == "__main__":
    main()
