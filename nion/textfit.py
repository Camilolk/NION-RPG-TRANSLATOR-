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
    """Ajusta solo si puede conservar exactamente los comandos 401 existentes.

    Evita insertar/eliminar comandos de evento: RPG Maker depende de su estructura.
    """
    if not isinstance(commands, list):
        return 0, 0
    fixed = skipped = 0
    i = 0
    while i < len(commands):
        command = commands[i]
        if not isinstance(command, dict) or command.get("code") != 101:
            i += 1
            continue
        j = i + 1
        while (j < len(commands) and isinstance(commands[j], dict)
               and commands[j].get("code") == 401):
            j += 1
        group = commands[i + 1:j]
        if group and all(isinstance(c.get("parameters"), list)
                         and len(c["parameters"]) == 1
                         and isinstance(c["parameters"][0], str) for c in group):
            lines = [c["parameters"][0] for c in group]
            if any(visible_width(line) > max_width for line in lines):
                # Conserva el número exacto de líneas y comandos del evento.
                # Si hace falta otra línea, omite el cuadro en vez de corromperlo.
                new_lines = wrap_message(lines, max_width, max_lines=len(group))
                if new_lines is None or len(new_lines) != len(group):
                    skipped += 1
                else:
                    for original_command, line in zip(group, new_lines):
                        original_command["parameters"][0] = line
                    fixed += 1
        i = j
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
