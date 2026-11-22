"""CTranslate2 INT8 para modelos Marian inglés -> idiomas validados (no japonés)."""
import re
from pathlib import Path

from .engine import Engine, EngineError, MarianEngine


class CT2MultiEngine(Engine):
    name = "ct2-multi"
    max_batch = 16
    supports_masking = False
    SUPPORTED = {"es", "fr", "de", "it", "ru", "zh"}
    LABEL = re.compile(r"^(\s*(?:\[[A-Za-z][A-Za-z ]{0,35}\]\s*)+)")
    HEADER = re.compile(r"^-{3,}\s*[A-Za-z ]+\s*$")

    def __init__(self):
        self._active = None
        self._tokenizer = None
        self._translator = None

    def _load(self, lang):
        if self._active == lang:
            return
        try:
            import ctranslate2
            from transformers import MarianTokenizer
        except ImportError as exc:
            raise EngineError("Instala ctranslate2, transformers, sentencepiece y sacremoses.") from exc
        model_id = MarianEngine.MODELS.get(("en", lang))
        if not model_id:
            raise EngineError("Modelo Marian no disponible para " + lang)
        model_dir = Path("models") / "ct2_benchmark" / lang
        if not (model_dir / "model.bin").is_file():
            print("Convirtiendo modelo CT2 INT8 para", lang, "(solo la primera vez)...", flush=True)
            model_dir.parent.mkdir(parents=True, exist_ok=True)
            try:
                ctranslate2.converters.TransformersConverter(model_id).convert(
                    str(model_dir), quantization="int8")
            except Exception as exc:
                raise EngineError("No se pudo convertir el modelo CT2 de %s: %s" % (lang, exc)) from exc
        try:
            self._tokenizer = MarianTokenizer.from_pretrained(model_id)
            self._translator = ctranslate2.Translator(
                str(model_dir), device="cpu", compute_type="int8")
        except Exception as exc:
            raise EngineError("No se pudo abrir CT2 %s: %s" % (lang, exc)) from exc
        self._active = lang

    def translate_repair(self, text, src, tgt):
        """Segundo intento más conservador, sin modificar la memoria."""
        lang = tgt.lower().replace("_", "-")
        if src.lower() != "en" or lang not in self.SUPPORTED:
            raise EngineError("Par de idiomas no admitido para reparación CT2.")
        self._load(lang)
        match = self.LABEL.match(text)
        prefix = match.group(0) if match else ""
        core = text[len(prefix):]
        if not core.strip() or self.HEADER.fullmatch(text.strip()):
            return text
        language_prefix = ">>cmn_Hans<< " if lang == "zh" else ""
        tokens = self._tokenizer.convert_ids_to_tokens(
            self._tokenizer.encode(language_prefix + core, truncation=True, max_length=512))
        result = self._translator.translate_batch(
            [tokens], beam_size=4, repetition_penalty=1.25,
            no_repeat_ngram_size=3, max_decoding_length=256)[0]
        return prefix + self._tokenizer.convert_tokens_to_string(
            result.hypotheses[0]).replace("</s>", "").strip()

    def translate_batch(self, texts, src, tgt):
        lang = tgt.lower().replace("_", "-")
        if src.lower() != "en" or lang not in self.SUPPORTED:
            raise EngineError("ct2-multi solo admite en -> es/fr/de/it/ru/zh.")
        if not texts:
            return []
        result = list(texts)
        pending = []
        for i, text in enumerate(texts):
            if self.HEADER.fullmatch(text.strip()):
                continue
            match = self.LABEL.match(text)
            prefix = match.group(0) if match else ""
            core = text[len(prefix):]
            if core.strip():
                pending.append((i, prefix, core))
        if not pending:
            return result
        self._load(lang)
        prefix_lang = ">>cmn_Hans<< " if lang == "zh" else ""
        try:
            tokens = [
                self._tokenizer.convert_ids_to_tokens(
                    self._tokenizer.encode(prefix_lang + core, truncation=True, max_length=512))
                for _, _, core in pending
            ]
            translated = self._translator.translate_batch(
                tokens, beam_size=1, max_decoding_length=512)
            if len(translated) != len(pending):
                raise EngineError("CT2 devolvió un lote incompleto.")
            for (i, prefix, _), item in zip(pending, translated):
                output = self._tokenizer.convert_tokens_to_string(
                    item.hypotheses[0]).replace("</s>", "").strip()
                if not output:
                    raise EngineError("CT2 devolvió una traducción vacía.")
                result[i] = prefix + output
        except EngineError:
            raise
        except Exception as exc:
            raise EngineError("Fallo CT2 %s: %s" % (lang, exc)) from exc
        return result
