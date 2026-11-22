# NION 4.0 — Criterios de salida

Estado: **preparacion de version candidata**, no lanzamiento confirmado.

## Alcance de la version 4.0

El objetivo es entregar una herramienta util para traducir juegos RPG Maker MV/MZ, sin prometer traduccion perfecta.

### Requisitos imprescindibles

- [ ] Ejecutar todas las pruebas automatizadas sin fallos.
- [ ] Probar `scan` sobre un juego real y confirmar el recuento de textos.
- [ ] Probar `translate` sobre una copia de un juego real con el motor elegido.
- [ ] Verificar que las traducciones con codigos RPG Maker mantienen variables y marcadores.
- [ ] Probar `apply` y confirmar que crea una salida independiente y no modifica el juego original.
- [ ] Abrir la copia traducida en RPG Maker o en el juego y comprobar dialogos, menus y eventos.
- [ ] Documentar los pasos de instalacion, uso, dependencias y limitaciones reales.
- [ ] Medir el tiempo de una muestra representativa y registrar el resultado sin prometer una velocidad concreta.

### Mejoras que pueden esperar

- Traduccion perfecta de tartamudeos y expresiones extremas.
- Soporte universal para plugins, imagenes con texto y todos los formatos.
- Traduccion automatica de todos los campos posibles.
- Optimizaciones sin evidencia de un cuello de botella.
- Una interfaz grafica completa, salvo que sea imprescindible para el lanzamiento acordado.

## Regla de estabilidad

No modificar archivos originales del juego ni sobrescribir memorias de traduccion. Los informes de prueba deben escribirse en archivos nuevos. Los casos que no pasen las validaciones se mantienen en cuarentena o se revisan manualmente.

## Pruebas locales

```powershell
git pull origin feature/translation-performance
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m nion --help
```

## Pendiente de decision

- Plataforma principal de lanzamiento: Windows, Android/Termux o ambas.
- Interfaz minima de lanzamiento: linea de comandos o interfaz grafica.
- Motor predeterminado y forma de distribuir dependencias pesadas.

**No etiquetar ni publicar 4.0 hasta completar las comprobaciones imprescindibles.**
