import unittest
from nion.guarded_translate import translate_guarded, review_alerts


class FakeEngine:
    max_batch = 2
    def __init__(self):
        self.retried = []
    def translate_batch(self, texts, src, tgt):
        return ["¡" * 40 if text == "No!" else "Hola" for text in texts]
    def translate_repair(self, text, src, tgt):
        self.retried.append(text)
        return "¡No!"


class GuardedTests(unittest.TestCase):
    def test_retries_only_corrupt_output(self):
        engine = FakeEngine()
        rows = translate_guarded(["No!", "Hello"], engine)
        self.assertEqual(engine.retried, ["No!"])
        self.assertEqual(rows[0]["traduccion"], "¡No!")
        self.assertEqual(rows[0]["estado"], "reparada")
        self.assertEqual(rows[1]["estado"], "lista")

    def test_quarantine_if_retry_remains_corrupt(self):
        class Bad(FakeEngine):
            def translate_repair(self, text, src, tgt):
                return "¡" * 40
        rows = translate_guarded(["No!"], Bad())
        self.assertEqual(rows[0]["estado"], "cuarentena")

    def test_no_repair_method_means_quarantine(self):
        class OnlyBatch:
            max_batch = 2
            def translate_batch(self, texts, src, tgt):
                return ["!" * 40 for _ in texts]
        self.assertEqual(translate_guarded(["No!"], OnlyBatch())[0]["estado"], "cuarentena")

    def test_omitted_question_is_detected(self):
        source = "What happened? And the device?"
        target = "¿Qué pasó?"
        self.assertIn("preguntas_omitidas_posibles", review_alerts(source, target))

    def test_stuttering_loss_is_detected(self):
        self.assertIn("tartamudeo_perdido_posible", review_alerts("N-No!!", "¡No!"))

    def test_untranslated_is_detected(self):
        self.assertIn("sin_traducir", review_alerts("N-No!!", "N-No!!"))

    def test_empty_batch(self):
        self.assertEqual(translate_guarded([], FakeEngine()), [])


if __name__ == "__main__":
    unittest.main()
