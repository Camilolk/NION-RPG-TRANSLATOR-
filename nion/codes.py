"""Protección de códigos de RPG Maker (\\C[2], \\V[1], %1, <tags>...)."""
import re

CODE_RE = re.compile("|".join([
    r"\\[A-Za-z]+\[[^\]\n]*\]",        # \C[2]  \V[1]  \N[1]  \FS[20]
    r"\\[A-Za-z]+<[^>\n]*>",           # \n<Nombre>
    r"\\[{}.|!><^$\\]",                # \{  \}  \.  \|  \!  \>  \<  \^  \$  \\
    r"\\[A-Za-z](?![A-Za-z\[<])",      # \G  (letra suelta)
    r"%\d",                            # %1  %2 (plantillas del motor)
    r"<[A-Za-z/][^<>\n]{0,60}>",       # <WordWrap>  <B>  <br>
]))

_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)


def needs_translation(text):
    """True si, quitados los códigos, queda alguna letra que traducir."""
    return bool(_LETTER.search(CODE_RE.sub("", text)))


def split_parts(text):
    """Divide en [(es_codigo, trozo), ...] conservando todo el texto."""
    parts, pos = [], 0
    for m in CODE_RE.finditer(text):
        if m.start() > pos:
            parts.append((False, text[pos:m.start()]))
        parts.append((True, m.group(0)))
        pos = m.end()
    if pos < len(text):
        parts.append((False, text[pos:]))
    return parts


def default_placeholder(i):
    return "\u27e6%d\u27e7" % i


def mask(text, placeholder=default_placeholder):
    """Sustituye cada código por un marcador. Devuelve (texto_enmascarado, codigos)."""
    out, codes = [], []
    for is_code, chunk in split_parts(text):
        if is_code:
            out.append(placeholder(len(codes)))
            codes.append(chunk)
        else:
            out.append(chunk)
    return "".join(out), codes


def unmask(translated, codes, placeholder=default_placeholder):
    """Restaura los códigos. Devuelve None si el traductor perdió o duplicó alguno."""
    result = translated
    for i, code in enumerate(codes):
        ph = placeholder(i)
        if result.count(ph) != 1:
            return None
        result = result.replace(ph, code)
    return result


def text_segments(text):
    """Trozos de texto traducible (sin códigos) como (relleno_izq, nucleo, relleno_der)."""
    segs = []
    for is_code, chunk in split_parts(text):
        if is_code or not _LETTER.search(chunk):
            continue
        core = chunk.strip()
        lead = chunk[:len(chunk) - len(chunk.lstrip())]
        trail = chunk[len(chunk.rstrip()):]
        segs.append((lead, core, trail))
    return segs


def compose_from_segments(text, memory):
    """Rearma `text` usando traducciones de trozos ya conocidas. None si falta alguno."""
    out = []
    for is_code, chunk in split_parts(text):
        if is_code or not _LETTER.search(chunk):
            out.append(chunk)
            continue
        core = chunk.strip()
        if core not in memory:
            return None
        lead = chunk[:len(chunk) - len(chunk.lstrip())]
        trail = chunk[len(chunk.rstrip()):]
        out.append(lead + memory[core] + trail)
    return "".join(out)
