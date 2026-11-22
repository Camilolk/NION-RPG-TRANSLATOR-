"""Prueba aislada NLLB-200 inglés -> japonés; no escribe memorias."""
import argparse
import time

SAMPLES = [
    "Linen clothing with high breathability.",
    "A vest made of tanned hide.",
    "A vest made of leather hardened with glue.",
    "Wait for me outside!",
    "I have to make sure to use my self-enhancing spells before going in.",
    "Woah, so you can see me? You must be a really powerful mage.",
    "%1 is blinded!",
]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="facebook/nllb-200-distilled-600M")
    args = parser.parse_args()
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    except ImportError as exc:
        parser.error("Faltan dependencias: pip install torch transformers sentencepiece")
    print("Cargando", args.model, flush=True)
    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(args.model, src_lang="eng_Latn")
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model)
    model.eval()
    target_id = tokenizer.convert_tokens_to_ids("jpn_Jpan")
    if not isinstance(target_id, int) or target_id == tokenizer.unk_token_id:
        raise RuntimeError("No se encontró el token de japonés jpn_Jpan.")
    print("Modelo listo en %.1f s" % (time.perf_counter()-started), flush=True)
    started = time.perf_counter()
    for source in SAMPLES:
        encoded = tokenizer(source, return_tensors="pt", truncation=True, max_length=256)
        with torch.inference_mode():
            output = model.generate(
                **encoded, forced_bos_token_id=target_id,
                max_new_tokens=128, num_beams=2)
        translated = tokenizer.batch_decode(output, skip_special_tokens=True)[0]
        print("\nEN:", source, "\nJA:", translated, flush=True)
    print("\nTiempo de traducción: %.1f s" % (time.perf_counter()-started))

if __name__ == "__main__":
    main()
