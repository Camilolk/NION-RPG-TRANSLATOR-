"""Orquestación segura: escanear -> traducir -> validar -> guardar -> aplicar a una COPIA."""
import json
import os
import shutil

from .codes import (
    compose_from_segments, mask, names_preserved, needs_translation,
    text_segments, unmask,
)
from .engine import EngineError
from .extract import find_data_dir, iter_entries, load_json, protected_names
from .glossary import load_glossary, normalize_names


def scan(game_path):
    data_dir = find_data_dir(game_path)
    return data_dir, list(iter_entries(data_dir))


def _has_unexpected_script(text, tgt):
    """Detecta contaminación CJK en destinos escritos con alfabeto latino."""
    language = (tgt or "").lower().replace("_", "-").split("-")[0]
    if language not in {"es", "en", "pt", "fr", "de", "it", "nl"}:
        return False
    for char in text:
        code = ord(char)
        if (0x3400 <= code <= 0x4DBF or 0x4E00 <= code <= 0x9FFF
                or 0x3040 <= code <= 0x30FF or 0xAC00 <= code <= 0xD7AF):
            return True
    return False


def _approve_translation(source, translated, src, tgt, glossary, protected_terms, log=None):
    """Valida integridad técnica; no intenta juzgar ni reescribir la semántica."""
    if not isinstance(translated, str) or not translated.strip():
        return None, "traducción vacía o inválida"
    if _has_unexpected_script(translated, tgt):
        return None, "la respuesta contiene caracteres de otro sistema de escritura"
    if translated.count("\n") != source.count("\n"):
        return None, "la respuesta alteró los saltos de línea del original"

    prepared = normalize_names(source, glossary)
    if not names_preserved(prepared, translated, protected_terms):
        return None, "se perdió o alteró un nombre protegido"

    return translated, None


def render(text, memory, protected_terms=(), glossary=None, src="en", tgt="es"):
    """Devuelve una traducción solo si pasa los controles aplicables al par de idiomas."""
    glossary = glossary or load_glossary()
    prepared = normalize_names(text, glossary)

    for key in (text, prepared):
        if key in memory:
            translated, issue = _approve_translation(
                prepared, normalize_names(memory[key], glossary),
                src, tgt, glossary, protected_terms,
            )
            if translated is not None:
                return translated

    composed = compose_from_segments(prepared, memory, protected_terms)
    if composed is None:
        return None
    translated, issue = _approve_translation(
        prepared, normalize_names(composed, glossary),
        src, tgt, glossary, protected_terms,
    )
    return translated


def pending_texts(entries, memory, protected_terms=(), glossary=None, src="en", tgt="es"):
    glossary = glossary or load_glossary()
    seen, out = set(), []
    for entry in entries:
        if entry.text in seen:
            continue
        seen.add(entry.text)
        if needs_translation(entry.text) and render(
            entry.text, memory, protected_terms, glossary, src, tgt
        ) is None:
            out.append(entry.text)
    return out


def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def _record_contexts(entries):
    """Relaciona descripciones RPG Maker con el nombre de su registro."""
    supported = {"Armors", "Items", "Weapons", "Skills"}
    names = {}
    for entry in entries:
        filename = getattr(entry, "file", "")
        path = getattr(entry, "path", ())
        stem = filename[:-5] if filename.endswith(".json") else filename
        if stem in supported and len(path) == 2 and path[1] == "name":
            names[(filename, path[0])] = entry.text

    contexts = {}
    labels = {
        "Armors": "armadura",
        "Items": "objeto",
        "Weapons": "arma",
        "Skills": "habilidad",
    }
    for entry in entries:
        filename = getattr(entry, "file", "")
        path = getattr(entry, "path", ())
        stem = filename[:-5] if filename.endswith(".json") else filename
        if (stem in supported and len(path) == 2
                and path[1] == "description"):
            source_name = names.get((filename, path[0]))
            if source_name:
                contexts.setdefault(
                    entry.text, (labels[stem], source_name)
                )
    return contexts


def _format_record_context(record, memory, protected_terms, glossary, src, tgt):
    if not record:
        return None
    label, source_name = record
    translated_name = render(
        source_name, memory, protected_terms, glossary, src, tgt
    )
    details = [
        "Tipo de registro: %s." % label,
        "Nombre original del registro: %s." % source_name,
    ]
    if translated_name:
        details.append("Nombre traducido y aprobado: %s." % translated_name)
    details.append(
        "La descripción pertenece a este registro. Usa el nombre para "
        "interpretar términos ambiguos y mantener la terminología; no "
        "insertes el nombre ni información nueva en la traducción."
    )
    return " ".join(details)


def _translate_one(engine, text, src, tgt, context=None):
    if context and hasattr(engine, "translate_with_context"):
        result = engine.translate_with_context(text, src, tgt, context)
        if not isinstance(result, str):
            raise EngineError("%s devolvió una traducción que no es texto." % engine.name)
        return result
    return _translate_exact(engine, [text], src, tgt)[0]


def _retry_one(engine, text, src, tgt, context=None):
    if context and hasattr(engine, "retry_masked_with_context"):
        return engine.retry_masked_with_context(text, src, tgt, context)
    return engine.retry_masked(text, src, tgt)


def _translate_exact(engine, texts, src, tgt):
    outputs = engine.translate_batch(texts, src, tgt)
    if not isinstance(outputs, (list, tuple)) or len(outputs) != len(texts):
        count = len(outputs) if isinstance(outputs, (list, tuple)) else "respuesta no válida"
        raise EngineError("%s devolvió %s resultados para un lote de %d textos."
                          % (engine.name, count, len(texts)))
    if any(not isinstance(item, str) for item in outputs):
        raise EngineError("%s devolvió una traducción que no es texto." % engine.name)
    return outputs


def translate_pending(entries, memory, engine, src, tgt, log=print,
                      protected_terms=(), glossary=None):
    """Traduce, valida y solo entonces guarda; los tokens y nombres quedan protegidos."""
    glossary = glossary or load_glossary()
    protected_terms = protected_terms or protected_names(glossary=glossary)
    pending = pending_texts(entries, memory, protected_terms, glossary, src, tgt)
    contexts = _record_contexts(entries)
    log("Textos por traducir: %d (%d caracteres)" %
        (len(pending), sum(map(len, pending))))
    leftovers = []
    rejected = []

    if engine.supports_masking:
        done = 0
        for chunk in _chunks(pending, engine.max_batch):
            plan = [
                mask(normalize_names(text, glossary), engine.placeholder, protected_terms)
                for text in chunk
            ]
            for original, (masked, tokens) in zip(chunk, plan):
                context = _format_record_context(
                    contexts.get(original), memory, protected_terms,
                    glossary, src, tgt,
                )
                translated = _translate_one(engine, masked, src, tgt, context)
                restored = unmask(translated, tokens, engine.placeholder)
                prepared = normalize_names(original, glossary)

                # Si el modelo dañó marcadores, un reintento puede recuperarlos.
                if restored is None and hasattr(engine, "retry_masked"):
                    log("  marcadores alterados; reintentando...")
                    retried = _retry_one(engine, masked, src, tgt, context)
                    restored = unmask(retried, tokens, engine.placeholder)

                if restored is None:
                    leftovers.append(original)
                    continue

                approved, issue = _approve_translation(
                    prepared, restored, src, tgt, glossary, protected_terms, log
                )
                if issue:
                    log("  control de calidad: %s; reintentando..." % issue)
                    if hasattr(engine, "retry_masked"):
                        retried = _retry_one(engine, masked, src, tgt, context)
                        restored = unmask(retried, tokens, engine.placeholder)
                        if restored is not None:
                            approved, issue = _approve_translation(
                                prepared, restored, src, tgt,
                                glossary, protected_terms, log,
                            )
                    if issue:
                        rejected.append(original)
                        log("  rechazado; no se guardó en memoria: %s" % original)
                        continue

                memory.set(original, approved)

            memory.save()
            done += len(chunk)
            log("  procesado %d / %d" % (done, len(pending)))
    else:
        # DeepL no usa marcadores propios: se traducen solo segmentos de texto,
        # manteniendo códigos RPG Maker y nombres oficiales fuera de la petición.
        leftovers = list(pending)

    if leftovers:
        log("Traducción segura por segmentos para %d textos..." % len(leftovers))
        prepared_texts = {
            text: normalize_names(text, glossary) for text in leftovers
        }
        segments = []
        for text in leftovers:
            for _, core, _ in text_segments(prepared_texts[text], protected_terms):
                if core not in memory and core not in segments:
                    segments.append(core)

        done = 0
        for chunk in _chunks(segments, engine.max_batch):
            outputs = _translate_exact(engine, chunk, src, tgt)
            for core, translated in zip(chunk, outputs):
                approved, issue = _approve_translation(
                    core, translated, src, tgt, glossary, protected_terms, log
                )
                if issue:
                    log("  segmento pendiente (%s): %s" % (issue, core))
                    continue
                memory.set(core, approved)
            memory.save()
            done += len(chunk)
            log("  segmentos procesados %d / %d" % (done, len(segments)))

        for original in leftovers:
            composed = compose_from_segments(
                prepared_texts[original], memory, protected_terms
            )
            if composed is None:
                rejected.append(original)
                continue
            approved, issue = _approve_translation(
                prepared_texts[original], composed, src, tgt,
                glossary, protected_terms, log,
            )
            if issue:
                rejected.append(original)
                log("  texto pendiente de revisión (%s): %s" % (issue, original))
                continue
            memory.set(original, approved)

    if rejected:
        log("  textos no aprobados: %d (no se guardaron como traducciones completas)" %
            len(set(rejected)))
    memory.save()


def _set_path(data, path, value):
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value


def _normalize_actor_names(out_dir, glossary):
    """Normaliza solo nombres de actores; no altera identificadores de eventos."""
    path = os.path.join(out_dir, "Actors.json")
    if not os.path.isfile(path):
        return
    data = load_json(path)
    changed = False
    if isinstance(data, list):
        for actor in data:
            if isinstance(actor, dict) and isinstance(actor.get("name"), str):
                normalized = normalize_names(actor["name"], glossary)
                if normalized != actor["name"]:
                    actor["name"] = normalized
                    changed = True
    if changed:
        temporary = path + ".nion-tmp"
        try:
            with open(temporary, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)


def apply_translations(game_path, out_dir, memory, log=print, glossary=None, src="en", tgt="es"):
    """No crea una salida parcial: exige todas las traducciones antes de copiar."""
    glossary = glossary or load_glossary()
    data_dir = find_data_dir(game_path)
    protected_terms = protected_names(data_dir, glossary)
    data_abs, out_abs = os.path.abspath(data_dir), os.path.abspath(out_dir)
    if out_abs == data_abs or os.path.commonpath([data_abs, out_abs]) == data_abs:
        raise EngineError(
            "La salida no puede ser la carpeta original ni estar dentro de ella."
        )
    if os.path.exists(out_abs):
        raise EngineError(
            "La carpeta de salida ya existe; elige otra para no mezclar archivos antiguos."
        )

    by_file, missing = {}, {}
    for entry in iter_entries(data_dir):
        by_file.setdefault(entry.file, []).append(entry)
        if needs_translation(entry.text) and render(
            entry.text, memory, protected_terms, glossary, src, tgt
        ) is None:
            missing[entry.text] = 1
    if missing:
        log("Exportación cancelada: faltan %d textos. No se creó ninguna copia." %
            len(missing))
        return 0, list(missing)

    parent = os.path.dirname(out_abs)
    if parent:
        os.makedirs(parent, exist_ok=True)
    shutil.copytree(data_dir, out_abs)

    applied = 0
    for filename, entries in by_file.items():
        data = load_json(os.path.join(data_dir, filename))
        changed = False
        for entry in entries:
            translated = (
                render(entry.text, memory, protected_terms, glossary, src, tgt)
                if needs_translation(entry.text) else None
            )
            if translated is not None:
                _set_path(data, entry.path, translated)
                applied += 1
                changed = True
        if changed:
            target = os.path.join(out_abs, filename)
            temporary = target + ".nion-tmp"
            try:
                with open(temporary, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary):
                    os.remove(temporary)
    _normalize_actor_names(out_abs, glossary)
    log("Textos aplicados: %d | sin traducir: 0" % applied)
    return applied, []
