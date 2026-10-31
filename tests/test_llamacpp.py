import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from nion.engine import EngineError, LlamaCppEngine, get_engine


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return self.payload


class LlamaCppTests(unittest.TestCase):
    def test_url_normalization(self):
        self.assertEqual(LlamaCppEngine().url, "http://127.0.0.1:8080/v1/chat/completions")
        self.assertEqual(LlamaCppEngine("http://localhost:8080/v1").url,
                         "http://localhost:8080/v1/chat/completions")
        self.assertEqual(LlamaCppEngine("http://localhost:8080/v1/chat/completions").url,
                         "http://localhost:8080/v1/chat/completions")

    @patch("nion.engine.urllib.request.urlopen")
    def test_chat_completion_response(self, mocked):
        mocked.return_value = FakeResponse({"choices": [{"message": {"content": "¡Hola, Elio!"}}]})
        self.assertEqual(LlamaCppEngine().translate_batch(["Hello, Elio!"], "en", "es"),
                         ["¡Hola, Elio!"])
        self.assertEqual(mocked.call_args.kwargs["timeout"], 180)

    @patch("nion.engine.urllib.request.urlopen")
    def test_prompt_preserves_mask_tokens(self, mocked):
        mocked.return_value = FakeResponse({"choices": [{"message": {"content": "⟦0⟧Hola⟦1⟧"}}]})
        LlamaCppEngine().translate_batch(["⟦0⟧Hello⟦1⟧"], "en", "es")
        request = mocked.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertIn("⟦n⟧", payload["messages"][0]["content"])
        self.assertIn("⟦0⟧Hello⟦1⟧", payload["messages"][1]["content"])

    @patch("nion.engine.urllib.request.urlopen")
    def test_spanish_prompt_requests_natural_grammar(self, mocked):
        mocked.return_value = FakeResponse({"choices": [{"message": {"content": "Debemos apresurarnos."}}]})
        LlamaCppEngine().translate_batch(["We should hurry."], "en", "es")
        request = mocked.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        prompt = payload["messages"][0]["content"]
        self.assertIn("español latinoamericano neutro", prompt)
        self.assertIn("concordancia de sujeto, verbo y pronombres", prompt)
        self.assertIn("Debemos apresurarnos", prompt)
        self.assertIn("⟦n⟧", prompt)

    @patch("nion.engine.urllib.request.urlopen")
    def test_other_languages_do_not_receive_spanish_specific_rules(self, mocked):
        mocked.return_value = FakeResponse({"choices": [{"message": {"content": "Nous devons nous dépêcher."}}]})
        LlamaCppEngine().translate_batch(["We should hurry."], "en", "fr")
        request = mocked.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertNotIn("español latinoamericano", payload["messages"][0]["content"])

    @patch("nion.engine.urllib.request.urlopen")
    def test_invalid_response_fails_loudly(self, mocked):
        mocked.return_value = FakeResponse({"unexpected": []})
        with self.assertRaises(EngineError):
            LlamaCppEngine().translate_batch(["Hello"], "en", "es")

    def test_engine_factory(self):
        self.assertEqual(get_engine("llamacpp").name, "llamacpp")


if __name__ == "__main__":
    unittest.main()
