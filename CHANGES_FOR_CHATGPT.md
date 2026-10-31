# Resumen de sesión (Claude, chat de la app; NO es Claude Code)

## 1. Qué se hizo
Primer núcleo de NION en Python estándar: extracción MV/MZ, protección de códigos, memoria de traducción,
motores intercambiables, pipeline por lotes reanudable y CLI mínima.

## 2. Archivos creados
`nion/{__init__,codes,memory,engine,extract,pipeline,cli,__main__}.py`, `tests/test_core.py`, `README.md`, este archivo.
No se modificó nada existente (el repo estaba vacío para esta sesión).

## 3. Pruebas ejecutadas (en un entorno de pruebas del chat, NO en Android)
- `python -m unittest discover -s tests`: 8 pruebas, todas OK (extracción MV y MZ, ida y vuelta de códigos,
  copia sin tocar el original, reanudación tras fallo, retraducción por trozos, reutilización de cachés antiguas).
- CLI de punta a punta con el motor `echo`: scan -> translate -> scan -> apply correctos.
- El motor `deepl` NO se probó contra la API real desde este chat (sin red).

## 4. Resultados
Todo lo anterior pasó. Falta probar en Termux real (versión de Python, rendimiento, rutas de /storage).

## 5. Pendiente
- Prueba de viabilidad del motor offline (ARM64/Termux). Aún sin motor offline.
- Traducción por bloque de diálogo (unir líneas 401 consecutivas).
- Limitación de longitud de línea al aplicar (en juegos MZ se resolvió con un plugin de ajuste de texto aparte).
- Plugins, comandos de plugin, interfaz web.

## 6. Qué debe hacer ChatGPT
Revisar la arquitectura, subir esto al repositorio (rama main), y decidir si `engine.py` y `codes.py` necesitan cambios
antes de añadir motores.

## 7. Qué debe hacer el usuario
Ejecutar en Termux: `uname -m`, `free -h`, `df -h ~`, `python --version`; luego `python -m unittest discover -s tests`
y `python -m nion scan RUTA_DEL_JUEGO`, y pasar los resultados reales.
