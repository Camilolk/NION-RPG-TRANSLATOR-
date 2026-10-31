"""Orquestación: escanear -> traducir (por lotes, reanudable) -> aplicar a una COPIA."""
import json
import os
import shutil

from .codes import (CODE_RE, compose_from_segments, mask, needs_translation,
                    text_segments, unmask)
from .engine import EngineError
from .extract import Entry, find_data_dir, iter_entries, load_json


def scan(game_path):
    data_dir = find_data_dir(game_path)
    return data_dir, list(iter_entries(data_dir))


def render(text, memory):
    """Traducción de `text` si ya se puede obtener de la memoria; si no, None."""
    if text in memory:
        return memory[text]
    return compose_from_segments(text, memory)


def pending_texts(entries, memory):
    seen, out = set(), []
    for e in entries:
        if e.text in seen:
            continue
        seen.add(e.text)
        if needs_translation(e.text) and render(e.text, memory) is None:
            out.append(e.text)
    return out


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def translate_pending(entries, memory, engine, src, tgt, log=print):
    """Traduce lo que falte. Guarda la memoria tras cada lote: si algo falla, se reanuda."""
    pending = pending_texts(entries, memory)
    log("Textos por traducir: %d (%d caracteres)" % (len(pending), sum(map(len, pending))))
    leftovers = []

    if engine.supports_masking:
        done = 0
        for chunk in _chunks(pending, engine.max_batch):
            plan = [mask(t, engine.placeholder) for t in chunk]
            outs = engine.translate_batch([m for m, _ in plan], src, tgt)
            for text, (_, codes), out in zip(chunk, plan, outs):
                restored = unmask(out, codes, engine.placeholder)
                if restored is None:
                    leftovers.append(text)
                else:
                    memory.set(text, restored)
            memory.save()
            done += len(chunk)
            log("  traducido %d / %d" % (done, len(pending)))
    else:
        leftovers = list(pending)

    if leftovers:
        log("Traducción por trozos para %d textos con códigos delicados..." % len(leftovers))
        segs = []
        for text in leftovers:
            for _, core, _ in text_segments(text):
                if core not in memory and core not in segs:
                    segs.append(core)
        done = 0
        for chunk in _chunks(segs, engine.max_batch):
            outs = engine.translate_batch(chunk, src, tgt)
            for core, out in zip(chunk, outs):
                memory.set(core, out)
            memory.save()
            done += len(chunk)
            log("  trozos %d / %d" % (done, len(segs)))
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
    """Escribe una COPIA traducida de data en out_dir. El original no se toca."""
    data_dir = find_data_dir(game_path)
    if os.path.abspath(out_dir) == os.path.abspath(data_dir):
        raise EngineError("La carpeta de salida no puede ser la original.")
    shutil.copytree(data_dir, out_dir, dirs_exist_ok=True)
    by_file, missing = {}, {}
    for e in iter_entries(data_dir):
        by_file.setdefault(e.file, []).append(e)
    applied = 0
    for fname, entries in by_file.items():
        data = load_json(os.path.join(data_dir, fname))
        changed = False
        for e in entries:
            tr = render(e.text, memory) if needs_translation(e.text) else None
            if tr is None:
                if needs_translation(e.text):
                    missing[e.text] = 1
                continue
            _set_path(data, e.path, tr)
            applied += 1
            changed = True
        if changed:
            tmp = os.path.join(out_dir, fname + ".tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, os.path.join(out_dir, fname))
    log("Textos aplicados: %d | sin traducir: %d" % (applied, len(missing)))
    return applied, list(missing)
