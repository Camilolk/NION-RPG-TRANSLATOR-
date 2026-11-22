import unittest

from nion.review_compare import merge_reviews, choices


class ReviewCompareTests(unittest.TestCase):
    def test_merge_by_original_not_index(self):
        marian = [{"original": "A", "propuesta": "Uno"}, {"original": "B"}]
        qwen = [{"original": "B", "propuesta_gguf": "Dos"}, {"original": "A", "propuesta_gguf": "Tres"}]
        result = merge_reviews(marian, qwen)
        self.assertEqual(result[0]["propuesta_gguf"], "Tres")
        self.assertEqual(result[1]["propuesta_gguf"], "Dos")

    def test_manual_decision_is_separate(self):
        source = [{"original": "N-No!!", "propuesta": "No", "propuesta_gguf": "¡No!"}]
        inputs = iter(["e", "¡N-No!"])
        result = choices(source, input_fn=lambda _: next(inputs), output_fn=lambda _: None)
        self.assertEqual(result[0]["traduccion_elegida"], "¡N-No!")
        self.assertTrue(result[0]["aprobado"])
        self.assertNotIn("aprobado", source[0])

    def test_missing_qwen_cannot_be_selected(self):
        inputs = iter(["q", "s"])
        result = choices([{"original": "Hello"}], input_fn=lambda _: next(inputs), output_fn=lambda _: None)
        self.assertEqual(result[0]["decision"], "pendiente")

    def test_duplicate_source_rejected(self):
        with self.assertRaises(ValueError):
            merge_reviews([{"original": "A"}, {"original": "A"}], [])


if __name__ == "__main__":
    unittest.main()
