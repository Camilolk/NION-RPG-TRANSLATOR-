"""Piloto NLLB inglés->japonés: 100 textos reales, sin tocar memorias.

Uso: python -m nion.pilot_nllb_ja RUTA_DATA --limit 100
"""
import argparse
import json
import os
import time
import re
from .codes import CODE_RE, text_segments
from .extract import find_data_dir, iter_entries
from .ja_sentences import split_sentences_safe

# Etiquetas de categoría verificadas en el piloto; no se envían al modelo.
CATEGORY_LABELS = {
    "[General Equipment]": "[一般装備]",
    "[Large Shield]": "[大盾]",
    "[Accessory]": "[アクセサリー]",
}
CATEGORY_RE = re.compile(r"^(\\s*)(\\[[A-Za-z][A-Za-z ]{0,40}\\])(\\s*)")



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", help="Carpeta data del juego original en inglés")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--out", help="Reporte JSON nuevo, opcional (no memoria)")
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000 or not 1 <= args.batch_size <= 16:
        parser.error("--limit debe ser 1..1000 y --batch-size 1..16")
    if args.out and os.path.exists(args.out):
        parser.error("El reporte ya existe; no se sobrescribirá: " + args.out)
    data_dir = find_data_dir(args.game)
    seen, sources = set(), []
    for entry in iter_entries(data_dir):
        for _, core, _ in text_segments(entry.text):
            if core not in seen and len(core) >= 18 and not CODE_RE.search(core):
                seen.add(core)
                sources.append(core)
        if len(sources) >= args.limit:
            break
    sources = sources[:args.limit]
    if not sources:
        parser.error("No se encontraron textos para el piloto.")
    print("Muestra: %d textos reales; datos originales intactos." % len(sources), flush=True)

    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    except ImportError:
        parser.error("Faltan torch, transformers o sentencepiece.")
    model_id = "facebook/nllb-200-distilled-600M"
    tokenizer = AutoTokenizer.from_pretrained(model_id, src_lang="eng_Latn")
    model = AutoModelForSeq2SeqLM.from_pretrained(model_id)
    model.eval()
    target = tokenizer.convert_tokens_to_ids("jpn_Jpan")
    if target == tokenizer.unk_token_id:
        parser.error("Token jpn_Jpan no disponible.")

    # Cada oración se traduce individualmente, pero se ejecuta en lotes.
    pieces, owners = [], []
    prefixes = [""] * len(sources)
    for index, source in enumerate(sources):
        body = source
        label_match = CATEGORY_RE.match(source)
        if label_match and label_match.group(2) in CATEGORY_LABELS:
            prefixes[index] = (label_match.group(1)
                               + CATEGORY_LABELS[label_match.group(2)]
                               + label_match.group(3))
            body = source[label_match.end():]
        for piece in split_sentences_safe(body):
            if piece.strip():
                pieces.append(piece.strip())
                owners.append(index)
    translated = []
    start = time.perf_counter()
    for offset in range(0, len(pieces), args.batch_size):
        batch = pieces[offset:offset + args.batch_size]
        encoded = tokenizer(batch, padding=True, truncation=True,
                            max_length=256, return_tensors="pt")
        with torch.inference_mode():
            ids = model.generate(**encoded, forced_bos_token_id=target,
                                 num_beams=4, max_new_tokens=160)
        translated.extend(tokenizer.batch_decode(ids, skip_special_tokens=True))
        if (offset // args.batch_size + 1) % 10 == 0:
            print("  %d/%d oraciones" % (min(offset + args.batch_size, len(pieces)),
                                          len(pieces)), flush=True)
    grouped = [[] for _ in sources]
    for owner, result in zip(owners, translated):
        grouped[owner].append(result.strip())
    rows = []
    for i, (source, fragments) in enumerate(zip(sources, grouped), 1):
        target_text = prefixes[i-1] + "".join(fragments)
        # Indicador heurístico, no evaluación semántica.
        suspicious = len(source) >= 50 and len(target_text) < max(6, int(len(source) * 0.17))
        rows.append({"id": i, "en": source, "ja": target_text,
                     "revisar_longitud": suspicious, "oraciones": len(fragments)})
        print("\n%03d EN: %s\n    JA: %s%s" %
              (i, source, target_text, " [REVISAR]" if suspicious else ""), flush=True)
    print("\nTiempo: %.1f s | %d textos | %d oraciones | alertas: %d" %
          (time.perf_counter()-start, len(rows), len(pieces),
           sum(row["revisar_longitud"] for row in rows)), flush=True)
    if args.out:
        parent = os.path.dirname(os.path.abspath(args.out))
        os.makedirs(parent, exist_ok=True)
        # Evita carreras y sobrescritura accidental.
        with open(args.out, "x", encoding="utf-8") as fh:
            json.dump({"model": model_id, "experimental": True, "rows": rows},
                      fh, ensure_ascii=False, indent=2)
        print("Reporte guardado:", args.out)
    print("No se escribió ninguna memoria ni archivo del juego.")


if __name__ == "__main__":
    main()
