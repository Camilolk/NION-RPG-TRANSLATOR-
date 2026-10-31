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
            "Eres traductor de localización de videojuegos RPG. Traduce el texto "
            "completo al idioma solicitado con precisión y naturalidad. Conserva "
            "el significado, el tono y la intención del personaje; evita calcos "
            "literales y palabras que no encajen en el contexto de un juego. "
            "No inventes información ni omitas partes del original. Responde solo "
            "con la traducción, sin explicaciones ni comillas. Copia literalmente "
            "cada marcador [[NION_TOKEN_n]]: no lo cambies, elimines, dupliques "
            "ni reordenes. Los nombres propios visibles deben conservarse. "
            "El mensaje del usuario contiene el único texto que debes traducir. "
            "No reproduzcas listas, glosarios, instrucciones ni ejemplos. No agregues "
            "explicaciones, alternativas ni contenido ajeno al original. Si el texto "
            "es un encabezado, una categoría o una etiqueta breve, traduce únicamente "
            "ese texto y conserva su formato."
        )
        language = (tgt or "").lower().replace("_", "-")
        if language == "es" or language.startswith("es-"):
            prompt += (
                " El idioma destino es español. Usa español latinoamericano natural "
                "y fluido. Cuida la concordancia de género y número entre artículos, "
                "sustantivos y adjetivos. Antes de traducir, identifica quién realiza "
                "la acción y conserva la persona, el número, el tiempo verbal y la "
                "modalidad del original. No conviertas primera, segunda o tercera "
                "persona en otra. Evita falsos amigos y expresiones calcadas del inglés. "
                "Si el texto es un fragmento de diálogo, conserva su sentido y sus "
                "puntos suspensivos; no inventes un sujeto ni información que no aparezca."
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
                        tgt, strict=strict
                    )},
                    {"role": "user", "content":
                     "Idioma de origen: %s. Idioma de destino: %s.\nTexto a traducir:\n%s"
                     % (src, tgt, text)},
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
