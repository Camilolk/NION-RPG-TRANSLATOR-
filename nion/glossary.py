"""Glosario editable de nombres propios y normalización segura."""
import json
import os
import re

from .codes import CODE_RE

DEFAULT_GLOSSARY = os.path.join(os.path.dirname(__file__), "glossary.json")


def load_glossary(path=None):
    """Carga y valida el glosario incluido o uno indicado por el usuario."""
    source = path or DEFAULT_GLOSSARY
    with open(source, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    names = data.get("names") if isinstance(data, dict) else None
    if not isinstance(names, dict):
        raise ValueError("El glosario debe contener un objeto 'names'.")
    aliases = {}
    canonical_names = set()
    for canonical, variants in names.items():
        if not isinstance(canonical, str) or not canonical.strip():
            raise ValueError("El glosario contiene un nombre oficial vacío o inválido.")
        if not isinstance(variants, list) or any(
            not isinstance(item, str) or not item.strip() for item in variants
        ):
            raise ValueError("Las variantes de %r deben ser una lista de textos." % canonical)
        canonical_names.add(canonical)
        for variant in variants:
            key = variant.casefold()
            previous = aliases.get(key)
            if previous is not None and previous != canonical:
                raise ValueError("La variante %r apunta a dos nombres oficiales." % variant)
            aliases[key] = canonical
    terms = data.get("terms", {})
    if not isinstance(terms, dict) or any(
        not isinstance(source, str) or not source.strip()
        or not isinstance(target, str) or not target.strip()
        for source, target in terms.items()
    ):
        raise ValueError("El glosario 'terms' debe ser un objeto de términos y traducciones no vacíos.")
    return {
        "names": names,
        "aliases": aliases,
        "canonical": canonical_names,
        "terms": terms,
    }


def glossary_terms(glossary):
    """Términos que deben protegerse después de normalizar variantes."""
    terms = set(glossary["canonical"])
    terms.update(glossary["aliases"].keys())
    return sorted(terms, key=lambda value: (-len(value), value.casefold()))


def _alias_pattern(glossary):
    aliases = glossary["aliases"]
    if not aliases:
        return None
    variants = sorted(aliases, key=len, reverse=True)
    return re.compile(
        r"(?<!\w)(?:" + "|".join(re.escape(item) for item in variants) + r")(?!\w)",
        re.IGNORECASE,
    )


def normalize_names(text, glossary):
    """Convierte variantes conocidas al nombre oficial sin tocar códigos RPG Maker."""
    if not isinstance(text, str) or not text:
        return text
    pattern = _alias_pattern(glossary)
    if pattern is None:
        return text

    def normalize_plain(segment):
        return pattern.sub(lambda match: glossary["aliases"][match.group(0).casefold()], segment)

    result, cursor = [], 0
    for match in CODE_RE.finditer(text):
        result.append(normalize_plain(text[cursor:match.start()]))
        result.append(match.group(0))
        cursor = match.end()
    result.append(normalize_plain(text[cursor:]))
    return "".join(result)
