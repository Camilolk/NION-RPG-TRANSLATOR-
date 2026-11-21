"""Auditoria no destructiva de memorias de traduccion NION."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path
from .codes import CODE_RE

TOKEN = re.compile(r"\[\[NION_TOKEN_\d+\]\]")
PUNCT_RUN = re.compile(r"([!?¡¿.,])\1{7,}")
WORD_RUN = re.compile(r"(?i)(\b[\wáéíóúñ]+\b)(?:\s+\1){5,}")
LETTERS = re.compile(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{4,}")

def inspect(source, translated):
    if not isinstance(translated, str) or not translated.strip():
        return ["traduccion_vacia"]
    issues = []
    if CODE_RE.findall(source) != CODE_RE.findall(translated):
        issues.append("codigos_diferentes")
    if TOKEN.findall(source) != TOKEN.findall(translated):
        issues.append("marcadores_diferentes")
    if PUNCT_RUN.search(translated) or WORD_RUN.search(translated):
        issues.append("repeticion_anomala")
    if len(source) >= 20 and len(translated) > len(source) * 3:
        issues.append("expansion_extrema")
    if len(source) >= 40 and len(translated) < len(source) * .25:
        issues.append("reduccion_extrema")
    if source == translated and LETTERS.search(source):
        issues.append("sin_cambios_revisar")
    # La memoria conserva espacios significativos: solo alertar si difieren.
    if (len(source)-len(source.lstrip()),len(source)-len(source.rstrip())) != (
        len(translated)-len(translated.lstrip()),len(translated)-len(translated.rstrip())
    ):
        issues.append("espacios_alterados")
    return issues

def audit(memory):
    result = []
    for source, translated in memory.items():
        if not isinstance(source, str):
            continue
        issues = inspect(source, translated)
        if issues:
            result.append({"original":source,"traduccion":translated,"problemas":issues})
    return result

def main(argv=None):
    p = argparse.ArgumentParser(description="Audita la memoria sin modificarla")
    p.add_argument("memory")
    p.add_argument("--out", default="nion_revisar_v2.json")
    args = p.parse_args(argv)
    source, output = Path(args.memory).resolve(), Path(args.out).resolve()
    if source == output or output.exists():
        p.error("El informe ya existe o coincide con la memoria: "+str(output))
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        p.error("La memoria debe ser un objeto JSON")
    result = audit(data)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Entradas:",len(data),"| Para revisar:",len(result),"| Informe:",output)
    for key, count in Counter(p for row in result for p in row["problemas"]).most_common():
        print(" ",key,":",count)
    print("No se modifico la memoria. Las alertas requieren revision humana.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
