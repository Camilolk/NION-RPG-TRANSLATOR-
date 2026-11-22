"""Genera informe no destructivo de textos pendientes y propuestas del motor."""
import json
from pathlib import Path

from .codes import text_segments
from .engine import EngineError
from .glossary import normalize_names
from .pipeline import pending_texts
from .quality import inspect


def create_review(entries, memory, engine, src, tgt, output, protected_terms=(), glossary=None):
    from .glossary import load_glossary
    glossary = glossary or load_glossary()
    destination = Path(output).resolve()
    if destination.exists():
        raise ValueError("El informe ya existe; elige otra ruta para evitar sobrescribirlo.")
    if destination == Path(memory.path).resolve():
        raise ValueError("No se puede sobrescribir la memoria.")
    pending = pending_texts(entries, memory, protected_terms, glossary)
    proposals = []
    for original in pending:
        prepared = normalize_names(original, glossary)
        cores = [core for _, core, _ in text_segments(prepared, ()) if core not in memory]
        proposals.append((original, cores))
    unique = list(dict.fromkeys(core for _, cores in proposals for core in cores))
    translations = {}
    batch_size = max(1, engine.max_batch)
    for start in range(0, len(unique), batch_size):
        batch = unique[start:start + batch_size]
        results = engine.translate_batch(batch, src, tgt)
        if len(results) != len(batch):
            raise EngineError("El motor devolvió un número incorrecto de traducciones.")
        for core, result in zip(batch, results):
            translations[core] = result
    rows = []
    for original, cores in proposals:
        details = []
        for core in cores:
            result = translations[core]
            details.append({
                "segmento_original": core,
                "propuesta": result,
                "alertas": inspect(core, result),
            })
        rows.append({"original": original, "segmentos": details})
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(rows), str(destination)
