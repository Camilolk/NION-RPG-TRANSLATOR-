"""Traduccion por lotes con reintento selectivo y cuarentena de errores."""
from .quality import inspect
from .repair_propose import semantic_warnings
from .repair_gguf import fidelity_warnings

BLOCKING = frozenset({
    "traduccion_vacia", "repeticion_anomala", "expansion_extrema",
    "reduccion_extrema", "codigos_diferentes", "marcadores_diferentes",
    "preguntas_omitidas_posibles", "sin_traducir", "tartamudeo_perdido_posible",
})


def review_alerts(source, candidate):
    """Combina calidad, cobertura de preguntas y fidelidad sin afirmar equivalencia."""
    if not isinstance(candidate, str):
        return ["traduccion_vacia"]
    alerts = set(inspect(source, candidate))
    alerts.update(semantic_warnings(source, candidate))
    alerts.update(fidelity_warnings(source, candidate))
    # Contar solo signos de cierre: el signo español de apertura no es otra pregunta.
    if source.count("?") > candidate.count("?"):
        alerts.add("preguntas_omitidas_posibles")
    return sorted(alerts)


def translate_guarded(texts, engine, src="en", tgt="es", qwen_engine=None):
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
            initial = review_alerts(source, candidate)
            blocking = BLOCKING.intersection(initial)
            retry = None
            final = candidate
            alerts = initial
            if blocking and hasattr(engine, "translate_repair"):
                try:
                    retry = engine.translate_repair(source, src, tgt)
                    retry_alerts = sorted(set(review_alerts(source, retry)))
                    # Aceptar solo si desaparecen TODOS los bloqueos.
                    if not BLOCKING.intersection(retry_alerts):
                        final, alerts = retry, retry_alerts
                except Exception as error:
                    retry = None
                    alerts = sorted(set(initial + ["reintento_fallido"]))
            qwen_used = False
            qwen_error = None
            if BLOCKING.intersection(alerts) and qwen_engine is not None:
                qwen_used = True
                try:
                    proposal = qwen_engine.translate(source)
                    proposal_alerts = review_alerts(source, proposal)
                    if not BLOCKING.intersection(proposal_alerts):
                        final, alerts = proposal, proposal_alerts
                except Exception as error:
                    qwen_error = str(error)[:200]
            results.append({
                "original": source,
                "traduccion": final,
                "alertas": alerts,
                "estado": ("cuarentena" if BLOCKING.intersection(alerts)
                           else "reparada" if final != candidate else "lista"),
                "reintento": bool(blocking),
                "qwen_usado": qwen_used,
                "qwen_error": qwen_error,
            })
    return results
