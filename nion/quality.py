"""Control conservador de calidad para errores semánticos ya verificados.

Las reglas son exact-match (inglés -> español): nunca reescriben frases no
registradas ni intentan adivinar la traducción de texto arbitrario.
"""
import re


_VERIFIED_ES = {
    "i should hurry": "Debería darme prisa.",
    "you should hurry": "Deberías darte prisa.",
    "we should hurry": "Deberíamos darnos prisa.",
    "they should hurry": "Deberían darse prisa.",
    "we are going to find him": "Vamos a encontrarlo.",
}


def _key(text):
    """Normaliza solo espacios, mayúsculas y puntuación final."""
    return re.sub(r"[.!?…]+$", "", " ".join(text.split()).casefold()).strip()


def verified_correction(source, translated, src, tgt):
    """Devuelve (texto, motivo); corrige solo frases exactas del registro."""
    if (src or "").lower().split("-")[0] != "en" or (tgt or "").lower().split("-")[0] != "es":
        return translated, None

    expected = _VERIFIED_ES.get(_key(source))
    if expected is None or _key(translated) == _key(expected):
        return translated, None

    return expected, "corrección verificada para: %s" % source


def quality_issue(source, translated, src, tgt, glossary=None):
    """Indica desviaciones exactas conocidas o términos RPG obligatorios ausentes."""
    corrected, reason = verified_correction(source, translated, src, tgt)
    if reason:
        return reason
    issues = terminology_issues(source, translated, glossary or {}, src, tgt)
    if issues:
        original, expected = issues[0]
        return "término RPG no conservado: %s → %s" % (original, expected)
    return None


def _has_term(text, term):
    """Busca un término completo, sin confundirlo con partes de otras palabras."""
    return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.IGNORECASE) is not None


def terminology_issues(source, translated, glossary, src, tgt):
    """Devuelve los términos RPG omitidos o sustituidos por otro material/objeto."""
    if (src or "").lower().split("-")[0] != "en" or (tgt or "").lower().split("-")[0] != "es":
        return []
    terms = glossary.get("terms", {}) if isinstance(glossary, dict) else {}
    issues = []
    for original, expected in sorted(terms.items(), key=lambda item: -len(item[0])):
        if _has_term(source, original) and not _has_term(translated, expected):
            issues.append((original, expected))
    return issues
