import unittest
from nion.repair_gguf import review, fidelity_warnings

class FakeGGUF:
    def translate(self, source):
        return "¡No!"

class GGUFRepairTests(unittest.TestCase):
    def test_review_does_not_modify_input(self):
        rows = [{"original": "N-No!!", "propuesta": "N-No!!", "aprobado": False}]
        output = review(rows, FakeGGUF(), 1)
        self.assertNotIn("propuesta_gguf", rows[0])
        self.assertEqual(output[0]["propuesta_gguf"], "¡No!")
        self.assertFalse(output[0]["aprobado"])
        self.assertEqual(output[0]["estado_gguf"], "revisar_con_alertas")

    def test_die_changed_to_move_is_flagged(self):
        self.assertIn("muerte_omitida_posible", fidelity_warnings(
            "Shut UP!!! And die!!!", "¡Calla, y muévete!"))

    def test_correct_die_translation_not_flagged(self):
        self.assertNotIn("muerte_omitida_posible", fidelity_warnings(
            "Shut UP!!! And die!!!", "¡Cállate! ¡Y muere!"))

    def test_stutter_loss_is_flagged(self):
        self.assertIn("tartamudeo_perdido_posible", fidelity_warnings("N-No!!", "¡No!"))

    def test_stutter_preserved(self):
        self.assertNotIn("tartamudeo_perdido_posible", fidelity_warnings("N-No!!", "¡N-No!"))

    def test_clean_output_still_needs_human_review(self):
        class GoodGGUF:
            def translate(self, source):
                return "¡Cállate! ¡Y muere!"
        output = review([{"original": "Shut UP!!! And die!!!"}], GoodGGUF(), 1)
        self.assertEqual(output[0]["estado_gguf"], "pendiente_revision_humana")

if __name__ == "__main__":
    unittest.main()
