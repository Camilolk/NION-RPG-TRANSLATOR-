"""V5: comparar traducción aislada vs. conjunta de fragmentos consecutivos.

Solo lee un piloto JSON existente. NO divide de vuelta la traducción japonesa,
ni modifica memorias, juegos o reportes anteriores. Grupos seleccionados
manualmente del piloto de 100 textos, sujetos a revisión humana.
"""
import argparse
import json
import os
import time

# Los ID son los del piloto de 100 entradas, NO índices de archivos del juego.
GROUPS = [
    (54, 55, 56),
    (57, 58, 59),
    (60, 61, 62),
    (63, 64, 65),
    (70, 71),
    (74, 75),
    (76, 77, 78),
    (79, 80, 81),
    (82, 83, 84),
    (86, 87),
    (92, 93, 94),
    (95, 96),
    (99, 100),
]


def make_groups(rows):
    by_id = {row["id"]: row for row in rows}
    groups = []
    for ids in GROUPS:
        if not all(i in by_id for i in ids):
            continue
        originals = [by_id[i]["en"] for i in ids]
        translated = [by_id[i]["ja"] for i in ids]
        # Los cortes de texto RPG Maker no son necesariamente oraciones.
        # Unir con espacio mantiene palabras separadas sin alterar originales.
        joined = " ".join(x.strip() for x in originals)
        groups.append({"ids": list(ids), "en_joined": joined,
                       "en_original": originals, "ja_original": translated})
    return groups


def translate(groups, batch_size):
    import torch
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    model_id = "facebook/nllb-200-distilled-600M"
    tokenizer = AutoTokenizer.from_pretrained(model_id, src_lang="eng_Latn")
    model = AutoModelForSeq2SeqLM.from_pretrained(model_id)
    model.eval()
    target = tokenizer.convert_tokens_to_ids("jpn_Jpan")
    if target == tokenizer.unk_token_id:
        raise ValueError("Token jpn_Jpan no disponible")
    # No usar truncamiento silencioso: los grupos del piloto son cortos.
    start = time.perf_counter()
    for offset in range(0, len(groups), batch_size):
        batch = groups[offset:offset + batch_size]
        inputs = [g["en_joined"] for g in batch]
        encoded = tokenizer(inputs, padding=True, truncation=False, return_tensors="pt")
        if encoded["input_ids"].shape[1] > 512:
            raise ValueError("Grupo demasiado largo para el piloto; abortado sin guardar")
        with torch.inference_mode():
            result = model.generate(**encoded, forced_bos_token_id=target,
                                    num_beams=4, max_new_tokens=320)
        decoded = tokenizer.batch_decode(result, skip_special_tokens=True)
        for group, ja in zip(batch, decoded):
            group["ja_joined"] = ja.strip()
            print("\nGRUPO", group["ids"], flush=True)
            print("EN:", group["en_joined"], flush=True)
            print("JA original:", " | ".join(group["ja_original"]), flush=True)
            print("JA conjunto:", group["ja_joined"], flush=True)
    return time.perf_counter() - start


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pilot", help="Reporte piloto_ja_100_v4.json")
    parser.add_argument("--out", required=True, help="Ruta nueva, sin sobrescribir")
    parser.add_argument("--batch-size", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 8:
        parser.error("--batch-size debe estar entre 1 y 8")
    if os.path.abspath(args.pilot) == os.path.abspath(args.out) or os.path.exists(args.out):
        parser.error("La salida ya existe o coincide con la entrada")
    with open(args.pilot, encoding="utf-8") as f:
        data = json.load(f)
    rows = data.get("rows")
    if not isinstance(rows, list):
        parser.error("Reporte sin lista rows")
    if any(not isinstance(r, dict) or not isinstance(r.get("id"), int)
           or not isinstance(r.get("en"), str) or not isinstance(r.get("ja"), str)
           for r in rows):
        parser.error("Filas inválidas")
    groups = make_groups(rows)
    if not groups:
        parser.error("No se encontraron grupos del piloto de 100 textos")
    print("V5: %d grupos de contexto; comparación experimental." % len(groups), flush=True)
    elapsed = translate(groups, args.batch_size)
    parent = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(parent, exist_ok=True)
    with open(args.out, "x", encoding="utf-8") as f:
        json.dump({"experimental": True, "model": "facebook/nllb-200-distilled-600M",
                   "elapsed_seconds": round(elapsed, 2),
                   "note": "Comparación de grupos; no se ha repartido texto a cuadros RPG Maker",
                   "groups": groups}, f, ensure_ascii=False, indent=2)
    print("\nTiempo: %.1f s | Grupos: %d" % (elapsed, len(groups)))
    print("Reporte nuevo:", args.out)
    print("Memorias y juego intactos.")


if __name__ == "__main__":
    main()
