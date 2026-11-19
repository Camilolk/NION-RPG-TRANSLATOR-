"""Genera ZIP de traduccion RPG Maker MZ, sin modificar el juego."""
import argparse
import json
import re
import zipfile
from pathlib import Path

def enable_autowrap(source):
    match = re.search(r'\$plugins\s*=\s*', source)
    if not match:
        raise ValueError('No se encontro $plugins = en js/plugins.js')
    decoder = json.JSONDecoder()
    tail = source[match.end():]
    start = match.end() + len(tail) - len(tail.lstrip())
    plugins, consumed = decoder.raw_decode(source[start:])
    if not isinstance(plugins, list):
        raise ValueError('La lista de plugins no es valida')
    for plugin in plugins:
        if isinstance(plugin, dict) and plugin.get('name') == 'AutoWrap':
            plugin['status'] = True
            break
    else:
        plugins.append({'name':'AutoWrap','status':True,'description':'Ajuste dinamico MZ','parameters':{}})
    return source[:start] + json.dumps(plugins,ensure_ascii=False,indent=2) + source[start+consumed:]

def main(argv=None):
    parser = argparse.ArgumentParser(description='NION Patch Builder (RPG Maker MZ)')
    parser.add_argument('game', help='Carpeta del juego que contiene Game.exe')
    parser.add_argument('--source', default='data', help='Carpeta traducida dentro del juego (default: data)')
    parser.add_argument('--original', default='data_ingles', help='Carpeta original dentro del juego')
    parser.add_argument('--output', default='Velgards_Trial_v0.3.3_ES_NION.zip')
    args = parser.parse_args(argv)
    game = Path(args.game).expanduser().resolve()
    data = game / args.source
    original = game / args.original
    config = game / 'js' / 'plugins.js'
    autowrap = Path(__file__).resolve().parent.parent / 'assets' / 'AutoWrap.js'
    if not (game/'js'/'rmmz_core.js').is_file():
        parser.error('Este exportador requiere RPG Maker MZ')
    for path in (data/'System.json',original/'System.json',config,autowrap):
        if not path.is_file():
            parser.error('Falta archivo: ' + str(path))
    changed = []
    for path in sorted(data.glob('*.json')):
        try:
            json.loads(path.read_text(encoding='utf-8-sig'))
        except (ValueError, UnicodeError) as exc:
            parser.error('JSON invalido en ' + str(path) + ': ' + str(exc))
        english = original / path.name
        if not english.is_file() or path.read_bytes() != english.read_bytes():
            changed.append(path)
    if not changed:
        parser.error('No hay JSON diferentes del original')
    plugins = enable_autowrap(config.read_text(encoding='utf-8-sig'))
    output = Path(args.output).expanduser().resolve()
    if output.exists():
        parser.error('El ZIP ya existe: ' + str(output))
    readme = """VELGARD'S TRIAL v0.3.3 - TRADUCCION AL ESPANOL (NION)

Requiere una copia original de Velgard's Trial v0.3.3 para Windows.
Cierra el juego y respalda data/ y js/ antes de instalar.
Extrae el ZIP en la carpeta que contiene Game.exe y acepta reemplazar archivos.
Incluye JSON traducidos y AutoWrap.js v2 (solo RPG Maker MZ).
El plugins.js incluido corresponde a la instalacion utilizada para crear el parche.
No es compatible necesariamente con otras versiones o configuraciones.
AutoWrap v2 une saltos de linea intencionales. Comprueba escenas especiales.
No incluye Game.exe ni archivos multimedia.
Verifica creditos y autorizacion del desarrollador antes de publicar.
"""
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as archive:
        for path in changed:
            archive.write(path,'data/'+path.name)
        archive.writestr('js/plugins.js',plugins)
        archive.write(autowrap,'js/plugins/AutoWrap.js')
        archive.writestr('LEEME.txt',readme)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError('Error de integridad en ZIP')
    print('Parche:',output)
    print('JSON modificados:',len(changed))
    print('Tamano MB:',round(output.stat().st_size/1048576,2))

if __name__ == '__main__':
    main()
