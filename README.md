# NION RPG Translator — núcleo v0.1.1

Núcleo inicial para traducir juegos RPG Maker MV y MZ. Está escrito con la biblioteca estándar de Python: no requiere pip, PyTorch ni modelos descargados.

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

## Uso
Ejecuta desde la raíz del repositorio:

    python -m nion scan RUTA_DEL_JUEGO --lang es
    python -m nion translate RUTA_DEL_JUEGO --lang es --engine echo
    python -m nion apply RUTA_DEL_JUEGO --lang es

echo solo comprueba el flujo; no traduce. Para DeepL, define NION_DEEPL_KEY en el entorno o usa --key. No escribas la clave en comandos que queden guardados en el historial.

La carpeta del juego puede ser la raíz que contiene data/ (MZ), la raíz que contiene www/data/ (MV), o directamente la carpeta data/.

## Flujo seguro
1. scan cuenta los textos sin llamar a ningún motor.
2. translate guarda traducciones en una memoria JSON y la actualiza por lote para permitir reanudación.
3. apply solo exporta cuando todos los textos detectados tienen traducción. Crea una carpeta nueva y nunca modifica los archivos originales.
4. Si la carpeta de salida ya existe, el programa se detiene para evitar mezclar archivos de una ejecución anterior.

La memoria y las copias de juegos son datos locales; no deben subirse a GitHub.

## Pruebas
    python -m unittest discover -s tests -v

## Protección de códigos
El núcleo intenta preservar códigos como \C[2], \V[1], \N[1], %1 y etiquetas compatibles. Los motores deben devolver exactamente un resultado de texto por entrada; una respuesta incompleta se trata como error.

## Limitaciones conocidas
- Cada línea de diálogo (comando 401) se procesa por separado; falta agrupar bloques consecutivos.
- No procesa plugins, comandos de plugin, imágenes con texto ni todos los campos posibles de RPG Maker.
- Motores incluidos: echo y deepl. Aún no hay motor offline; su viabilidad debe medirse en Android.
- No hay interfaz web.
- DeepL no ha sido validado contra la API real en este proyecto.
