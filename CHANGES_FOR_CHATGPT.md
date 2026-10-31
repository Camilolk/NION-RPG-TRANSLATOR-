# Resumen de sesión — reorganización del núcleo NION

## Cambios
- Código organizado como paquete Python nion/ y pruebas en tests/.
- Se conserva nion-core.zip como referencia original.
- Se valida que cada motor devuelva exactamente un resultado de texto por entrada; respuestas incompletas generan EngineError.
- La exportación se cancela antes de copiar archivos si falta alguna traducción.
- Se rechazan destinos existentes y destinos dentro de la carpeta original para evitar mezclar archivos antiguos o tocar el juego fuente.
- Se añadió GitHub Actions para ejecutar pruebas con Python 3.11.
- README actualizado.

## Validación
Los archivos se reorganizaron en GitHub. No se ejecutó Python en Termux ni en Android durante esta sesión. Consultar el resultado de GitHub Actions antes de afirmar que las pruebas pasan en CI.

## Pendiente
- Confirmar resultado del workflow.
- Ejecutar pruebas manuales en Termux.
- Probar scan con una copia de juegos MV y MZ.
- Probar DeepL con clave local, nunca en GitHub.
- Evaluar motor offline tras conocer arquitectura, RAM y almacenamiento del teléfono.
- Agrupar líneas consecutivas de diálogo 401.

No subir juegos, claves, memorias ni modelos al repositorio. No afirmar que algo funciona en Android sin probarlo allí.
