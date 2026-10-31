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


def quality_issue(source, translated, src, tgt):
    """Indica si una frase conocida se aparta de su traducción verificada."""
    corrected, reason = verified_correction(source, translated, src, tgt)
    return reason
