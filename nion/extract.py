"""Extracción de textos RPG Maker MV/MZ y recopilación de nombres propios."""
import json
import os
from collections import namedtuple

from .glossary import glossary_terms, load_glossary

Entry = namedtuple("Entry", "file path text")

DB_FIELDS = {
    "Actors": ("nickname", "profile"),
    "Armors": ("name", "description"),
    "Classes": ("name",),
    "Enemies": ("name",),
    "Items": ("name", "description"),
    "Skills": ("name", "description", "message1", "message2"),
    "States": ("name", "message1", "message2", "message3", "message4"),
    "Weapons": ("name", "description"),
}
SYSTEM_LISTS = ("skillTypes", "weaponTypes", "armorTypes", "equipTypes")


def find_data_dir(path):
    """Acepta raíz de juego o carpeta data. MZ: data/; MV: www/data/."""
    for cand in (path, os.path.join(path, "data"), os.path.join(path, "www", "data")):
        if os.path.isfile(os.path.join(cand, "System.json")):
            return cand
    raise FileNotFoundError("No encuentro data/System.json en " + path)


def load_json(path):
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def _is_str(value):
    return isinstance(value, str) and value != ""


def protected_names(data_dir=None, glossary=None):
    """Solo protege nombres confirmados en el glosario, nunca nombres de eventos."""
    return glossary_terms(glossary or load_glossary())


def _command_entries(file, commands, base):
    for i, command in enumerate(commands):
        if not isinstance(command, dict):
            continue
        code, params = command.get("code"), command.get("parameters")
        if not isinstance(params, list):
            continue
        params_base = base + (i, "parameters")
        if code == 101 and len(params) > 4 and _is_str(params[4]):
            # Nombre visible del hablante: se traduce salvo que esté en el glosario.
            yield Entry(file, params_base + (4,), params[4])
        elif code in (401, 405) and params and _is_str(params[0]):
            yield Entry(file, params_base + (0,), params[0])
        elif code == 102 and params and isinstance(params[0], list):
            for k, value in enumerate(params[0]):
                if _is_str(value):
                    yield Entry(file, params_base + (0, k), value)
        elif code == 402 and len(params) > 1 and _is_str(params[1]):
            yield Entry(file, params_base + (1,), params[1])


def _pages_entries(file, pages, base):
    for j, page in enumerate(pages or []):
        if isinstance(page, dict) and isinstance(page.get("list"), list):
            yield from _command_entries(file, page["list"], base + (j, "list"))


def iter_entries(data_dir):
    for fname in sorted(os.listdir(data_dir)):
        if not fname.endswith(".json"):
            continue
        stem = fname[:-5]
        if stem in DB_FIELDS:
            data = load_json(os.path.join(data_dir, fname))
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    for key in DB_FIELDS[stem]:
                        if _is_str(item.get(key)):
                            yield Entry(fname, (i, key), item[key])
        elif stem == "System":
            data = load_json(os.path.join(data_dir, fname))
            if _is_str(data.get("currencyUnit")):
                yield Entry(fname, ("currencyUnit",), data["currencyUnit"])
            for key in SYSTEM_LISTS:
                for i, value in enumerate(data.get(key) or []):
                    if _is_str(value):
                        yield Entry(fname, (key, i), value)
            terms = data.get("terms") or {}
            for key in ("basic", "commands", "params"):
                for i, value in enumerate(terms.get(key) or []):
                    if _is_str(value):
                        yield Entry(fname, ("terms", key, i), value)
            for key, value in (terms.get("messages") or {}).items():
                if _is_str(value):
                    yield Entry(fname, ("terms", "messages", key), value)
        elif stem == "CommonEvents":
            data = load_json(os.path.join(data_dir, fname))
            for i, event in enumerate(data):
                if isinstance(event, dict) and isinstance(event.get("list"), list):
                    yield from _command_entries(fname, event["list"], (i, "list"))
        elif stem == "Troops":
            data = load_json(os.path.join(data_dir, fname))
            for i, troop in enumerate(data):
                if isinstance(troop, dict):
                    yield from _pages_entries(fname, troop.get("pages"), (i, "pages"))
        elif stem.startswith("Map") and stem != "MapInfos":
            data = load_json(os.path.join(data_dir, fname))
            if _is_str(data.get("displayName")):
                yield Entry(fname, ("displayName",), data["displayName"])
            for i, event in enumerate(data.get("events") or []):
                if isinstance(event, dict):
                    yield from _pages_entries(fname, event.get("pages"), ("events", i, "pages"))
