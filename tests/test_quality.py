import os
import tempfile
import unittest
from types import SimpleNamespace

from nion.engine import Engine
from nion.memory import Memory
from nion.pipeline import translate_pending
from nion.quality import quality_issue, terminology_issues, verified_correction
from nion.glossary import load_glossary


class QualityTests(unittest.TestCase):
    def test_corrects_verified_subject_and_number_examples(self):
        cases = {
            "I should hurry.": "Debería darme prisa.",
            "You should hurry.": "Deberías darte prisa.",
            "We should hurry.": "Deberíamos darnos prisa.",
            "They should hurry.": "Deberían darse prisa.",
        }
        bad_outputs = [
            "Debería acelerar.",
            "¡Tienes que irte pronto!",
            "Debemos acelerar.",
            "Deben acelerarse.",
        ]
        for (source, expected), bad in zip(cases.items(), bad_outputs):
            with self.subTest(source=source):
                corrected, reason = verified_correction(source, bad, "en", "es")
                self.assertEqual(corrected, expected)
                self.assertTrue(reason)
                self.assertIsNotNone(quality_issue(source, bad, "en", "es"))

    def test_corrects_find_him_semantic_drift(self):
        corrected, reason = verified_correction(
            "We are going to find him.",
            "¡Nos vamos a encontrar con él!",
            "en", "es",
        )
        self.assertEqual(corrected, "Vamos a encontrarlo.")
        self.assertTrue(reason)

    def test_accepts_already_verified_translation(self):
        text = "Deberíamos darnos prisa."
        self.assertEqual(verified_correction("We should hurry.", text, "en", "es"),
                         (text, None))
        self.assertIsNone(quality_issue("We should hurry.", text, "en", "es"))

    def test_does_not_touch_unregistered_phrases_or_other_languages(self):
        text = "Debemos acelerar."
        self.assertEqual(verified_correction("We must leave now.", text, "en", "es"),
                         (text, None))
        self.assertEqual(verified_correction("We should hurry.", text, "en", "fr"),
                         (text, None))
        self.assertEqual(verified_correction("I should hurry.", text, "es", "en"),
                         (text, None))


    def test_pipeline_retries_then_applies_verified_correction(self):
        class BadEngine(Engine):
            name = "bad-test"
            max_batch = 1

            def __init__(self):
                self.retry_calls = 0

            def translate_batch(self, texts, src, tgt):
                return ["Debemos acelerar."]

            def retry_masked(self, text, src, tgt):
                self.retry_calls += 1
                return "Debemos acelerar."

        with tempfile.TemporaryDirectory() as directory:
            engine = BadEngine()
            memory = Memory(os.path.join(directory, "memory.json"))
            entry = SimpleNamespace(text="We should hurry.")
            logs = []
            translate_pending([entry], memory, engine, "en", "es",
                              log=logs.append, protected_terms=[])
            self.assertEqual(engine.retry_calls, 0)
            self.assertEqual(memory["We should hurry."], "Deberíamos darnos prisa.")
            self.assertTrue(any("corrección verificada" in line for line in logs))

    def test_detects_wrong_rpg_object_and_material(self):
        glossary = load_glossary()
        self.assertTrue(quality_issue("Bronze Shield", "Escudo de plata", "en", "es", glossary))
        self.assertIsNone(quality_issue("Bronze Shield", "Escudo de bronce", "en", "es", glossary))
        self.assertTrue(quality_issue("Hard Leather", "Cuerda dura", "en", "es", glossary))
        self.assertTrue(quality_issue("Helmets", "Cabezas", "en", "es", glossary))

    def test_pipeline_rejects_rpg_term_after_failed_retry(self):
        class WrongTermEngine(Engine):
            name = "wrong-term-test"
            max_batch = 1

            def translate_batch(self, texts, src, tgt):
                return ["Escudo de plata"]

            def retry_masked(self, text, src, tgt):
                return "Escudo de plata"

        with tempfile.TemporaryDirectory() as directory:
            engine = WrongTermEngine()
            memory = Memory(os.path.join(directory, "memory.json"))
            entry = SimpleNamespace(text="Bronze Shield")
            logs = []
            translate_pending([entry], memory, engine, "en", "es",
                              log=logs.append, protected_terms=[])
            self.assertNotIn("Bronze Shield", memory)
            self.assertTrue(any("término RPG no conservado" in line for line in logs))

    def test_pipeline_applies_verified_description_correction_without_retry(self):
        class AwkwardEngine(Engine):
            name = "awkward-description-test"
            max_batch = 1

            def __init__(self):
                self.retry_calls = 0

            def translate_batch(self, texts, src, tgt):
                return ["A vestido hecho de cuero curtido."]

            def retry_masked(self, text, src, tgt):
                self.retry_calls += 1
                return "A vestido hecho de cuero curtido."

        with tempfile.TemporaryDirectory() as directory:
            engine = AwkwardEngine()
            memory = Memory(os.path.join(directory, "memory.json"))
            entry = SimpleNamespace(text="A vest made of tanned hide.")
            logs = []
            translate_pending([entry], memory, engine, "en", "es",
                              log=logs.append, protected_terms=[])
            self.assertEqual(engine.retry_calls, 0)
            self.assertEqual(
                memory["A vest made of tanned hide."],
                "Un chaleco hecho de cuero curtido.",
            )
            self.assertTrue(any("corrección verificada" in line for line in logs))

    def test_accepts_contextual_rpg_term_variants(self):
        glossary = load_glossary()
        self.assertIsNone(quality_issue(
            "A large, old shield that survived time.",
            "Un escudo grande y viejo que ha resistido el paso del tiempo.",
            "en", "es", glossary,
        ))
        self.assertIsNone(quality_issue(
            "Linen clothing with high breathability.",
            "Ropa de lino con buena ventilación.",
            "en", "es", glossary,
        ))

    def test_compound_material_overrides_component_term(self):
        glossary = load_glossary()
        self.assertIsNone(quality_issue(
            "A large shield made of iron steel.",
            "Un escudo grande hecho de acero.",
            "en", "es", glossary,
        ))

    def test_verified_rpg_descriptions_correct_known_grammar_and_material(self):
        cases = {
            "A vest made of tanned hide.": "Un chaleco hecho de cuero curtido.",
            "A vest made of leather hardened with glue.": (
                "Un chaleco de cuero endurecido con pegamento."
            ),
            "[Large Shield] A large shield made of iron steel.": (
                "[Escudo grande] Un escudo grande hecho de acero."
            ),
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                corrected, reason = verified_correction(
                    source, "Traducción defectuosa", "en", "es"
                )
                self.assertEqual(corrected, expected)
                self.assertTrue(reason)

    def test_normalizes_case_spacing_and_final_punctuation(self):
        corrected, reason = verified_correction(
            "  WE   SHOULD HURRY!! ", "Debemos acelerar", "en-US", "es-CO"
        )
        self.assertEqual(corrected, "Deberíamos darnos prisa.")
        self.assertTrue(reason)


if __name__ == "__main__":
    unittest.main()
