import unittest

from nion.quality import quality_issue, verified_correction


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

    def test_normalizes_case_spacing_and_final_punctuation(self):
        corrected, reason = verified_correction(
            "  WE   SHOULD HURRY!! ", "Debemos acelerar", "en-US", "es-CO"
        )
        self.assertEqual(corrected, "Deberíamos darnos prisa.")
        self.assertTrue(reason)


if __name__ == "__main__":
    unittest.main()
