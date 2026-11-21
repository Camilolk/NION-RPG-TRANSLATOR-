"""Auditoria conservadora de calidad de memorias de traduccion NION."""
import argparse
import json
import re
from pathlib import Path
from .codes import CODE_RE

SPACE = re.compile(r"\\s+")
REPEAT = re.compile(r"([!?.,])\\1{2,}")
TOKEN = re.compile(r"\\[\\[NION_TOKEN_\\d+\\]\\]")

def inspect(source, translated):
    issues = []
    if not isinstance(translated, str) or not translated.strip():
        return ["traduccion_vacia"]
    if source == translated and re.search(r"[A-Za-z]{4,}", source):
        issues.append("sin_cambios")
    if CODE_RE.findall(source) != CODE_RE.findall(translated):
        issues.append("codigos_diferentes")
    if TOKEN.findall(source) != TOKEN.findall(translated):
        issues.append("marcadores_diferentes")
    if REPEAT.search(translated):
        issues.append("puntuacion_repetida")
    if len(source) >= 20 and len(translated) > len(source) * 3:
        issues.append("expansion_extrema")
    if len(source) >= 40 and len(translated) < len(source) * .25:
        issues.append("reduccion_extrema")
    if translated != translated.strip():
        issues.append("espacios_extremos")
    return issues

def audit(memory):
    return [{"original":s,"traduccion":t,"problemas":inspect(s,t)}
            for s,t in memory.items() if isinstance(s,str) and inspect(s,t)]

def main(argv=None):
    p=argparse.ArgumentParser(description="Audita una memoria NION sin modificarla")
    p.add_argument("memory",help="Ruta a nion_marian_es.json")
    p.add_argument("--out",default="nion_revisar.json")
    args=p.parse_args(argv)
    path=Path(args.memory).resolve()
    output=Path(args.out).resolve()
    if path==output:
        p.error("La salida no puede sobrescribir la memoria")
    data=json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data,dict):
        p.error("La memoria debe ser un objeto JSON")
    issues=audit(data)
    if output.exists():
        p.error("El informe ya existe: "+str(output))
    output.write_text(json.dumps(issues,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Entradas:",len(data),"| Para revisar:",len(issues),"| Informe:",output)
    print("Aviso: son alertas heuristicas, no correcciones automaticas.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
