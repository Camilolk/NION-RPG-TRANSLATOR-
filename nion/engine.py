"""Motores de traducción intercambiables."""
import json
import time
import urllib.error
import urllib.request
from .codes import default_placeholder


class EngineError(Exception):
    pass


class Engine:
    name = "base"
    max_batch = 40
    supports_masking = True

    def placeholder(self, i):
        return default_placeholder(i)

    def translate_batch(self, texts, src, tgt):
        raise NotImplementedError


class EchoEngine(Engine):
    name = "echo"

    def translate_batch(self, texts, src, tgt):
        return ["[%s] %s" % (tgt.upper(), t) for t in texts]


class DeepLEngine(Engine):
    name = "deepl"
    supports_masking = False

    def __init__(self, key):
        if not key:
            raise EngineError("Falta la clave de DeepL (--key o variable NION_DEEPL_KEY).")
        self.key = key.strip()
        self.url = ("https://api-free.deepl.com/v2/translate" if self.key.endswith(":fx")
                    else "https://api.deepl.com/v2/translate")

    def translate_batch(self, texts, src, tgt):
        body = json.dumps({"text": texts, "source_lang": src.upper(),
                           "target_lang": tgt.upper(), "preserve_formatting": True}).encode()
        req = urllib.request.Request(self.url, body, {
            "Authorization": "DeepL-Auth-Key " + self.key,
            "Content-Type": "application/json"})
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    out = [x["text"] for x in json.load(r)["translations"]]
                time.sleep(0.2)
                if len(out) != len(texts):
                    raise EngineError("DeepL devolvió un número distinto de textos.")
                return out
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 4:
                    time.sleep(10 * (attempt + 1))
                    continue
                msg = {403: "clave no válida", 456: "cuota agotada"}.get(e.code, "HTTP %d" % e.code)
                raise EngineError("DeepL: " + msg)
            except urllib.error.URLError as e:
                if attempt < 4:
                    time.sleep(10)
                    continue
                raise EngineError("DeepL: sin conexión (%s)" % e.reason)


class LlamaCppEngine(Engine):
    """API local compatible con OpenAI proporcionada por llama-server."""
    name = "llamacpp"
    max_batch = 4
    supports_masking = True

    def __init__(self, url="http://127.0.0.1:8080", timeout=180):
        if not url or not url.strip():
            raise EngineError("La URL de llama.cpp está vacía.")
        base = url.strip().rstrip("/")
        if base.endswith("/chat/completions"):
            self.url = base
        elif base.endswith("/v1"):
            self.url = base + "/chat/completions"
        else:
            self.url = base + "/v1/chat/completions"
        self.timeout = timeout

    @staticmethod
    def _system_prompt(tgt, strict=False):
        prompt = (
            "Eres traductor y editor profesional de localización de videojuegos RPG. "
            "Traduce el significado completo con naturalidad, precisión y coherencia "
            "con el contexto de un diálogo de fantasía. Mantén el tono y la intención "
            "del personaje. Escribe frases gramaticalmente correctas y fluidas; evita "
            "calcos, construcciones literales y palabras que no encajen en el contexto. "
            "No inventes información ni omitas partes del original. "
            "Responde únicamente con el texto traducido, sin explicaciones, etiquetas "
            "ni comillas. Conserva literalmente todos los marcadores [[NION_TOKEN_n]]: no los "
            "cambies, elimines, dupliques ni reordenes. No traduzcas los nombres propios "
            "protegidos por esos marcadores."
        )
        language = (tgt or "").lower().replace("_", "-")
        if language == "es" or language.startswith("es-"):
            prompt += (
                " Usa español latinoamericano neutro, natural y actual. "
                "Cuida especialmente la concordancia de sujeto, verbo y pronombres. "
                "Si el original habla en primera persona del plural (we), conserva "
                "esa persona verbal (nosotros/nosotras o la forma verbal correspondiente). "
                "Por ejemplo, 'We should hurry' debe expresar 'Debemos apresurarnos', "
                "no 'Debe irnos'. Evita expresiones rígidas como 'bosque norteño' "
                "cuando 'bosque del norte' resulte más natural."
            )
        if strict:
            prompt += (
                " MODO DE REINTENTO ESTRICTO: los marcadores [[NION_TOKEN_n]] son elementos "
                "técnicos obligatorios, no palabras. Copia cada marcador exactamente "
                "una vez y en el mismo orden. No escribas variantes, espacios dentro "
                "del marcador ni texto adicional. Traduce toda la frase como una unidad; "
                "no resumas ni reformules omitiendo información."
            )
        return prompt

    def retry_masked(self, text, src, tgt):
        """Reintenta una frase enmascarada con instrucciones más estrictas."""
        return self.translate_batch([text], src, tgt, strict=True)[0]

    def translate_batch(self, texts, src, tgt, strict=False):
        if len(texts) > 1:
            # Ask llama.cpp to constrain the output to a JSON object.
            # Validate count and types; otherwise fall back safely.
            prompt = (
                "Translate each item from %s to %s. Return only JSON with "
                "a 'translations' array of exactly %d strings in input order. "
                "Preserve all technical placeholders verbatim. "
                "Input JSON: %s"
                % (src, tgt, len(texts), json.dumps(texts, ensure_ascii=False))
            )
            schema = {
                "type": "object",
                "properties": {
                    "translations": {
                        "type": "array",
                        "minItems": len(texts),
                        "maxItems": len(texts),
                        "items": {"type": "string"}
                    }
                },
                "required": ["translations"],
                "additionalProperties": False
            }
            payload = {
                "model": "local-model",
                "messages": [
                    {"role": "system", "content":
                     "You translate RPG dialogue. Output only the requested JSON. "
                     "Keep all placeholders unchanged. Do not add commentary."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": min(4096, max(256, sum(len(t) for t in texts) * 3)),
                "response_format": {"type": "json_schema", "schema": schema}
            }
            req = urllib.request.Request(
                self.url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
                raw = data["choices"][0]["message"]["content"]
                parsed = json.loads(raw)
                translations = parsed["translations"]
                if (isinstance(translations, list) and len(translations) == len(texts)
                        and all(isinstance(t, str) and t.strip() for t in translations)):
                    return translations
            except (urllib.error.URLError, ValueError, TypeError, KeyError, IndexError):
                pass
            # Never silently accept missing or misaligned batch outputs.
            return [self.translate_batch([text], src, tgt, strict=strict)[0]
                    for text in texts]
        outputs = []
        for text in texts:
            payload = {
                "model": "local-model",
                "messages": [
                    {"role": "system", "content": self._system_prompt(tgt, strict=strict)},
                    {"role": "user", "content":
                     "Idioma origen: %s\nIdioma destino: %s\nTexto:\n%s" % (src, tgt, text)}
                ],
                "temperature": 0.1,
                "max_tokens": min(1024, max(128, len(text) * 3)),
            }
            req = urllib.request.Request(
                self.url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                if not isinstance(content, str) or not content.strip():
                    raise EngineError("llama.cpp devolvió una respuesta vacía o inválida.")
                outputs.append(content.strip())
            except EngineError:
                raise
            except urllib.error.HTTPError as error:
                try:
                    detail = error.read().decode("utf-8", "replace")[:300]
                except Exception:
                    detail = str(error.reason)
                raise EngineError("llama.cpp respondió HTTP %d: %s" % (error.code, detail))
            except urllib.error.URLError as error:
                raise EngineError("No se pudo conectar con llama.cpp en %s: %s" %
                                  (self.url, error.reason))
            except (KeyError, IndexError, TypeError, ValueError) as error:
                raise EngineError("Respuesta API de llama.cpp no válida: %s" % error)
        return outputs



class MarianEngine(Engine):
    """Traductor local MarianMT con selección de modelo por idioma (CPU)."""
    name = "marian"
    max_batch = 16
    supports_masking = False

    MODELS = {
        ("en", "es"): "Helsinki-NLP/opus-mt-en-es",
        ("en", "fr"): "Helsinki-NLP/opus-mt-en-fr",
        ("en", "de"): "Helsinki-NLP/opus-mt-en-de",
        ("en", "it"): "Helsinki-NLP/opus-mt-en-it",
        ("en", "ru"): "Helsinki-NLP/opus-mt-en-ru",
        ("en", "pt-br"): "Helsinki-NLP/opus-mt-en-ROMANCE",
        ("en", "ja"): "Helsinki-NLP/opus-mt-en-jap",
        ("en", "zh"): "Helsinki-NLP/opus-mt-en-zh",
    }

    def __init__(self, model_id=None):
        self.model_id = model_id
        self._active_pair = None
        self._tokenizer = None
        self._model = None

    def _load(self):
        if self._model is not None:
            return
        try:
            import torch
            from transformers import MarianMTModel, MarianTokenizer
        except ImportError as error:
            raise EngineError(
                "MarianMT requiere dependencias: "
                "python -m pip install torch transformers sentencepiece sacremoses"
            ) from error
        try:
            self._tokenizer = MarianTokenizer.from_pretrained(self.model_id)
            self._model = MarianMTModel.from_pretrained(self.model_id)
            self._model.eval()
        except Exception as error:
            raise EngineError("No se pudo cargar MarianMT: %s" % error) from error

    def _select_pair(self, src, tgt):
        source = src.lower().replace("_", "-")
        target = tgt.lower().replace("_", "-")
        pair = (source, target)
        model_id = self.MODELS.get(pair)
        if model_id is None:
            raise EngineError(
                "MarianMT no tiene un modelo configurado para %s -> %s. "
                "Pares disponibles: %s." %
                (src, tgt, ", ".join("%s->%s" % p for p in self.MODELS))
            )
        if self._active_pair != pair:
            self.model_id = model_id
            self._tokenizer = None
            self._model = None
            self._active_pair = pair

    @staticmethod
    def _prepare_texts(texts, tgt):
        # Chinese model is multilingual: force Simplified Mandarin.
        target = tgt.lower().replace("_", "-")
        if target == "zh":
            return [">>cmn_Hans<< " + text for text in texts]
        if target == "pt-br":
            return [">>pt<< " + text for text in texts]
        return texts

    def translate_repair(self, text, src="en", tgt="es"):
        """Decodificacion alternativa, solo para reparaciones solicitadas."""
        self._select_pair(src, tgt)
        self._load()
        import torch
        inputs = self._tokenizer(
            self._prepare_texts([text], tgt), return_tensors="pt", padding=True,
            truncation=True, max_length=512
        )
        with torch.inference_mode():
            generated = self._model.generate(
                **inputs, max_new_tokens=160, num_beams=4,
                repetition_penalty=1.25, no_repeat_ngram_size=3,
                early_stopping=True
            )
        return self._tokenizer.batch_decode(generated, skip_special_tokens=True)[0]

    def translate_batch(self, texts, src, tgt):
        self._select_pair(src, tgt)
        if not texts:
            return []
        self._load()
        import torch
        try:
            inputs = self._tokenizer(
                self._prepare_texts(texts, tgt), return_tensors="pt", padding=True, truncation=True,
                max_length=512
            )
            with torch.inference_mode():
                generated = self._model.generate(
                    **inputs, max_new_tokens=512, num_beams=1
                )
            return self._tokenizer.batch_decode(
                generated, skip_special_tokens=True
            )
        except Exception as error:
            raise EngineError("MarianMT no pudo traducir el lote: %s" % error) from error



class CTranslate2PortugueseEngine(Engine):
    """CT2 INT8 opcional, exclusivamente inglés -> portugués."""
    name = "ct2-pt"
    max_batch = 16
    supports_masking = False

    def __init__(self, model_dir="models/ct2_en_romance"):
        self.model_dir = model_dir
        self._tokenizer = None
        self._translator = None

    def _load(self):
        if self._translator is not None:
            return
        try:
            import ctranslate2
            from transformers import MarianTokenizer
            from pathlib import Path
        except ImportError as error:
            raise EngineError("Instala ctranslate2 y transformers para ct2-pt.") from error
        if not (Path(self.model_dir) / "model.bin").is_file():
            raise EngineError(
                "No existe el modelo CT2 convertido en %s. "
                "Ejecuta primero python -m nion.benchmark_ct2_pt JUEGO." % self.model_dir
            )
        try:
            self._tokenizer = MarianTokenizer.from_pretrained(
                "Helsinki-NLP/opus-mt-en-ROMANCE")
            self._translator = ctranslate2.Translator(
                self.model_dir, device="cpu", compute_type="int8")
        except Exception as error:
            raise EngineError("No se pudo cargar CT2 portugués: %s" % error) from error

    def translate_batch(self, texts, src, tgt):
        if src.lower().replace("_", "-") != "en" or tgt.lower().replace("_", "-") != "pt-br":
            raise EngineError("ct2-pt solo permite en -> pt-br.")
        if not texts:
            return []
        # Only CT2 Portuguese gets these rules; other engines stay unchanged.
        import re
        tag_re = re.compile(r"^(\s*(?:\[[A-Za-z][A-Za-z ]{0,35}\]\s*)+)")
        header_re = re.compile(r"^-{3,}\s*[A-Za-z ]+\s*$")
        # Standalone item names and RPG section headers must not be mistranslated.
        preserve = {"elixir"}
        output = list(texts)
        pending = []
        for index, text in enumerate(texts):
            if header_re.fullmatch(text.strip()) or text.strip().casefold() in preserve:
                continue
            match = tag_re.match(text)
            prefix = match.group(0) if match else ""
            core = text[len(prefix):]
            if not core.strip():
                continue
            pending.append((index, prefix, core))
        if not pending:
            return output
        self._load()
        try:
            inputs = [
                self._tokenizer.convert_ids_to_tokens(
                    self._tokenizer.encode(">>pt<< " + core, truncation=True, max_length=512)
                )
                for _, _, core in pending
            ]
            outputs = self._translator.translate_batch(
                inputs, beam_size=1, max_decoding_length=512)
            if len(outputs) != len(pending):
                raise EngineError("CT2 portugués devolvió un lote incompleto.")
            for (index, prefix, core), item in zip(pending, outputs):
                translated = (self._tokenizer.convert_tokens_to_string(item.hypotheses[0])
                              .replace("</s>", "").strip())
                if not translated:
                    raise EngineError("CT2 portugués devolvió texto vacío.")
                # Conservative pt-BR spelling and phrasing adjustments.
                # Do not alter RPG labels or escape codes in the preserved prefix.
                import re
                brazilian_words = {
                    "demónio": "demônio",
                    "demónios": "demônios",
                    "económico": "econômico",
                    "económica": "econômica",
                    "académico": "acadêmico",
                    "académica": "acadêmica",
                    "fenómeno": "fenômeno",
                    "fenómenos": "fenômenos",
                    "género": "gênero",
                    "géneros": "gêneros",
                }
                def brazilianize(match):
                    word = match.group(0)
                    replacement = brazilian_words[word.lower()]
                    if word.isupper():
                        return replacement.upper()
                    if word[0].isupper():
                        return replacement.capitalize()
                    return replacement
                translated = re.sub(
                    r"\b(?:" + "|".join(map(re.escape, brazilian_words)) + r")\b",
                    brazilianize, translated, flags=re.IGNORECASE)
                translated = re.sub(
                    r"\b([Tt]emos) de (?=[a-zà-ú])",
                    lambda match: match.group(1) + " que ",
                    translated)
                output[index] = prefix + translated
            return output
        except EngineError:
            raise
        except Exception as error:
            raise EngineError("Error traduciendo con CT2 portugués: %s" % error) from error


class M2M100Engine(Engine):
    """Traducción multilingüe local con M2M100 (CPU)."""
    name = "m2m100"
    max_batch = 8
    supports_masking = False
    model_id = "facebook/m2m100_418M"
    languages = {"en", "pt", "ja", "zh"}

    def __init__(self):
        self._tokenizer = None
        self._model = None

    def _load(self):
        if self._model is not None:
            return
        try:
            from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
        except ImportError as error:
            raise EngineError(
                "M2M100 requiere torch, transformers y sentencepiece."
            ) from error
        try:
            self._tokenizer = M2M100Tokenizer.from_pretrained(self.model_id)
            self._model = M2M100ForConditionalGeneration.from_pretrained(self.model_id)
            self._model.eval()
        except Exception as error:
            raise EngineError("No se pudo cargar M2M100: %s" % error) from error

    def translate_batch(self, texts, src, tgt):
        source = src.lower().replace("_", "-")
        target = tgt.lower().replace("_", "-")
        if target == "pt-br":
            target = "pt"
        if source != "en" or target not in {"pt", "ja", "zh"}:
            raise EngineError("M2M100 en NION admite en -> pt-br, ja, zh.")
        if not texts:
            return []
        self._load()
        import torch
        try:
            self._tokenizer.src_lang = source
            inputs = self._tokenizer(
                texts, return_tensors="pt", padding=True,
                truncation=True, max_length=512
            )
            with torch.inference_mode():
                generated = self._model.generate(
                    **inputs,
                    forced_bos_token_id=self._tokenizer.get_lang_id(target),
                    max_new_tokens=512,
                    num_beams=1
                )
            results = self._tokenizer.batch_decode(
                generated, skip_special_tokens=True
            )
            if len(results) != len(texts):
                raise EngineError("M2M100 devolvió un número distinto de textos.")
            return results
        except EngineError:
            raise
        except Exception as error:
            raise EngineError("M2M100 no pudo traducir el lote: %s" % error) from error


def get_engine(name, key=None, url=None):
    if name == "echo":
        return EchoEngine()
    if name == "deepl":
        return DeepLEngine(key)
    if name == "marian":
        return MarianEngine()
    if name == "ct2-multi":
        from .ct2_multi import CT2MultiEngine
        return CT2MultiEngine()
    if name == "ct2-pt":
        return CTranslate2PortugueseEngine()
    if name == "m2m100":
        return M2M100Engine()
    if name == "llamacpp":
        return LlamaCppEngine(url or "http://127.0.0.1:8080")
    raise EngineError("Motor desconocido: %s (disponibles: echo, deepl, llamacpp, marian, m2m100, ct2-pt, ct2-multi)" % name)
