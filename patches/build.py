"""Empaqueta traducciones locales de Velgard's Trial v0.3.3 en ZIP instalables.

Uso: python -m patches.build --game "RUTA_JUEGO" --translations "RUTA_NION_6_IDIOMAS"
Nunca modifica la instalación del juego ni los JSON de traducción.
"""
import argparse
import json
import re
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

LANGUAGES = {
    "es": ("Español", "data_es", 26),
    "pt": ("Português (Brasil)", "data_pt_br_final", 26),
    "de": ("Deutsch", "data_de", 25),
    "fr": ("Français", "data_fr", 26),
    "it": ("Italiano", "data_it", 26),
    "ru": ("Русский", "data_ru", 26),
    "ja": ("日本語", "data_ja_prueba", 24),
    "zh": ("简体中文", "data_zh", 24),
}
ROOT = Path(__file__).resolve().parent
PLUGIN_NAME = "NION_AutoWrap"
PLUGIN_FILENAME = PLUGIN_NAME + ".js"


def plugin_list(path, font_size):
    raw = path.read_text(encoding="utf-8-sig")
    match = re.fullmatch(r"\s*(?:var|let|const)\s+\$plugins\s*=\s*(\[.*\])\s*;\s*", raw, re.S)
    if not match:
        raise ValueError("Formato js/plugins.js no reconocido. No se modifica ni se empaqueta.")
    items = json.loads(match.group(1))
    if not isinstance(items, list):
        raise ValueError("js/plugins.js no contiene una lista.")
    if any(not isinstance(item, dict) for item in items):
        raise ValueError("Lista de plugins inválida.")
    if any(item.get("name") == PLUGIN_NAME for item in items):
        raise ValueError("El juego ya registra NION_AutoWrap: revisar manualmente.")
    items.append({"name": PLUGIN_NAME, "status": True, "description": "NION AutoWrap", "parameters": {"fontSize": str(font_size)}})
    return "var $plugins =\n" + json.dumps(items, ensure_ascii=False, indent=2) + ";\n"


def readme(code, name, font_size):
    return f"""NION RPG Translator — Parche {name} ({code})
Compatible únicamente con Velgard's Trial v0.3.3
===================================================

INSTALACIÓN (WINDOWS)
1. Comprueba que tu juego sea Velgard's Trial v0.3.3.
2. Haz una copia de seguridad de las carpetas data y js del juego.
3. Extrae el CONTENIDO de este ZIP en la carpeta donde está Game.exe.
4. Acepta reemplazar los archivos cuando Windows lo solicite.
5. Inicia una PARTIDA NUEVA: los guardados anteriores pueden conservar texto inglés.

ANDROID / JOIPLAY
1. Haz una copia de seguridad de data y js.
2. Con ZArchiver extrae el contenido del ZIP en la carpeta raíz del juego.
3. Acepta reemplazar archivos e inicia una partida nueva.

DESINSTALAR
Restaura las carpetas data y js que respaldaste antes de instalar.

ARCHIVOS DEL PARCHE
- data/*.json: traducción de textos del juego.
- js/plugins.js: lista de plugins original más NION_AutoWrap activado.
- js/plugins/NION_AutoWrap.js: ajuste automático experimental de líneas.
- README.txt: estas instrucciones.

TAMAÑO DE FUENTE
El tamaño sugerido para este idioma es {font_size}px. No todos los motores
RPG Maker usan la propiedad fontSize de data/System.json; el tamaño real
depende del motor y de los plugins del juego. Si el texto no cabe, repórtalo.

AVISOS
- No instalar en otras versiones del juego.
- Las traducciones son automáticas y pueden contener errores.
- AutoWrap es experimental: prueba mensajes largos, opciones y códigos.
- No mezcles varios parches de idioma en la misma instalación.
- Los nombres propios oficiales se mantienen en inglés cuando es posible.
- El parche NO incluye ejecutables, imágenes, audio ni recursos del juego.

Generado por NION RPG Translator.
"""


def main():
    parser = argparse.ArgumentParser(description="Crea 8 ZIP de traducciones v0.3.3")
    parser.add_argument("--game", required=True, type=Path, help="carpeta raíz con Game.exe y js/plugins.js")
    parser.add_argument("--translations", required=True, type=Path, help="carpeta NION_6_IDIOMAS")
    parser.add_argument("--out", type=Path, help="carpeta de ZIP (predeterminado NION-RPG-TRANSLATOR-/parches_v0.3.3)")
    parser.add_argument("--langs", default=",".join(LANGUAGES), help="idiomas: es,pt,de,fr,it,ru,ja,zh")
    args = parser.parse_args()
    game = args.game.resolve()
    translations = args.translations.resolve()
    out = (args.out or ROOT.parent / "parches_v0.3.3").resolve()
    plugin_path = game / "js" / "plugins.js"
    if not plugin_path.is_file():
        parser.error("No existe js/plugins.js en --game; indica la raíz real del juego.")
    wrap_js = (ROOT / "AutoWrap.js").read_bytes()
    codes = [c.strip().lower() for c in args.langs.split(",")]
    if any(c not in LANGUAGES for c in codes) or len(codes) != len(set(codes)):
        parser.error("Idiomas desconocidos o duplicados.")
    plans = []
    for code in codes:
        name, dirname, font_size = LANGUAGES[code]
        data_dir = translations / dirname
        if not data_dir.is_dir():
            parser.error(f"Falta {data_dir}")
        files = sorted(data_dir.glob("*.json"))
        if not files or not (data_dir / "System.json").is_file():
            parser.error(f"Faltan JSON o System.json en {data_dir}")
        for file in files:
            try:
                json.loads(file.read_text(encoding="utf-8-sig"))
            except (ValueError, UnicodeError) as error:
                parser.error(f"JSON inválido {file}: {error}")
        plans.append((code, name, font_size, files))
    out.mkdir(parents=True, exist_ok=True)
    for code, name, font_size, files in plans:
        target = out / f"Parche_{code}_facil.zip"
        if target.exists():
            parser.error(f"Ya existe {target}; mueve o elimina el ZIP antiguo primero.")
        with ZipFile(target, "w", compression=ZIP_DEFLATED, compresslevel=6) as zipfile:
            for file in files:
                zipfile.write(file, "data/" + file.name)
            zipfile.writestr("js/plugins.js", plugin_list(plugin_path, font_size))
            zipfile.writestr("js/plugins/" + PLUGIN_FILENAME, wrap_js)
            zipfile.writestr("README.txt", readme(code, name, font_size))
        with ZipFile(target) as zipfile:
            corrupt = zipfile.testzip()
            if corrupt:
                raise RuntimeError(f"ZIP corrupto: {target} ({corrupt})")
        print(f"OK {name}: {target.name} ({target.stat().st_size / 1048576:.2f} MiB)")
    print(f"TERMINADO: {out}")


if __name__ == "__main__":
    main()
