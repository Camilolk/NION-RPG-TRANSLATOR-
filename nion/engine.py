"""Motores de traducción intercambiables. Todos fallan EN VOZ ALTA (EngineError)."""
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
    """Motor de prueba: no traduce de verdad, solo marca el texto. Sin red."""
    name = "echo"

    def translate_batch(self, texts, src, tgt):
        return ["[%s] %s" % (tgt.upper(), t) for t in texts]


class DeepLEngine(Engine):
    """DeepL API (plan Free: clave terminada en :fx). Solo biblioteca estándar."""
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
    """Motor local llama.cpp mediante su API compatible con OpenAI."""
    name = "llamacpp"
    max_batch = 1  # una petición por texto: evita respuestas mezcladas o desalineadas
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

    def translate_batch(self, texts, src, tgt):
        outputs = []
        for text in texts:
            payload = {
                "model": "local-model",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Eres un traductor profesional de videojuegos RPG Maker. "
                            "Traduce del idioma indicado al idioma de destino con español "
                            "natural y fiel al contexto. Devuelve únicamente la traducción, "
                            "sin explicaciones, comillas ni texto adicional. "
                            "Conserva literalmente todos los marcadores ⟦n⟧, sin cambiarlos, "
                            "eliminarlos, duplicarlos ni reordenarlos. No traduzcas nombres "
                            "propios que aparezcan protegidos por esos marcadores."
                        ),
                    },
                    {
                        "role": "user",
                        "content": "Idioma origen: %s\nIdioma destino: %s\nTexto:\n%s"
                                   % (src, tgt, text),
                    },
                ],
                "temperature": 0.1,
                "max_tokens": min(1024, max(128, len(text) * 3)),
            }
            req = urllib.request.Request(
                self.url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
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
                detail = ""
                try:
                    detail = error.read().decode("utf-8", "replace")[:300]
                except Exception:
                    pass
                raise EngineError("llama.cpp respondió HTTP %d: %s" %
                                  (error.code, detail or error.reason))
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
        return LlamaCppEngine(url)
    raise EngineError("Motor desconocido: %s (disponibles: echo, deepl, llamacpp)" % name)
