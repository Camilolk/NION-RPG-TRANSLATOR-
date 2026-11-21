"""Reparacion opcional con un modelo GGUF local, sin servidor."""
import argparse
import json
from pathlib import Path
from .quality import inspect
from .repair import SEVERE
from .repair_propose import semantic_warnings

class LocalGGUF:
    def __init__(self, model_path, n_ctx=2048, n_threads=4):
        try:
            from llama_cpp import Llama
        except ImportError as error:
            raise RuntimeError("Instala llama-cpp-python en el entorno de NION") from error
        self.llm = Llama(model_path=str(model_path), n_ctx=n_ctx,
                         n_threads=n_threads, n_gpu_layers=0, verbose=False)

    def translate(self, source):
        prompt = (
            "Translate the following RPG dialogue from English to natural Latin American "
            "Spanish. Preserve the complete meaning, all questions, and technical codes. "
            "Do not add commentary. Output only the Spanish translation.\n"
            "English: " + source + "\nSpanish:"
        )
        result = self.llm.create_completion(
            prompt=prompt, max_tokens=256, temperature=0.1,
            repeat_penalty=1.2, stop=["\nEnglish:", "\n\n"]
        )
        return result["choices"][0]["text"].strip()

def review(rows, engine, limit=5):
    result = [dict(row) for row in rows]
    processed = 0
    for row in result:
        if processed >= limit:
            break
        if not row.get("original") or row.get("aprobado"):
            continue
        # Comparar incluso propuestas sin alertas, pues las heuristicas no son infalibles.
        try:
            candidate = engine.translate(row["original"])
            warnings = sorted(SEVERE.intersection(inspect(row["original"], candidate)))
            warnings.extend(semantic_warnings(row["original"], candidate))
            row["propuesta_gguf"] = candidate
            row["alertas_gguf"] = warnings
            row["estado_gguf"] = "revisar" if warnings else "sin_alertas_automaticas"
        except Exception as error:
            row["estado_gguf"] = "error"
            row["error_gguf"] = str(error)[:300]
        processed += 1
        print("GGUF:", processed, "/", limit, "|", row["estado_gguf"])
    return result

def main(argv=None):
    parser = argparse.ArgumentParser(description="Compara reparaciones con GGUF local; no altera memoria")
    parser.add_argument("review", help="Informe de propuestas de MarianMT")
    parser.add_argument("--model", required=True, help="Ruta local al modelo .gguf")
    parser.add_argument("--out", default="nion_propuestas_gguf.json")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args(argv)
    source, output, model = Path(args.review).resolve(), Path(args.out).resolve(), Path(args.model).resolve()
    if not source.is_file() or not model.is_file():
        parser.error("No existe el informe o el modelo GGUF")
    if source == output or output.exists():
        parser.error("El archivo de salida ya existe o coincide con el informe")
    if not 1 <= args.limit <= 10000 or not 1 <= args.threads <= 64:
        parser.error("Parametros fuera de rango")
    rows = json.loads(source.read_text(encoding="utf-8-sig"))
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        parser.error("El informe debe ser una lista de objetos")
    print("Cargando GGUF bajo demanda (solo modo reparacion)...")
    result = review(rows, LocalGGUF(model, n_threads=args.threads), args.limit)
    with output.open("x", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print("Informe:", output, "| Memoria original intacta.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
