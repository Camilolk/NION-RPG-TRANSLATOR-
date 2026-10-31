"""Orquestación: escanear -> traducir por lotes -> aplicar a una COPIA."""
import json
import os
import shutil

from .codes import compose_from_segments, mask, needs_translation, text_segments, unmask
from .engine import EngineError
from .extract import find_data_dir, iter_entries, load_json


def scan(game_path):
    data_dir = find_data_dir(game_path)
    return data_dir, list(iter_entries(data_dir))


def render(text, memory):
    if text in memory:
        return memory[text]
    return compose_from_segments(text, memory)


def pending_texts(entries, memory):
    seen, out = set(), []
    for entry in entries:
        if entry.text not in seen:
            seen.add(entry.text)
            if needs_translation(entry.text) and render(entry.text, memory) is None:
                out.append(entry.text)
    return out


def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def _translate_exact(engine, texts, src, tgt):
    outputs = engine.translate_batch(texts, src, tgt)
    if not isinstance(outputs, (list, tuple)) or len(outputs) != len(texts):
        count = len(outputs) if isinstance(outputs, (list, tuple)) else "respuesta no válida"
        raise EngineError("%s devolvió %s resultados para un lote de %d textos."
                          % (engine.name, count, len(texts)))
    if any(not isinstance(item, str) for item in outputs):
        raise EngineError("%s devolvió una traducción que no es texto." % engine.name)
    return outputs


def translate_pending(entries, memory, engine, src, tgt, log=print):
    """Guarda la memoria tras cada lote para permitir reanudar."""
    pending = pending_texts(entries, memory)
    log("Textos por traducir: %d (%d caracteres)" % (len(pending), sum(map(len, pending))))
    leftovers = []

    if engine.supports_masking:
        done = 0
        for chunk in _chunks(pending, engine.max_batch):
            plan = [mask(text, engine.placeholder) for text in chunk]
            outputs = _translate_exact(engine, [masked for masked, _ in plan], src, tgt)
            for original, (_, codes), translated in zip(chunk, plan, outputs):
                restored = unmask(translated, codes, engine.placeholder)
                if restored is None:
                    leftovers.append(original)
                else:
                    memory.set(original, restored)
            memory.save()
            done += len(chunk)
            log("  traducido %d / %d" % (done, len(pending)))
    else:
        leftovers = list(pending)

    if leftovers:
        log("Traducción por trozos para %d textos con códigos delicados..." % len(leftovers))
        segments = []
        for text in leftovers:
            for _, core, _ in text_segments(text):
                if core not in memory and core not in segments:
                    segments.append(core)
        done = 0
        for chunk in _chunks(segments, engine.max_batch):
            outputs = _translate_exact(engine, chunk, src, tgt)
            for core, translated in zip(chunk, outputs):
                memory.set(core, translated)
            memory.save()
            done += len(chunk)
            log("  trozos %d / %d" % (done, len(segments)))
        for text in leftovers:
            composed = compose_from_segments(text, memory)
            if composed is not None:
                memory.set(text, composed)
    memory.save()


def _set_path(data, path, value):
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value


def apply_translations(game_path, out_dir, memory, log=print):
    """No crea una salida parcial: exige todas las traducciones antes de copiar."""
    data_dir = find_data_dir(game_path)
    data_abs, out_abs = os.path.abspath(data_dir), os.path.abspath(out_dir)
    if out_abs == data_abs or os.path.commonpath([data_abs, out_abs]) == data_abs:
        raise EngineError("La salida no puede ser la carpeta original ni estar dentro de ella.")
    if os.path.exists(out_abs):
        raise EngineError("La carpeta de salida ya existe; elige otra para no mezclar archivos antiguos.")

    by_file, missing = {}, {}
    for entry in iter_entries(data_dir):
        by_file.setdefault(entry.file, []).append(entry)
        if needs_translation(entry.text) and render(entry.text, memory) is None:
            missing[entry.text] = 1
    if missing:
        log("Exportación cancelada: faltan %d textos. No se creó ninguna copia." % len(missing))
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
            translated = render(entry.text, memory) if needs_translation(entry.text) else None
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
    log("Textos aplicados: %d | sin traducir: 0" % applied)
    return applied, []
