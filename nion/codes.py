"""Protección de códigos RPG Maker y nombres propios durante la traducción."""
import re

CODE_RE = re.compile("|".join([
    r"\\[A-Za-z]+\[[^\]\n]*\]",        # \C[2]  \V[1]  \N[1]  \FS[20]
    r"\\[A-Za-z]+<[^>\n]*>",           # \n<Nombre>
    r"\\[{}.|!><^$\\]",                # \{  \}  \.  \|  \!  \>  \<  \^  \$  \\
    r"\\[A-Za-z](?![A-Za-z\[<])",      # \G  (letra suelta)
    r"%\d",                            # %1  %2
    r"<[A-Za-z/][^<>\n]{0,60}>",       # <WordWrap>  <B>  <br>
]))

_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)
_NEWLINE_RE = re.compile(r"\r\n|\n|\r")
_PLACEHOLDER_RE = re.compile(r"\[\[NION_TOKEN_(\d+)\]\]")



def needs_translation(text):
    """Indica si queda texto legible después de retirar códigos y etiquetas."""
    if not isinstance(text, str) or not text:
        return False
    return bool(_LETTER.search(CODE_RE.sub("", text)))

def default_placeholder(i):
    return "[[NION_TOKEN_%d]]" % i


def _name_pattern(protected_terms):
    terms = sorted({term for term in protected_terms
                    if isinstance(term, str) and len(term.strip()) >= 2},
                   key=len, reverse=True)
    if not terms:
        return None
    alternatives = "|".join(re.escape(term) for term in terms)
    return re.compile(r"(?<!\w)(?:" + alternatives + r")(?!\w)", re.IGNORECASE)


def split_parts(text, protected_terms=()):
    """Divide en [(es_token, trozo), ...], sin perder códigos ni nombres protegidos."""
    parts, pos = [], 0
    names_re = _name_pattern(protected_terms)
    while pos < len(text):
        code_match = CODE_RE.search(text, pos)
        name_match = names_re.search(text, pos) if names_re else None
        newline_match = _NEWLINE_RE.search(text, pos)
        matches = [m for m in (code_match, name_match, newline_match) if m is not None]
        if not matches:
            parts.append((False, text[pos:]))
            break
        match = min(
            matches,
            key=lambda m: (
                m.start(),
                0 if m is code_match else 1 if m is name_match else 2,
            ),
        )
        if match.start() > pos:
            parts.append((False, text[pos:match.start()]))
        token = match.group(0)
        end = match.end()
        # Preserve the speaker delimiter in dialogue labels such as "Elio:".
        if match is name_match and end < len(text) and text[end] == ":":
            token += ":"
            end += 1
        parts.append((True, token))
        pos = end
    return parts


def mask(text, placeholder=default_placeholder, protected_terms=()):
    """Sustituye códigos y nombres protegidos por marcadores. Devuelve (texto, tokens)."""
    out, tokens = [], []
    for is_token, chunk in split_parts(text, protected_terms):
        if is_token:
            out.append(placeholder(len(tokens)))
            tokens.append(chunk)
        else:
            out.append(chunk)
    return "".join(out), tokens


def unmask(translated, tokens, placeholder=default_placeholder):
    """Restaura tokens solo si están todos, una vez y en su orden original."""
    expected = [str(i) for i in range(len(tokens))]
    found = _PLACEHOLDER_RE.findall(translated)
    if found != expected:
        return None
    result = translated
    for i, token in enumerate(tokens):
        ph = placeholder(i)
        if result.count(ph) != 1:
            return None
        result = result.replace(ph, token)
    return result


def names_preserved(original, translated, protected_terms=()):
    """Comprueba que los nombres protegidos visibles sigan presentes en la salida."""
    source_names = [
        chunk.rstrip(":")
        for is_token, chunk in split_parts(original, protected_terms)
        if (is_token and not CODE_RE.fullmatch(chunk)
                and not _NEWLINE_RE.fullmatch(chunk))
    ]
    output = translated.casefold()
    for name in source_names:
        if name.casefold() not in output:
            return False
    return True


def text_segments(text, protected_terms=()):
    """Trozos traducibles (relleno_izq, núcleo, relleno_der), excluyendo tokens."""
    segs = []
    for is_token, chunk in split_parts(text, protected_terms):
        if is_token or not _LETTER.search(chunk):
            continue
        core = chunk.strip()
        if not core:
            continue
        lead = chunk[:len(chunk) - len(chunk.lstrip())]
        trail = chunk[len(chunk.rstrip()):]
        segs.append((lead, core, trail))
    return segs


def compose_from_segments(text, memory, protected_terms=()):
    """Rearma el texto con memoria, sin traducir códigos ni nombres protegidos."""
    out = []
    for is_token, chunk in split_parts(text, protected_terms):
        if is_token or not _LETTER.search(chunk):
            out.append(chunk)
            continue
        core = chunk.strip()
        if core not in memory:
            return None
        lead = chunk[:len(chunk) - len(chunk.lstrip())]
        trail = chunk[len(chunk.rstrip()):]
        out.append(lead + memory[core] + trail)
    return "".join(out)
