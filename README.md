# NION core (v0.1.0)

Núcleo del traductor de RPG Maker MV/MZ. **Solo biblioteca estándar de Python** (sin pip, sin PyTorch),
pensado para Termux/ARM64. Nunca modifica el juego original: escribe una COPIA de `data`.

## Uso (desde la carpeta que contiene `nion/`)

    python -m nion scan      JUEGO --lang es                    # cuenta, no gasta nada
    python -m nion translate JUEGO --lang es --engine deepl --key CLAVE:fx
    python -m nion apply     JUEGO --lang es                    # crea JUEGO/data_es

`JUEGO` es la raíz del juego (MZ: `data/`, MV: `www/data/`) o la propia carpeta `data`.
La memoria se guarda en `nion_memory_<lang>.json`; si se corta, se vuelve a ejecutar `translate`.
`--engine echo` no traduce de verdad (prueba de tuberías, sin red).

## Piezas

| Archivo | Qué hace |
|---|---|
| `nion/codes.py` | detecta y protege códigos (`\C[2]`, `\V[1]`, `%1`, `<tags>`...) |
| `nion/extract.py` | localiza los textos traducibles de MV y MZ, con su ruta exacta en el JSON |
| `nion/memory.py` | memoria de traducción (JSON, guardado atómico) |
| `nion/engine.py` | motores intercambiables: `echo`, `deepl`. Aquí irá el motor offline |
| `nion/pipeline.py` | escanear -> traducir por lotes (reanudable) -> aplicar a una copia |
| `nion/cli.py` | línea de comandos |

## Decisiones de diseño

- Un motor es una clase con `translate_batch()`. Si falla lanza `EngineError`: **nunca falla en silencio**.
- Si el motor respeta marcadores (`supports_masking`), los códigos se enmascaran. Si el motor pierde un
  marcador, ese texto se retraduce por trozos (el texto entre códigos). DeepL va directo por trozos.
- La memoria es compatible con los diccionarios `cache_deepl*.json` anteriores (trozo -> traducción).
- Los archivos del juego se escriben solo tras tener las traducciones, y de forma atómica.

## Pruebas

    python -m unittest discover -s tests -v

## Límites conocidos (v0.1.0)

- Cada línea de diálogo (código 401) se traduce por separado. Falta traducir el bloque entero para más contexto.
- No toca plugins (`js/plugins.js`), comandos de plugin (357), ni imágenes con texto.
- Solo motores `echo` y `deepl`. El motor offline depende de la prueba de viabilidad en Termux.
- No hay interfaz web todavía.
