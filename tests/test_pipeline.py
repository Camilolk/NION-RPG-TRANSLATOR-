import os
import tempfile
import unittest
from types import SimpleNamespace

from nion.engine import Engine
from nion.memory import Memory
from nion.pipeline import pending_texts, render, translate_pending


class PipelineSafetyTests(unittest.TestCase):
    def memory(self, directory):
        return Memory(os.path.join(directory, "memory.json"))

    def test_non_masking_engine_keeps_proper_names_out_of_translation(self):
        class PlainEngine(Engine):
            name = "plain-test"
            supports_masking = False
            max_batch = 1

            def translate_batch(self, texts, src, tgt):
                self.asserted_input = list(texts)
                return ["Hola"]

        with tempfile.TemporaryDirectory() as directory:
            engine = PlainEngine()
            memory = self.memory(directory)
            entry = SimpleNamespace(text="Elio: Hello")
            translate_pending(
                [entry], memory, engine, "en", "es",
                log=lambda _: None, protected_terms=["Elio"],
            )
            self.assertEqual(engine.asserted_input, ["Hello"])
            self.assertEqual(memory["Elio: Hello"], "Elio: Hola")

    def test_pipeline_does_not_override_engine_translation_with_glossary_rules(self):
        class PlainEngine(Engine):
            name = "plain-translation-test"
            supports_masking = False
            max_batch = 1

            def translate_batch(self, texts, src, tgt):
                return ["Escudo de plata"]

        with tempfile.TemporaryDirectory() as directory:
            memory = self.memory(directory)
            entry = SimpleNamespace(text="Bronze Shield")
            translate_pending(
                [entry], memory, PlainEngine(), "en", "es",
                log=lambda _: None, protected_terms=[],
            )
            self.assertEqual(memory["Bronze Shield"], "Escudo de plata")
            self.assertEqual(render("Bronze Shield", memory, []), "Escudo de plata")

    def test_masking_engine_protects_names_and_rpg_codes(self):
        class MaskedEngine(Engine):
            name = "masked-test"
            max_batch = 1

            def translate_batch(self, texts, src, tgt):
                self.asserted_input = list(texts)
                return ["[[NION_TOKEN_0]] Hola [[NION_TOKEN_1]]"]

        with tempfile.TemporaryDirectory() as directory:
            engine = MaskedEngine()
            memory = self.memory(directory)
            entry = SimpleNamespace(text=r"Elio: Hello \C[2]")
            translate_pending(
                [entry], memory, engine, "en", "es",
                log=lambda _: None, protected_terms=["Elio"],
            )
            self.assertEqual(
                engine.asserted_input,
                ["[[NION_TOKEN_0]] Hello [[NION_TOKEN_1]]"],
            )
            self.assertEqual(
                memory[r"Elio: Hello \C[2]"],
                r"Elio: Hola \C[2]",
            )

    def test_existing_memory_is_reused_without_semantic_glossary_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = self.memory(directory)
            memory.set("Bronze Shield", "Escudo de bronce")
            entry = SimpleNamespace(text="Bronze Shield")
            self.assertEqual(pending_texts([entry], memory, []), [])


if __name__ == "__main__":
    unittest.main()
