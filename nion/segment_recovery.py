"""Recuperacion conservadora de dialogos multioracion en cuarentena."""
import re

from .codes import CODE_RE
from .quality import TOKEN

_BOUNDARY = re.compile(r"(?<=[!?])\\s+(?=[A-Za-z])")


def split_dialogue(source):
    """Solo separar dialogos simples; nunca dividir codigos o marcadores RPG."""
    if not isinstance(source, str) or CODE_RE.search(source) or TOKEN.search(source):
        return []
    if "\\n" in source or "\\r" in source or "\\t" in source:
        return []
    if re.search(r"(?i)\\b([a-z])-\\1[a-z]+", source):
        return []
    parts = _BOUNDARY.split(source)
    if not 2 <= len(parts) <= 5 or any(len(p.strip()) < 6 for p in parts):
        return []
    return parts


def recover_segments(source, engine, src, tgt, qwen_engine, validate, blocking):
    """Solo devuelve una propuesta si todos los fragmentos y el total pasan controles."""
    parts = split_dialogue(source)
    if not parts:
        return None
    translated = []
    used_qwen = False
    for part in parts:
        candidate = None
        if hasattr(engine, "translate_repair"):
            try:
                trial = engine.translate_repair(part, src, tgt)
                if not blocking.intersection(validate(part, trial, tgt)):
                    candidate = trial
            except Exception:
                pass
        if candidate is None and qwen_engine is not None:
            try:
                trial = qwen_engine.translate(part)
                used_qwen = True
                if not blocking.intersection(validate(part, trial, tgt)):
                    candidate = trial
            except Exception:
                pass
        if candidate is None:
            return None
        translated.append(candidate)
    combined = " ".join(translated)
    alerts = validate(source, combined, tgt)
    if blocking.intersection(alerts):
        return None
    return combined, alerts, used_qwen
