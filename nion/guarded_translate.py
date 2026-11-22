"""Traduccion por lotes con reintento selectivo y cuarentena de errores."""
from .quality import inspect

BLOCKING = frozenset({
    "traduccion_vacia", "repeticion_anomala", "expansion_extrema",
    "reduccion_extrema", "codigos_diferentes", "marcadores_diferentes",
})


def translate_guarded(texts, engine, src="en", tgt="es"):
    """Devuelve resultados y alertas; no guarda en memoria ni sustituye el original."""
    if not isinstance(texts, list) or any(not isinstance(t, str) for t in texts):
        raise ValueError("texts debe ser una lista de cadenas")
    if not texts:
        return []
    results = []
    batch_size = max(1, int(getattr(engine, "max_batch", 1)))
    for offset in range(0, len(texts), batch_size):
        batch = texts[offset:offset + batch_size]
        translations = engine.translate_batch(batch, src, tgt)
        if len(translations) != len(batch):
            raise ValueError("El motor devolvio un numero incorrecto de traducciones")
        for source, candidate in zip(batch, translations):
            initial = sorted(set(inspect(source, candidate)))
            blocking = BLOCKING.intersection(initial)
            retry = None
            final = candidate
            alerts = initial
            if blocking and hasattr(engine, "translate_repair"):
                try:
                    retry = engine.translate_repair(source, src, tgt)
                    retry_alerts = sorted(set(inspect(source, retry)))
                    # Aceptar solo si desaparecen TODOS los bloqueos.
                    if not BLOCKING.intersection(retry_alerts):
                        final, alerts = retry, retry_alerts
                except Exception as error:
                    retry = None
                    alerts = sorted(set(initial + ["reintento_fallido"]))
            results.append({
                "original": source,
                "traduccion": final,
                "alertas": alerts,
                "estado": ("cuarentena" if BLOCKING.intersection(alerts)
                           else "reparada" if final != candidate else "lista"),
                "reintento": bool(blocking),
            })
    return results
