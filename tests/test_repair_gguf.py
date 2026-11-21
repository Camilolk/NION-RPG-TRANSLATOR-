import unittest
from nion.repair_gguf import review

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

if __name__ == "__main__":
    unittest.main()
