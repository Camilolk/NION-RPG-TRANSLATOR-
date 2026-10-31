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


    def test_description_receives_its_item_name_and_approved_translation(self):
        class ContextEngine(Engine):
            name = "context-test"
            max_batch = 1
            supports_context = True

            def translate_batch(self, texts, src, tgt):
                return [
                    "Ropa de lino" if text == "Linen Clothing" else "Traducción"
                    for text in texts
                ]

            def translate_with_context(self, text, src, tgt, context):
                self.context = context
                if text == "Linen Clothing":
                    return "Ropa de lino"
                return "Ropa de lino con alta\\ntranspirabilidad."

        with tempfile.TemporaryDirectory() as directory:
            engine = ContextEngine()
            memory = self.memory(directory)
            entries = [
                SimpleNamespace(file="Armors.json", path=(1, "name"),
                                text="Linen Clothing"),
                SimpleNamespace(file="Armors.json", path=(1, "description"),
                                text="Linen clothing with high\\nbreathability."),
            ]
            translate_pending(
                entries, memory, engine, "en", "es",
                log=lambda _: None, protected_terms=[],
            )
            self.assertEqual(memory["Linen Clothing"], "Ropa de lino")
            self.assertEqual(
                memory["Linen clothing with high\\nbreathability."],
                "Ropa de lino con alta\\ntranspirabilidad.",
            )
            self.assertIn("Nombre original del registro: Linen Clothing", engine.context)
            self.assertNotIn("Nombre traducido y aprobado", engine.context)


    def test_masking_engine_never_fragments_text_after_marker_failure(self):
        class BrokenMarkerEngine(Engine):
            name = "broken-marker-test"
            max_batch = 1

            def translate_batch(self, texts, src, tgt):
                return ["marcador alterado"]

            def retry_masked(self, text, src, tgt):
                return "marcador alterado"

        with tempfile.TemporaryDirectory() as directory:
            memory = self.memory(directory)
            source = "A vest made of leather\\nhardened with glue."
            logs = []
            translate_pending(
                [SimpleNamespace(text=source)], memory, BrokenMarkerEngine(),
                "en", "es", log=logs.append, protected_terms=[],
            )
            self.assertNotIn(source, memory)
            self.assertNotIn("A vest made of leather", memory)
            self.assertNotIn("hardened with glue.", memory)
            self.assertTrue(any("sin fragmentarlo" in line for line in logs))

    def test_existing_memory_is_reused_without_semantic_glossary_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = self.memory(directory)
            memory.set("Bronze Shield", "Escudo de bronce")
            entry = SimpleNamespace(text="Bronze Shield")
            self.assertEqual(pending_texts([entry], memory, []), [])


if __name__ == "__main__":
    unittest.main()
