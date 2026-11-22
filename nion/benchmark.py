"""Benchmark de traducción sin escribir memorias ni archivos del juego."""
import gc
import time
from .engine import get_engine
from .glossary import load_glossary, normalize_names
from .pipeline import scan
from .codes import needs_translation, text_segments
from .multilingual import LANG_ENGINES

def run_benchmark(args):
    _, entries = scan(args.game)
    seen = set()
    segments = []
    for entry in entries:
        if not needs_translation(entry.text):
            continue
        prepared = normalize_names(entry.text, load_glossary())
        for _, core, _ in text_segments(prepared, ()):
            if core and core not in seen and len(core) <= 350:
                seen.add(core)
                segments.append(core)
    # Sample from across the corpus, not just the first map.
    if not segments:
        raise ValueError("No se encontraron segmentos para medir.")
    count = min(args.samples, len(segments))
    selected = [segments[min(len(segments)-1, (i*len(segments))//count)] for i in range(count)]
    langs = [x.strip().lower() for x in args.langs.split(",") if x.strip()]
    if not langs or any(x not in LANG_ENGINES for x in langs):
        raise ValueError("Idiomas no válidos en --langs.")
    print("Benchmark: %d segmentos reales; %d caracteres. Sin guardar traducciones." %
          (count, sum(map(len, selected))), flush=True)
    for lang in langs:
        engine = None
        try:
            engine = get_engine(LANG_ENGINES[lang])
            start = time.perf_counter()
            translated = 0
            for i in range(0, count, engine.max_batch):
                batch = selected[i:i+engine.max_batch]
                results = engine.translate_batch(batch, "en", lang)
                if len(results) != len(batch):
                    raise ValueError("Resultados incompletos para " + lang)
                translated += len(batch)
            seconds = time.perf_counter() - start
            print("%s: %.1f s | %.2f segmentos/s | %d segmentos" %
                  (lang, seconds, translated / max(seconds, 0.001), translated), flush=True)
        except Exception as error:
            print("%s: ERROR %s" % (lang, error), flush=True)
        finally:
            del engine
            gc.collect()
    print("Benchmark terminado. No se modificaron memorias ni archivos del juego.")
    return 0
