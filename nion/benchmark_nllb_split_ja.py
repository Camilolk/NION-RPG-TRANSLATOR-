"""Prueba si dividir diálogos por oraciones reduce omisiones en NLLB japonés.

No modifica memorias ni archivos de juego.
"""
import re
import time

SAMPLES = [
    "Woah, so you can see me? You must be a really powerful mage.",
    "Woah, so you can see me? You must be a really powerful mage. That's quite a difficult",
    "I have to make sure to use my self-enhancing spells before going in.",
    "You really are, son! Make sure to keep her close. It'd be bad if someone took her away...",
    "A vest made of tanned hide.",
    "Linen clothing with high breathability.",
]
# Dividir solo en puntuación final seguida de espacio y mayúscula.
# Evitar puntos suspensivos y abreviaturas en este experimento.
BOUNDARY = re.compile(r"(?<=[!?])\\s+(?=[A-Z])|(?<!\\.)\\.(?!\\.)\\s+(?=[A-Z])")

def main():
    import torch
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    model_id = "facebook/nllb-200-distilled-600M"
    print("Cargando", model_id, flush=True)
    tokenizer = AutoTokenizer.from_pretrained(model_id, src_lang="eng_Latn")
    model = AutoModelForSeq2SeqLM.from_pretrained(model_id)
    model.eval()
    target = tokenizer.convert_tokens_to_ids("jpn_Jpan")
    for source in SAMPLES:
        parts = [p.strip() for p in BOUNDARY.split(source) if p.strip()]
        print("\nEN:", source)
        print("PARTES:", repr(parts))
        for label, pieces in [("completo", [source]), ("separado", parts)]:
            start = time.perf_counter()
            inputs = tokenizer(pieces, return_tensors="pt", padding=True,
                               truncation=True, max_length=256)
            with torch.inference_mode():
                ids = model.generate(**inputs, forced_bos_token_id=target,
                                     num_beams=4, max_new_tokens=160)
            translated = tokenizer.batch_decode(ids, skip_special_tokens=True)
            print("%s (%.2f s): %s" % (label, time.perf_counter()-start,
                                       " ".join(translated)), flush=True)
    print("\nPrueba terminada; no se guardó ninguna traducción.")

if __name__ == "__main__":
    main()
