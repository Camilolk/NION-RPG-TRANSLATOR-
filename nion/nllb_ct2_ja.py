"""NLLB-200 inglés -> japonés con CTranslate2 INT8 (CPU).

Conversión local única del modelo HF; reutiliza caché de Hugging Face.
No modifica memorias ni archivos del juego.
"""
from pathlib import Path

MODEL_ID = "facebook/nllb-200-distilled-600M"
MODEL_DIR = Path("models") / "ct2_nllb_ja_int8"


class NLLBCT2Japanese:
    def __init__(self, threads=0):
        try:
            import ctranslate2
            from transformers import AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("Instala ctranslate2, transformers y sentencepiece") from exc
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, src_lang="eng_Latn")
        if not (MODEL_DIR / "model.bin").is_file():
            MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)
            print("Convirtiendo NLLB a CT2 INT8 (solo primera ejecución)...", flush=True)
            ctranslate2.converters.TransformersConverter(MODEL_ID).convert(
                str(MODEL_DIR), quantization="int8")
        self.translator = ctranslate2.Translator(
            str(MODEL_DIR), device="cpu", compute_type="int8",
            inter_threads=1, intra_threads=threads or 0)
        self.target_lang = "jpn_Jpan"

    def translate(self, texts, beams=2):
        if not texts:
            return []
        encoded = self.tokenizer(texts, padding=False, truncation=False)
        sources = [self.tokenizer.convert_ids_to_tokens(ids)
                   for ids in encoded["input_ids"]]
        if any(len(tokens) > 512 for tokens in sources):
            raise ValueError("segmento_mayor_512_tokens")
        results = self.translator.translate_batch(
            sources,
            target_prefix=[[self.target_lang] for _ in sources],
            beam_size=beams,
            max_decoding_length=160)
        outputs = []
        for result in results:
            hypothesis = result.hypotheses[0]
            if hypothesis and hypothesis[0] == self.target_lang:
                hypothesis = hypothesis[1:]
            ids = self.tokenizer.convert_tokens_to_ids(hypothesis)
            outputs.append(self.tokenizer.decode(
                ids, skip_special_tokens=True, clean_up_tokenization_spaces=False).strip())
        return outputs
