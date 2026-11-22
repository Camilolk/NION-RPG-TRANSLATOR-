"""Traducción japonesa reanudable con NLLB; salida en memoria NUEVA y aislada.

Uso:
 python -m nion.translate_ja_nllb GAME --memory RUTA_NUEVA --limit 300
 python -m nion.translate_ja_nllb GAME --memory MISMA_RUTA --limit 300

Nunca importa memorias Marian antiguas. No exporta ni modifica el juego.
--limit limita los segmentos nuevos examinados en esta ejecución (0 = todos).
"""
import argparse
import json
import os
import re

from .codes import CODE_RE, compose_from_segments, needs_translation, text_segments
from .extract import find_data_dir, iter_entries, protected_names
from .glossary import load_glossary, normalize_names
from .memory import Memory
from .quality import inspect as inspect_quality
from .review_semantics_ja_v8 import review

# Solo frases completas y términos inequívocos en este corpus.
EXACT = {
    "A charm that increases Defense.": "防御力を上げるお守り。",
    "A charm that increases Attack.": "攻撃力を上げるお守り。",
    "A charm that increases Agility.": "敏捷性を上げるお守り。",
    "A charm that increases Luck.": "運を上げるお守り。",
    "You've already ventured into the dungeon today.": "今日はすでにダンジョンに入っています。",
    "This vein has already been depleted.": "この鉱脈はすでに採掘し尽くされています。",
}
# Regla conservadora: proteger solo frases con sentido RPG inequívoco.
REPLACEMENTS = (
    (r"\bdungeons\b", "ダンジョン"),
    (r"\bdungeon\b", "ダンジョン"),
    (r"\bpacific kingdom\b", "平和な王国"),
    (r"\bcorruption elements\b", "堕落の要素"),
    (r"\bdemon king\b", "魔王"),
)
REPEAT = re.compile(r"(.{2,8}?)\1{3,}")


def check(source, target):
    if not isinstance(target, str) or not target.strip():
        return ["vacia"]
    problems = inspect_quality(source, target, target_lang="ja")
    bad = {"traduccion_vacia", "repeticion_anomala", "expansion_extrema",
           "reduccion_extrema", "codigos_diferentes", "marcadores_diferentes"}
    issues = sorted(set(problems) & bad)
    if REPEAT.search(target):
        issues.append("repeticion_grave")
    issues.extend(a["code"] for a in review(source, target))
    if CODE_RE.search(target) and not CODE_RE.search(source):
        issues.append("codigo_inesperado")
    return sorted(set(issues))


def collect(data_dir, memory, glossary):
    unique = set()
    segments = []
    for entry in iter_entries(data_dir):
        if not needs_translation(entry.text):
            continue
        prepared = normalize_names(entry.text, glossary)
        for _, core, _ in text_segments(prepared, ()):
            if core not in unique and core not in memory:
                unique.add(core)
                segments.append(core)
    return segments


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("game")
    p.add_argument("--memory", required=True, help="Archivo JSON NUEVO exclusivo para NLLB japonés")
    p.add_argument("--limit", type=int, default=300, help="Máximo de segmentos nuevos (0 = todos)")
    p.add_argument("--batch-size", type=int, default=4)
    p.add_argument("--save-every", type=int, default=32)
    p.add_argument("--retry-rejected", action="store_true")
    args = p.parse_args()
    if args.limit < 0 or not 1 <= args.batch_size <= 8 or args.save_every < 1:
        p.error("limit >= 0, batch-size 1..8, save-every >= 1")
    data_dir = os.path.abspath(find_data_dir(args.game))
    mem_path = os.path.abspath(args.memory)
    if os.path.commonpath([data_dir, mem_path]) == data_dir:
        p.error("La memoria no puede estar dentro de los datos originales")
    if os.path.basename(mem_path) == "nion_memory_en_ja.json":
        p.error("Usa una memoria nueva, NO la memoria japonesa antigua")
    if os.path.exists(mem_path) and not os.path.isfile(mem_path):
        p.error("La ruta de memoria no es un archivo")
    glossary = load_glossary()
    memory = Memory(mem_path)
    rejected_path = mem_path + ".rejected.json"
    rejected_data = {}
    if os.path.isfile(rejected_path):
        with open(rejected_path, encoding="utf-8") as fh:
            rejected_data = json.load(fh)
        if not isinstance(rejected_data, dict):
            p.error("Registro de rechazos inválido")
    segments = collect(data_dir, memory, glossary)
    if not args.retry_rejected:
        skipped = sum(source in rejected_data for source in segments)
        segments = [source for source in segments if source not in rejected_data]
        print("Rechazados previos omitidos:", skipped)
    print("Memoria NLLB:", mem_path)
    print("Segmentos nuevos pendientes:", len(segments))
    if not segments:
        return
    selected = segments[:args.limit] if args.limit else segments
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    except ImportError:
        p.error("Faltan torch, transformers o sentencepiece")
    tokenizer = AutoTokenizer.from_pretrained("facebook/nllb-200-distilled-600M", src_lang="eng_Latn")
    model = AutoModelForSeq2SeqLM.from_pretrained("facebook/nllb-200-distilled-600M")
    model.eval()
    target = tokenizer.convert_tokens_to_ids("jpn_Jpan")
    if target == tokenizer.unk_token_id:
        p.error("No se encontró jpn_Jpan")
    os.makedirs(os.path.dirname(mem_path), exist_ok=True)
    done = accepted = rejected = 0
    def save_progress():
        memory.save()
        tmp = rejected_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(rejected_data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, rejected_path)

    try:
        for offset in range(0, len(selected), args.batch_size):
            chunk = selected[offset:offset + args.batch_size]
            candidates = []
            for source in chunk:
                if source in EXACT:
                    candidates.append((source, None, [], EXACT[source]))
                    continue
                prepared = source
                terms = []
                for pattern, ja in REPLACEMENTS:
                    def sub(match):
                        marker = "ZXQCTX%dQXZ" % len(terms)
                        terms.append((marker, ja))
                        return marker
                    prepared = re.sub(pattern, sub, prepared, flags=re.I)
                candidates.append((source, prepared, terms, None))
            to_translate = [item for item in candidates if item[3] is None]
            outputs = []
            if to_translate:
                texts = [item[1] for item in to_translate]
                inputs = tokenizer(texts, padding=True, return_tensors="pt", truncation=False)
                if inputs["input_ids"].shape[1] > 512:
                    # Evitar que un segmento extremo interrumpa los demás.
                    print("  Lote omitido por longitud >512 tokens:", offset)
                    rejected += len(chunk)
                    for source in chunk:
                        rejected_data[source] = ["longitud_mayor_512_tokens"]
                    done += len(chunk)
                    save_progress()
                    continue
                with torch.inference_mode():
                    ids = model.generate(**inputs, forced_bos_token_id=target,
                                         num_beams=4, max_new_tokens=160)
                outputs = tokenizer.batch_decode(ids, skip_special_tokens=True)
            iterator = iter(outputs)
            for source, prepared, terms, exact in candidates:
                translated = exact if exact is not None else next(iterator)
                valid = True
                for marker, japanese in terms:
                    # Exigir exactamente un marcador, sin tolerar pérdidas.
                    pattern = r"\s*".join(map(re.escape, marker))
                    if len(re.findall(pattern, translated, re.I)) != 1:
                        valid = False
                        break
                    translated = re.sub(pattern, lambda _: japanese, translated,
                                        count=1, flags=re.I)
                if re.search(r"ZXQCTX\d+QXZ", translated):
                    valid = False
                issues = check(source, translated) if valid else ["marcador_perdido"]
                if issues:
                    rejected += 1
                    rejected_data[source] = issues
                    print("  PENDIENTE:", source[:75], "|", ", ".join(issues))
                else:
                    memory.set(source, translated)
                    rejected_data.pop(source, None)
                    accepted += 1
            done += len(chunk)
            if done % args.save_every < args.batch_size or done == len(selected):
                save_progress()
                print("  Procesados %d/%d | guardados %d | pendientes %d" %
                      (done, len(selected), accepted, rejected), flush=True)
    finally:
        # Ctrl+C o error: preservar los lotes ya aceptados.
        save_progress()
        print("Memoria y rechazos guardados. Nuevos aceptados:", accepted,
              "| rechazados en esta pasada:", rejected)
    print("Rechazos acumulados:", len(rejected_data))
    print("Para reintentar rechazos, añade --retry-rejected.")
    print("Para continuar ejecuta el mismo comando con --memory igual.")
    print("No se modificaron archivos del juego ni la memoria japonesa antigua.")


if __name__ == "__main__":
    main()
