import os
import unittest

from nion.engine import Engine, EngineError, EchoEngine
from nion.memory import Memory
from nion.pipeline import apply_translations, scan, translate_pending
from test_core import make_game


class ShortEngine(Engine):
    name = "short"
    max_batch = 100

    def translate_batch(self, texts, src, tgt):
        return []


class RetryEngine(Engine):
    name = "retry-test"
    max_batch = 1

    def __init__(self):
        self.retried = []

    def translate_batch(self, texts, src, tgt):
        return ["[[NION_TOKEN_99]] respuesta rota"]

    def retry_masked(self, text, src, tgt):
        self.retried.append(text)
        return text.replace("[[NION_TOKEN_0]]", "[[NION_TOKEN_0]]Traducción correcta")


class SafetyTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name

    def tearDown(self):
        self.temp.cleanup()

    def test_masked_translation_retries_before_rejecting_unrecoverable_text(self):
        game = os.path.join(self.root, "game")
        make_game(game)
        _, entries = scan(game)
        engine = RetryEngine()
        memory = Memory(os.path.join(self.root, "retry.json"))
        translate_pending(entries, memory, engine, "en", "es", log=lambda *_: None,
                          protected_terms=["Elio"])
        self.assertTrue(engine.retried)

    def test_incomplete_engine_response_fails_loudly(self):
        game = os.path.join(self.root, "game")
        make_game(game)
        _, entries = scan(game)
        memory = Memory(os.path.join(self.root, "memory.json"))
        with self.assertRaises(EngineError):
            translate_pending(entries, memory, ShortEngine(), "en", "es", log=lambda *_: None)

    def test_partial_translation_does_not_create_output(self):
        game = os.path.join(self.root, "game")
        make_game(game)
        output = os.path.join(self.root, "partial")
        count, missing = apply_translations(
            game, output, Memory(os.path.join(self.root, "empty.json")), log=lambda *_: None
        )
        self.assertEqual(count, 0)
        self.assertTrue(missing)
        self.assertFalse(os.path.exists(output))

    def test_existing_output_is_not_overwritten(self):
        game = os.path.join(self.root, "game")
        make_game(game)
        _, entries = scan(game)
        memory = Memory(os.path.join(self.root, "memory.json"))
        translate_pending(entries, memory, EchoEngine(), "en", "es", log=lambda *_: None)
        output = os.path.join(self.root, "existing")
        os.makedirs(output)
        with self.assertRaises(EngineError):
            apply_translations(game, output, memory, log=lambda *_: None)


if __name__ == "__main__":
    unittest.main()
