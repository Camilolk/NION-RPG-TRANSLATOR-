"""V7: probar traducción por oraciones completas de grupos reconstruidos.

Lee V5, traduce cada oración del grupo en lotes, y compara con V5.
No redistribuye a cuadros RPG Maker ni toca memorias o datos originales.
"""
import argparse
import json
import os
import time
from .ja_sentences import split_sentences_safe
from .compare_context_ja_v6 import inspect


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("report", help="comparacion_contexto_ja_v5.json")
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
        p.error("Faltan grupos V5")
    pieces, owners = [], []
    for idx, g in enumerate(groups):
        if not isinstance(g.get("en_joined"), str) or not isinstance(g.get("ja_joined"), str):
            p.error("Grupo incompleto")
        for sentence in split_sentences_safe(g["en_joined"]):
            if sentence.strip():
                pieces.append(sentence.strip())
                owners.append(idx)
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    except ImportError:
        p.error("Instala torch, transformers y sentencepiece")
    tokenizer = AutoTokenizer.from_pretrained("facebook/nllb-200-distilled-600M", src_lang="eng_Latn")
    model = AutoModelForSeq2SeqLM.from_pretrained("facebook/nllb-200-distilled-600M")
    model.eval()
    target = tokenizer.convert_tokens_to_ids("jpn_Jpan")
    if target == tokenizer.unk_token_id:
        p.error("Token japonés no disponible")
    outputs = []
    start = time.perf_counter()
    for offset in range(0, len(pieces), args.batch_size):
        batch = pieces[offset:offset + args.batch_size]
        encoded = tokenizer(batch, padding=True, truncation=False, return_tensors="pt")
        if encoded["input_ids"].shape[1] > 512:
            p.error("Oración demasiado larga; no se guardó reporte")
        with torch.inference_mode():
            ids = model.generate(**encoded, forced_bos_token_id=target,
                                 num_beams=4, max_new_tokens=160)
        outputs.extend(tokenizer.batch_decode(ids, skip_special_tokens=True))
        print("Oraciones: %d/%d" % (min(offset + len(batch), len(pieces)), len(pieces)), flush=True)
    grouped = [[] for _ in groups]
    for owner, ja in zip(owners, outputs):
        grouped[owner].append(ja.strip())
    results = []
    for g, sentences in zip(groups, grouped):
        en = g["en_joined"]
        ja = "".join(sentences)
        old = g["ja_joined"]
        flags_old, flags_new = inspect(en, old), inspect(en, ja)
        results.append({"ids": g.get("ids"), "en_joined": en,
                        "ja_v5_conjunto": old, "ja_v7_oraciones": ja,
                        "alertas_v5": flags_old, "alertas_v7": flags_new,
                        "oraciones": len(sentences), "aprobado_para_exportar": False})
        print("\nGRUPO", g.get("ids"))
        print("V5:", old)
        print("V7:", ja)
        print("Alertas V5:", flags_old, "| V7:", flags_new)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "x", encoding="utf-8") as f:
        json.dump({"experimental": True, "elapsed_seconds": round(time.perf_counter()-start, 2),
                   "note": "Ninguna traducción está aprobada para exportación.",
                   "groups": results}, f, ensure_ascii=False, indent=2)
    print("\nReporte:", args.out)
    print("Memorias y archivos del juego intactos.")


if __name__ == "__main__":
    main()
