"""Ajuste conservador de mensajes RPG Maker MV/MZ (comandos 101/401)."""
import re
import unicodedata

from .codes import CODE_RE

WORD_RE = re.compile(r"\S+")


def visible_width(text):
    """Estimación de ancho: ignora códigos de control, pondera caracteres anchos."""
    stripped = CODE_RE.sub("", text)
    return sum(2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1
               for ch in stripped)


def wrap_message(lines, max_width=48, max_lines=4):
    """Devuelve líneas ajustadas o None si no caben de forma segura."""
    if not lines or any("\n" in line or "\r" in line for line in lines):
        return None
    if all(visible_width(line) <= max_width for line in lines):
        return None
    words = WORD_RE.findall(" ".join(lines))
    if not words:
        return None
    output = []
    current = ""
    for word in words:
        if visible_width(word) > max_width:
            return None
        candidate = (current + " " + word) if current else word
        if visible_width(candidate) > max_width and current:
            output.append(current)
            current = word
        else:
            current = candidate
    if current:
        output.append(current)
    if len(output) > max_lines:
        return None
    return output


def fit_commands(commands, max_width=48):
    """Refluye bloques 101/401 y pagina cada cuatro líneas como máximo.

    Conserva los parámetros e indentación del 101, y no toca otros eventos.
    Omite textos con códigos de control para evitar cambiar su semántica.
    """
    if not isinstance(commands, list):
        return 0, 0
    fixed = skipped = 0
    i = 0
    while i < len(commands):
        header = commands[i]
        if not isinstance(header, dict) or header.get("code") != 101:
            i += 1
            continue
        j = i + 1
        while (j < len(commands) and isinstance(commands[j], dict)
               and commands[j].get("code") == 401):
            j += 1
        group = commands[i + 1:j]
        if not group:
            i = j
            continue
        if (not isinstance(header.get("parameters"), list)
                or not all(isinstance(c.get("parameters"), list)
                           and len(c["parameters"]) == 1
                           and isinstance(c["parameters"][0], str)
                           and c.get("indent") == header.get("indent")
                           for c in group)):
            skipped += 1
            i = j
            continue
        lines = [c["parameters"][0] for c in group]
        if all(visible_width(line) <= max_width for line in lines):
            i = j
            continue
        # Reflow of special RPG codes (timing, font size, icons, variables,
        # wordwrap tags) requires a separate pixel-aware implementation.
        if any(CODE_RE.search(line) for line in lines):
            skipped += 1
            i = j
            continue
        # Cap total pages to avoid generating pathological dialogue sequences.
        wrapped = wrap_message(lines, max_width, max_lines=80)
        if not wrapped:
            skipped += 1
            i = j
            continue
        from copy import deepcopy
        new_commands = []
        for start in range(0, len(wrapped), 4):
            if start:
                new_commands.append(deepcopy(header))
            for line in wrapped[start:start + 4]:
                cmd = deepcopy(group[0])
                cmd["parameters"] = [line]
                new_commands.append(cmd)
        commands[i + 1:j] = new_commands
        fixed += 1
        i += 1 + len(new_commands)
    return fixed, skipped


def fit_data(data, stem, max_width=48):
    """Aplica TextFit a listas de comandos de mapas, tropas y eventos comunes."""
    total_fixed = total_skipped = 0

    def process(commands):
        nonlocal total_fixed, total_skipped
        fixed, skipped = fit_commands(commands, max_width)
        total_fixed += fixed
        total_skipped += skipped

    if stem == "CommonEvents" and isinstance(data, list):
        for event in data:
            if isinstance(event, dict):
                process(event.get("list"))
    elif stem == "Troops" and isinstance(data, list):
        for troop in data:
            if isinstance(troop, dict):
                for page in troop.get("pages") or []:
                    if isinstance(page, dict):
                        process(page.get("list"))
    elif stem.startswith("Map") and stem != "MapInfos" and isinstance(data, dict):
        for event in data.get("events") or []:
            if isinstance(event, dict):
                for page in event.get("pages") or []:
                    if isinstance(page, dict):
                        process(page.get("list"))
    return total_fixed, total_skipped
