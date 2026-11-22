"""Segmentación conservadora para experimentos de traducción japonesa.

Conserva puntuación y espacios originales. No modifica datos del juego.
"""
import re
from .codes import CODE_RE

# Delimitador tras oración; no consume puntuación ni espacios.
_SENTENCE_END = re.compile(r"[.!?]+(?=\s+[A-Z])")
_ABBREVIATIONS = {"mr.", "mrs.", "ms.", "dr.", "prof.", "st.", "vs.", "etc.", "e.g.", "i.e."}


def split_sentences_safe(text):
    """Devuelve trozos completos; si hay duda, conserva el texto sin dividir."""
    if not isinstance(text, str):
        raise TypeError("Se esperaba una cadena de texto")
    if not text:
        return [text]
    # Los códigos RPG Maker deben mantenerse en su contexto original.
    if CODE_RE.search(text):
        return [text]
    pieces = []
    start = 0
    for match in _SENTENCE_END.finditer(text):
        end = match.end()
        punctuation = match.group()
        if punctuation.startswith(".") and len(punctuation) > 1:
            continue  # puntos suspensivos
        before = text[start:end]
        last_word = before.rsplit(None, 1)[-1].lower() if before.split() else ""
        if last_word in _ABBREVIATIONS:
            continue
        # Evitar dividir en abreviaturas con iniciales (p. ej. A. Smith).
        if re.search(r"\b[A-Za-z]\.$", before):
            continue
        # Preservar los espacios exactos en el fragmento anterior.
        whitespace = re.match(r"\s+", text[end:])
        if not whitespace:
            continue
        split_at = end + len(whitespace.group())
        pieces.append(text[start:split_at])
        start = split_at
    pieces.append(text[start:])
    assert "".join(pieces) == text
    return pieces
