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
    max_batch = 1
    supports_masking = True

    def __init__(self, url="http://127.0.0.1:8080", timeout=180):
        if not url or not url.strip():
            raise EngineError("La URL de llama.cpp está vacía.")
        self.terminology = {}
        base = url.strip().rstrip("/")
        if base.endswith("/chat/completions"):
            self.url = base
        elif base.endswith("/v1"):
            self.url = base + "/chat/completions"
        else:
            self.url = base + "/v1/chat/completions"
        self.timeout = timeout

    def set_terminology(self, terms):
        """Configura términos RPG confirmados para la dirección inglés -> español."""
        if not isinstance(terms, dict):
            raise EngineError("El glosario de términos debe ser un objeto.")
        self.terminology = {
            source.strip(): target.strip()
            for source, target in terms.items()
            if isinstance(source, str) and source.strip()
            and isinstance(target, str) and target.strip()
        }

    @staticmethod
    def _system_prompt(tgt, strict=False, terminology=None):
        prompt = (
            "Traduce todo el texto al idioma solicitado con precisión y naturalidad. "
            "Conserva el significado, el tono y la intención del personaje. "
            "No añadas, omitas ni expliques nada. Responde solo con la traducción. "
            "Copia literalmente cada marcador [[NION_TOKEN_n]]: no lo cambies, "
            "elimines, dupliques ni reordenes. Los nombres propios visibles deben "
            "conservarse sin traducir."
        )
        language = (tgt or "").lower().replace("_", "-")
        if language == "es" or language.startswith("es-"):
            prompt += (
                " El idioma destino es español. Usa español latinoamericano natural. "
                "Antes de traducir, identifica quién realiza la acción y conserva "
                "exactamente la persona y el número gramatical del sujeto, así como "
                "el tiempo verbal y la modalidad. No conviertas primera, segunda o "
                "tercera persona en otra, ni cambies singular por plural o viceversa. "
                "Interpreta el sentido de la frase completa; no reutilices una "
                "traducción fija para sujetos diferentes."
            )
        if (language == "es" or language.startswith("es-")) and terminology:
            lines = ["- %s → %s" % (source, target)
                     for source, target in sorted(
                         terminology.items(), key=lambda item: (-len(item[0]), item[0].casefold())
                     )]
            prompt += (
                " TERMINOLOGÍA RPG OBLIGATORIA: cuando aparezca uno de estos términos "
                "en el texto original, usa su equivalente indicado. No confundas "
                "materiales ni sustituyas objetos por otros. No fuerces un término "
                "si la palabra original no aparece.\n" + "\n".join(lines)
            )
        if strict:
            prompt += (
                " MODO DE REINTENTO ESTRICTO: copia cada marcador [[NION_TOKEN_n]] "
                "exactamente una vez y en el mismo orden. No alteres los marcadores. "
                "Traduce la frase completa sin resumir ni omitir información."
            )
        return prompt

    def retry_masked(self, text, src, tgt):
        """Reintenta una frase enmascarada con instrucciones más estrictas."""
        return self.translate_batch([text], src, tgt, strict=True)[0]

    def translate_batch(self, texts, src, tgt, strict=False):
        outputs = []
        for text in texts:
            payload = {
                "model": "local-model",
                "messages": [
                    {"role": "system", "content": self._system_prompt(
                        tgt, strict=strict, terminology=self.terminology
                    )},
                    {"role": "user", "content": text}
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


def get_engine(name, key=None, url=None):
    if name == "echo":
        return EchoEngine()
    if name == "deepl":
        return DeepLEngine(key)
    if name == "llamacpp":
        return LlamaCppEngine(url or "http://127.0.0.1:8080")
    raise EngineError("Motor desconocido: %s (disponibles: echo, deepl, llamacpp)" % name)
