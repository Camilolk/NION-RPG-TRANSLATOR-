"""Motores de traducción intercambiables."""
import json
import logging
import os
import time
import urllib.error
import urllib.request
from .codes import default_placeholder

logger = logging.getLogger(__name__)


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
    """Motor OpenRouter con perfiles, diagnóstico seguro y recuperación por causa."""
    name = "openrouter"
    max_batch = 1
    supports_masking = False
    supports_context = True

    MODEL_PROFILES = {
        "nvidia/nemotron-3.5-super-vl:free": {
            "min_output_tokens": 512,
            "max_output_tokens": 4096,
            "reasoning": {"enabled": False},
        },
        "nvidia/nemotron-3.5-super-vl": {
            "min_output_tokens": 512,
            "max_output_tokens": 4096,
            "reasoning": {"enabled": False},
        },
    }
    DEFAULT_PROFILE = {
        "min_output_tokens": 256,
        "max_output_tokens": 1200,
        "reasoning": None,
    }

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
        self.profile = dict(self.DEFAULT_PROFILE)
        self.profile.update(self.MODEL_PROFILES.get(self.model, {}))

    def retry_masked_with_context(self, text, src, tgt, context):
        return self.translate_batch(
            [text], src, tgt, strict=True, contexts=[context]
        )[0]

    def translate_with_context(self, text, src, tgt, context):
        return self.translate_batch([text], src, tgt, contexts=[context])[0]

    def _safe_detail(self, value, limit=240):
        """Evita que una respuesta del proveedor pueda repetir la clave."""
        detail = str(value or "").replace(self.key, "[REDACTED]")
        return detail[:limit]

    @staticmethod
    def _extract_message_text(message):
        """Acepta texto plano y bloques multimodales que contengan texto."""
        content = message.get("content")
        if isinstance(content, str):
            return content.strip(), "text", []
        if isinstance(content, list):
            text_parts, block_types = [], []
            for block in content:
                if not isinstance(block, dict):
                    block_types.append(type(block).__name__)
                    continue
                block_type = str(block.get("type", "unknown"))
                block_types.append(block_type)
                if block_type == "text" and isinstance(block.get("text"), str):
                    if block["text"].strip():
                        text_parts.append(block["text"].strip())
            return "\n".join(text_parts).strip(), "blocks", block_types
        if content is None:
            return "", "null", []
        return "", type(content).__name__, []

    @staticmethod
    def _response_diagnostics(data):
        """Extrae solo metadatos seguros; nunca guarda prompt ni razonamiento."""
        choices = data.get("choices") if isinstance(data, dict) else None
        choice = choices[0] if isinstance(choices, list) and choices else {}
        message = choice.get("message") if isinstance(choice, dict) else {}
        if not isinstance(message, dict):
            message = {}
        content, content_kind, block_types = OpenRouterEngine._extract_message_text(message)
        reasoning = message.get("reasoning")
        if reasoning is None:
            reasoning = message.get("reasoning_details")
        reasoning_present = reasoning is not None and reasoning != "" and reasoning != []
        reasoning_chars = len(reasoning) if isinstance(reasoning, str) else (
            sum(len(str(item)) for item in reasoning) if isinstance(reasoning, list) else 0
        )
        usage = data.get("usage") if isinstance(data, dict) else {}
        usage = usage if isinstance(usage, dict) else {}
        details = usage.get("completion_tokens_details")
        details = details if isinstance(details, dict) else {}
        return content, {
            "finish_reason": choice.get("finish_reason"),
            "content_kind": content_kind,
            "content_chars": len(content),
            "reasoning_present": reasoning_present,
            "reasoning_chars": reasoning_chars,
            "reasoning_tokens": details.get("reasoning_tokens"),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "block_types": block_types,
            "choice_count": len(choices) if isinstance(choices, list) else 0,
        }

    def _log_response(self, attempt, diagnostics, elapsed):
        logger.info(
            "OpenRouter response model=%s attempt=%d elapsed_ms=%d "
            "finish_reason=%s content_kind=%s content_chars=%d "
            "reasoning_present=%s reasoning_chars=%d reasoning_tokens=%s "
            "prompt_tokens=%s completion_tokens=%s total_tokens=%s "
            "block_types=%s",
            self.model, attempt, int(elapsed * 1000),
            diagnostics["finish_reason"], diagnostics["content_kind"],
            diagnostics["content_chars"], diagnostics["reasoning_present"],
            diagnostics["reasoning_chars"], diagnostics["reasoning_tokens"],
            diagnostics["prompt_tokens"], diagnostics["completion_tokens"],
            diagnostics["total_tokens"], diagnostics["block_types"],
        )

    def _make_request(self, payload):
        return urllib.request.Request(
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

    def _request_content(self, payload):
        """Reintenta fallos HTTP y aumenta tokens solo ante truncamiento."""
        retryable_statuses = {429, 500, 502, 503, 504}
        delays = (2, 5)
        attempt_payload = dict(payload)
        empty_retries = 0

        for attempt in range(3):
            started = time.monotonic()
            try:
                with urllib.request.urlopen(
                    self._make_request(attempt_payload), timeout=self.timeout
                ) as response:
                    status = getattr(response, "status", 200)
                    data = json.loads(response.read().decode("utf-8"))

                content, diagnostics = self._response_diagnostics(data)
                self._log_response(attempt + 1, diagnostics, time.monotonic() - started)
                finish_reason = diagnostics["finish_reason"]

                if finish_reason == "length":
                    current = int(attempt_payload.get("max_tokens", 512))
                    ceiling = int(self.profile["max_output_tokens"])
                    if attempt < 2 and current < ceiling:
                        attempt_payload["max_tokens"] = min(ceiling, current * 2)
                        logger.warning(
                            "OpenRouter truncó salida (length); se amplía max_tokens "
                            "de %d a %d para modelo=%s",
                            current, attempt_payload["max_tokens"], self.model,
                        )
                        continue
                    raise EngineError(
                        "OpenRouter agotó max_tokens (finish_reason=length); "
                        "respuesta incompleta. Revisa el presupuesto del modelo."
                    )

                if content:
                    return content

                if empty_retries < 1 and attempt < 2:
                    empty_retries += 1
                    time.sleep(delays[0])
                    logger.warning(
                        "OpenRouter devolvió contenido vacío; finish_reason=%s "
                        "reasoning_present=%s reasoning_tokens=%s status=%s",
                        finish_reason, diagnostics["reasoning_present"],
                        diagnostics["reasoning_tokens"], status,
                    )
                    # Si el perfil permite razonamiento, el reintento reserva
                    # presupuesto para la respuesta visible.
                    if attempt_payload.get("reasoning") is not None:
                        attempt_payload["reasoning"] = {"enabled": False}
                    continue

                reason = (
                    "razonamiento sin contenido visible"
                    if diagnostics["reasoning_present"]
                    else "contenido vacío o nulo"
                )
                raise EngineError(
                    "OpenRouter devolvió %s (finish_reason=%s, "
                    "reasoning_tokens=%s, completion_tokens=%s)."
                    % (reason, finish_reason, diagnostics["reasoning_tokens"],
                       diagnostics["completion_tokens"])
                )

            except urllib.error.HTTPError as error:
                if error.code in retryable_statuses and attempt < 2:
                    retry_after = error.headers.get("Retry-After") if error.headers else None
                    try:
                        delay = min(15, max(0, float(retry_after))) if retry_after else delays[attempt]
                    except (TypeError, ValueError):
                        delay = delays[attempt]
                    logger.warning(
                        "OpenRouter HTTP %d; reintento %d/3 en %ss",
                        error.code, attempt + 1, delay,
                    )
                    time.sleep(delay)
                    continue
                try:
                    detail = self._safe_detail(error.read().decode("utf-8", "replace"))
                except Exception:
                    detail = self._safe_detail(error.reason)
                if error.code == 429:
                    detail = "límite de solicitudes alcanzado. " + detail
                logger.error("OpenRouter HTTP error status=%d detail=%s", error.code, detail)
                raise EngineError("OpenRouter HTTP %d: %s" % (error.code, detail))
            except urllib.error.URLError as error:
                if attempt < 2:
                    logger.warning("OpenRouter conexión fallida; reintento %d/3", attempt + 1)
                    time.sleep(delays[attempt])
                    continue
                raise EngineError(
                    "No se pudo conectar con OpenRouter tras 3 intentos: %s"
                    % self._safe_detail(error.reason)
                )
            except EngineError:
                raise
            except (KeyError, IndexError, TypeError, ValueError) as error:
                logger.exception("OpenRouter devolvió una estructura JSON no válida")
                raise EngineError(
                    "Respuesta de OpenRouter no válida: %s" % self._safe_detail(error)
                )
        raise EngineError("OpenRouter no pudo completar la solicitud.")

    def translate_batch(self, texts, src, tgt, strict=False, contexts=None):
        outputs = []
        for index, text in enumerate(texts):
            system = LlamaCppEngine._system_prompt(tgt, strict=strict)
            min_tokens = int(self.profile["min_output_tokens"])
            max_tokens = int(self.profile["max_output_tokens"])
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content":
                     "Idioma de origen: %s. Idioma de destino: %s.\nTexto a traducir:\n%s"
                     % (src, tgt, text)},
                ],
                "temperature": 0.15,
                "max_tokens": min(max_tokens, max(min_tokens, len(text) * 4)),
            }
            if self.profile.get("reasoning") is not None:
                payload["reasoning"] = dict(self.profile["reasoning"])
            context = contexts[index] if contexts and index < len(contexts) else None
            if context:
                payload["messages"][1]["content"] = (
                    "Contexto del registro del juego (úsalo para desambiguar, "
                    "pero traduce únicamente el texto indicado):\n"
                    + context + "\n\n" + payload["messages"][1]["content"]
                )
            outputs.append(self._request_content(payload))
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

