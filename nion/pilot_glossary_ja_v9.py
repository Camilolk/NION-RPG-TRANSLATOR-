"""V9: piloto reversible de protección contextual para NLLB japonés.

Solo usa frases de los 13 grupos V7, no toca memorias ni el juego.
Los marcadores se comprueban antes de restaurar el texto; si se pierden,
la propuesta queda rechazada. No distribuye texto a cajas RPG Maker.
"""
import argparse
import json
import os
import re
import time
from .ja_sentences import split_sentences_safe
from .review_semantics_ja_v8 import review

# Solo expresiones inequívocas de este corpus; no sustituir "hope" o
# "corruption" de forma global fuera de contexto.
PHRASES = (
    (r"\bdungeons\b", "DUNGEONS", "ダンジョン"),
    (r"\bdungeon\b", "DUNGEON", "ダンジョン"),
    (r"\bpacific kingdom\b", "PACIFIC_KINGDOM", "平和な王国"),
    (r"\bCorruption elements\b", "CORRUPTION_ELEMENTS", "堕落の要素"),
    (r"\bDemon King\b", "DEMON_KING", "魔王"),
)
PLACEHOLDER = re.compile(r"ZXQCTX(\d+)QXZ")


def protect(sentence):
    replacements = []
    protected = sentence
    for pattern, label, japanese in PHRASES:
        def sub(match):
            token = "ZXQCTX%dQXZ" % len(replacements)
            replacements.append({"token": token, "source": match.group(),
                                 "label": label, "ja": japanese})
            return token
        protected = re.sub(pattern, sub, protected, flags=re.I)
    return protected, replacements


def restore(translated, replacements):
    result = translated
    for r in replacements:
        # NLLB a veces introduce espacios en marcadores; no aceptar salidas
        # si no podemos reconstruir exactamente todos los marcadores.
        token = r["token"]
        pattern = r"\s*".join(map(re.escape, token))
        hits = list(re.finditer(pattern, result, re.I))
        if len(hits) != 1:
            return None, "marcador_perdido_o_duplicado:" + r["label"]
        result = re.sub(pattern, lambda _: r["ja"], result, count=1, flags=re.I)
    if PLACEHOLDER.search(result):
        return None, "marcador_desconocido"
    return result, None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("report", help="piloto_oraciones_ja_v7.json")
    p.add_argument("--out", required=True)
    p.add_argument("--batch-size", type=int, default=4)
    args = p.parse_args()
    if not 1 <= args.batch_size <= 8:
        p.error("batch-size debe estar entre 1 y 8")
    if os.path.abspath(args.report) == os.path.abspath(args.out) or os.path.exists(args.out):
        p.error("La salida ya existe o coincide con la entrada")
    with open(args.report, encoding="utf-8") as f:
        data = json.load(f)
    groups = data.get("groups")
    if not isinstance(groups, list) or not groups:
        p.error("Reporte sin grupos")
    sentences, owners, replacements = [], [], []
    for i, g in enumerate(groups):
        if not isinstance(g.get("en_joined"), str):
            p.error("Grupo inválido")
        for sentence in split_sentences_safe(g["en_joined"]):
            if sentence.strip():
                protected, terms = protect(sentence.strip())
                sentences.append(protected)
                replacements.append(terms)
                owners.append(i)
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    except ImportError:
        p.error("Se requieren torch, transformers y sentencepiece")
    tokenizer = AutoTokenizer.from_pretrained("facebook/nllb-200-distilled-600M", src_lang="eng_Latn")
    model = AutoModelForSeq2SeqLM.from_pretrained("facebook/nllb-200-distilled-600M")
    model.eval()
    target = tokenizer.convert_tokens_to_ids("jpn_Jpan")
    if target == tokenizer.unk_token_id:
        p.error("Token jpn_Jpan desconocido")
    generated = []
    started = time.perf_counter()
    for start in range(0, len(sentences), args.batch_size):
        batch = sentences[start:start + args.batch_size]
        encoded = tokenizer(batch, padding=True, return_tensors="pt", truncation=False)
        if encoded["input_ids"].shape[1] > 512:
            p.error("Oración demasiado larga")
        with torch.inference_mode():
            ids = model.generate(**encoded, forced_bos_token_id=target,
                                 num_beams=4, max_new_tokens=160)
        generated.extend(tokenizer.batch_decode(ids, skip_special_tokens=True))
        print("Oraciones:", len(generated), "/", len(sentences), flush=True)
    by_group = [[] for _ in groups]
    failures = [[] for _ in groups]
    for i, raw, terms in zip(owners, generated, replacements):
        ja, error = restore(raw.strip(), terms)
        if error:
            failures[i].append({"source": sentences[len(by_group[i])],
                                "raw": raw, "reason": error})
        else:
            by_group[i].append(ja)
    results = []
    for i, g in enumerate(groups):
        candidate = "".join(by_group[i]) if not failures[i] else None
        alerts = review(g["en_joined"], candidate) if candidate is not None else []
        results.append({"ids": g.get("ids"), "en": g["en_joined"],
                        "ja_v7": g.get("ja_v7_oraciones"),
                        "ja_v9": candidate, "errors": failures[i],
                        "alerts_v9": alerts, "approved": False})
        print("Grupo %s: %s" % (g.get("ids"),
              "RECHAZADO (marcadores)" if failures[i] else
              "Candidato para revisión; alertas: " +
              (", ".join(a["code"] for a in alerts) or "ninguna")))
        if candidate is not None:
            print("JA:", candidate)
    output = {"experimental": True, "elapsed_seconds": round(time.perf_counter()-started, 2),
              "groups": results,
              "warning": "Marcadores y reglas no garantizan fidelidad. No exportar."}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "x", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("Reporte:", args.out)
    print("Memorias y archivos del juego intactos.")


if __name__ == "__main__":
    main()
