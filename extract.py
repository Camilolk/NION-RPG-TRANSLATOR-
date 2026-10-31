"""Extracción de textos traducibles de RPG Maker MV y MZ (carpeta data/*.json)."""
import json
import os
from collections import namedtuple

# Entry.path es una tupla de claves/índices dentro del JSON de `file`.
Entry = namedtuple("Entry", "file path text")

DB_FIELDS = {
    "Actors": ("name", "nickname", "profile"),
    "Armors": ("name", "description"),
    "Classes": ("name",),
    "Enemies": ("name",),
    "Items": ("name", "description"),
    "Skills": ("name", "description", "message1", "message2"),
    "States": ("name", "message1", "message2", "message3", "message4"),
    "Weapons": ("name", "description"),
}
SYSTEM_LISTS = ("skillTypes", "weaponTypes", "armorTypes", "equipTypes")
EVENT_FILES = ("CommonEvents", "Troops")


def find_data_dir(path):
    """Acepta la raíz del juego o la propia carpeta data. MZ: data/  MV: www/data/"""
    for cand in (path, os.path.join(path, "data"), os.path.join(path, "www", "data")):
        if os.path.isfile(os.path.join(cand, "System.json")):
            return cand
    raise FileNotFoundError("No encuentro data/System.json en " + path)


def load_json(path):
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def _is_str(v):
    return isinstance(v, str) and v != ""


def _command_entries(file, cmds, base):
    for i, cmd in enumerate(cmds):
        if not isinstance(cmd, dict):
            continue
        code, p = cmd.get("code"), cmd.get("parameters")
        if not isinstance(p, list):
            continue
        pb = base + (i, "parameters")
        if code in (401, 405) and p and _is_str(p[0]):
            yield Entry(file, pb + (0,), p[0])
        elif code == 101 and len(p) > 4 and _is_str(p[4]):      # nombre del hablante (MZ)
            yield Entry(file, pb + (4,), p[4])
        elif code == 102 and p and isinstance(p[0], list):       # opciones
            for k, s in enumerate(p[0]):
                if _is_str(s):
                    yield Entry(file, pb + (0, k), s)
        elif code == 402 and len(p) > 1 and _is_str(p[1]):       # rama de una opción
            yield Entry(file, pb + (1,), p[1])


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
                for i, s in enumerate(data.get(key) or []):
                    if _is_str(s):
                        yield Entry(fname, (key, i), s)
            terms = data.get("terms") or {}
            for key in ("basic", "commands", "params"):
                for i, s in enumerate(terms.get(key) or []):
                    if _is_str(s):
                        yield Entry(fname, ("terms", key, i), s)
            for key, s in (terms.get("messages") or {}).items():
                if _is_str(s):
                    yield Entry(fname, ("terms", "messages", key), s)
        elif stem == "CommonEvents":
            data = load_json(os.path.join(data_dir, fname))
            for i, ev in enumerate(data):
                if isinstance(ev, dict) and isinstance(ev.get("list"), list):
                    yield from _command_entries(fname, ev["list"], (i, "list"))
        elif stem == "Troops":
            data = load_json(os.path.join(data_dir, fname))
            for i, tr in enumerate(data):
                if isinstance(tr, dict):
                    yield from _pages_entries(fname, tr.get("pages"), (i, "pages"))
        elif stem.startswith("Map") and stem != "MapInfos":
            data = load_json(os.path.join(data_dir, fname))
            if _is_str(data.get("displayName")):
                yield Entry(fname, ("displayName",), data["displayName"])
            for i, ev in enumerate(data.get("events") or []):
                if isinstance(ev, dict):
                    yield from _pages_entries(fname, ev.get("pages"), ("events", i, "pages"))
