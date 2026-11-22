import unittest
from nion.apply_review import plan


class ApplyReviewTests(unittest.TestCase):
    def test_safe_change(self):
        changes, conflicts, skipped = plan({"Hello": "Hola"}, [
            {"original": "Hello", "traduccion_elegida": "Buenas", "aprobado": True}
        ])
        self.assertEqual(len(changes), 1)
        self.assertEqual(conflicts, [])
        self.assertEqual(skipped, [])

    def test_unapproved_is_skipped(self):
        changes, conflicts, skipped = plan({"Hello": "Hola"}, [
            {"original": "Hello", "traduccion_elegida": "Buenas", "aprobado": False}
        ])
        self.assertFalse(changes)
        self.assertEqual(len(skipped), 1)

    def test_missing_original_is_conflict(self):
        _, conflicts, _ = plan({}, [
            {"original": "Hello", "traduccion_elegida": "Hola", "aprobado": True}
        ])
        self.assertEqual(conflicts[0]["motivo"], "original_ausente")

    def test_duplicate_is_conflict(self):
        _, conflicts, _ = plan({"Hello": "Hola"}, [
            {"original": "Hello", "traduccion_elegida": "Buenas", "aprobado": True},
            {"original": "Hello", "traduccion_elegida": "Saludos", "aprobado": True},
        ])
        self.assertEqual(conflicts[0]["motivo"], "original_duplicado")


if __name__ == "__main__":
    unittest.main()
