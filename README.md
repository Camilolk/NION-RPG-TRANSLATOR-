# NION RPG Translator — núcleo v0.2.0

Núcleo para traducir juegos RPG Maker MV y MZ. El núcleo usa la biblioteca estándar de Python; el motor local requiere `llama.cpp` y un modelo GGUF servido localmente.

> Estado: prototipo en revisión. Las pruebas automáticas no sustituyen la validación en Termux/Android ni una prueba con un juego real.

## Estructura
- nion/: paquete Python del núcleo.
- tests/: pruebas automáticas.
- CHANGES_FOR_CHATGPT.md: historial y traspaso de trabajo.
- nion-core.zip: archivo original recibido; se conserva como referencia.

## Requisitos
- Python 3.9 o superior recomendado.
- Android con Termux para la validación objetivo.
- Para DeepL: una clave API válida. No guardes claves en el repositorio.
- Para traducción local: `llama.cpp` y un modelo GGUF compatible. NION usa la API local compatible con OpenAI.

## Uso
Desde la raíz del repositorio:

    python -m nion scan RUTA_DEL_JUEGO --lang es
    python -m nion translate RUTA_DEL_JUEGO --lang es --engine echo
    python -m nion translate RUTA_DEL_JUEGO --lang es --engine hybrid --limit 10
    python -m nion translate RUTA_DEL_JUEGO --lang es --engine hybrid
    python -m nion translate RUTA_DEL_JUEGO --lang es --engine llamacpp
    python -m nion apply RUTA_DEL_JUEGO --lang es

`echo` solo comprueba el flujo; no traduce. El motor predeterminado es `hybrid`: aplica primero equivalencias exactas del glosario, usa OpenRouter si existe `NION_OPENROUTER_KEY` y recurre a llama.cpp cuando la nube falla o no está configurada. `--limit 10` permite una ejecución piloto de hasta 10 textos únicos sin traducir el resto; omite `--limit` para continuar sin límite. Para OpenRouter, define `NION_OPENROUTER_KEY`; el modelo predeterminado es `openrouter/free` y puede cambiarse con `NION_OPENROUTER_MODEL` o `--model`. Los modelos gratuitos tienen límites de uso y disponibilidad variables. Los textos enviados a OpenRouter salen del teléfono y se procesan por el proveedor; no incluyas datos privados del juego si no aceptas ese envío. Para DeepL, define `NION_DEEPL_KEY` o usa `--key`. Para llama.cpp, inicia el servidor en otra sesión de Termux:

    llama-server -m RUTA_DEL_MODELO.gguf -c 2048 --host 127.0.0.1 --port 8080

Después ejecuta NION con `--engine llamacpp` o deja que `hybrid` lo use como respaldo. La URL predeterminada es `http://127.0.0.1:8080`; se puede cambiar con `--url` o `NION_LLAMACPP_URL`. El servidor debe permanecer activo. Las peticiones al servidor local no necesitan clave API ni conexión a Internet.

El motor local envía un texto por petición para mantener la correspondencia entre entrada y salida. NION enmascara códigos RPG Maker y nombres protegidos antes de enviarlos y los restaura después. Si el modelo altera los marcadores, el pipeline recurre a traducir segmentos. El glosario solo normaliza y protege nombres propios; no se inyecta como lista de traducciones ni impone equivalencias de objetos. NION valida la integridad de los marcadores, los nombres y las respuestas vacías, pero no puede verificar automáticamente si una traducción conserva todo el significado o la gramática. La calidad lingüística depende del modelo; revisa una muestra antes de usar el resultado en un juego.

La carpeta del juego puede ser la raíz que contiene data/ (MZ), www/data/ (MV), o directamente data/.

## Flujo seguro
1. `scan` cuenta los textos sin llamar a ningún motor.
2. `translate` traduce y valida la integridad técnica antes de guardar en la memoria JSON. Los códigos RPG Maker y los nombres confirmados se protegen también en la ruta por segmentos (usada por DeepL o como respaldo). No hay reglas que reescriban frases ni un control semántico basado en términos; la memoria se actualiza por lote para permitir reanudación. La memoria predeterminada nueva es `nion_memory_<lang>_v2.json`, separada de las memorias antiguas.
3. `apply` solo exporta cuando todos los textos detectados tienen traducción. Crea una carpeta nueva y nunca modifica los archivos originales.
4. Si la carpeta de salida ya existe, NION se detiene para evitar mezclar archivos antiguos.

La memoria y las copias de juegos son datos locales; no deben subirse a GitHub.

## Pruebas
    python -m unittest discover -s tests -v

## Códigos RPG Maker y glosario
NION protege códigos como \\C[2], \\V[1], \\N[1], \\I[64], %1 y etiquetas compatibles. Los marcadores deben regresar una sola vez y en el mismo orden; si el motor los altera, NION recurre a traducir segmentos sin tocar los tokens.

El archivo `nion/glossary.json` contiene nombres oficiales y variantes conocidas. Normaliza, por ejemplo, `Грант` a `Grant` y `Элио` a `Elio`, sin tocar códigos de formato. La lista inicial incluye Elio, Shiori, Erika, Grant, Tama, Kael y Ryou. Las equivalencias de objetos y materiales no se envían al modelo ni se usan para rechazar traducciones.

Los nombres de actores de `Actors.json` se normalizan en la copia exportada. Los nombres visibles de hablantes (comando 101) se extraen como texto: nombres del glosario se conservan; descripciones como `Охранник` se traducen. Los nombres internos de eventos, como `EV002` o `GrantHouse`, no se extraen.

## Limitaciones
- Cada línea de diálogo (comando 401) se procesa por separado; falta agrupar bloques y analizar desbordamiento visual. NION no debe cambiar el tamaño original de la fuente.
- No procesa plugins, imágenes con texto ni todos los campos posibles de RPG Maker.
- Motores: hybrid, openrouter, deepl, llamacpp y echo. `hybrid` combina reglas exactas, memoria, OpenRouter opcional y llama.cpp local como respaldo. Las reglas solo se aplican a entradas completas del glosario; no sustituyen palabras dentro de frases. La validación rechaza contaminación de caracteres CJK en idiomas latinos, pero no puede certificar la calidad semántica. Los modelos gratuitos remotos pueden aplicar límites o dejar de estar disponibles.
- No hay interfaz web.
- DeepL no ha sido validado contra la API real en este proyecto.
