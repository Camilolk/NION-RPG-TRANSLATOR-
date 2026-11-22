"""Prueba aislada de CTranslate2 para portugués. No altera motores ni memorias."""
import argparse
import time
from pathlib import Path

MODEL = "Helsinki-NLP/opus-mt-en-ROMANCE"


def main():
    parser = argparse.ArgumentParser(description="Benchmark experimental CT2: solo en -> pt-br")
    parser.add_argument("game")
    parser.add_argument("--samples", type=int, default=50)
    parser.add_argument("--model-dir", default="models/ct2_en_romance")
    args = parser.parse_args()
    if not 1 <= args.samples <= 1000:
        parser.error("--samples debe estar entre 1 y 1000")
    try:
        import ctranslate2
        from transformers import MarianTokenizer
        from .pipeline import scan
        from .glossary import load_glossary, normalize_names
        from .codes import needs_translation, text_segments
    except ImportError as exc:
        parser.error("Instala la dependencia opcional: python -m pip install ctranslate2 (%s)" % exc)

    output = Path(args.model_dir)
    if not (output / "model.bin").exists():
        if output.exists() and any(output.iterdir()):
            parser.error("La carpeta de modelo CT2 existe pero no está completa: %s" % output)
        print("Convirtiendo modelo portugués a CT2 (solo una vez)...", flush=True)
        from ctranslate2.converters import TransformersConverter
        output.parent.mkdir(parents=True, exist_ok=True)
        TransformersConverter(MODEL).convert(str(output), force=False)
    tokenizer = MarianTokenizer.from_pretrained(MODEL)
    translator = ctranslate2.Translator(str(output), device="cpu", compute_type="int8")

    _, entries = scan(args.game)
    glossary = load_glossary()
    seen = set()
    segments = []
    for entry in entries:
        if not needs_translation(entry.text):
            continue
        prepared = normalize_names(entry.text, glossary)
        for _, core, _ in text_segments(prepared, ()):
            if core and core not in seen and len(core) <= 350:
                seen.add(core)
                segments.append(core)
    if not segments:
        parser.error("No se encontraron segmentos")
    count = min(args.samples, len(segments))
    selected = [segments[min(len(segments) - 1, (i * len(segments)) // count)] for i in range(count)]
    print("CT2 portugués: %d segmentos; %d caracteres. Sin escribir memorias." %
          (count, sum(map(len, selected))), flush=True)
    start = time.perf_counter()
    results = []
    for i in range(0, count, 16):
        batch = selected[i:i + 16]
        prepared = [">>pt<< " + item for item in batch]
        tokens = [tokenizer.convert_ids_to_tokens(tokenizer.encode(item, truncation=True, max_length=512))
                  for item in prepared]
        outputs = translator.translate_batch(tokens, beam_size=1, max_decoding_length=512)
        for item in outputs:
            results.append(tokenizer.convert_tokens_to_string(item.hypotheses[0]).replace("</s>", "").strip())
    elapsed = time.perf_counter() - start
    if len(results) != count:
        raise RuntimeError("CT2 devolvió menos resultados de los esperados")
    print("ct2 pt-br: %.1f s | %.2f segmentos/s | %d segmentos" %
          (elapsed, count / max(elapsed, 0.001), count), flush=True)
    print("Muestras:")
    for src, dst in list(zip(selected, results))[:3]:
        print("EN:", src[:120], "\\nPT:", dst[:120])
    print("No se modificaron otros idiomas ni memorias.")


if __name__ == "__main__":
    main()
