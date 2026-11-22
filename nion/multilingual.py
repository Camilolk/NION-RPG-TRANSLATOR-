"""Traducción secuencial y reanudable desde data_ingles."""
import os
from .engine import EngineError, get_engine
from .extract import protected_names
from .glossary import load_glossary
from .memory import Memory
from .pipeline import scan, pending_texts, translate_pending, apply_translations

LANG_ENGINES = {
    "es": "marian", "fr": "marian", "de": "marian",
    "it": "marian", "ru": "marian",
    "pt-br": "marian", "ja": "marian", "zh": "marian",
}

def run_all(args):
    languages = [s.strip().lower() for s in args.langs.split(",") if s.strip()]
    if not languages or len(languages) != len(set(languages)):
        raise ValueError("Lista de idiomas vacía o duplicada.")
    invalid = [lang for lang in languages if lang not in LANG_ENGINES]
    if invalid:
        raise ValueError("Idiomas no admitidos: " + ", ".join(invalid))
    data_dir, entries = scan(args.game)
    base = os.path.abspath(args.out)
    data_abs = os.path.abspath(data_dir)
    if os.path.commonpath([data_abs, base]) == data_abs:
        raise EngineError("La salida no puede estar dentro de data_ingles.")
    os.makedirs(base, exist_ok=True)
    glossary = load_glossary()
    names = protected_names(data_dir, glossary)
    failed = []
    for lang in languages:
        print("\n===== NION: inglés -> %s =====" % lang, flush=True)
        path = (args.es_memory if lang == "es" and args.es_memory
                else os.path.join(base, "nion_memory_en_%s.json" % lang))
        memory = Memory(path)
        remaining = pending_texts(entries, memory, names, glossary)
        if remaining:
            if lang == "es" and args.es_memory:
                print("Memoria española existente incompleta; no se modificará:", path)
                failed.append(lang)
                continue
            try:
                engine = get_engine(LANG_ENGINES[lang])
                translate_pending(entries, memory, engine, "en", lang,
                                  protected_terms=names, glossary=glossary)
            except (EngineError, OSError, ValueError) as error:
                print("FALLO %s: %s" % (lang, error), flush=True)
                failed.append(lang)
                continue
            finally:
                if 'engine' in locals():
                    del engine
        remaining = pending_texts(entries, memory, names, glossary)
        if remaining:
            print("PENDIENTES %s: %d; se omite exportación." % (lang, len(remaining)))
            failed.append(lang)
            continue
        if args.no_apply:
            print("Memoria completa:", path)
            continue
        target = os.path.join(base, "data_" + lang)
        if os.path.exists(target):
            print("Salida ya existente, no se sobrescribe:", target)
            continue
        try:
            applied, missing = apply_translations(
                data_dir, target, memory, glossary=glossary, textfit=args.textfit)
            if missing:
                failed.append(lang)
            else:
                print("EXPORTADO %s: %d textos -> %s" % (lang, applied, target))
        except (EngineError, OSError, ValueError) as error:
            print("FALLO EXPORTACIÓN %s: %s" % (lang, error))
            failed.append(lang)
    if failed:
        print("\nIdiomas pendientes:", ", ".join(failed))
        return 2
    print("\nNION: todos los idiomas solicitados procesados.")
    return 0
