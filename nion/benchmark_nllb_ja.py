"""Compara decodificación NLLB-200 en -> ja sin tocar memorias ni archivos del juego."""
import argparse
import re
import time

SAMPLES = [
    "Linen clothing with high breathability.",
    "A vest made of tanned hide.",
    "A vest made of leather hardened with glue.",
    "Wait for me outside!",
    "I have to make sure to use my self-enhancing spells before going in.",
    "Woah, so you can see me? You must be a really powerful mage.",
    "%1 is blinded!",
    "Woah, so you can see me? You must be a really powerful mage. That's quite a difficult",
    "You really are, son! Make sure to keep her close. It'd be bad if someone took her away...",
    "I can't go back! I have to do something!",
]
CONFIGS = [
    ("rapido_lote", {"num_beams": 1}),
    ("equilibrado_lote", {"num_beams": 4, "length_penalty": 1.0}),
    ("cobertura_lote", {"num_beams": 4, "length_penalty": 1.35}),
]
PLACEHOLDER = re.compile(r"%[1-9][0-9]*|\\\\[A-Za-z{}|!.<>^]")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="facebook/nllb-200-distilled-600M")
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size debe ser positivo")
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    except ImportError:
        parser.error("Instala torch, transformers y sentencepiece en el entorno virtual.")
    print("Cargando", args.model, flush=True)
    start = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(args.model, src_lang="eng_Latn")
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model)
    model.eval()
    target_id = tokenizer.convert_tokens_to_ids("jpn_Jpan")
    if not isinstance(target_id, int) or target_id == tokenizer.unk_token_id:
        raise RuntimeError("Token de idioma jpn_Jpan no disponible.")
    print("Modelo listo en %.1f s" % (time.perf_counter() - start), flush=True)
    for name, options in CONFIGS:
        started = time.perf_counter()
        outputs = []
        for offset in range(0, len(SAMPLES), args.batch_size):
            batch = SAMPLES[offset:offset + args.batch_size]
            encoded = tokenizer(batch, return_tensors="pt", padding=True,
                                truncation=True, max_length=256)
            with torch.inference_mode():
                generated = model.generate(
                    **encoded, forced_bos_token_id=target_id,
                    max_new_tokens=160, early_stopping=True if options["num_beams"] > 1 else False,
                    **options)
            outputs.extend(tokenizer.batch_decode(generated, skip_special_tokens=True))
        elapsed = time.perf_counter() - started
        print("\n===== %s | %.1f s | %.2f textos/s =====" %
              (name, elapsed, len(SAMPLES) / max(elapsed, 0.001)), flush=True)
        for i, (source, target) in enumerate(zip(SAMPLES, outputs), 1):
            src_tokens = PLACEHOLDER.findall(source)
            tgt_tokens = PLACEHOLDER.findall(target)
            status = " | CODIGOS ALTERADOS" if src_tokens != tgt_tokens else ""
            print("%02d EN: %s\n   JA: %s%s" % (i, source, target, status), flush=True)
    print("\nPRUEBA FINALIZADA. No se modificaron memorias ni datos del juego.")

if __name__ == "__main__":
    main()
