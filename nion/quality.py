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
    "[general equipment] linen clothing with high breathability": (
        "[Equipamiento general] Ropa de lino con alta transpirabilidad."
    ),
    "a vest made of tanned hide": "Un chaleco hecho de cuero curtido.",
    "[general equipment] a vest made of tanned hide": (
        "[Equipamiento general] Un chaleco hecho de cuero curtido."
    ),
    "a vest made of leather hardened with glue": (
        "Un chaleco de cuero endurecido con pegamento."
    ),
    "[general equipment] a vest made of leather hardened with glue": (
        "[Equipamiento general] Un chaleco de cuero endurecido con pegamento."
    ),
    "a large, old shield that survived time. has something inscribed but it has mostly faded away": (
        "Un escudo grande y viejo que ha resistido el paso del tiempo. "
        "Tiene algo grabado, pero casi se ha borrado."
    ),
    "[large shield] a large shield made of iron steel": (
        "[Escudo grande] Un escudo grande hecho de acero."
    ),
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
    variants = glossary.get("term_variants", {}) if isinstance(glossary, dict) else {}
    issues = []
    covered = []
    for original, expected in sorted(terms.items(), key=lambda item: -len(item[0])):
        match = re.search(r"(?<!\w)" + re.escape(original) + r"(?!\w)", source, re.IGNORECASE)
        if not match:
            continue
        # Una expresión compuesta prevalece sobre sus componentes: "iron steel"
        # no exige además que aparezca "hierro" por separado.
        if any(match.start() < end and match.end() > start for start, end in covered):
            continue
        covered.append(match.span())
        accepted = [expected]
        accepted.extend(variants.get(original, []))
        if not any(_has_term(translated, candidate) for candidate in accepted):
            issues.append((original, expected))
    return issues
