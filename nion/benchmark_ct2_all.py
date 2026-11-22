"""Benchmark aislado CTranslate2 para los ocho idiomas; no modifica memorias ni motores."""
import argparse
import gc
import time
from pathlib import Path

MODELS = {
    "es": ("Helsinki-NLP/opus-mt-en-es", ""),
    "fr": ("Helsinki-NLP/opus-mt-en-fr", ""),
    "de": ("Helsinki-NLP/opus-mt-en-de", ""),
    "it": ("Helsinki-NLP/opus-mt-en-it", ""),
    "ru": ("Helsinki-NLP/opus-mt-en-ru", ""),
    "pt-br": ("Helsinki-NLP/opus-mt-en-ROMANCE", ">>pt<< "),
    "ja": ("Helsinki-NLP/opus-mt-en-jap", ""),
    "zh": ("Helsinki-NLP/opus-mt-en-zh", ">>cmn_Hans<< "),
}


def sample_segments(game, count):
    from .pipeline import scan
    from .glossary import load_glossary, normalize_names
    from .codes import needs_translation, text_segments
    _, entries = scan(game)
    glossary = load_glossary()
    seen, segments = set(), []
    for entry in entries:
        if not needs_translation(entry.text):
            continue
        prepared = normalize_names(entry.text, glossary)
        for _, core, _ in text_segments(prepared, ()):
            if core and core not in seen and len(core) <= 350:
                seen.add(core)
                segments.append(core)
    if not segments:
        raise ValueError("No se encontraron segmentos")
    n = min(count, len(segments))
    return [segments[min(len(segments)-1, i*len(segments)//n)] for i in range(n)]


def run():
    parser = argparse.ArgumentParser(description="Benchmark CT2 aislado para ocho idiomas")
    parser.add_argument("game", help="Carpeta data_ingles")
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--langs", default="es,fr,de,it,ru,pt-br,ja,zh")
    parser.add_argument("--models-dir", default="models/ct2_benchmark")
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    if not 1 <= args.samples <= 1000 or not 1 <= args.batch_size <= 64:
        parser.error("--samples debe ser 1..1000 y --batch-size 1..64")
    langs = [lang.strip().lower() for lang in args.langs.split(",") if lang.strip()]
    if not langs or len(langs) != len(set(langs)) or any(lang not in MODELS for lang in langs):
        parser.error("Idiomas inválidos o duplicados")
    try:
        import ctranslate2
        from transformers import MarianTokenizer
        from ctranslate2.converters import TransformersConverter
    except ImportError:
        parser.error("Instala ctranslate2 y transformers en el entorno virtual")
    selected = sample_segments(args.game, args.samples)
    print("CT2: %d segmentos; %d caracteres; sin guardar memorias." %
          (len(selected), sum(map(len, selected))), flush=True)
    for lang in langs:
        model_id, prefix = MODELS[lang]
        path = Path(args.models_dir) / lang
        # Reuse the already converted Portuguese model when available.
        existing_pt = Path("models/ct2_en_romance")
        if lang == "pt-br" and not (path / "model.bin").is_file() and (existing_pt / "model.bin").is_file():
            path = existing_pt
        try:
            if not (path / "model.bin").is_file():
                if path.exists() and any(path.iterdir()):
                    raise RuntimeError("Carpeta de conversión incompleta: %s" % path)
                path.parent.mkdir(parents=True, exist_ok=True)
                print("%s: convirtiendo %s (primera ejecución)..." % (lang, model_id), flush=True)
                TransformersConverter(model_id).convert(str(path), force=False)
            tokenizer = MarianTokenizer.from_pretrained(model_id)
            translator = ctranslate2.Translator(str(path), device="cpu", compute_type="int8")
            results = []
            start = time.perf_counter()
            for i in range(0, len(selected), args.batch_size):
                batch = selected[i:i + args.batch_size]
                tokens = [tokenizer.convert_ids_to_tokens(
                    tokenizer.encode(prefix + item, truncation=True, max_length=512)
                ) for item in batch]
                outputs = translator.translate_batch(tokens, beam_size=1, max_decoding_length=512)
                for output in outputs:
                    results.append(tokenizer.convert_tokens_to_string(
                        output.hypotheses[0]).replace("</s>", "").strip())
            elapsed = time.perf_counter() - start
            if len(results) != len(selected):
                raise RuntimeError("Resultados incompletos")
            print("%s: %.2f s | %.2f segmentos/s" %
                  (lang, elapsed, len(selected)/max(elapsed, 0.001)), flush=True)
            for source, target in list(zip(selected, results))[:3]:
                print("  EN: %s\n  %s: %s" % (source[:100], lang.upper(), target[:100]), flush=True)
            del translator, tokenizer
            gc.collect()
        except Exception as exc:
            print("%s: ERROR: %s" % (lang, exc), flush=True)
    print("Benchmark terminado. No se modificaron motores, memorias ni archivos del juego.")


if __name__ == "__main__":
    run()
