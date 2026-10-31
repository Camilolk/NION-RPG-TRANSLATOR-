"""Motores de traducción intercambiables."""
import json
import os
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
    supports_context = False

    def placeholder(self, i):
        return default_placeholder(i)

    def translate_batch(self, texts, src, tgt):
        raise NotImplementedError

    def translate_with_context(self, text, src, tgt, context):
        """Traduce un texto con contexto opcional; los motores antiguos lo ignoran."""
        return self.translate_batch([text], src, tgt)[0]

    def retry_masked_with_context(self, text, src, tgt, context):
        return self.retry_masked(text, src, tgt)


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
    supports_context = True

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
            "ese texto y conserva su formato. Si el mensaje incluye contexto del "
            "registro del juego, úsalo solo como metadato para desambiguar; no traduzcas "
            "ni reproduzcas ese contexto. Traduce únicamente el texto señalado."
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
                "puntos suspensivos; no inventes un sujeto ni información que no aparezca. "
                "CONTEXTO DE RPG: cuando traduzcas inventario, armas, armaduras, ropa, "
                "materiales o descripciones de objetos, interpreta cada palabra como parte "
                "de ese contexto y no como conversación cotidiana. 'Vest' en una pieza de "
                "armadura o ropa es una prenda (por ejemplo, un chaleco), no el verbo "
                "'vestir' ni un vestido. 'Clothing' se refiere a prendas o ropa; 'linen' "
                "es el tejido lino, no ropa de cama. 'Leather' es cuero o piel curtida; "
                "'hard leather' describe cuero endurecido, no comodidad ni muebles. "
                "'Shield' en inventario es un escudo defensivo. Elige el sentido que encaje "
                "con el objeto y su descripción; no sustituyas el objeto por otro. "
                "En descripciones, conserva todos los datos, materiales, propiedades y "
                "relaciones del original sin añadir explicaciones. "
                "FORMATO: conserva exactamente los saltos de línea, líneas en blanco, "
                "signos, corchetes y estructura del texto de entrada. Traduce el contenido "
                "de etiquetas descriptivas entre corchetes, pero conserva los corchetes. "
                "No unas líneas ni dividas una línea en varias."
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

    def retry_masked_with_context(self, text, src, tgt, context):
        return self.translate_batch(
            [text], src, tgt, strict=True, contexts=[context]
        )[0]

    def translate_with_context(self, text, src, tgt, context):
        return self.translate_batch([text], src, tgt, contexts=[context])[0]

    def translate_batch(self, texts, src, tgt, strict=False, contexts=None):
        outputs = []
        for index, text in enumerate(texts):
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
            context = contexts[index] if contexts and index < len(contexts) else None
            if context:
                payload["messages"][1]["content"] = (
                    "Contexto del registro del juego (úsalo para desambiguar, "
                    "pero traduce únicamente el texto indicado):\n"
                    + context + "\n\n" + payload["messages"][1]["content"]
                )
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




class OpenRouterEngine(Engine):
    """Motor remoto compatible con OpenAI; usa openrouter/free por defecto."""
    name = "openrouter"
    max_batch = 1
    supports_masking = True
    supports_context = True

    def __init__(self, key=None, model=None, timeout=120):
        self.key = (key or os.environ.get("NION_OPENROUTER_KEY") or "").strip()
        if not self.key:
            raise EngineError(
                "Falta NION_OPENROUTER_KEY para usar OpenRouter. "
                "Configura la clave localmente; nunca la guardes en Git."
            )
        self.model = (model or os.environ.get(
            "NION_OPENROUTER_MODEL", "openrouter/free"
        )).strip()
        self.url = "https://openrouter.ai/api/v1/chat/completions"
        self.timeout = timeout

    def retry_masked_with_context(self, text, src, tgt, context):
        return self.translate_batch(
            [text], src, tgt, strict=True, contexts=[context]
        )[0]

    def translate_with_context(self, text, src, tgt, context):
        return self.translate_batch([text], src, tgt, contexts=[context])[0]

    def translate_batch(self, texts, src, tgt, strict=False, contexts=None):
        outputs = []
        for index, text in enumerate(texts):
            system = LlamaCppEngine._system_prompt(tgt, strict=strict)
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content":
                     "Idioma de origen: %s. Idioma de destino: %s.\nTexto a traducir:\n%s"
                     % (src, tgt, text)},
                ],
                "temperature": 0.15,
                "max_tokens": min(1200, max(160, len(text) * 4)),
            }
            context = contexts[index] if contexts and index < len(contexts) else None
            if context:
                payload["messages"][1]["content"] = (
                    "Contexto del registro del juego (úsalo para desambiguar, "
                    "pero traduce únicamente el texto indicado):\n"
                    + context + "\n\n" + payload["messages"][1]["content"]
                )
            req = urllib.request.Request(
                self.url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Authorization": "Bearer " + self.key,
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/Camilolk/NION-RPG-TRANSLATOR-",
                    "X-Title": "NION RPG Translator",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
                result = data["choices"][0]["message"]["content"]
                if not isinstance(result, str) or not result.strip():
                    raise EngineError("OpenRouter devolvió una respuesta vacía.")
                outputs.append(result.strip())
            except EngineError:
                raise
            except urllib.error.HTTPError as error:
                try:
                    detail = error.read().decode("utf-8", "replace")[:300]
                except Exception:
                    detail = str(error.reason)
                if error.code == 429:
                    detail = "límite de solicitudes alcanzado. " + detail
                raise EngineError("OpenRouter HTTP %d: %s" % (error.code, detail))
            except urllib.error.URLError as error:
                raise EngineError("No se pudo conectar con OpenRouter: %s" % error.reason)
            except (KeyError, IndexError, TypeError, ValueError) as error:
                raise EngineError("Respuesta de OpenRouter no válida: %s" % error)
        return outputs

    def retry_masked(self, text, src, tgt):
        return self.translate_batch([text], src, tgt, strict=True)[0]


class HybridEngine(Engine):
    """Reglas exactas primero, nube después y llama.cpp como respaldo local."""
    name = "hybrid"
    max_batch = 1
    supports_masking = True
    supports_context = True

    def __init__(self, glossary=None, openrouter_key=None, model=None,
                 local_url="http://127.0.0.1:8080"):
        self.terms = {}
        if isinstance(glossary, dict):
            raw_terms = glossary.get("terms", {})
            if isinstance(raw_terms, dict):
                self.terms = {
                    str(source).casefold(): str(target)
                    for source, target in raw_terms.items()
                    if isinstance(source, str) and isinstance(target, str)
                }
        self.cloud = None
        key = openrouter_key or os.environ.get("NION_OPENROUTER_KEY")
        if key:
            self.cloud = OpenRouterEngine(key=key, model=model)
        self.local = LlamaCppEngine(local_url)

    def _rule_translation(self, text):
        # Conserva el prefijo decorativo de categorías como "-----Armors".
        prefix = text[:len(text) - len(text.lstrip("-"))]
        body = text[len(prefix):]
        target = self.terms.get(body.strip().casefold())
        if target is None:
            return None
        return prefix + target

    def translate_batch(self, texts, src, tgt):
        outputs = []
        for text in texts:
            ruled = self._rule_translation(text)
            if ruled is not None:
                outputs.append(ruled)
                continue

            cloud_error = None
            if self.cloud is not None:
                try:
                    outputs.extend(self.cloud.translate_batch([text], src, tgt))
                    continue
                except EngineError as error:
                    cloud_error = error

            try:
                outputs.extend(self.local.translate_batch([text], src, tgt))
            except EngineError as local_error:
                if cloud_error is not None:
                    raise EngineError(
                        "Fallaron nube y motor local. Nube: %s | Local: %s"
                        % (cloud_error, local_error)
                    )
                raise
        return outputs

    def translate_with_context(self, text, src, tgt, context):
        ruled = self._rule_translation(text)
        if ruled is not None:
            return ruled
        cloud_error = None
        if self.cloud is not None:
            try:
                if hasattr(self.cloud, "translate_with_context"):
                    return self.cloud.translate_with_context(text, src, tgt, context)
                return self.cloud.translate_batch([text], src, tgt)[0]
            except EngineError as error:
                cloud_error = error
        try:
            if hasattr(self.local, "translate_with_context"):
                return self.local.translate_with_context(text, src, tgt, context)
            return self.local.translate_batch([text], src, tgt)[0]
        except EngineError as local_error:
            if cloud_error is not None:
                raise EngineError(
                    "Fallaron nube y motor local. Nube: %s | Local: %s"
                    % (cloud_error, local_error)
                )
            raise

    def retry_masked_with_context(self, text, src, tgt, context):
        cloud_error = None
        if self.cloud is not None:
            try:
                if hasattr(self.cloud, "retry_masked_with_context"):
                    return self.cloud.retry_masked_with_context(text, src, tgt, context)
                return self.cloud.retry_masked(text, src, tgt)
            except EngineError as error:
                cloud_error = error
        try:
            if hasattr(self.local, "retry_masked_with_context"):
                return self.local.retry_masked_with_context(text, src, tgt, context)
            return self.local.retry_masked(text, src, tgt)
        except EngineError as local_error:
            if cloud_error is not None:
                raise EngineError(
                    "Fallaron nube y motor local. Nube: %s | Local: %s"
                    % (cloud_error, local_error)
                )
            raise

    def retry_masked(self, text, src, tgt):
        return self.translate_batch([text], src, tgt)[0]


def get_engine(name, key=None, url=None, glossary=None, model=None,
               openrouter_key=None):
    if name == "echo":
        return EchoEngine()
    if name == "deepl":
        return DeepLEngine(key)
    if name == "llamacpp":
        return LlamaCppEngine(url or "http://127.0.0.1:8080")
    if name == "openrouter":
        return OpenRouterEngine(
            key=openrouter_key or key, model=model
        )
    if name == "hybrid":
        return HybridEngine(
            glossary=glossary,
            openrouter_key=openrouter_key,
            model=model,
            local_url=url or "http://127.0.0.1:8080",
        )
    raise EngineError(
        "Motor desconocido: %s (disponibles: echo, deepl, llamacpp, "
        "openrouter, hybrid)" % name
    )

