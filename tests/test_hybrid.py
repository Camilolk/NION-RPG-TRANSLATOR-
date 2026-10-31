import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nion.engine import EngineError, HybridEngine, OpenRouterEngine, LlamaCppEngine
import nion.cli  # noqa: F401 - verifies the command-line module remains importable
from nion.pipeline import _approve_translation
from nion.glossary import load_glossary


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class FakeEngine:
    def __init__(self, result=None, error=None):
        self.result = result or []
        self.error = error
        self.calls = []

    def translate_batch(self, texts, src, tgt):
        self.calls.append(list(texts))
        if self.error:
            raise self.error
        return list(self.result)


class HybridEngineTests(unittest.TestCase):
    def test_exact_glossary_rule_handles_category_prefix(self):
        engine = HybridEngine(glossary={
            "terms": {
                "hard leather": "cuero endurecido",
                "armors": "armaduras",
            }
        })
        self.assertEqual(
            engine.translate_batch(["Hard Leather", "-----Armors"], "en", "es"),
            ["cuero endurecido", "-----armaduras"],
        )

    def test_unknown_text_uses_local_engine_when_no_cloud_key(self):
        with patch.dict("os.environ", {"NION_OPENROUTER_KEY": ""}):
            engine = HybridEngine(glossary={"terms": {}})
            local = FakeEngine(["Una frase traducida"])
            engine.local = local
            self.assertIsNone(engine.cloud)
            self.assertEqual(
                engine.translate_batch(["A complete sentence."], "en", "es"),
                ["Una frase traducida"],
            )
            self.assertEqual(local.calls, [["A complete sentence."]])

    def test_cloud_failure_falls_back_to_local(self):
        engine = HybridEngine(glossary={"terms": {}})
        engine.cloud = FakeEngine(error=EngineError("límite remoto"))
        engine.local = FakeEngine(["Traducción local"])
        self.assertEqual(
            engine.translate_batch(["A sentence."], "en", "es"),
            ["Traducción local"],
        )

    @patch("nion.engine.urllib.request.urlopen")
    def test_openrouter_uses_compatible_api_and_selected_model(self, mocked):
        mocked.return_value = FakeResponse({
            "choices": [{"message": {"content": "¡Hola!"}}]
        })
        engine = OpenRouterEngine(key="test-secret", model="openrouter/free")
        self.assertEqual(engine.translate_batch(["Hello"], "en", "es"), ["¡Hola!"])
        request = mocked.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "openrouter/free")
        self.assertEqual(
            request.get_header("Authorization"), "Bearer test-secret"
        )

    @patch("nion.engine.time.sleep")
    @patch("nion.engine.urllib.request.urlopen")
    def test_openrouter_retries_empty_response_then_succeeds(self, mocked, sleep):
        mocked.side_effect = [
            FakeResponse({"choices": [{"message": {"content": ""}}]}),
            FakeResponse({"choices": [{"message": {"content": "Cuero endurecido"}}]}),
        ]
        engine = OpenRouterEngine(key="test-secret", model="test/model")
        self.assertEqual(
            engine.translate_batch(["Hard Leather"], "en", "es"),
            ["Cuero endurecido"],
        )
        self.assertEqual(mocked.call_count, 2)
        sleep.assert_called_once_with(2)

    @patch("nion.engine.time.sleep")
    @patch("nion.engine.urllib.request.urlopen")
    def test_openrouter_stops_after_two_unclassified_empty_responses(self, mocked, sleep):
        empty = FakeResponse({"choices": [{
            "message": {"content": None}, "finish_reason": "stop"
        }]})
        mocked.side_effect = [empty, empty]
        engine = OpenRouterEngine(key="test-secret", model="test/model")
        with self.assertRaisesRegex(EngineError, "contenido vacío o nulo"):
            engine.translate_batch(["Hard Leather"], "en", "es")
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(sleep.call_count, 1)

    @patch("nion.engine.urllib.request.urlopen")
    def test_nemotron_profile_disables_reasoning_and_reserves_output_tokens(self, mocked):
        mocked.return_value = FakeResponse({"choices": [{
            "message": {"content": "Cuero endurecido"}, "finish_reason": "stop"
        }]})
        engine = OpenRouterEngine(
            key="test-secret", model="nvidia/nemotron-3.5-super-vl:free"
        )
        self.assertEqual(
            engine.translate_batch(["Hard Leather"], "en", "es"),
            ["Cuero endurecido"],
        )
        payload = json.loads(mocked.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload["reasoning"], {"enabled": False})
        self.assertEqual(payload["max_tokens"], 512)

    @patch("nion.engine.urllib.request.urlopen")
    def test_openrouter_expands_budget_after_finish_reason_length(self, mocked):
        mocked.side_effect = [
            FakeResponse({
                "choices": [{
                    "message": {"content": None, "reasoning": "internal"},
                    "finish_reason": "length",
                }],
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 512,
                    "completion_tokens_details": {"reasoning_tokens": 500},
                },
            }),
            FakeResponse({"choices": [{
                "message": {"content": "Cuero endurecido"},
                "finish_reason": "stop",
            }]}),
        ]
        engine = OpenRouterEngine(
            key="test-secret", model="nvidia/nemotron-3.5-super-vl:free"
        )
        self.assertEqual(
            engine.translate_batch(["Hard Leather"], "en", "es"),
            ["Cuero endurecido"],
        )
        first = json.loads(mocked.call_args_list[0].args[0].data.decode("utf-8"))
        second = json.loads(mocked.call_args_list[1].args[0].data.decode("utf-8"))
        self.assertEqual(first["max_tokens"], 512)
        self.assertEqual(second["max_tokens"], 1024)

    @patch("nion.engine.time.sleep")
    @patch("nion.engine.urllib.request.urlopen")
    def test_openrouter_identifies_reasoning_without_visible_content(self, mocked, sleep):
        response = FakeResponse({
            "choices": [{
                "message": {"content": None, "reasoning": "reasoning trace"},
                "finish_reason": "stop",
            }],
            "usage": {
                "completion_tokens": 64,
                "completion_tokens_details": {"reasoning_tokens": 64},
            },
        })
        mocked.side_effect = [response, response]
        engine = OpenRouterEngine(key="test-secret", model="test/model")
        with self.assertRaisesRegex(EngineError, "razonamiento sin contenido visible"):
            engine.translate_batch(["Hard Leather"], "en", "es")
        self.assertEqual(mocked.call_count, 2)

    @patch("nion.engine.urllib.request.urlopen")
    def test_openrouter_extracts_text_from_multimodal_content_blocks(self, mocked):
        mocked.return_value = FakeResponse({"choices": [{
            "message": {"content": [
                {"type": "image", "image_url": {"url": "data:image/png;base64,hidden"}},
                {"type": "text", "text": "Cuero endurecido"},
            ]},
            "finish_reason": "stop",
        }]})
        engine = OpenRouterEngine(key="test-secret", model="test/model")
        self.assertEqual(
            engine.translate_batch(["Hard Leather"], "en", "es"),
            ["Cuero endurecido"],
        )


    def test_cjk_contamination_is_rejected_for_spanish(self):
        glossary = load_glossary()
        approved, issue = _approve_translation(
            "Hard Leather", "Cómoda皮带", "en", "es",
            glossary, [], None,
        )
        self.assertIsNone(approved)
        self.assertIn("otro sistema de escritura", issue)



    def test_openrouter_context_is_included_in_user_message(self):
        mocked = None
        with patch("nion.engine.urllib.request.urlopen") as mocked:
            mocked.return_value = FakeResponse({
                "choices": [{"message": {"content": "Ropa de lino."}}]
            })
            engine = OpenRouterEngine(key="test-secret", model="openrouter/free")
            engine.translate_with_context(
                "Linen clothing.", "en", "es",
                "Nombre original: Linen Clothing."
            )
            request = mocked.call_args.args[0]
            payload = json.loads(request.data.decode("utf-8"))
            user_message = payload["messages"][1]["content"]
            self.assertIn("Nombre original: Linen Clothing", user_message)
            self.assertNotIn("Nombre traducido:", user_message)

    def test_spanish_rpg_prompt_explains_equipment_context(self):
        prompt = LlamaCppEngine._system_prompt("es")
        self.assertIn("'linen' es el tejido lino", prompt)
        self.assertIn("'vest' en una pieza de armadura o ropa", prompt.lower())
        self.assertIn("FORMATO: conserva exactamente los saltos de línea", prompt)
        self.assertIn("no traduzcas ni reproduzcas ese contexto", prompt)

    def test_changed_line_breaks_are_rejected(self):
        glossary = load_glossary()
        approved, issue = _approve_translation(
            "A vest made of leather\nhardened with glue.",
            "Un chaleco hecho de cuero endurecido con pegamento.",
            "en", "es", glossary, [], None,
        )
        self.assertIsNone(approved)
        self.assertIn("saltos de línea", issue)

    def test_preserved_line_breaks_are_accepted(self):
        glossary = load_glossary()
        approved, issue = _approve_translation(
            "A vest made of leather\nhardened with glue.",
            "Un chaleco hecho de cuero\nendurecido con pegamento.",
            "en", "es", glossary, [], None,
        )
        self.assertEqual(approved, "Un chaleco hecho de cuero\nendurecido con pegamento.")
        self.assertIsNone(issue)

    def test_normal_spanish_translation_is_not_rejected(self):
        glossary = load_glossary()
        approved, issue = _approve_translation(
            "Old Shield", "Escudo antiguo", "en", "es",
            glossary, [], None,
        )
        self.assertEqual(approved, "Escudo antiguo")
        self.assertIsNone(issue)


if __name__ == "__main__":
    unittest.main()
